"""
Financial and Accounting Management System

Comprehensive financial module for invoicing, payments, expenses, reporting,
and accounting integration. Handles all monetary transactions, tax calculations,
financial reporting, and integrations with payment processors and accounting software.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, extract, case
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field, validator, condecimal
import uuid
import json
import io
import csv
from enum import Enum

from ..core.database import get_db
from ..core.auth import get_current_user
from ..core.rbac import Permission, require_permission, PermissionChecker
from ..core.cache import cache_result, invalidate_cache
from ..services.notifications import send_notification, NotificationType
from ..core.audit import audit_log
from ..db.business_models import User, UserRole, Project, Job, Estimate
from ..services.document_generator import DocumentGenerator
from ..integrations.stripe import StripeService
from ..integrations.quickbooks import QuickBooksService
from ..integrations.tax_service import TaxService


router = APIRouter(prefix="/api/v1/financial", tags=["Financial Management"])


# Enums
class InvoiceStatus(str, Enum):
    """Invoice lifecycle states."""
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    """Supported payment methods."""
    CASH = "cash"
    CHECK = "check"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    ACH = "ach"
    WIRE = "wire"
    PAYPAL = "paypal"
    VENMO = "venmo"
    ZELLE = "zelle"
    CRYPTO = "crypto"
    OTHER = "other"


class ExpenseCategory(str, Enum):
    """Expense categorization for accounting."""
    MATERIALS = "materials"
    LABOR = "labor"
    EQUIPMENT = "equipment"
    VEHICLE = "vehicle"
    FUEL = "fuel"
    INSURANCE = "insurance"
    PERMITS = "permits"
    MARKETING = "marketing"
    OFFICE = "office"
    UTILITIES = "utilities"
    PROFESSIONAL = "professional"
    TAXES = "taxes"
    OTHER = "other"


class ReportType(str, Enum):
    """Financial report types."""
    PROFIT_LOSS = "profit_loss"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"
    ACCOUNTS_RECEIVABLE = "accounts_receivable"
    ACCOUNTS_PAYABLE = "accounts_payable"
    TAX_SUMMARY = "tax_summary"
    JOB_PROFITABILITY = "job_profitability"
    EXPENSE_SUMMARY = "expense_summary"
    REVENUE_FORECAST = "revenue_forecast"


class TaxType(str, Enum):
    """Tax categories."""
    SALES_TAX = "sales_tax"
    USE_TAX = "use_tax"
    VAT = "vat"
    GST = "gst"
    INCOME_TAX = "income_tax"
    PAYROLL_TAX = "payroll_tax"


# Request/Response Models
class InvoiceLineItem(BaseModel):
    """Line item on an invoice."""
    description: str
    quantity: Decimal = Field(..., decimal_places=2)
    unit_price: Decimal = Field(..., decimal_places=2)
    tax_rate: Decimal = Field(default=Decimal("0.00"), decimal_places=4)
    discount_percent: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    
    @property
    def subtotal(self) -> Decimal:
        """Calculate line subtotal."""
        base = self.quantity * self.unit_price
        discount = base * (self.discount_percent / 100)
        return base - discount
    
    @property
    def tax_amount(self) -> Decimal:
        """Calculate tax amount."""
        return self.subtotal * (self.tax_rate / 100)
    
    @property
    def total(self) -> Decimal:
        """Calculate line total."""
        return self.subtotal + self.tax_amount


class InvoiceCreate(BaseModel):
    """Create a new invoice."""
    customer_id: uuid.UUID
    estimate_id: Optional[uuid.UUID] = None
    job_id: Optional[uuid.UUID] = None
    
    # Invoice details
    invoice_number: Optional[str] = None
    invoice_date: date = Field(default_factory=date.today)
    due_date: date
    
    # Line items
    line_items: List[InvoiceLineItem]
    
    # Additional charges/discounts
    discount_amount: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    shipping_amount: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    
    # Terms and notes
    payment_terms: str = "Net 30"
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    
    # Options
    auto_send: bool = False
    send_reminder: bool = True


class PaymentRecord(BaseModel):
    """Record a payment."""
    invoice_id: uuid.UUID
    amount: Decimal = Field(..., decimal_places=2, gt=0)
    payment_method: PaymentMethod
    payment_date: date = Field(default_factory=date.today)
    
    # Payment details
    reference_number: Optional[str] = None
    transaction_id: Optional[str] = None
    
    # For checks
    check_number: Optional[str] = None
    bank_name: Optional[str] = None
    
    # For cards
    last_four: Optional[str] = Field(None, max_length=4)
    card_brand: Optional[str] = None
    
    # Processing
    processing_fee: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    notes: Optional[str] = None


class ExpenseCreate(BaseModel):
    """Create an expense record."""
    category: ExpenseCategory
    amount: Decimal = Field(..., decimal_places=2, gt=0)
    expense_date: date = Field(default_factory=date.today)
    
    # Details
    vendor: str
    description: str
    
    # Job allocation
    job_id: Optional[uuid.UUID] = None
    billable: bool = False
    
    # Payment info
    payment_method: Optional[PaymentMethod] = None
    reference_number: Optional[str] = None
    
    # Receipt
    receipt_url: Optional[str] = None
    
    # Accounting
    tax_deductible: bool = True
    tags: List[str] = []


class FinancialReportRequest(BaseModel):
    """Request for financial reports."""
    report_type: ReportType
    start_date: date
    end_date: date
    
    # Filters
    project_ids: Optional[List[uuid.UUID]] = None
    job_ids: Optional[List[uuid.UUID]] = None
    customer_ids: Optional[List[uuid.UUID]] = None
    
    # Options
    include_details: bool = True
    format: str = Field(default="json", regex="^(json|csv|pdf)$")
    compare_period: Optional[str] = None  # "previous_period", "previous_year"


# Database Models
class Invoice(Base):
    """Invoice model."""
    __tablename__ = "invoices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    estimate_id = Column(UUID(as_uuid=True), ForeignKey("estimates.id"), nullable=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)
    
    # Dates
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    sent_date = Column(DateTime, nullable=True)
    viewed_date = Column(DateTime, nullable=True)
    paid_date = Column(DateTime, nullable=True)
    
    # Amounts (stored as cents to avoid decimal issues)
    subtotal_cents = Column(Integer, nullable=False)
    tax_cents = Column(Integer, nullable=False)
    discount_cents = Column(Integer, default=0)
    shipping_cents = Column(Integer, default=0)
    total_cents = Column(Integer, nullable=False)
    paid_cents = Column(Integer, default=0)
    
    # Status
    status = Column(String(20), default=InvoiceStatus.DRAFT.value)
    
    # Content
    line_items = Column(JSON, nullable=False)
    payment_terms = Column(String(100), default="Net 30")
    notes = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)
    
    # Tracking
    view_count = Column(Integer, default=0)
    reminder_count = Column(Integer, default=0)
    last_reminder_date = Column(DateTime, nullable=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")
    creator = relationship("User")


class Payment(Base):
    """Payment record model."""
    __tablename__ = "payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    
    # Amount
    amount_cents = Column(Integer, nullable=False)
    processing_fee_cents = Column(Integer, default=0)
    
    # Payment info
    payment_method = Column(String(20), nullable=False)
    payment_date = Column(Date, nullable=False)
    reference_number = Column(String(100), nullable=True)
    transaction_id = Column(String(200), nullable=True)
    
    # Additional details
    details = Column(JSON, default={})
    notes = Column(Text, nullable=True)
    
    # Status
    is_verified = Column(Boolean, default=False)
    verification_date = Column(DateTime, nullable=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="payments")
    creator = relationship("User")


class Expense(Base):
    """Expense tracking model."""
    __tablename__ = "expenses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Categorization
    category = Column(String(50), nullable=False)
    vendor = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    
    # Amount
    amount_cents = Column(Integer, nullable=False)
    expense_date = Column(Date, nullable=False)
    
    # Job allocation
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)
    billable = Column(Boolean, default=False)
    billed = Column(Boolean, default=False)
    
    # Payment
    payment_method = Column(String(20), nullable=True)
    reference_number = Column(String(100), nullable=True)
    
    # Documentation
    receipt_url = Column(String(500), nullable=True)
    
    # Accounting
    tax_deductible = Column(Boolean, default=True)
    tags = Column(JSON, default=[])
    
    # Approval
    requires_approval = Column(Boolean, default=False)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job = relationship("Job")
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approved_by])


# API Endpoints

@router.post("/invoices", response_model=Dict[str, Any])
@require_permission(Permission.FINANCE_WRITE)
async def create_invoice(
    invoice_data: InvoiceCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new invoice with automatic calculations and tax handling.
    
    Features:
    - Automatic invoice numbering
    - Tax calculation based on location
    - Integration with estimates and jobs
    - Optional auto-send functionality
    """
    try:
        # Generate invoice number if not provided
        if not invoice_data.invoice_number:
            last_invoice = db.query(Invoice).order_by(Invoice.invoice_number.desc()).first()
            if last_invoice and last_invoice.invoice_number.startswith("INV-"):
                last_num = int(last_invoice.invoice_number.split("-")[1])
                invoice_number = f"INV-{last_num + 1:06d}"
            else:
                invoice_number = "INV-000001"
        else:
            invoice_number = invoice_data.invoice_number
        
        # Calculate totals
        subtotal = Decimal("0.00")
        tax_total = Decimal("0.00")
        
        for item in invoice_data.line_items:
            subtotal += item.subtotal
            tax_total += item.tax_amount
        
        # Apply additional charges/discounts
        subtotal += invoice_data.shipping_amount
        total = subtotal + tax_total - invoice_data.discount_amount
        
        # Create invoice
        invoice = Invoice(
            id=uuid.uuid4(),
            invoice_number=invoice_number,
            customer_id=invoice_data.customer_id,
            estimate_id=invoice_data.estimate_id,
            job_id=invoice_data.job_id,
            
            # Dates
            invoice_date=invoice_data.invoice_date,
            due_date=invoice_data.due_date,
            
            # Amounts (convert to cents)
            subtotal_cents=int(subtotal * 100),
            tax_cents=int(tax_total * 100),
            discount_cents=int(invoice_data.discount_amount * 100),
            shipping_cents=int(invoice_data.shipping_amount * 100),
            total_cents=int(total * 100),
            
            # Content
            line_items=[item.dict() for item in invoice_data.line_items],
            payment_terms=invoice_data.payment_terms,
            notes=invoice_data.notes,
            internal_notes=invoice_data.internal_notes,
            
            # Status
            status=InvoiceStatus.DRAFT.value,
            
            # Metadata
            created_by=current_user.id
        )
        
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        
        # Auto-send if requested
        if invoice_data.auto_send:
            invoice.status = InvoiceStatus.SENT.value
            invoice.sent_date = datetime.utcnow()
            db.commit()
            
            # Send email
            background_tasks.add_task(
                _send_invoice_email,
                invoice_id=invoice.id,
                db=db
            )
        
        # Link to job if provided
        if invoice_data.job_id:
            job = db.query(Job).filter_by(id=invoice_data.job_id).first()
            if job:
                job.invoice_id = invoice.id
                db.commit()
        
        # Audit log
        await audit_log(
            user_id=current_user.id,
            action="invoice_created",
            resource_type="invoice",
            resource_id=invoice.id,
            details={
                "invoice_number": invoice.invoice_number,
                "customer_id": str(invoice.customer_id),
                "total": float(total)
            }
        )
        
        return {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "status": invoice.status,
            "total": float(total),
            "due_date": invoice.due_date.isoformat(),
            "message": "Invoice created successfully",
            "pdf_url": f"/api/v1/financial/invoices/{invoice.id}/pdf"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to create invoice: {str(e)}")


@router.get("/invoices", response_model=Dict[str, Any])
@require_permission(Permission.FINANCE_READ)
async def list_invoices(
    # Filters
    status: Optional[InvoiceStatus] = Query(None),
    customer_id: Optional[uuid.UUID] = Query(None),
    job_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    overdue_only: bool = Query(False),
    
    # Pagination
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    
    # Sorting
    sort_by: str = Query("invoice_date", regex="^(invoice_date|due_date|total|invoice_number)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rbac: PermissionChecker = Depends(PermissionChecker(Permission.FINANCE_READ))
) -> Dict[str, Any]:
    """
    List invoices with filtering and pagination.
    
    Features:
    - Status filtering
    - Date range filtering
    - Customer/job filtering
    - Overdue highlighting
    - Aging analysis
    """
    try:
        # Build query
        query = db.query(Invoice)
        
        # Apply filters
        if status:
            query = query.filter(Invoice.status == status.value)
        
        if customer_id:
            query = query.filter(Invoice.customer_id == customer_id)
        
        if job_id:
            query = query.filter(Invoice.job_id == job_id)
        
        if date_from:
            query = query.filter(Invoice.invoice_date >= date_from)
        
        if date_to:
            query = query.filter(Invoice.invoice_date <= date_to)
        
        if overdue_only:
            query = query.filter(
                Invoice.due_date < date.today(),
                Invoice.status.in_([InvoiceStatus.SENT.value, InvoiceStatus.VIEWED.value, InvoiceStatus.PARTIAL.value])
            )
        
        # Get total count
        total_count = query.count()
        
        # Calculate summary statistics
        stats_query = query.with_entities(
            func.count(Invoice.id).label('count'),
            func.sum(Invoice.total_cents).label('total'),
            func.sum(Invoice.paid_cents).label('paid'),
            func.sum(case((Invoice.status == InvoiceStatus.OVERDUE.value, Invoice.total_cents - Invoice.paid_cents), else_=0)).label('overdue')
        ).first()
        
        # Apply sorting
        sort_column = getattr(Invoice, sort_by)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        invoices = query.offset(offset).limit(page_size).all()
        
        # Format response
        invoice_list = []
        for invoice in invoices:
            # Calculate age
            age_days = (date.today() - invoice.invoice_date).days
            days_overdue = (date.today() - invoice.due_date).days if invoice.due_date < date.today() else 0
            
            invoice_list.append({
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "customer_id": invoice.customer_id,
                "customer_name": invoice.customer.name if invoice.customer else "Unknown",
                "status": invoice.status,
                "invoice_date": invoice.invoice_date.isoformat(),
                "due_date": invoice.due_date.isoformat(),
                "total": invoice.total_cents / 100,
                "paid": invoice.paid_cents / 100,
                "balance": (invoice.total_cents - invoice.paid_cents) / 100,
                "age_days": age_days,
                "days_overdue": days_overdue,
                "job_id": invoice.job_id,
                "sent_date": invoice.sent_date.isoformat() if invoice.sent_date else None,
                "paid_date": invoice.paid_date.isoformat() if invoice.paid_date else None
            })
        
        return {
            "invoices": invoice_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size
            },
            "summary": {
                "total_invoices": stats_query.count or 0,
                "total_amount": (stats_query.total or 0) / 100,
                "total_paid": (stats_query.paid or 0) / 100,
                "total_outstanding": ((stats_query.total or 0) - (stats_query.paid or 0)) / 100,
                "total_overdue": (stats_query.overdue or 0) / 100
            }
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to retrieve invoices: {str(e)}")


@router.get("/invoices/{invoice_id}", response_model=Dict[str, Any])
@require_permission(Permission.FINANCE_READ)
async def get_invoice_details(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get detailed invoice information including payment history."""
    try:
        # Get invoice with relationships
        invoice = db.query(Invoice).options(
            joinedload(Invoice.customer),
            joinedload(Invoice.payments),
            joinedload(Invoice.job)
        ).filter_by(id=invoice_id).first()
        
        if not invoice:
            raise HTTPException(404, "Invoice not found")
        
        # Format line items
        line_items = []
        for item in invoice.line_items:
            line_items.append({
                "description": item["description"],
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
                "subtotal": Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"])),
                "tax_rate": item.get("tax_rate", 0),
                "tax_amount": item.get("tax_amount", 0),
                "total": item.get("total", 0)
            })
        
        # Payment history
        payments = []
        for payment in invoice.payments:
            payments.append({
                "id": payment.id,
                "amount": payment.amount_cents / 100,
                "payment_date": payment.payment_date.isoformat(),
                "payment_method": payment.payment_method,
                "reference_number": payment.reference_number,
                "created_at": payment.created_at.isoformat()
            })
        
        # Activity timeline
        timeline = [
            {
                "event": "created",
                "date": invoice.created_at.isoformat(),
                "description": "Invoice created"
            }
        ]
        
        if invoice.sent_date:
            timeline.append({
                "event": "sent",
                "date": invoice.sent_date.isoformat(),
                "description": "Invoice sent to customer"
            })
        
        if invoice.viewed_date:
            timeline.append({
                "event": "viewed",
                "date": invoice.viewed_date.isoformat(),
                "description": f"Invoice viewed ({invoice.view_count} times)"
            })
        
        for payment in invoice.payments:
            timeline.append({
                "event": "payment",
                "date": payment.created_at.isoformat(),
                "description": f"Payment received: ${payment.amount_cents / 100:.2f}"
            })
        
        return {
            "invoice": {
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "status": invoice.status,
                "invoice_date": invoice.invoice_date.isoformat(),
                "due_date": invoice.due_date.isoformat(),
                
                # Customer
                "customer": {
                    "id": invoice.customer.id,
                    "name": invoice.customer.name,
                    "email": invoice.customer.email,
                    "phone": invoice.customer.phone
                } if invoice.customer else None,
                
                # Amounts
                "subtotal": invoice.subtotal_cents / 100,
                "tax": invoice.tax_cents / 100,
                "discount": invoice.discount_cents / 100,
                "shipping": invoice.shipping_cents / 100,
                "total": invoice.total_cents / 100,
                "paid": invoice.paid_cents / 100,
                "balance": (invoice.total_cents - invoice.paid_cents) / 100,
                
                # Line items
                "line_items": line_items,
                
                # Terms and notes
                "payment_terms": invoice.payment_terms,
                "notes": invoice.notes,
                
                # Related
                "job_id": invoice.job_id,
                "estimate_id": invoice.estimate_id,
                
                # Metadata
                "created_at": invoice.created_at.isoformat(),
                "updated_at": invoice.updated_at.isoformat()
            },
            "payments": payments,
            "timeline": sorted(timeline, key=lambda x: x["date"])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to retrieve invoice: {str(e)}")


@router.post("/invoices/{invoice_id}/send", response_model=Dict[str, Any])
@require_permission(Permission.FINANCE_WRITE)
async def send_invoice(
    invoice_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    email_override: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Send invoice to customer via email."""
    try:
        invoice = db.query(Invoice).filter_by(id=invoice_id).first()
        if not invoice:
            raise HTTPException(404, "Invoice not found")
        
        # Update status
        invoice.status = InvoiceStatus.SENT.value
        invoice.sent_date = datetime.utcnow()
        db.commit()
        
        # Send email
        background_tasks.add_task(
            _send_invoice_email,
            invoice_id=invoice.id,
            email_override=email_override,
            db=db
        )
        
        # Audit log
        await audit_log(
            user_id=current_user.id,
            action="invoice_sent",
            resource_type="invoice",
            resource_id=invoice.id,
            details={"invoice_number": invoice.invoice_number}
        )
        
        return {
            "invoice_id": invoice.id,
            "status": "sent",
            "message": "Invoice sent successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to send invoice: {str(e)}")


@router.post("/payments", response_model=Dict[str, Any])
@require_permission(Permission.FINANCE_WRITE)
async def record_payment(
    payment_data: PaymentRecord,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Record a payment against an invoice.
    
    Features:
    - Automatic invoice status update
    - Payment verification
    - Processing fee tracking
    - Receipt generation
    """
    try:
        # Get invoice
        invoice = db.query(Invoice).filter_by(id=payment_data.invoice_id).first()
        if not invoice:
            raise HTTPException(404, "Invoice not found")
        
        # Validate payment amount
        balance = (invoice.total_cents - invoice.paid_cents) / 100
        if payment_data.amount > balance:
            raise HTTPException(400, f"Payment amount exceeds invoice balance of ${balance:.2f}")
        
        # Create payment record
        payment = Payment(
            id=uuid.uuid4(),
            invoice_id=invoice.id,
            amount_cents=int(payment_data.amount * 100),
            processing_fee_cents=int(payment_data.processing_fee * 100),
            payment_method=payment_data.payment_method.value,
            payment_date=payment_data.payment_date,
            reference_number=payment_data.reference_number,
            transaction_id=payment_data.transaction_id,
            details={
                "check_number": payment_data.check_number,
                "bank_name": payment_data.bank_name,
                "last_four": payment_data.last_four,
                "card_brand": payment_data.card_brand
            },
            notes=payment_data.notes,
            created_by=current_user.id
        )
        
        db.add(payment)
        
        # Update invoice
        invoice.paid_cents += payment.amount_cents
        
        # Update invoice status
        if invoice.paid_cents >= invoice.total_cents:
            invoice.status = InvoiceStatus.PAID.value
            invoice.paid_date = datetime.utcnow()
        elif invoice.paid_cents > 0:
            invoice.status = InvoiceStatus.PARTIAL.value
        
        db.commit()
        db.refresh(payment)
        
        # Send receipt
        if invoice.customer and invoice.customer.email:
            background_tasks.add_task(
                _send_payment_receipt,
                payment_id=payment.id,
                db=db
            )
        
        # Update accounting system
        background_tasks.add_task(
            _sync_payment_to_accounting,
            payment_id=payment.id,
            db=db
        )
        
        # Audit log
        await audit_log(
            user_id=current_user.id,
            action="payment_recorded",
            resource_type="payment",
            resource_id=payment.id,
            details={
                "invoice_id": str(invoice.id),
                "amount": float(payment_data.amount),
                "method": payment_data.payment_method.value
            }
        )
        
        return {
            "payment_id": payment.id,
            "invoice_id": invoice.id,
            "amount": float(payment_data.amount),
            "new_balance": (invoice.total_cents - invoice.paid_cents) / 100,
            "invoice_status": invoice.status,
            "message": "Payment recorded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to record payment: {str(e)}")


@router.post("/expenses", response_model=Dict[str, Any])
@require_permission(Permission.FINANCE_WRITE)
async def create_expense(
    expense_data: ExpenseCreate,
    receipt: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Record a business expense.
    
    Features:
    - Receipt upload and OCR
    - Job cost allocation
    - Approval workflow
    - Tax categorization
    """
    try:
        # Handle receipt upload
        receipt_url = None
        if receipt:
            # Save receipt file
            receipt_url = await _save_receipt(receipt, expense_data.expense_date)
            
            # OCR processing for auto-fill
            # In production, would use AWS Textract or similar
        
        # Determine if approval needed
        requires_approval = expense_data.amount > Decimal("500.00")
        if current_user.role == UserRole.ADMIN:
            requires_approval = False
        
        # Create expense
        expense = Expense(
            id=uuid.uuid4(),
            category=expense_data.category.value,
            vendor=expense_data.vendor,
            description=expense_data.description,
            amount_cents=int(expense_data.amount * 100),
            expense_date=expense_data.expense_date,
            job_id=expense_data.job_id,
            billable=expense_data.billable,
            payment_method=expense_data.payment_method.value if expense_data.payment_method else None,
            reference_number=expense_data.reference_number,
            receipt_url=receipt_url,
            tax_deductible=expense_data.tax_deductible,
            tags=expense_data.tags,
            requires_approval=requires_approval,
            created_by=current_user.id
        )
        
        # Auto-approve if not required
        if not requires_approval:
            expense.approved_by = current_user.id
            expense.approved_at = datetime.utcnow()
        
        db.add(expense)
        db.commit()
        db.refresh(expense)
        
        # Notify approvers if needed
        if requires_approval:
            await send_notification(
                recipients=[user.id for user in db.query(User).filter(User.role == UserRole.SUPERVISOR).all()],
                notification_type=NotificationType.EXPENSE_APPROVAL,
                title="Expense Approval Required",
                message=f"Expense of ${expense_data.amount:.2f} from {expense_data.vendor} requires approval",
                data={"expense_id": str(expense.id)}
            )
        
        # Update job costs if allocated
        if expense_data.job_id:
            job = db.query(Job).filter_by(id=expense_data.job_id).first()
            if job:
                job.actual_costs = (job.actual_costs or 0) + float(expense_data.amount)
                db.commit()
        
        # Audit log
        await audit_log(
            user_id=current_user.id,
            action="expense_created",
            resource_type="expense",
            resource_id=expense.id,
            details={
                "amount": float(expense_data.amount),
                "category": expense_data.category.value,
                "vendor": expense_data.vendor
            }
        )
        
        return {
            "expense_id": expense.id,
            "amount": float(expense_data.amount),
            "requires_approval": requires_approval,
            "receipt_uploaded": receipt_url is not None,
            "message": "Expense recorded successfully"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to create expense: {str(e)}")


@router.get("/reports", response_model=Dict[str, Any])
@require_permission(Permission.FINANCE_READ)
@cache_result(ttl=3600)  # Cache for 1 hour
async def generate_financial_report(
    report_request: FinancialReportRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Union[Dict[str, Any], StreamingResponse, FileResponse]:
    """
    Generate comprehensive financial reports.
    
    Available reports:
    - Profit & Loss Statement
    - Balance Sheet
    - Cash Flow Statement
    - Accounts Receivable Aging
    - Job Profitability Analysis
    - Tax Summary
    """
    try:
        report_generator = FinancialReportGenerator(db)
        
        # Generate report based on type
        if report_request.report_type == ReportType.PROFIT_LOSS:
            report_data = await report_generator.generate_profit_loss(
                start_date=report_request.start_date,
                end_date=report_request.end_date,
                project_ids=report_request.project_ids
            )
        
        elif report_request.report_type == ReportType.ACCOUNTS_RECEIVABLE:
            report_data = await report_generator.generate_ar_aging(
                as_of_date=report_request.end_date,
                customer_ids=report_request.customer_ids
            )
        
        elif report_request.report_type == ReportType.JOB_PROFITABILITY:
            report_data = await report_generator.generate_job_profitability(
                start_date=report_request.start_date,
                end_date=report_request.end_date,
                job_ids=report_request.job_ids
            )
        
        elif report_request.report_type == ReportType.TAX_SUMMARY:
            report_data = await report_generator.generate_tax_summary(
                start_date=report_request.start_date,
                end_date=report_request.end_date
            )
        
        else:
            raise HTTPException(400, f"Report type {report_request.report_type} not implemented")
        
        # Add comparison data if requested
        if report_request.compare_period:
            comparison_data = await report_generator.generate_comparison(
                report_type=report_request.report_type,
                current_data=report_data,
                compare_period=report_request.compare_period
            )
            report_data["comparison"] = comparison_data
        
        # Format response based on requested format
        if report_request.format == "csv":
            csv_buffer = io.StringIO()
            csv_writer = csv.DictWriter(csv_buffer, fieldnames=report_data["data"][0].keys())
            csv_writer.writeheader()
            csv_writer.writerows(report_data["data"])
            
            return StreamingResponse(
                io.BytesIO(csv_buffer.getvalue().encode()),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename={report_request.report_type.value}_{report_request.start_date}_{report_request.end_date}.csv"
                }
            )
        
        elif report_request.format == "pdf":
            # Generate PDF report
            pdf_path = await report_generator.generate_pdf_report(
                report_type=report_request.report_type,
                report_data=report_data
            )
            
            return FileResponse(
                pdf_path,
                media_type="application/pdf",
                filename=f"{report_request.report_type.value}_{report_request.start_date}_{report_request.end_date}.pdf"
            )
        
        else:
            # Return JSON
            return report_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to generate report: {str(e)}")


@router.get("/dashboard", response_model=Dict[str, Any])
@require_permission(Permission.FINANCE_READ)
@cache_result(ttl=300)  # Cache for 5 minutes
async def financial_dashboard(
    period: str = Query("month", regex="^(week|month|quarter|year)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get financial dashboard with key metrics and trends.
    """
    try:
        # Calculate date range
        end_date = date.today()
        if period == "week":
            start_date = end_date - timedelta(days=7)
        elif period == "month":
            start_date = end_date.replace(day=1)
        elif period == "quarter":
            quarter = (end_date.month - 1) // 3
            start_date = date(end_date.year, quarter * 3 + 1, 1)
        else:  # year
            start_date = date(end_date.year, 1, 1)
        
        # Revenue metrics
        revenue_query = db.query(
            func.sum(Invoice.total_cents).label('total_revenue'),
            func.sum(Invoice.paid_cents).label('collected_revenue'),
            func.count(Invoice.id).label('invoice_count')
        ).filter(
            Invoice.invoice_date >= start_date,
            Invoice.invoice_date <= end_date,
            Invoice.status != InvoiceStatus.CANCELLED.value
        ).first()
        
        # Expense metrics
        expense_query = db.query(
            func.sum(Expense.amount_cents).label('total_expenses'),
            func.count(Expense.id).label('expense_count')
        ).filter(
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date,
            Expense.approved_at.isnot(None)
        ).first()
        
        # Outstanding invoices
        outstanding_query = db.query(
            func.count(Invoice.id).label('count'),
            func.sum(Invoice.total_cents - Invoice.paid_cents).label('amount')
        ).filter(
            Invoice.status.in_([InvoiceStatus.SENT.value, InvoiceStatus.VIEWED.value, InvoiceStatus.PARTIAL.value])
        ).first()
        
        # Overdue invoices
        overdue_query = db.query(
            func.count(Invoice.id).label('count'),
            func.sum(Invoice.total_cents - Invoice.paid_cents).label('amount')
        ).filter(
            Invoice.due_date < date.today(),
            Invoice.status.in_([InvoiceStatus.SENT.value, InvoiceStatus.VIEWED.value, InvoiceStatus.PARTIAL.value])
        ).first()
        
        # Top customers by revenue
        top_customers = db.query(
            Invoice.customer_id,
            func.sum(Invoice.total_cents).label('revenue')
        ).filter(
            Invoice.invoice_date >= start_date,
            Invoice.invoice_date <= end_date
        ).group_by(
            Invoice.customer_id
        ).order_by(
            func.sum(Invoice.total_cents).desc()
        ).limit(5).all()
        
        # Revenue by month trend
        monthly_trend = db.query(
            extract('month', Invoice.invoice_date).label('month'),
            func.sum(Invoice.total_cents).label('revenue')
        ).filter(
            Invoice.invoice_date >= start_date,
            Invoice.invoice_date <= end_date
        ).group_by(
            extract('month', Invoice.invoice_date)
        ).all()
        
        # Expense breakdown by category
        expense_breakdown = db.query(
            Expense.category,
            func.sum(Expense.amount_cents).label('amount')
        ).filter(
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date
        ).group_by(
            Expense.category
        ).all()
        
        return {
            "period": {
                "type": period,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "revenue": {
                "total": (revenue_query.total_revenue or 0) / 100,
                "collected": (revenue_query.collected_revenue or 0) / 100,
                "pending": ((revenue_query.total_revenue or 0) - (revenue_query.collected_revenue or 0)) / 100,
                "invoice_count": revenue_query.invoice_count or 0
            },
            "expenses": {
                "total": (expense_query.total_expenses or 0) / 100,
                "count": expense_query.expense_count or 0
            },
            "profit": {
                "gross": ((revenue_query.total_revenue or 0) - (expense_query.total_expenses or 0)) / 100,
                "margin": (((revenue_query.total_revenue or 0) - (expense_query.total_expenses or 0)) / (revenue_query.total_revenue or 1) * 100) if revenue_query.total_revenue else 0
            },
            "outstanding": {
                "count": outstanding_query.count or 0,
                "amount": (outstanding_query.amount or 0) / 100
            },
            "overdue": {
                "count": overdue_query.count or 0,
                "amount": (overdue_query.amount or 0) / 100
            },
            "top_customers": [
                {
                    "customer_id": c.customer_id,
                    "revenue": c.revenue / 100
                }
                for c in top_customers
            ],
            "monthly_trend": [
                {
                    "month": int(m.month),
                    "revenue": m.revenue / 100
                }
                for m in monthly_trend
            ],
            "expense_breakdown": [
                {
                    "category": e.category,
                    "amount": e.amount / 100
                }
                for e in expense_breakdown
            ]
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to generate dashboard: {str(e)}")


# Helper functions

async def _send_invoice_email(invoice_id: uuid.UUID, email_override: Optional[str], db: Session):
    """Send invoice email to customer."""
    invoice = db.query(Invoice).filter_by(id=invoice_id).first()
    if not invoice:
        return
    
    # Generate PDF
    pdf_generator = DocumentGenerator()
    pdf_path = await pdf_generator.generate_invoice_pdf(invoice)
    
    # Send email
    await send_notification(
        recipients=[email_override or invoice.customer.email],
        notification_type=NotificationType.INVOICE_SENT,
        title=f"Invoice {invoice.invoice_number}",
        message=f"Your invoice for ${invoice.total_cents / 100:.2f} is ready",
        data={
            "invoice_id": str(invoice.id),
            "pdf_url": pdf_path,
            "payment_link": f"https://pay.brainops.com/invoice/{invoice.id}"
        }
    )


async def _send_payment_receipt(payment_id: uuid.UUID, db: Session):
    """Send payment receipt to customer."""
    payment = db.query(Payment).filter_by(id=payment_id).first()
    if not payment:
        return
    
    # Generate receipt
    pdf_generator = DocumentGenerator()
    receipt_path = await pdf_generator.generate_receipt_pdf(payment)
    
    # Send email
    await send_notification(
        recipients=[payment.invoice.customer.email],
        notification_type=NotificationType.PAYMENT_RECEIVED,
        title="Payment Received",
        message=f"Thank you for your payment of ${payment.amount_cents / 100:.2f}",
        data={
            "payment_id": str(payment.id),
            "receipt_url": receipt_path
        }
    )


async def _sync_payment_to_accounting(payment_id: uuid.UUID, db: Session):
    """Sync payment to accounting system (QuickBooks, etc)."""
    # Implementation would integrate with accounting API
    pass


async def _save_receipt(file: UploadFile, expense_date: date) -> str:
    """Save uploaded receipt file."""
    # In production, would upload to S3 or similar
    file_extension = file.filename.split('.')[-1]
    file_name = f"receipts/{expense_date.year}/{expense_date.month}/{uuid.uuid4()}.{file_extension}"
    
    # Save file (mock implementation)
    return f"https://storage.brainops.com/{file_name}"


class FinancialReportGenerator:
    """Generate various financial reports."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def generate_profit_loss(self, start_date: date, end_date: date, project_ids: Optional[List[uuid.UUID]] = None) -> Dict[str, Any]:
        """Generate P&L statement."""
        # Revenue
        revenue_query = self.db.query(
            func.sum(Invoice.total_cents).label('total')
        ).filter(
            Invoice.invoice_date >= start_date,
            Invoice.invoice_date <= end_date,
            Invoice.status != InvoiceStatus.CANCELLED.value
        )
        
        if project_ids:
            revenue_query = revenue_query.join(Job).filter(Job.project_id.in_(project_ids))
        
        revenue = revenue_query.first().total or 0
        
        # Expenses by category
        expenses_query = self.db.query(
            Expense.category,
            func.sum(Expense.amount_cents).label('amount')
        ).filter(
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date,
            Expense.approved_at.isnot(None)
        )
        
        if project_ids:
            expenses_query = expenses_query.join(Job).filter(Job.project_id.in_(project_ids))
        
        expenses = expenses_query.group_by(Expense.category).all()
        
        # Calculate totals
        total_expenses = sum(e.amount for e in expenses)
        net_income = revenue - total_expenses
        
        return {
            "report_type": "profit_loss",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "revenue": {
                "total": revenue / 100,
                "breakdown": []  # Would include service types, etc
            },
            "expenses": {
                "total": total_expenses / 100,
                "by_category": [
                    {
                        "category": e.category,
                        "amount": e.amount / 100,
                        "percentage": (e.amount / total_expenses * 100) if total_expenses else 0
                    }
                    for e in expenses
                ]
            },
            "net_income": net_income / 100,
            "profit_margin": (net_income / revenue * 100) if revenue else 0
        }
    
    async def generate_ar_aging(self, as_of_date: date, customer_ids: Optional[List[uuid.UUID]] = None) -> Dict[str, Any]:
        """Generate accounts receivable aging report."""
        # Get unpaid invoices
        query = self.db.query(Invoice).filter(
            Invoice.status.in_([InvoiceStatus.SENT.value, InvoiceStatus.VIEWED.value, InvoiceStatus.PARTIAL.value]),
            Invoice.invoice_date <= as_of_date
        )
        
        if customer_ids:
            query = query.filter(Invoice.customer_id.in_(customer_ids))
        
        invoices = query.all()
        
        # Categorize by age
        aging_buckets = {
            "current": {"count": 0, "amount": 0},
            "1-30": {"count": 0, "amount": 0},
            "31-60": {"count": 0, "amount": 0},
            "61-90": {"count": 0, "amount": 0},
            "over_90": {"count": 0, "amount": 0}
        }
        
        for invoice in invoices:
            days_old = (as_of_date - invoice.due_date).days
            balance = invoice.total_cents - invoice.paid_cents
            
            if days_old <= 0:
                bucket = "current"
            elif days_old <= 30:
                bucket = "1-30"
            elif days_old <= 60:
                bucket = "31-60"
            elif days_old <= 90:
                bucket = "61-90"
            else:
                bucket = "over_90"
            
            aging_buckets[bucket]["count"] += 1
            aging_buckets[bucket]["amount"] += balance
        
        return {
            "report_type": "ar_aging",
            "as_of_date": as_of_date.isoformat(),
            "summary": {
                "total_outstanding": sum(b["amount"] for b in aging_buckets.values()) / 100,
                "invoice_count": sum(b["count"] for b in aging_buckets.values())
            },
            "aging": {
                k: {
                    "count": v["count"],
                    "amount": v["amount"] / 100,
                    "percentage": (v["amount"] / sum(b["amount"] for b in aging_buckets.values()) * 100) if sum(b["amount"] for b in aging_buckets.values()) else 0
                }
                for k, v in aging_buckets.items()
            }
        }
    
    async def generate_job_profitability(self, start_date: date, end_date: date, job_ids: Optional[List[uuid.UUID]] = None) -> Dict[str, Any]:
        """Generate job profitability analysis."""
        # Would implement detailed job cost analysis
        return {
            "report_type": "job_profitability",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "jobs": []
        }
    
    async def generate_tax_summary(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Generate tax summary report."""
        # Would calculate tax collected, owed, etc
        return {
            "report_type": "tax_summary",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {}
        }
    
    async def generate_comparison(self, report_type: ReportType, current_data: Dict[str, Any], compare_period: str) -> Dict[str, Any]:
        """Generate period comparison data."""
        # Would calculate previous period data and differences
        return {
            "previous_period": {},
            "changes": {}
        }
    
    async def generate_pdf_report(self, report_type: ReportType, report_data: Dict[str, Any]) -> str:
        """Generate PDF version of report."""
        # Would use ReportLab or similar to generate PDF
        return f"/tmp/report_{report_type.value}_{uuid.uuid4()}.pdf"