"""QA and Review System API endpoints."""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from core.auth import get_current_user
from services.qa_system import QASystem, ReviewType, ReviewStatus
from models.db import User
from utils.audit import AuditLogger

router = APIRouter(prefix="/qa", tags=["qa"])
audit_logger = AuditLogger()

# Initialize services
qa_system = QASystem()


class ReviewCreate(BaseModel):
    """Review creation model."""
    review_type: ReviewType = Field(..., description="Type of review")
    target_path: str = Field(..., description="Path to review target")
    title: str = Field(..., description="Review title")
    description: Optional[str] = Field(default=None, description="Review description")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Review configuration")
    auto_fix: bool = Field(default=False, description="Enable automatic fixes")


class CodeReview(BaseModel):
    """Code review model."""
    file_path: str = Field(..., description="Path to code file")
    pull_request_url: Optional[str] = Field(default=None, description="Pull request URL")
    auto_fix: bool = Field(default=False, description="Enable automatic fixes")


class ContentReview(BaseModel):
    """Content review model."""
    content: str = Field(..., description="Content to review")
    content_type: str = Field(default="markdown", description="Content type")
    auto_fix: bool = Field(default=False, description="Enable automatic fixes")


class SecurityScan(BaseModel):
    """Security scan model."""
    target_path: str = Field(..., description="Path to scan")
    scan_type: str = Field(default="comprehensive", description="Type of scan")


class RegressionTest(BaseModel):
    """Regression test model."""
    test_suite_path: str = Field(..., description="Path to test suite")
    baseline_results: Optional[Dict[str, Any]] = Field(default=None, description="Baseline results")


class QAReport(BaseModel):
    """QA report model."""
    review_ids: List[str] = Field(..., description="Review IDs to include")
    report_type: str = Field(default="executive", description="Type of report")


