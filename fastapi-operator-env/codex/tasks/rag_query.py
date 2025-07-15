"""Answer a query using local documents via simple RAG."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict

import openai
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

TASK_ID = "rag_query"
TASK_DESCRIPTION = "Answer a question using local docs with RAG"
REQUIRED_FIELDS = ["query", "docs_path"]

logger = logging.getLogger(__name__)

_CACHE_DIR = Path("rag_cache")


def _load_index(doc_dir: Path) -> FAISS:
    _CACHE_DIR.mkdir(exist_ok=True)
    index_file = _CACHE_DIR / f"{doc_dir.name}.faiss"
    embeddings = OpenAIEmbeddings()
    if index_file.exists():
        return FAISS.load_local(str(index_file), embeddings)

    texts: list[str] = []
    for path in doc_dir.rglob("*"):
        if path.suffix.lower() in {".md", ".txt"}:
            try:
                texts.append(path.read_text())
            except Exception:  # noqa: BLE001
                continue
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = splitter.create_documents(texts)
    db = FAISS.from_documents(docs, embeddings)
    db.save_local(str(index_file))
    return db


def _call_gpt(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    openai.api_key = api_key
    response = openai.chat.completions.create(
        model="gpt-4o", messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def run(context: Dict[str, str]) -> Dict[str, str]:
    query = context.get("query", "")
    docs_path = Path(context.get("docs_path", ""))
    if not query or not docs_path.exists():
        return {"error": "invalid_input"}

    try:
        db = _load_index(docs_path)
        matches = db.similarity_search(query, k=3)
        context_text = "\n\n".join(m.page_content for m in matches)
        prompt = f"Use the following context to answer the question:\n{context_text}\n\nQuestion: {query}"
        answer = _call_gpt(prompt)
        return {"answer": answer}
    except Exception as exc:  # noqa: BLE001
        logger.error("RAG query failed: %s", exc)
        return {"error": str(exc)}
