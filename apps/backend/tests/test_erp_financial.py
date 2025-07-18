"""
Comprehensive tests for ERP Financial module.
Tests invoice management, payment processing, expense tracking,
and accounting integrations.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ..main import app
from ..db.models import User
from ..db.financial_models import (
    Customer, Invoice, Payment, Expense, 
    Estimate, Job, Vendor
)
from ..core.rbac import Permission, Role


client = TestClient(app)


class TestFinancialModule:
    """Test suite for financial module endpoints."""
    
    @pytest.fixture
    def auth_headers(self, test_user):
        """Get auth headers for test user."""
        return {"Authorization": f"Bearer {test_user.token}"}
    
    @pytest.fixture
    def admin_headers(self, admin_user):
        """Get auth headers for admin user."""
        return {"Authorization": f"Bearer {admin_user.token}"}
    
    @pytest.fixture
    def test_customer(self, db: Session):
        """Create test customer."""
        customer = Customer(
            name="Test Corp",
            email="billing@testcorp.com",
            phone="555-0123",
            billing_address="123 Test St",
            billing_city="Test City",
            billing_state="CA",
            billing_zip="90210",
            payment_terms="Net 30",
            credit_limit=1000000  # $10,000 in cents
        )
        db.add(customer)
        db.commit()
        return customer
    
    @pytest.fixture
    def test_invoice(self, db: Session, test_customer, test_user):
        """Create test invoice."""
        invoice = Invoice(
            invoice_number="INV-2024-001",
            customer_id=test_customer.id,
            title="January Services",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal_cents=100000,
            tax_cents=7500,
            total_cents=107500,
            balance_cents=107500,
            line_items=[
                {
                    "description": "Consulting Services",
                    "quantity": 10,
                    "rate": 10000,
                    "amount": 100000
                }
            ],
            status="sent",
            created_by=test_user.id
        )
        db.add(invoice)
        db.commit()
        return invoice


class TestInvoiceEndpoints(TestFinancialModule):
    """Test invoice management endpoints."""
    
    def test_create_invoice(self, admin_headers, test_customer):
        """Test creating new invoice."""
        invoice_data = {
            "customer_id": str(test_customer.id),
            "title": "February Services",
            "description": "Monthly consulting services",
            "invoice_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=30)),
            "line_items": [
                {
                    "description": "Backend Development",
                    "quantity": 20,
                    "rate": 15000,
                    "amount": 300000
                },
                {
                    "description": "Frontend Development",
                    "quantity": 15,
                    "rate": 12000,
                    "amount": 180000
                }
            ],
            "tax_rate": 0.075,
            "discount_percentage": 5,
            "notes": "Thank you for your business"
        }
        
        response = client.post(
            "/api/v1/erp/invoices",
            json=invoice_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["invoice"]["title"] == "February Services"
        assert data["invoice"]["subtotal_cents"] == 480000
        assert data["invoice"]["discount_cents"] == 24000  # 5% discount
        assert data["invoice"]["tax_cents"] == 34200  # 7.5% on discounted amount
        assert data["invoice"]["total_cents"] == 490200
        assert data["invoice"]["status"] == "draft"
    
    def test_get_invoice(self, auth_headers, test_invoice):
        """Test getting invoice details."""
        response = client.get(
            f"/api/v1/erp/invoices/{test_invoice.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["invoice"]["invoice_number"] == "INV-2024-001"
        assert data["invoice"]["total_cents"] == 107500
    
    def test_list_invoices_with_filters(self, auth_headers, test_invoice):
        """Test listing invoices with filters."""
        response = client.get(
            "/api/v1/erp/invoices?status=sent&customer_id=" + str(test_invoice.customer_id),
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["invoices"]) >= 1
        assert data["invoices"][0]["status"] == "sent"
    
    def test_update_invoice_status(self, admin_headers, test_invoice):
        """Test updating invoice status."""
        response = client.put(
            f"/api/v1/erp/invoices/{test_invoice.id}",
            json={"status": "paid"},
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["invoice"]["status"] == "paid"
        assert data["invoice"]["paid_date"] is not None
    
    def test_send_invoice(self, admin_headers, test_invoice):
        """Test sending invoice to customer."""
        with patch('apps.backend.services.email_service.send_invoice_email') as mock_send:
            mock_send.return_value = True
            
            response = client.post(
                f"/api/v1/erp/invoices/{test_invoice.id}/send",
                headers=admin_headers
            )
            
            assert response.status_code == 200
            assert mock_send.called
    
    def test_void_invoice(self, admin_headers, test_invoice):
        """Test voiding invoice."""
        response = client.post(
            f"/api/v1/erp/invoices/{test_invoice.id}/void",
            json={"reason": "Duplicate invoice"},
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["invoice"]["status"] == "void"
        assert data["invoice"]["void_reason"] == "Duplicate invoice"
    
    def test_invoice_summary_stats(self, auth_headers):
        """Test getting invoice summary statistics."""
        response = client.get(
            "/api/v1/erp/invoices/summary",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_outstanding" in data
        assert "total_overdue" in data
        assert "by_status" in data


class TestPaymentEndpoints(TestFinancialModule):
    """Test payment processing endpoints."""
    
    def test_record_payment(self, admin_headers, test_invoice):
        """Test recording payment for invoice."""
        payment_data = {
            "invoice_id": str(test_invoice.id),
            "amount": 500.00,
            "payment_date": str(date.today()),
            "payment_method": "check",
            "reference_number": "CHK-12345",
            "notes": "Partial payment"
        }
        
        response = client.post(
            "/api/v1/erp/payments",
            json=payment_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["payment"]["amount_cents"] == 50000
        assert data["payment"]["payment_method"] == "check"
        assert data["invoice"]["balance_cents"] == 57500  # Original 107500 - 50000
    
    def test_process_stripe_payment(self, admin_headers, test_invoice):
        """Test processing payment through Stripe."""
        with patch('apps.backend.integrations.stripe.StripeService.charge_card') as mock_charge:
            mock_charge.return_value = {
                "id": "ch_test_123",
                "status": "succeeded"
            }
            
            payment_data = {
                "invoice_id": str(test_invoice.id),
                "amount": 1075.00,
                "payment_method_id": "pm_test_123"
            }
            
            response = client.post(
                "/api/v1/erp/payments/stripe",
                json=payment_data,
                headers=admin_headers
            )
            
            assert response.status_code == 200
            assert mock_charge.called
    
    def test_refund_payment(self, admin_headers, test_invoice, db: Session):
        """Test refunding a payment."""
        # First create a payment
        payment = Payment(
            payment_number="PMT-2024-001",
            invoice_id=test_invoice.id,
            customer_id=test_invoice.customer_id,
            payment_date=date.today(),
            amount_cents=50000,
            payment_method="card",
            status="cleared",
            created_by=test_invoice.created_by
        )
        db.add(payment)
        db.commit()
        
        # Now refund it
        response = client.post(
            f"/api/v1/erp/payments/{payment.id}/refund",
            json={
                "amount": 250.00,
                "reason": "Service issue"
            },
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["payment"]["is_refunded"] == True
        assert data["payment"]["refund_amount_cents"] == 25000
    
    def test_list_payments(self, auth_headers, test_customer):
        """Test listing payments with filters."""
        response = client.get(
            f"/api/v1/erp/payments?customer_id={test_customer.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "payments" in data
        assert "total" in data


class TestExpenseEndpoints(TestFinancialModule):
    """Test expense tracking endpoints."""
    
    @pytest.fixture
    def test_vendor(self, db: Session):
        """Create test vendor."""
        vendor = Vendor(
            name="Test Supplies Inc",
            email="orders@testsupplies.com",
            phone="555-9876",
            categories=["materials", "equipment"],
            payment_terms="Net 15"
        )
        db.add(vendor)
        db.commit()
        return vendor
    
    def test_create_expense(self, admin_headers, test_vendor):
        """Test creating new expense."""
        expense_data = {
            "expense_date": str(date.today()),
            "vendor_id": str(test_vendor.id),
            "category": "materials",
            "subcategory": "lumber",
            "description": "2x4 lumber for project",
            "amount": 450.75,
            "tax": 33.81,
            "payment_method": "company_card",
            "is_billable": True,
            "markup_percentage": 15.0,
            "tags": ["construction", "framing"]
        }
        
        response = client.post(
            "/api/v1/erp/expenses",
            json=expense_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["expense"]["amount_cents"] == 45075
        assert data["expense"]["total_cents"] == 48456  # amount + tax
        assert data["expense"]["is_billable"] == True
    
    def test_attach_expense_to_job(self, admin_headers, test_vendor, db: Session):
        """Test attaching expense to job."""
        # Create a job first
        job = Job(
            job_number="JOB-2024-001",
            customer_id=test_vendor.id,  # Using vendor ID as customer for test
            title="Test Project",
            status="in_progress",
            created_by=test_vendor.id  # Dummy user ID
        )
        db.add(job)
        db.commit()
        
        expense_data = {
            "expense_date": str(date.today()),
            "job_id": str(job.id),
            "category": "labor",
            "description": "Contractor hours",
            "amount": 800.00,
            "is_billable": True
        }
        
        response = client.post(
            "/api/v1/erp/expenses",
            json=expense_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["expense"]["job_id"] == str(job.id)
    
    def test_approve_expense(self, admin_headers, db: Session, test_user):
        """Test expense approval workflow."""
        # Create expense requiring approval
        expense = Expense(
            expense_number="EXP-2024-001",
            expense_date=date.today(),
            category="equipment",
            description="Heavy machinery rental",
            amount_cents=500000,  # $5000 - requires approval
            total_cents=500000,
            requires_approval=True,
            created_by=test_user.id
        )
        db.add(expense)
        db.commit()
        
        response = client.post(
            f"/api/v1/erp/expenses/{expense.id}/approve",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["expense"]["approved"] == True
        assert data["expense"]["approved_by"] is not None
    
    def test_expense_reimbursement(self, admin_headers, test_user):
        """Test employee expense reimbursement."""
        expense_data = {
            "expense_date": str(date.today()),
            "category": "travel",
            "subcategory": "mileage",
            "description": "Client site visit - 45 miles",
            "amount": 25.88,
            "is_reimbursable": True,
            "employee_id": str(test_user.id),
            "receipt_url": "https://receipts.example.com/123"
        }
        
        response = client.post(
            "/api/v1/erp/expenses",
            json=expense_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["expense"]["is_reimbursable"] == True
        assert data["expense"]["employee_id"] == str(test_user.id)
    
    def test_expense_report_generation(self, auth_headers):
        """Test generating expense reports."""
        response = client.get(
            "/api/v1/erp/expenses/report?start_date=2024-01-01&end_date=2024-12-31",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_expenses" in data
        assert "by_category" in data
        assert "by_vendor" in data
        assert "billable_vs_non_billable" in data


class TestAccountingIntegrations(TestFinancialModule):
    """Test accounting software integrations."""
    
    def test_quickbooks_sync(self, admin_headers, test_invoice):
        """Test syncing with QuickBooks."""
        with patch('apps.backend.integrations.quickbooks.QuickBooksService.sync_invoice') as mock_sync:
            mock_sync.return_value = {
                "qb_invoice_id": "QB-INV-123",
                "sync_status": "success"
            }
            
            response = client.post(
                f"/api/v1/erp/accounting/quickbooks/sync/invoice/{test_invoice.id}",
                headers=admin_headers
            )
            
            assert response.status_code == 200
            assert mock_sync.called
    
    def test_tax_calculation(self, auth_headers):
        """Test tax calculation service."""
        tax_data = {
            "amount": 1000.00,
            "from_address": {
                "state": "CA",
                "zip": "90210"
            },
            "to_address": {
                "state": "TX",
                "zip": "75001"
            }
        }
        
        response = client.post(
            "/api/v1/erp/tax/calculate",
            json=tax_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "tax_amount" in data
        assert "tax_rate" in data
    
    def test_financial_reports(self, auth_headers):
        """Test financial report generation."""
        response = client.get(
            "/api/v1/erp/reports/profit-loss?start_date=2024-01-01&end_date=2024-03-31",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "revenue" in data
        assert "expenses" in data
        assert "net_income" in data


class TestCustomerManagement(TestFinancialModule):
    """Test customer management endpoints."""
    
    def test_create_customer(self, admin_headers):
        """Test creating new customer."""
        customer_data = {
            "name": "New Customer LLC",
            "email": "contact@newcustomer.com",
            "phone": "555-5555",
            "company_name": "New Customer LLC",
            "billing_address": "456 New St",
            "billing_city": "New City",
            "billing_state": "NY",
            "billing_zip": "10001",
            "payment_terms": "Net 15",
            "credit_limit": 5000.00,
            "tax_exempt": False,
            "tags": ["commercial", "priority"]
        }
        
        response = client.post(
            "/api/v1/erp/customers",
            json=customer_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["customer"]["name"] == "New Customer LLC"
        assert data["customer"]["credit_limit"] == 500000  # In cents
    
    def test_update_customer_credit(self, admin_headers, test_customer):
        """Test updating customer credit limit."""
        response = client.put(
            f"/api/v1/erp/customers/{test_customer.id}",
            json={"credit_limit": 20000.00},
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["customer"]["credit_limit"] == 2000000
    
    def test_customer_statement(self, auth_headers, test_customer):
        """Test generating customer statement."""
        response = client.get(
            f"/api/v1/erp/customers/{test_customer.id}/statement",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "customer" in data
        assert "invoices" in data
        assert "total_outstanding" in data
        assert "statement_date" in data


class TestFinancialWorkflows(TestFinancialModule):
    """Test complex financial workflows."""
    
    def test_estimate_to_invoice_conversion(self, admin_headers, test_customer, db: Session):
        """Test converting estimate to invoice."""
        # Create estimate
        estimate = Estimate(
            estimate_number="EST-2024-001",
            customer_id=test_customer.id,
            title="Project Estimate",
            estimate_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            subtotal_cents=200000,
            tax_cents=15000,
            total_cents=215000,
            line_items=[
                {
                    "description": "Design Services",
                    "quantity": 40,
                    "rate": 5000,
                    "amount": 200000
                }
            ],
            status="accepted",
            accepted_date=datetime.utcnow(),
            created_by=test_customer.id  # Dummy user ID
        )
        db.add(estimate)
        db.commit()
        
        response = client.post(
            f"/api/v1/erp/estimates/{estimate.id}/convert-to-invoice",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["invoice"]["estimate_id"] == str(estimate.id)
        assert data["invoice"]["total_cents"] == estimate.total_cents
    
    def test_recurring_invoice_generation(self, admin_headers, test_customer):
        """Test creating recurring invoices."""
        recurring_data = {
            "customer_id": str(test_customer.id),
            "template": {
                "title": "Monthly Maintenance",
                "line_items": [
                    {
                        "description": "System Maintenance",
                        "quantity": 1,
                        "rate": 150000,
                        "amount": 150000
                    }
                ]
            },
            "frequency": "monthly",
            "start_date": str(date.today()),
            "occurrences": 12
        }
        
        response = client.post(
            "/api/v1/erp/invoices/recurring",
            json=recurring_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["recurring_schedule"]["frequency"] == "monthly"
        assert data["recurring_schedule"]["occurrences"] == 12
    
    def test_bulk_payment_processing(self, admin_headers, test_customer, db: Session):
        """Test processing multiple payments at once."""
        # Create multiple invoices
        invoice_ids = []
        for i in range(3):
            invoice = Invoice(
                invoice_number=f"INV-BULK-{i+1}",
                customer_id=test_customer.id,
                title=f"Service {i+1}",
                invoice_date=date.today(),
                due_date=date.today() + timedelta(days=30),
                subtotal_cents=100000,
                total_cents=100000,
                balance_cents=100000,
                line_items=[{"description": "Service", "amount": 100000}],
                created_by=test_customer.id
            )
            db.add(invoice)
            db.commit()
            invoice_ids.append(str(invoice.id))
        
        bulk_payment_data = {
            "payment_date": str(date.today()),
            "payment_method": "ach",
            "payments": [
                {"invoice_id": invoice_ids[0], "amount": 1000.00},
                {"invoice_id": invoice_ids[1], "amount": 1000.00},
                {"invoice_id": invoice_ids[2], "amount": 500.00}
            ]
        }
        
        response = client.post(
            "/api/v1/erp/payments/bulk",
            json=bulk_payment_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["payments"]) == 3
        assert data["total_processed"] == 250000  # In cents
    
    def test_financial_audit_trail(self, auth_headers, test_invoice):
        """Test financial audit trail tracking."""
        response = client.get(
            f"/api/v1/erp/audit/invoice/{test_invoice.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "audit_events" in data
        assert len(data["audit_events"]) > 0
        assert data["audit_events"][0]["entity_type"] == "invoice"


def test_financial_permissions():
    """Test RBAC permissions for financial operations."""
    # These would be integration tests with actual permission checks
    # Verifying that users without FINANCE_WRITE can't create invoices, etc.
    pass