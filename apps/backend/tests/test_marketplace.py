"""
Comprehensive tests for marketplace endpoints.
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
from unittest.mock import patch, AsyncMock
from uuid import uuid4
from decimal import Decimal

from ..main import app
from ..core.database import get_db
from ..core.security import create_access_token
from ..db.business_models import User, UserRole, Product, Purchase, Review

# Using fixtures from conftest.py instead of redefining

# Helper function to create valid Product objects
def create_test_product(seller_id, name, **kwargs):
    """Create a test product with all required fields."""
    return Product(
        id=kwargs.get('id', uuid4()),
        seller_id=seller_id,
        name=name,
        slug=kwargs.get('slug', name.lower().replace(' ', '-')),
        description=kwargs.get('description', f'Description for {name}'),
        category=kwargs.get('category', 'general'),
        product_type=kwargs.get('product_type', 'digital'),
        price=kwargs.get('price', 29.99),
        currency=kwargs.get('currency', 'USD'),
        status=kwargs.get('status', 'approved'),
        tags=kwargs.get('tags', []),
        downloads=kwargs.get('downloads', 0),
        is_published=kwargs.get('is_published', True),
        files=kwargs.get('files', []),
        features=kwargs.get('features', []),
        requirements=kwargs.get('requirements', []),
        view_count=kwargs.get('view_count', 0),
        purchase_count=kwargs.get('purchase_count', 0),
        rating_average=kwargs.get('rating_average', 0.0),
        rating_count=kwargs.get('rating_count', 0)
    )


# Helper function to create valid Purchase objects
def create_test_purchase(buyer_id, product_id, amount, **kwargs):
    """Create a test purchase with all required fields."""
    return Purchase(
        id=kwargs.get('id', uuid4()),
        buyer_id=buyer_id,
        product_id=product_id,
        amount=amount,
        price=amount,  # Set price same as amount
        currency=kwargs.get('currency', 'USD'),
        status=kwargs.get('status', 'completed'),
        transaction_id=kwargs.get('transaction_id'),
        payment_method=kwargs.get('payment_method'),
        payment_id=kwargs.get('payment_id'),
        license_key=kwargs.get('license_key'),
        license_expires_at=kwargs.get('license_expires_at'),
        created_at=kwargs.get('created_at', datetime.utcnow())
    )


@pytest.fixture
def marketplace_user(test_db: Session):
    """Create a test user for marketplace tests."""
    user = User(
        email="marketplace@example.com",
        username="marketuser",
        hashed_password="hashedpassword",
        full_name="Marketplace Test User",
        is_active=True,
        is_verified=True,
        role=UserRole.USER
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_seller(test_db: Session):
    """Create a test seller user."""
    seller = User(
        id=uuid4(),
        email="seller@example.com",
        username="selleruser",
        hashed_password="hashedpassword",
        full_name="Test Seller",
        is_active=True,
        is_verified=True,
        role=UserRole.USER,
        is_seller=True
    )
    test_db.add(seller)
    test_db.commit()
    test_db.refresh(seller)
    return seller


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers."""
    token = create_access_token({"sub": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seller_headers(test_seller):
    """Create seller authentication headers."""
    token = create_access_token({"sub": test_seller.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_item_data():
    """Create sample marketplace item data."""
    return {
        "name": "AI Workflow Template Pack",
        "description": "Professional workflow templates for AI automation",
        "type": "workflow",
        "price": 49.99,
        "tags": ["ai", "automation", "productivity"],
        "features": [
            "10 pre-built workflows",
            "Customizable templates",
            "Documentation included"
        ],
        "requirements": {
            "min_version": "1.0.0",
            "dependencies": ["claude-api", "automation-core"]
        },
        "preview_url": "https://example.com/preview"
    }


class TestProducts:
    """Test marketplace item management."""
    
    def test_create_marketplace_item(self, client, seller_headers, sample_item_data):
        """Test creating a new marketplace item."""
        response = client.post(
            "/api/v1/marketplace/items",
            json=sample_item_data,
            headers=seller_headers
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        assert response.status_code == 200
        item = response.json()
        assert item["name"] == sample_item_data["name"]
        assert item["price"] == sample_item_data["price"]
        assert item["status"] == "pending"  # Needs approval
        assert "id" in item
    
    def test_list_marketplace_items(self, client, auth_headers, test_db, test_seller):
        """Test listing marketplace items."""
        # Create test items
        items = []
        for i in range(3):
            item = Product(
                id=uuid4(),
                seller_id=test_seller.id,
                name=f"Test Item {i}",
                slug=f"test-item-{i}",
                description=f"Description {i}",
                category="test",
                product_type="workflow" if i % 2 == 0 else "template",
                price=Decimal(str(29.99 + i * 10)),
                status="approved",
                tags=["test"],
                downloads=i * 10,
                is_published=True,
                files=[],
                features=[],
                requirements=[]
            )
            items.append(item)
        test_db.add_all(items)
        test_db.commit()
        
        response = client.get(
            "/api/v1/marketplace/items",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3
        # Items should be sorted by some criteria (e.g., popularity)
    
    def test_search_marketplace_items(self, client, auth_headers, test_db, test_seller):
        """Test searching marketplace items."""
        # Create items with different attributes
        item1 = create_test_product(
            test_seller.id,
            "AI Assistant Template",
            description="Build your own AI assistant",
            product_type="template",
            price=Decimal("39.99"),
            tags=["ai", "assistant", "chatbot"]
        )
        item2 = create_test_product(
            test_seller.id,
            "Data Processing Workflow",
            description="Automate data processing tasks",
            product_type="workflow",
            price=Decimal("59.99"),
            tags=["data", "automation", "etl"]
        )
        test_db.add_all([item1, item2])
        test_db.commit()
        
        # Search by query
        response = client.get(
            "/api/v1/marketplace/items?search=AI&product_type=template",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        results = response.json()
        assert len(results) >= 1
        assert any("AI" in item["name"] for item in results)
    
    def test_get_marketplace_item(self, client, auth_headers, test_db, test_seller):
        """Test getting marketplace item details."""
        item = create_test_product(
            test_seller.id,
            "Premium Workflow",
            description="Advanced automation workflow",
            product_type="workflow",
            price=Decimal("99.99"),
            tags=["premium", "advanced"],
            features=["Feature 1", "Feature 2"]
        )
        item.version = "2.0.0"
        test_db.add(item)
        test_db.commit()
        test_db.refresh(item)
        
        response = client.get(
            f"/api/v1/marketplace/items/{item.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Premium Workflow"
        assert data["version"] == "2.0.0"
        assert len(data["features"]) == 2
    
    def test_update_marketplace_item(self, client, seller_headers, test_db, test_seller):
        """Test updating a marketplace item."""
        item = create_test_product(
            test_seller.id,
            "Original Name",
            description="Original description",
            product_type="template",
            price=Decimal("29.99"),
            status="approved"
        )
        test_db.add(item)
        test_db.commit()
        test_db.refresh(item)
        
        response = client.put(
            f"/api/v1/marketplace/items/{item.id}",
            json={
                "name": "Updated Name",
                "price": 39.99,
                "description": "Updated description with more features"
            },
            headers=seller_headers
        )
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["price"] == 39.99
        assert data["status"] == "pending"  # Goes back to pending after update
    
    def test_delete_marketplace_item(self, client, seller_headers, test_db, test_seller):
        """Test deleting a marketplace item."""
        item = create_test_product(
            test_seller.id,
            "To Delete",
            description="Will be deleted",
            product_type="workflow",
            price=Decimal("19.99"),
            status="approved"
        )
        test_db.add(item)
        test_db.commit()
        test_db.refresh(item)
        
        response = client.delete(
            f"/api/v1/marketplace/items/{item.id}",
            headers=seller_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Item deleted successfully"
        
        # Verify soft delete
        test_db.refresh(item)
        assert item.is_deleted is True


class TestPurchases:
    """Test purchase functionality."""
    
    @patch('apps.backend.routes.marketplace.process_payment')
    def test_purchase_item(self, mock_payment, client, auth_headers, test_db, test_user, test_seller):
        """Test purchasing a marketplace item."""
        mock_payment.return_value = {
            "success": True,
            "transaction_id": "txn_123456"
        }
        
        item = create_test_product(
            test_seller.id,
            "Test Purchase Item",
            description="Item for purchase testing",
            product_type="template",
            price=Decimal("29.99"),
            status="approved"
        )
        test_db.add(item)
        test_db.commit()
        test_db.refresh(item)
        
        response = client.post(
            f"/api/v1/marketplace/items/{item.id}/purchase",
            json={
                "payment_method": "card",
                "payment_token": "tok_test123"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        purchase = response.json()
        assert purchase["product_id"] == str(item.id)
        assert purchase["amount"] == 29.99
        assert purchase["status"] == "completed"
        assert "download_url" in purchase
    
    def test_purchase_already_owned(self, client, auth_headers, test_db, test_user, test_seller):
        """Test purchasing an already owned item."""
        item = create_test_product(
            test_seller.id,
            "Already Owned",
            product_type="workflow",
            price=Decimal("49.99"),
            status="approved"
        )
        test_db.add(item)
        
        # Create existing purchase
        purchase = create_test_purchase(
            buyer_id=test_user.id,
            product_id=item.id,
            amount=item.price,
            status="completed"
        )
        test_db.add(purchase)
        test_db.commit()
        test_db.refresh(item)
        
        response = client.post(
            f"/api/v1/marketplace/items/{item.id}/purchase",
            json={"payment_method": "card"},
            headers=auth_headers
        )
        
        if response.status_code != 400:
            print(f"Response status: {response.status_code}")
            print(f"Response: {response.text}")
        assert response.status_code == 400
        assert "already own this item" in response.json().get("detail", response.json().get("message", ""))
    
    def test_list_purchases(self, client, auth_headers, test_db, test_user):
        """Test listing user's purchases."""
        # Create test purchases
        purchases = []
        for i in range(3):
            item = create_test_product(
                uuid4(),
                f"Purchased Item {i}",
                product_type="template",
                price=Decimal("29.99"),
                status="approved"
            )
            test_db.add(item)
            test_db.flush()
            
            purchase = create_test_purchase(
                buyer_id=test_user.id,
                product_id=item.id,
                amount=item.price,
                status="completed",
                transaction_id=f"txn_{i}"
            )
            purchases.append(purchase)
        
        test_db.add_all(purchases)
        test_db.commit()
        
        response = client.get(
            "/api/v1/marketplace/purchases",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all(p["status"] == "completed" for p in data)
    
    def test_download_purchased_item(self, client, auth_headers, test_db, test_user, test_seller):
        """Test downloading a purchased item."""
        item = create_test_product(
            test_seller.id,
            "Downloadable Item",
            product_type="workflow",
            price=Decimal("39.99"),
            status="approved",
            files=[{"url": "https://storage.example.com/item.zip", "name": "item.zip"}]
        )
        item.file_url = "https://storage.example.com/item.zip"  # Add for backward compatibility
        test_db.add(item)
        test_db.flush()
        
        purchase = create_test_purchase(
            buyer_id=test_user.id,
            product_id=item.id,
            amount=item.price,
            status="completed"
        )
        test_db.add(purchase)
        test_db.commit()
        test_db.refresh(purchase)
        
        response = client.get(
            f"/api/v1/marketplace/purchases/{purchase.id}/download",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "download_url" in data
        assert "expires_at" in data


class TestReviews:
    """Test review functionality."""
    
    def test_create_review(self, client, auth_headers, test_db, test_user, test_seller):
        """Test creating a review for a purchased item."""
        item = create_test_product(
            test_seller.id,
            "Reviewable Item",
            product_type="template",
            price=Decimal("29.99"),
            status="approved"
        )
        test_db.add(item)
        test_db.flush()
        
        # User must have purchased the item
        purchase = create_test_purchase(
            buyer_id=test_user.id,
            product_id=item.id,
            amount=item.price,
            status="completed"
        )
        test_db.add(purchase)
        test_db.commit()
        test_db.refresh(item)
        
        response = client.post(
            f"/api/v1/marketplace/items/{item.id}/reviews",
            json={
                "rating": 5,
                "comment": "Excellent workflow template!",
                "pros": ["Easy to use", "Well documented"],
                "cons": ["Could use more examples"]
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        review = response.json()
        assert review["rating"] == 5
        assert review["comment"] == "Excellent workflow template!"
    
    def test_cannot_review_unpurchased(self, client, auth_headers, test_db, test_seller):
        """Test that users cannot review items they haven't purchased."""
        item = create_test_product(
            test_seller.id,
            "Unpurchased Item",
            product_type="workflow",
            price=Decimal("49.99"),
            status="approved"
        )
        test_db.add(item)
        test_db.commit()
        test_db.refresh(item)
        
        response = client.post(
            f"/api/v1/marketplace/items/{item.id}/reviews",
            json={
                "rating": 5,
                "comment": "Great!"
            },
            headers=auth_headers
        )
        
        if response.status_code != 403:
            print(f"Response status: {response.status_code}")
            print(f"Response: {response.text}")
        assert response.status_code == 403
        assert "must purchase" in response.json().get("detail", response.json().get("message", ""))
    
    def test_list_item_reviews(self, client, auth_headers, test_db, test_seller):
        """Test listing reviews for an item."""
        item = create_test_product(
            test_seller.id,
            "Popular Item",
            product_type="template",
            price=Decimal("39.99"),
            status="approved"
        )
        test_db.add(item)
        test_db.flush()
        
        # Create test reviews
        reviews = []
        for i in range(3):
            reviewer = User(
                email=f"reviewer{i}@example.com",
                username=f"reviewer{i}",
                hashed_password="hash",
                is_active=True
            )
            test_db.add(reviewer)
            test_db.flush()
            
            review = Review(
                product_id=item.id,
                reviewer_id=reviewer.id,
                rating=5 - i,
                comment=f"Review comment {i}",
                is_verified_purchase=True
            )
            reviews.append(review)
        
        test_db.add_all(reviews)
        test_db.commit()
        test_db.refresh(item)
        
        response = client.get(
            f"/api/v1/marketplace/items/{item.id}/reviews",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["rating"] >= data[1]["rating"]  # Sorted by helpfulness/rating


class TestSellerDashboard:
    """Test seller dashboard functionality."""
    
    def test_get_seller_stats(self, client, seller_headers, test_db, test_seller):
        """Test getting seller statistics."""
        # Create items and sales
        items = []
        total_revenue = Decimal("0")
        
        for i in range(3):
            item = create_test_product(
                test_seller.id,
                f"Seller Item {i}",
                product_type="workflow",
                price=Decimal("49.99"),
                status="approved",
                downloads=i * 5
            )
            items.append(item)
            test_db.add(item)
            test_db.flush()
            
            # Create some purchases
            for j in range(i + 1):
                buyer = User(
                    email=f"buyer{i}{j}@example.com",
                    username=f"buyer{i}{j}",
                    hashed_password="hash",
                    is_active=True
                )
                test_db.add(buyer)
                test_db.flush()
                
                purchase = create_test_purchase(
                    buyer_id=buyer.id,
                    product_id=item.id,
                    amount=item.price,
                    status="completed"
                )
                test_db.add(purchase)
                total_revenue += item.price
        
        test_db.commit()
        
        response = client.get(
            "/api/v1/marketplace/seller/stats",
            headers=seller_headers
        )
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
        assert response.status_code == 200
        stats = response.json()
        assert stats["total_items"] == 3
        assert stats["total_sales"] == 6  # 1 + 2 + 3
        assert float(stats["total_revenue"]) == float(total_revenue)
        assert stats["average_rating"] is not None
    
    def test_list_seller_items(self, client, seller_headers, test_db, test_seller):
        """Test listing seller's own items."""
        # Create seller's items
        for i in range(2):
            item = create_test_product(
                test_seller.id,
                f"My Item {i}",
                product_type="template",
                price=Decimal("29.99"),
                status="approved" if i == 0 else "pending"
            )
            test_db.add(item)
        
        # Create another seller's item
        other_seller = User(
            email="other@example.com",
            username="other",
            hashed_password="hash",
            is_active=True,
            is_seller=True
        )
        test_db.add(other_seller)
        test_db.flush()
        
        other_item = create_test_product(
            other_seller.id,
            "Other Seller Item",
            product_type="workflow",
            price=Decimal("39.99"),
            status="approved"
        )
        test_db.add(other_item)
        test_db.commit()
        
        response = client.get(
            "/api/v1/marketplace/seller/items",
            headers=seller_headers
        )
        
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2
        assert all(item["seller_id"] == str(test_seller.id) for item in items)
    
    def test_get_sales_history(self, client, seller_headers, test_db, test_seller):
        """Test getting seller's sales history."""
        item = create_test_product(
            test_seller.id,
            "Best Seller",
            product_type="workflow",
            price=Decimal("79.99"),
            status="approved"
        )
        test_db.add(item)
        test_db.flush()
        
        # Create sales
        sales = []
        for i in range(5):
            buyer = User(
                email=f"customer{i}@example.com",
                username=f"customer{i}",
                hashed_password="hash",
                is_active=True
            )
            test_db.add(buyer)
            test_db.flush()
            
            purchase = create_test_purchase(
                buyer_id=buyer.id,
                product_id=item.id,
                amount=item.price,
                status="completed",
                created_at=datetime.utcnow()
            )
            sales.append(purchase)
        
        test_db.add_all(sales)
        test_db.commit()
        
        response = client.get(
            "/api/v1/marketplace/seller/sales",
            headers=seller_headers
        )
        
        assert response.status_code == 200
        sales_data = response.json()
        assert len(sales_data) == 5
        assert all(sale["amount"] == 79.99 for sale in sales_data)


class TestMarketplaceAdmin:
    """Test marketplace admin functionality."""
    
    def test_approve_item(self, client, test_db, test_seller):
        """Test approving a marketplace item (admin only)."""
        admin = User(
            email="admin@example.com",
            username="admin",
            hashed_password="hash",
            is_active=True,
            is_verified=True,
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        test_db.commit()
        test_db.refresh(admin)
        
        admin_token = create_access_token({"sub": admin.email})
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        item = create_test_product(
            test_seller.id,
            "Pending Approval",
            product_type="template",
            price=Decimal("39.99"),
            status="pending"
        )
        test_db.add(item)
        test_db.commit()
        test_db.refresh(item)
        
        response = client.post(
            f"/api/v1/marketplace/admin/items/{item.id}/approve",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Item approved"
        
        test_db.refresh(item)
        assert item.status == "approved"
    
    def test_reject_item(self, client, test_db, test_seller):
        """Test rejecting a marketplace item (admin only)."""
        admin = User(
            email="admin@example.com",
            username="admin",
            hashed_password="hash",
            is_active=True,
            is_verified=True,
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        test_db.commit()
        test_db.refresh(admin)
        
        admin_token = create_access_token({"sub": admin.email})
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        item = create_test_product(
            test_seller.id,
            "To Reject",
            product_type="workflow",
            price=Decimal("99.99"),
            status="pending"
        )
        test_db.add(item)
        test_db.commit()
        test_db.refresh(item)
        
        response = client.post(
            f"/api/v1/marketplace/admin/items/{item.id}/reject",
            json={"reason": "Does not meet quality standards"},
            headers=admin_headers
        )
        
        assert response.status_code == 200
        
        test_db.refresh(item)
        assert item.status == "rejected"