@router.post("/reviews", response_model=Dict[str, Any])
async def create_review(
    review: ReviewCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Create a new review."""
    try:
        result = await qa_system.create_review(
            review_type=review.review_type,
            target_path=review.target_path,
            title=review.title,
            description=review.description,
            config=review.config,
            created_by=current_user.id,
            auto_fix=review.auto_fix
        )
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="qa_review_created",
            resource_type="qa_review",
            resource_id=result["review_id"],
            details={
                "type": review.review_type.value,
                "target_path": review.target_path,
                "title": review.title
            }
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reviews", response_model=List[Dict[str, Any]])
async def list_reviews(
    review_type: Optional[ReviewType] = None,
    status: Optional[ReviewStatus] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """List reviews."""
    try:
        reviews = await qa_system.list_reviews(
            review_type=review_type,
            status=status,
            created_by=current_user.id,
            limit=limit,
            offset=offset
        )
        
        return [
            {
                "id": review["id"],
                "type": review["type"],
                "target_path": review["target_path"],
                "title": review["title"],
                "description": review["description"],
                "status": review["status"],
                "created_at": review["created_at"].isoformat(),
                "completed_at": review.get("completed_at").isoformat() if review.get("completed_at") else None,
                "issues_count": len(review.get("issues", [])),
                "metrics": review.get("metrics", {})
            }
            for review in reviews
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reviews/{review_id}", response_model=Dict[str, Any])
async def get_review(
    review_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific review."""
    try:
        review = await qa_system.get_review(review_id)
        
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        
        return {
            "id": review["id"],
            "type": review["type"],
            "target_path": review["target_path"],
            "title": review["title"],
            "description": review["description"],
            "status": review["status"],
            "created_at": review["created_at"].isoformat(),
            "started_at": review.get("started_at").isoformat() if review.get("started_at") else None,
            "completed_at": review.get("completed_at").isoformat() if review.get("completed_at") else None,
            "config": review.get("config", {}),
            "results": review.get("results", {}),
            "issues": review.get("issues", []),
            "metrics": review.get("metrics", {}),
            "reports": review.get("reports", [])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reviews/{review_id}/cancel", response_model=Dict[str, Any])
async def cancel_review(
    review_id: str,
    current_user: User = Depends(get_current_user)
):
    """Cancel a running review."""
    try:
        success = await qa_system.cancel_review(review_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Review not found or cannot be cancelled")
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="qa_review_cancelled",
            resource_type="qa_review",
            resource_id=review_id
        )
        
        return {
            "success": True,
            "message": "Review cancelled"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/code-review", response_model=Dict[str, Any])
async def run_code_review(
    review: CodeReview,
    current_user: User = Depends(get_current_user)
):
    """Run code review."""
    try:
        result = await qa_system.run_code_review(
            file_path=review.file_path,
            pull_request_url=review.pull_request_url,
            auto_fix=review.auto_fix
        )
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="code_review_run",
            resource_type="code_review",
            resource_id=result.get("review_id", "unknown"),
            details={
                "file_path": review.file_path,
                "auto_fix": review.auto_fix,
                "overall_score": result.get("overall_score", 0)
            }
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/content-review", response_model=Dict[str, Any])
async def run_content_review(
    review: ContentReview,
    current_user: User = Depends(get_current_user)
):
    """Run content review."""
    try:
        result = await qa_system.run_content_review(
            content=review.content,
            content_type=review.content_type,
            auto_fix=review.auto_fix
        )
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="content_review_run",
            resource_type="content_review",
            resource_id=result.get("review_id", "unknown"),
            details={
                "content_type": review.content_type,
                "content_length": len(review.content),
                "auto_fix": review.auto_fix,
                "overall_score": result.get("overall_score", 0)
            }
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/security-scan", response_model=Dict[str, Any])
async def run_security_scan(
    scan: SecurityScan,
    current_user: User = Depends(get_current_user)
):
    """Run security scan."""
    try:
        result = await qa_system.run_security_scan(
            target_path=scan.target_path,
            scan_type=scan.scan_type
        )
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="security_scan_run",
            resource_type="security_scan",
            resource_id=result.get("scan_id", "unknown"),
            details={
                "target_path": scan.target_path,
                "scan_type": scan.scan_type,
                "risk_score": result.get("risk_score", 0),
                "vulnerabilities_count": len(result.get("vulnerabilities", []))
            }
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regression-test", response_model=Dict[str, Any])
async def run_regression_test(
    test: RegressionTest,
    current_user: User = Depends(get_current_user)
):
    """Run regression tests."""
    try:
        result = await qa_system.run_regression_tests(
            test_suite_path=test.test_suite_path,
            baseline_results=test.baseline_results
        )
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="regression_test_run",
            resource_type="regression_test",
            resource_id=result.get("test_id", "unknown"),
            details={
                "test_suite_path": test.test_suite_path,
                "regressions_count": len(result.get("regressions", [])),
                "new_failures_count": len(result.get("new_failures", []))
            }
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports", response_model=Dict[str, Any])
async def generate_qa_report(
    report: QAReport,
    current_user: User = Depends(get_current_user)
):
    """Generate QA report."""
    try:
        result = await qa_system.generate_qa_report(
            review_ids=report.review_ids,
            report_type=report.report_type
        )
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="qa_report_generated",
            resource_type="qa_report",
            resource_id=result.get("report_id", "unknown"),
            details={
                "report_type": report.report_type,
                "reviews_count": len(report.review_ids)
            }
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review-types", response_model=List[Dict[str, str]])
async def get_review_types():
    """Get available review types."""
    return [
        {"type": review_type.value, "description": review_type.value.replace("_", " ").title()}
        for review_type in ReviewType
    ]


@router.get("/health")
async def health_check():
    """Health check for QA system."""
    try:
        # Check QA system health
        active_reviews_count = len(qa_system.active_reviews)
        
        status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "qa_system",
            "active_reviews": active_reviews_count,
            "supported_review_types": [t.value for t in ReviewType],
            "available_tools": {
                "security_tools": list(qa_system.security_tools.keys()),
                "quality_tools": list(qa_system.quality_tools.keys()),
                "content_tools": list(qa_system.content_tools.keys())
            }
        }
        
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))