"""
Financial domain models for invoicing, payments, and accounting.
"""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Text, Integer, ForeignKey, Index, Float, Date
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from .models import Base, User


class Customer(Base):
    """Customer/Client model for billing and CRM."""
    __tablename__ = "customers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic info
    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    company_name = Column(String(200), nullable=True)
    
    # Billing address
    billing_address = Column(Text, nullable=True)
    billing_city = Column(String(100), nullable=True)
    billing_state = Column(String(50), nullable=True)
    billing_zip = Column(String(20), nullable=True)
    billing_country = Column(String(2), default="US")
    
    # Service address (if different)
    service_address = Column(Text, nullable=True)
    service_city = Column(String(100), nullable=True)
    service_state = Column(String(50), nullable=True)
    service_zip = Column(String(20), nullable=True)
    
    # Financial
    credit_limit = Column(Integer, default=0)  # In cents
    payment_terms = Column(String(50), default="Net 30")
    tax_exempt = Column(Boolean, default=False)
    tax_exempt_number = Column(String(100), nullable=True)
    
    # CRM
    source = Column(String(50), nullable=True)  # How they found us
    tags = Column(JSON, default=[])
    notes = Column(Text, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    invoices = relationship("Invoice", back_populates="customer")
    estimates = relationship("Estimate", back_populates="customer")
    jobs = relationship("Job", back_populates="customer")
    opportunities = relationship("Opportunity", back_populates="customer")
    contacts = relationship("Contact", back_populates="customer")
    
    __table_args__ = (
        Index("idx_customer_email", "email"),
        Index("idx_customer_active", "is_active"),
    )


class Estimate(Base):
    """Estimate/Quote model."""
    __tablename__ = "estimates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    estimate_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    
    # Details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Dates
    estimate_date = Column(Date, nullable=False)
    valid_until = Column(Date, nullable=False)
    
    # Amounts (in cents)
    subtotal_cents = Column(Integer, nullable=False)
    tax_cents = Column(Integer, default=0)
    discount_cents = Column(Integer, default=0)
    total_cents = Column(Integer, nullable=False)
    
    # Content
    line_items = Column(JSON, nullable=False)
    terms_conditions = Column(Text, nullable=True)
    
    # Status
    status = Column(String(20), default="draft")  # draft, sent, viewed, accepted, declined, expired
    sent_date = Column(DateTime, nullable=True)
    viewed_date = Column(DateTime, nullable=True)
    accepted_date = Column(DateTime, nullable=True)
    declined_date = Column(DateTime, nullable=True)
    
    # Conversion
    converted_to_invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="estimates")
    
    __table_args__ = (
        Index("idx_estimate_status", "status"),
        Index("idx_estimate_customer", "customer_id"),
    )


class Job(Base):
    """Job/Project model for work tracking."""
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    estimate_id = Column(UUID(as_uuid=True), ForeignKey("estimates.id"), nullable=True)
    
    # Details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Location
    job_address = Column(Text, nullable=True)
    job_city = Column(String(100), nullable=True)
    job_state = Column(String(50), nullable=True)
    job_zip = Column(String(20), nullable=True)
    
    # Scheduling
    scheduled_start = Column(Date, nullable=True)
    scheduled_end = Column(Date, nullable=True)
    actual_start = Column(Date, nullable=True)
    actual_end = Column(Date, nullable=True)
    
    # Financial
    estimated_revenue = Column(Integer, default=0)  # In cents
    actual_revenue = Column(Integer, default=0)
    estimated_costs = Column(Integer, default=0)
    actual_costs = Column(Integer, default=0)
    
    # Status
    status = Column(String(20), default="scheduled")  # scheduled, in_progress, completed, cancelled
    completion_percentage = Column(Integer, default=0)
    
    # Billing
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)
    is_billable = Column(Boolean, default=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="jobs")
    expenses = relationship("Expense", back_populates="job")
    
    __table_args__ = (
        Index("idx_job_status", "status"),
        Index("idx_job_customer", "customer_id"),
        Index("idx_job_dates", "scheduled_start", "scheduled_end"),
    )


