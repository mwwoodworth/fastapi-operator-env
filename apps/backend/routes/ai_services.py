"""
AI service routes for BrainOps backend.

Comprehensive AI endpoints for chat, document generation, analysis, and multi-model support.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
import asyncio
import json
import io

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..core.database import get_db
from ..core.auth import get_current_user
from ..db.business_models import User, Subscription
from ..agents import claude_agent, gemini, codex
from ..memory.vector_store import VectorStore
from ..core.settings import settings

router = APIRouter()


# Pydantic models
class ChatMessage(BaseModel):
    role: str  # user, assistant, system
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    model: Optional[str] = "auto"  # auto, claude, gpt, gemini
    stream: bool = False
    context_window: int = 10
    temperature: float = 0.7
    max_tokens: Optional[int] = None


class ChatSession(BaseModel):
    id: str
    title: str
    model: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class DocumentGenerateRequest(BaseModel):
    template_id: Optional[str] = None
    document_type: str  # report, proposal, estimate, contract, email
    title: str
    context: Dict[str, Any]
    format: str = "markdown"  # markdown, html, pdf
    model: Optional[str] = "auto"


class DocumentTemplate(BaseModel):
    name: str
    description: str
    document_type: str
    template: str
    variables: List[str]
    example_context: Dict[str, Any]


class AnalysisRequest(BaseModel):
    content: str
    analysis_type: str  # sentiment, entities, summary, classification
    model: Optional[str] = "auto"
    options: Dict[str, Any] = {}


class TranslationRequest(BaseModel):
    text: str
    source_language: Optional[str] = "auto"
    target_language: str
    model: Optional[str] = "auto"


class ImageAnalysisRequest(BaseModel):
    task: str  # describe, ocr, classify, detect_objects
    model: Optional[str] = "auto"
    options: Dict[str, Any] = {}


class ModelSelection(BaseModel):
    session_id: str
    model: str  # claude, gpt, gemini


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    capabilities: List[str]
    context_window: int
    max_output_tokens: int
    cost_per_1k_input: float
    cost_per_1k_output: float
    is_available: bool


# Helper functions
async def get_ai_model(model_preference: str, task_type: str = "general"):
    """Select appropriate AI model based on preference and task."""
    if model_preference == "auto":
        # Auto-select based on task type
        if task_type in ["code", "technical"]:
            return codex
        elif task_type in ["creative", "long_form"]:
            return claude_agent
        else:
            return gemini
    
    model_map = {
        "claude": claude_agent,
        "gpt": codex,
        "gemini": gemini
    }
    
    return model_map.get(model_preference, claude_agent)


async def check_ai_quota(user: User, db: Session):
    """Check if user has remaining AI requests."""
    if user.subscription:
        if user.subscription.used_ai_requests >= user.subscription.monthly_ai_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Monthly AI request limit reached"
            )


async def increment_ai_usage(user: User, tokens_used: int, db: Session):
    """Increment user's AI usage counter."""
    if user.subscription:
        user.subscription.used_ai_requests += 1
        # Could also track tokens for more granular billing
        db.commit()


def format_chat_context(messages: List[ChatMessage], max_messages: int = 10):
    """Format chat messages for AI context."""
    recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages
    return "\n".join([f"{msg.role}: {msg.content}" for msg in recent_messages])


# Chat Endpoints
@router.post("/chat")
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a chat message to AI."""
    # Check quota
    await check_ai_quota(current_user, db)
    
    # Get or create session
    session_id = request.session_id or str(uuid4())
    
    # Get conversation history from memory
    vector_store = VectorStore()
    history = await vector_store.get_conversation_history(
        user_id=str(current_user.id),
        session_id=session_id,
        limit=request.context_window
    )
    
    # Select AI model
    ai_model = await get_ai_model(request.model, "chat")
    
    # Prepare context
    context = format_chat_context(history)
    full_prompt = f"{context}\nuser: {request.message}\nassistant:"
    
    if request.stream:
        # Stream response
        async def generate():
            response_text = ""
            async for chunk in ai_model.stream(
                full_prompt,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                response_text += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            # Save to memory in background
            background_tasks.add_task(
                save_chat_messages,
                current_user.id,
                session_id,
                request.message,
                response_text,
                db
            )
            
            yield f"data: {json.dumps({'done': True})}\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    
    else:
        # Regular response
        response = await ai_model.generate(
            full_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        # Save to memory
        await save_chat_messages(
            current_user.id,
            session_id,
            request.message,
            response,
            db
        )
        
        # Increment usage
        await increment_ai_usage(current_user, len(response.split()), db)
        
        return {
            "session_id": session_id,
            "message": response,
            "model_used": ai_model.name,
            "tokens_used": len(response.split())  # Rough estimate
        }


@router.get("/chat/sessions", response_model=List[ChatSession])
async def list_chat_sessions(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's chat sessions."""
    vector_store = VectorStore()
    sessions = await vector_store.get_user_sessions(
        user_id=str(current_user.id),
        limit=limit,
        offset=offset
    )
    
    return [
        ChatSession(
            id=session["id"],
            title=session.get("title", "Untitled Chat"),
            model=session.get("model", "unknown"),
            created_at=session["created_at"],
            updated_at=session["updated_at"],
            message_count=session["message_count"]
        )
        for session in sessions
    ]


@router.get("/chat/sessions/{session_id}")
async def get_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat session history."""
    vector_store = VectorStore()
    messages = await vector_store.get_conversation_history(
        user_id=str(current_user.id),
        session_id=session_id,
        limit=1000  # Get all messages
    )
    
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return {
        "session_id": session_id,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp
            }
            for msg in messages
        ]
    }


@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a chat session."""
    vector_store = VectorStore()
    await vector_store.delete_session(
        user_id=str(current_user.id),
        session_id=session_id
    )
    
    return {"message": "Session deleted successfully"}