class Invoice(Base):
    """Invoice model for billing."""
    __tablename__ = "invoices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    
    # Reference
    estimate_id = Column(UUID(as_uuid=True), ForeignKey("estimates.id"), nullable=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)
    
    # Details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Dates
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    
    # Amounts (in cents)
    subtotal_cents = Column(Integer, nullable=False)
    tax_cents = Column(Integer, default=0)
    discount_cents = Column(Integer, default=0)
    total_cents = Column(Integer, nullable=False)
    amount_paid_cents = Column(Integer, default=0)
    balance_cents = Column(Integer, nullable=False)
    
    # Content
    line_items = Column(JSON, nullable=False)
    tax_details = Column(JSON, nullable=True)
    terms_conditions = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Status
    status = Column(String(20), default="draft")  # draft, sent, viewed, partial, paid, overdue, void
    sent_date = Column(DateTime, nullable=True)
    viewed_date = Column(DateTime, nullable=True)
    paid_date = Column(DateTime, nullable=True)
    void_date = Column(DateTime, nullable=True)
    void_reason = Column(Text, nullable=True)
    
    # Payment
    payment_method = Column(String(50), nullable=True)  # card, check, cash, ach, other
    payment_reference = Column(String(100), nullable=True)
    
    # External references
    stripe_invoice_id = Column(String(100), nullable=True)
    quickbooks_invoice_id = Column(String(100), nullable=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")
    job = relationship("Job", foreign_keys=[job_id])
    estimate = relationship("Estimate", foreign_keys=[estimate_id])
    
    __table_args__ = (
        Index("idx_invoice_status", "status"),
        Index("idx_invoice_customer", "customer_id"),
        Index("idx_invoice_due_date", "due_date"),
        Index("idx_invoice_date", "invoice_date"),
    )


class Payment(Base):
    """Payment model for tracking received payments."""
    __tablename__ = "payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_number = Column(String(50), unique=True, nullable=False, index=True)
    
    # Reference
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    
    # Payment details
    payment_date = Column(Date, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    
    # Method
    payment_method = Column(String(50), nullable=False)  # card, check, cash, ach, other
    reference_number = Column(String(100), nullable=True)  # Check number, transaction ID
    
    # Card details (if applicable)
    card_last_four = Column(String(4), nullable=True)
    card_brand = Column(String(20), nullable=True)
    
    # Bank details (if applicable)
    bank_name = Column(String(100), nullable=True)
    account_last_four = Column(String(4), nullable=True)
    
    # Status
    status = Column(String(20), default="pending")  # pending, cleared, failed, refunded
    cleared_date = Column(Date, nullable=True)
    failed_reason = Column(Text, nullable=True)
    
    # Refund info
    is_refunded = Column(Boolean, default=False)
    refund_amount_cents = Column(Integer, default=0)
    refund_date = Column(Date, nullable=True)
    refund_reason = Column(Text, nullable=True)
    
    # External references
    stripe_payment_id = Column(String(100), nullable=True)
    quickbooks_payment_id = Column(String(100), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="payments")
    customer = relationship("Customer")
    
    __table_args__ = (
        Index("idx_payment_invoice", "invoice_id"),
        Index("idx_payment_customer", "customer_id"),
        Index("idx_payment_date", "payment_date"),
        Index("idx_payment_status", "status"),
    )


class Expense(Base):
    """Expense model for tracking business expenses."""
    __tablename__ = "expenses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expense_number = Column(String(50), unique=True, nullable=False, index=True)
    
    # Reference
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True)
    
    # Details
    expense_date = Column(Date, nullable=False)
    category = Column(String(50), nullable=False)  # materials, labor, equipment, travel, etc
    subcategory = Column(String(50), nullable=True)
    description = Column(Text, nullable=False)
    
    # Amounts
    amount_cents = Column(Integer, nullable=False)
    tax_cents = Column(Integer, default=0)
    total_cents = Column(Integer, nullable=False)
    
    # Payment
    payment_method = Column(String(50), nullable=True)  # card, check, cash, account
    payment_reference = Column(String(100), nullable=True)
    
    # Receipt
    receipt_url = Column(Text, nullable=True)
    receipt_stored = Column(Boolean, default=False)
    
    # Reimbursement
    is_reimbursable = Column(Boolean, default=False)
    reimbursed = Column(Boolean, default=False)
    reimbursement_date = Column(Date, nullable=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Billable
    is_billable = Column(Boolean, default=False)
    markup_percentage = Column(Float, default=0.0)
    billed = Column(Boolean, default=False)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)
    
    # External references
    quickbooks_expense_id = Column(String(100), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    tags = Column(JSON, default=[])
    
    # Approval
    requires_approval = Column(Boolean, default=False)
    approved = Column(Boolean, nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_date = Column(DateTime, nullable=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="expenses")
    employee = relationship("User", foreign_keys=[employee_id])
    created_by_user = relationship("User", foreign_keys=[created_by])
    approved_by_user = relationship("User", foreign_keys=[approved_by])
    
    __table_args__ = (
        Index("idx_expense_date", "expense_date"),
        Index("idx_expense_category", "category"),
        Index("idx_expense_job", "job_id"),
        Index("idx_expense_billable", "is_billable", "billed"),
    )


class Vendor(Base):
    """Vendor model for expense tracking."""
    __tablename__ = "vendors"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic info
    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)
    
    # Address
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    country = Column(String(2), default="US")
    
    # Financial
    tax_id = Column(String(50), nullable=True)
    payment_terms = Column(String(50), default="Net 30")
    account_number = Column(String(100), nullable=True)
    
    # Categories
    categories = Column(JSON, default=[])  # ["materials", "equipment", "services"]
    preferred = Column(Boolean, default=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_vendor_name", "name"),
        Index("idx_vendor_active", "is_active"),
    )