@router.post("/chat/sessions/{session_id}/export")
async def export_chat_session(
    session_id: str,
    format: str = "markdown",  # markdown, json, pdf
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export conversation history."""
    vector_store = VectorStore()
    messages = await vector_store.get_conversation_history(
        user_id=str(current_user.id),
        session_id=session_id,
        limit=10000
    )
    
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if format == "markdown":
        content = "# Chat Session Export\n\n"
        for msg in messages:
            content += f"**{msg.role}** ({msg.timestamp}):\n{msg.content}\n\n"
        
        return StreamingResponse(
            io.StringIO(content),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=chat_{session_id}.md"}
        )
    
    elif format == "json":
        data = {
            "session_id": session_id,
            "exported_at": datetime.utcnow().isoformat(),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in messages
            ]
        }
        
        return StreamingResponse(
            io.StringIO(json.dumps(data, indent=2)),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=chat_{session_id}.json"}
        )
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported export format"
        )


# Document Generation Endpoints
@router.post("/documents/generate")
async def generate_document(
    request: DocumentGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a document using AI."""
    # Check quota
    await check_ai_quota(current_user, db)
    
    # Get template if specified
    template_content = ""
    if request.template_id:
        # Load template from database
        template = await get_document_template(request.template_id, db)
        if template:
            template_content = template.template
    
    # Select AI model
    ai_model = await get_ai_model(request.model, "document")
    
    # Build prompt
    prompt = f"""Generate a {request.document_type} document with the following details:
Title: {request.title}
Context: {json.dumps(request.context, indent=2)}
Format: {request.format}

{f'Using template: {template_content}' if template_content else ''}

Please generate a professional, well-structured document."""
    
    # Generate document
    document_content = await ai_model.generate(prompt, max_tokens=4000)
    
    # Post-process based on format
    if request.format == "html":
        # Convert markdown to HTML if needed
        document_content = markdown_to_html(document_content)
    elif request.format == "pdf":
        # Generate PDF (would need additional library)
        pass
    
    # Save to documents
    doc_id = str(uuid4())
    await save_generated_document(
        doc_id,
        current_user.id,
        request.title,
        request.document_type,
        document_content,
        request.format,
        db
    )
    
    # Increment usage
    await increment_ai_usage(current_user, len(document_content.split()), db)
    
    return {
        "document_id": doc_id,
        "title": request.title,
        "type": request.document_type,
        "format": request.format,
        "content": document_content,
        "generated_at": datetime.utcnow()
    }


@router.post("/documents/templates", response_model=DocumentTemplate)
async def create_document_template(
    template: DocumentTemplate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a document template."""
    # Save template to database
    template_id = await save_document_template(
        current_user.id,
        template,
        db
    )
    
    template.id = template_id
    return template


@router.get("/documents/templates", response_model=List[DocumentTemplate])
async def list_document_templates(
    document_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available document templates."""
    templates = await get_user_templates(
        current_user.id,
        document_type,
        db
    )
    
    return templates


@router.put("/documents/templates/{template_id}")
async def update_document_template(
    template_id: str,
    template: DocumentTemplate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a document template."""
    # Verify ownership and update
    success = await update_template(
        template_id,
        current_user.id,
        template,
        db
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or not authorized"
        )
    
    return {"message": "Template updated successfully"}


@router.delete("/documents/templates/{template_id}")
async def delete_document_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a document template."""
    success = await delete_template(
        template_id,
        current_user.id,
        db
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or not authorized"
        )
    
    return {"message": "Template deleted successfully"}


# Analysis Endpoints
@router.post("/analyze/text")
async def analyze_text(
    request: AnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze text content."""
    # Check quota
    await check_ai_quota(current_user, db)
    
    # Select AI model
    ai_model = await get_ai_model(request.model, "analysis")
    
    # Build analysis prompt based on type
    prompts = {
        "sentiment": "Analyze the sentiment of the following text. Provide a score from -1 (very negative) to 1 (very positive) and explain why:",
        "entities": "Extract all named entities (people, places, organizations, dates, etc.) from the following text:",
        "summary": "Provide a concise summary of the following text:",
        "classification": "Classify the following text into appropriate categories:"
    }
    
    prompt = f"{prompts.get(request.analysis_type, 'Analyze the following text:')}\n\n{request.content}"
    
    # Add any specific options
    if request.options:
        prompt += f"\n\nAdditional instructions: {json.dumps(request.options)}"
    
    # Perform analysis
    result = await ai_model.generate(prompt)
    
    # Parse result based on analysis type
    analysis_result = parse_analysis_result(request.analysis_type, result)
    
    # Increment usage
    await increment_ai_usage(current_user, len(request.content.split()), db)
    
    return {
        "analysis_type": request.analysis_type,
        "result": analysis_result,
        "model_used": ai_model.name,
        "timestamp": datetime.utcnow()
    }


@router.post("/analyze/document")
async def analyze_document(
    file: UploadFile = File(...),
    analysis_type: str = "summary",
    model: Optional[str] = "auto",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze uploaded document."""
    # Check quota
    await check_ai_quota(current_user, db)
    
    # Read and process document
    content = await file.read()
    text_content = await extract_text_from_document(content, file.filename)
    
    if not text_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract text from document"
        )
    
    # Use text analysis
    request = AnalysisRequest(
        content=text_content,
        analysis_type=analysis_type,
        model=model
    )
    
    return await analyze_text(request, current_user, db)


@router.post("/analyze/image")
async def analyze_image(
    file: UploadFile = File(...),
    request: ImageAnalysisRequest = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze uploaded image."""
    # Check quota
    await check_ai_quota(current_user, db)
    
    # Read image
    image_data = await file.read()
    
    # Select vision-capable model
    ai_model = await get_ai_model(request.model, "vision")
    
    # Build prompt based on task
    prompts = {
        "describe": "Describe what you see in this image in detail:",
        "ocr": "Extract all text visible in this image:",
        "classify": "Classify this image into appropriate categories:",
        "detect_objects": "List all objects and their locations in this image:"
    }
    
    prompt = prompts.get(request.task, "Analyze this image:")
    
    # Perform analysis (assuming model supports image input)
    result = await ai_model.analyze_image(image_data, prompt)
    
    # Increment usage
    await increment_ai_usage(current_user, 1, db)
    
    return {
        "task": request.task,
        "result": result,
        "model_used": ai_model.name,
        "timestamp": datetime.utcnow()
    }


@router.post("/summarize")
async def summarize_content(
    content: str,
    summary_length: str = "medium",  # short, medium, long
    model: Optional[str] = "auto",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Summarize long content."""
    # Check quota
    await check_ai_quota(current_user, db)
    
    # Select AI model
    ai_model = await get_ai_model(model, "summary")
    
    # Build prompt
    length_instructions = {
        "short": "in 2-3 sentences",
        "medium": "in 1-2 paragraphs",
        "long": "in 3-4 paragraphs with key points"
    }
    
    prompt = f"Summarize the following content {length_instructions.get(summary_length, '')}:\n\n{content}"
    
    # Generate summary
    summary = await ai_model.generate(prompt)
    
    # Increment usage
    await increment_ai_usage(current_user, len(content.split()), db)
    
    return {
        "summary": summary,
        "original_length": len(content),
        "summary_length": len(summary),
        "compression_ratio": len(summary) / len(content),
        "model_used": ai_model.name
    }


@router.post("/translate")
async def translate_text(
    request: TranslationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Translate text between languages."""
    # Check quota
    await check_ai_quota(current_user, db)
    
    # Select AI model
    ai_model = await get_ai_model(request.model, "translation")
    
    # Build prompt
    if request.source_language == "auto":
        prompt = f"Translate the following text to {request.target_language}:\n\n{request.text}"
    else:
        prompt = f"Translate the following text from {request.source_language} to {request.target_language}:\n\n{request.text}"
    
    # Perform translation
    translation = await ai_model.generate(prompt)
    
    # Detect source language if auto
    detected_language = None
    if request.source_language == "auto":
        detected_language = await detect_language(request.text, ai_model)
    
    # Increment usage
    await increment_ai_usage(current_user, len(request.text.split()), db)
    
    return {
        "original_text": request.text,
        "translated_text": translation,
        "source_language": detected_language or request.source_language,
        "target_language": request.target_language,
        "model_used": ai_model.name
    }


@router.post("/extract")
async def extract_data(
    content: str,
    extraction_schema: Dict[str, Any],
    model: Optional[str] = "auto",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Extract structured data from unstructured text."""
    # Check quota
    await check_ai_quota(current_user, db)
    
    # Select AI model
    ai_model = await get_ai_model(model, "extraction")
    
    # Build prompt
    prompt = f"""Extract the following information from the text according to the schema:

Schema:
{json.dumps(extraction_schema, indent=2)}

Text:
{content}

Return the extracted data as valid JSON matching the schema."""
    
    # Perform extraction
    result = await ai_model.generate(prompt)
    
    # Parse JSON result
    try:
        extracted_data = json.loads(result)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        import re
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            extracted_data = json.loads(json_match.group())
        else:
            extracted_data = {"error": "Could not parse extraction result"}
    
    # Increment usage
    await increment_ai_usage(current_user, len(content.split()), db)
    
    return {
        "extracted_data": extracted_data,
        "schema": extraction_schema,
        "model_used": ai_model.name
    }


# Model Management Endpoints
@router.get("/models", response_model=List[ModelInfo])
async def list_available_models(
    current_user: User = Depends(get_current_user)
):
    """List all available AI models."""
    models = [
        ModelInfo(
            id="claude-3-opus",
            name="Claude 3 Opus",
            provider="Anthropic",
            capabilities=["chat", "analysis", "code", "creative"],
            context_window=200000,
            max_output_tokens=4096,
            cost_per_1k_input=0.015,
            cost_per_1k_output=0.075,
            is_available=bool(settings.ANTHROPIC_API_KEY)
        ),
        ModelInfo(
            id="gpt-4-turbo",
            name="GPT-4 Turbo",
            provider="OpenAI",
            capabilities=["chat", "analysis", "code", "vision"],
            context_window=128000,
            max_output_tokens=4096,
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.03,
            is_available=bool(settings.OPENAI_API_KEY)
        ),
        ModelInfo(
            id="gemini-pro",
            name="Gemini Pro",
            provider="Google",
            capabilities=["chat", "analysis", "vision", "multimodal"],
            context_window=32000,
            max_output_tokens=2048,
            cost_per_1k_input=0.00025,
            cost_per_1k_output=0.0005,
            is_available=bool(settings.GEMINI_API_KEY)
        )
    ]
    
    return models


@router.post("/models/select")
async def select_model_for_session(
    selection: ModelSelection,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Select a specific model for a session."""
    # Update session preference
    vector_store = VectorStore()
    await vector_store.update_session_model(
        user_id=str(current_user.id),
        session_id=selection.session_id,
        model=selection.model
    )
    
    return {"message": f"Model {selection.model} selected for session"}


@router.get("/models/usage")
async def get_model_usage(
    period: str = "month",  # day, week, month
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get AI usage statistics."""
    # Calculate usage stats
    usage_stats = await calculate_usage_stats(
        user_id=current_user.id,
        period=period,
        db=db
    )
    
    return usage_stats


@router.get("/models/costs")
async def get_usage_costs(
    period: str = "month",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get cost breakdown for AI usage."""
    # Calculate costs
    cost_breakdown = await calculate_cost_breakdown(
        user_id=current_user.id,
        period=period,
        db=db
    )
    
    return cost_breakdown


# Helper functions (these would be implemented separately)
async def save_chat_messages(user_id, session_id, user_message, ai_response, db):
    """Save chat messages to memory."""
    vector_store = VectorStore()
    
    # Save user message
    await vector_store.add_memory(
        content=user_message,
        memory_type="conversation",
        metadata={
            "user_id": str(user_id),
            "session_id": session_id,
            "role": "user",
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    # Save AI response
    await vector_store.add_memory(
        content=ai_response,
        memory_type="conversation",
        metadata={
            "user_id": str(user_id),
            "session_id": session_id,
            "role": "assistant",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


async def get_document_template(template_id: str, db: Session):
    """Get document template from database."""
    from ..db.business_models import DocumentTemplate as DBDocumentTemplate
    
    template = db.query(DBDocumentTemplate).filter(
        DBDocumentTemplate.id == template_id
    ).first()
    
    if template:
        return DocumentTemplate(
            name=template.name,
            description=template.description,
            document_type=template.document_type,
            template=template.template,
            variables=template.variables,
            example_context=template.example_context
        )
    
    return None


async def save_generated_document(doc_id, user_id, title, doc_type, content, format, db):
    """Save generated document."""
    from ..db.business_models import Document
    
    document = Document(
        id=doc_id,
        user_id=user_id,
        title=title,
        document_type=doc_type,
        content=content,
        format=format,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return document


async def save_document_template(user_id, template, db):
    """Save document template."""
    from ..db.business_models import DocumentTemplate as DBDocumentTemplate
    
    db_template = DBDocumentTemplate(
        user_id=user_id,
        name=template.name,
        description=template.description,
        document_type=template.document_type,
        template=template.template,
        variables=template.variables,
        example_context=template.example_context,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    
    return str(db_template.id)


async def get_user_templates(user_id, document_type, db):
    """Get user's document templates."""
    from ..db.business_models import DocumentTemplate as DBDocumentTemplate
    
    query = db.query(DBDocumentTemplate).filter(
        DBDocumentTemplate.user_id == user_id
    )
    
    if document_type:
        query = query.filter(DBDocumentTemplate.document_type == document_type)
    
    templates = query.all()
    
    return [
        DocumentTemplate(
            name=template.name,
            description=template.description,
            document_type=template.document_type,
            template=template.template,
            variables=template.variables,
            example_context=template.example_context
        )
        for template in templates
    ]


async def update_template(template_id, user_id, template, db):
    """Update document template."""
    from ..db.business_models import DocumentTemplate as DBDocumentTemplate
    
    db_template = db.query(DBDocumentTemplate).filter(
        DBDocumentTemplate.id == template_id,
        DBDocumentTemplate.user_id == user_id
    ).first()
    
    if not db_template:
        return False
    
    db_template.name = template.name
    db_template.description = template.description
    db_template.document_type = template.document_type
    db_template.template = template.template
    db_template.variables = template.variables
    db_template.example_context = template.example_context
    db_template.updated_at = datetime.utcnow()
    
    db.commit()
    
    return True


async def delete_template(template_id, user_id, db):
    """Delete document template."""
    from ..db.business_models import DocumentTemplate as DBDocumentTemplate
    
    db_template = db.query(DBDocumentTemplate).filter(
        DBDocumentTemplate.id == template_id,
        DBDocumentTemplate.user_id == user_id
    ).first()
    
    if not db_template:
        return False
    
    db.delete(db_template)
    db.commit()
    
    return True


def parse_analysis_result(analysis_type, raw_result):
    """Parse AI analysis result based on type."""
    # Implementation would parse based on analysis type
    return raw_result


async def extract_text_from_document(content, filename):
    """Extract text from various document formats."""
    # Implementation would use appropriate libraries for PDF, DOCX, etc.
    return "Extracted text content"


async def detect_language(text, ai_model):
    """Detect language of text."""
    prompt = f"What language is this text written in? Just return the language name: {text[:200]}"
    result = await ai_model.generate(prompt)
    return result.strip()


def markdown_to_html(markdown_text):
    """Convert markdown to HTML."""
    # Implementation would use markdown library
    return f"<html><body>{markdown_text}</body></html>"


async def calculate_usage_stats(user_id, period, db):
    """Calculate AI usage statistics."""
    from sqlalchemy import func
    from ..db.business_models import AIUsageLog
    
    # Calculate date range based on period
    end_date = datetime.utcnow()
    if period == "day":
        start_date = end_date - timedelta(days=1)
    elif period == "week":
        start_date = end_date - timedelta(weeks=1)
    else:  # month
        start_date = end_date - timedelta(days=30)
    
    # Query usage logs
    logs = db.query(AIUsageLog).filter(
        AIUsageLog.user_id == user_id,
        AIUsageLog.created_at >= start_date,
        AIUsageLog.created_at <= end_date
    ).all()
    
    # Calculate statistics
    total_requests = len(logs)
    total_tokens = sum(log.tokens_used for log in logs)
    
    by_model = {}
    by_type = {}
    
    for log in logs:
        # Count by model
        if log.model not in by_model:
            by_model[log.model] = 0
        by_model[log.model] += 1
        
        # Count by type
        if log.request_type not in by_type:
            by_type[log.request_type] = 0
        by_type[log.request_type] += 1
    
    return {
        "period": period,
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "by_model": by_model,
        "by_type": by_type
    }


async def calculate_cost_breakdown(user_id, period, db):
    """Calculate cost breakdown for AI usage."""
    from ..db.business_models import AIUsageLog, Subscription
    
    # Get usage stats first
    stats = await calculate_usage_stats(user_id, period, db)
    
    # Model pricing (per 1k tokens)
    model_pricing = {
        "claude": {"input": 0.015, "output": 0.075},
        "gpt": {"input": 0.01, "output": 0.03},
        "gemini": {"input": 0.00025, "output": 0.0005}
    }
    
    # Calculate costs
    total_cost = 0.0
    by_model = {}
    by_type = {}
    
    # Get detailed usage logs
    end_date = datetime.utcnow()
    if period == "day":
        start_date = end_date - timedelta(days=1)
    elif period == "week":
        start_date = end_date - timedelta(weeks=1)
    else:  # month
        start_date = end_date - timedelta(days=30)
    
    logs = db.query(AIUsageLog).filter(
        AIUsageLog.user_id == user_id,
        AIUsageLog.created_at >= start_date,
        AIUsageLog.created_at <= end_date
    ).all()
    
    for log in logs:
        # Calculate cost for this request
        model_rates = model_pricing.get(log.model, model_pricing["gemini"])
        # Assume 70% input, 30% output tokens
        input_tokens = int(log.tokens_used * 0.7)
        output_tokens = int(log.tokens_used * 0.3)
        
        cost = (input_tokens * model_rates["input"] / 1000 + 
                output_tokens * model_rates["output"] / 1000)
        
        total_cost += cost
        
        # Track by model
        if log.model not in by_model:
            by_model[log.model] = 0.0
        by_model[log.model] += cost
        
        # Track by type
        if log.request_type not in by_type:
            by_type[log.request_type] = 0.0
        by_type[log.request_type] += cost
    
    # Get user's subscription budget
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user_id
    ).first()
    
    monthly_budget = subscription.monthly_budget if subscription else 100.0
    remaining_budget = monthly_budget - total_cost
    
    return {
        "period": period,
        "total_cost": round(total_cost, 2),
        "by_model": {k: round(v, 2) for k, v in by_model.items()},
        "by_type": {k: round(v, 2) for k, v in by_type.items()},
        "remaining_budget": round(remaining_budget, 2)
    }