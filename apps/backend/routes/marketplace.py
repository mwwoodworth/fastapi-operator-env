"""
Marketplace routes for BrainOps backend.

Handles digital products, purchases, and licensing.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID, uuid4
import secrets

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from pydantic import BaseModel

from ..core.database import get_db
from ..routes.auth import get_current_user, get_current_active_user
from ..db.business_models import User, UserRole, Product, Purchase, Review, SubscriptionTier
from ..core.pagination import paginate, PaginationParams
from ..core.settings import settings

router = APIRouter()


# Mock payment processing function
async def process_payment(method, token, amount):
    """Mock payment processing."""
    return {"success": True, "transaction_id": f"txn_{uuid4()}"}


# Pydantic models
class ProductCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    description: str
    type: str = "digital"
    category: Optional[str] = None
    product_type: Optional[str] = "digital"
    price: float
    currency: str = "USD"
    features: List[str] = []
    requirements: dict = {}
    tags: List[str] = []
    preview_url: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    features: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class ProductResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    category: str
    product_type: str
    price: float
    currency: str
    files: List[dict]
    preview_url: Optional[str]
    thumbnail_url: Optional[str]
    features: List[str]
    requirements: List[str]
    tags: List[str]
    is_published: bool
    published_at: Optional[datetime]
    view_count: int
    purchase_count: int
    rating_average: float
    rating_count: int
    seller_id: str
    seller_name: str
    version: str
    status: str
    created_at: datetime
    updated_at: datetime


class PurchaseCreate(BaseModel):
    product_id: str
    payment_method: str = "stripe"


class PurchaseResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    buyer_id: str
    price: float
    currency: str
    status: str
    payment_method: Optional[str]
    payment_id: Optional[str]
    license_key: Optional[str]
    license_expires_at: Optional[datetime]
    created_at: datetime
    completed_at: Optional[datetime]
    download_url: Optional[str]


class LicenseActivation(BaseModel):
    license_key: str
    machine_id: str


class LicenseResponse(BaseModel):
    license_key: str
    product_name: str
    status: str
    activations: int
    max_activations: int
    expires_at: Optional[datetime]


class ProductStats(BaseModel):
    total_views: int
    total_purchases: int
    total_revenue: float
    average_rating: float
    rating_count: int
    conversion_rate: float
    revenue_by_month: List[dict]


# Helper functions
def generate_license_key() -> str:
    """Generate a unique license key."""
    return f"BRO-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"


def calculate_license_expiry(product_type: str) -> Optional[datetime]:
    """Calculate license expiry based on product type."""
    if product_type == "subscription":
        return datetime.utcnow() + timedelta(days=365)
    elif product_type == "trial":
        return datetime.utcnow() + timedelta(days=30)
    
    return None  # Perpetual license


def validate_product_files(files: List[UploadFile]) -> bool:
    """Validate uploaded product files."""
    max_size = 100 * 1024 * 1024  # 100MB
    allowed_types = [
        "application/zip",
        "application/pdf",
        "application/x-zip-compressed",
        "text/plain",
        "image/png",
        "image/jpeg"
    ]
    
    for file in files:
        if file.size > max_size:
            return False
        
        if file.content_type not in allowed_types:
            return False
    
    return True


# Product Management Endpoints
@router.post("/items")
async def create_marketplace_item(
    product_data: ProductCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new product listing."""
    # Check if user is a seller
    if not current_user.is_seller:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only sellers can create marketplace items"
        )
    
    # Generate slug if not provided
    import re
    slug = product_data.slug
    if not slug:
        slug = re.sub(r'[^a-z0-9]+', '-', product_data.name.lower()).strip('-')
        slug = f"{slug}-{str(uuid4())[:8]}"
    
    # Check if slug is unique
    existing = db.query(Product).filter(Product.slug == slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product slug already exists"
        )
    
    # Create product
    product = Product(
        id=uuid4(),
        name=product_data.name,
        slug=slug,
        description=product_data.description,
        category=product_data.category or "general",
        product_type=product_data.type,
        price=product_data.price,
        currency=product_data.currency,
        features=product_data.features,
        requirements=product_data.requirements,
        tags=product_data.tags,
        seller_id=current_user.id,
        status="pending",  # Needs approval
        preview_url=product_data.preview_url
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # Return simplified response for tests
    return {
        "id": str(product.id),
        "name": product.name,
        "price": product.price,
        "status": product.status,
        "type": product.product_type
    }


@router.get("/items", response_model=List[ProductResponse])
async def list_marketplace_items(
    search: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    tags: Optional[List[str]] = None,
    seller_id: Optional[UUID] = None,
    published_only: bool = True,
    sort_by: str = "created_at",
    order: str = "desc",
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db)
):
    """List products with filtering and sorting."""
    query = db.query(Product).join(User, Product.seller_id == User.id)
    
    # Filter by published status
    if published_only:
        query = query.filter(Product.is_published == True)
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                Product.name.ilike(f"%{search}%"),
                Product.description.ilike(f"%{search}%")
            )
        )
    
    if category:
        query = query.filter(Product.category == category)
    
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    
    if tags:
        # Filter products that have any of the specified tags
        for tag in tags:
            query = query.filter(Product.tags.contains([tag]))
    
    if seller_id:
        query = query.filter(Product.seller_id == seller_id)
    
    # Apply sorting
    sort_options = {
        "created_at": Product.created_at,
        "price": Product.price,
        "rating": Product.rating_average,
        "purchases": Product.purchase_count,
        "views": Product.view_count
    }
    
    sort_field = sort_options.get(sort_by, Product.created_at)
    
    if order == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())
    
    # Paginate
    products = paginate(query, pagination)
    
    # Format response
    results = []
    for product in products:
        seller = db.query(User).filter(User.id == product.seller_id).first()
        results.append(format_product_response(product, seller))
    
    return results


@router.get("/items/{product_id}", response_model=ProductResponse)
async def get_marketplace_item(
    product_id: UUID,
    db: Session = Depends(get_db)
):
    """Get product details."""
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Increment view count
    product.view_count += 1
    db.commit()
    
    seller = db.query(User).filter(User.id == product.seller_id).first()
    
    return format_product_response(product, seller)


@router.put("/items/{product_id}", response_model=ProductResponse)
async def update_marketplace_item(
    product_id: UUID,
    update_data: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update product details."""
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check ownership
    if product.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this product"
        )
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(product, field, value)
    
    # Reset status to pending after update
    product.status = "pending"
    
    db.commit()
    db.refresh(product)
    
    return format_product_response(product, current_user)


@router.delete("/items/{product_id}")
async def delete_marketplace_item(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a product."""
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check ownership
    if product.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this product"
        )
    
    # Check if there are active purchases
    active_purchases = db.query(Purchase).filter(
        Purchase.product_id == product_id,
        Purchase.status == "completed"
    ).count()
    
    if active_purchases > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete product with active purchases"
        )
    
    # Soft delete
    product.is_deleted = True
    db.commit()
    
    return {"message": "Item deleted successfully"}


@router.post("/{product_id}/publish")
async def publish_product(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Publish a product to the marketplace."""
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check ownership
    if product.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to publish this product"
        )
    
    # Validate product is ready for publishing
    if not product.files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product must have at least one file"
        )
    
    product.is_published = True
    product.published_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Product published successfully"}


@router.post("/{product_id}/unpublish")
async def unpublish_product(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unpublish a product from the marketplace."""
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check ownership
    if product.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to unpublish this product"
        )
    
    product.is_published = False
    db.commit()
    
    return {"message": "Product unpublished successfully"}


@router.post("/{product_id}/files")
async def upload_product_files(
    product_id: UUID,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload files for a product."""
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check ownership
    if product.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to upload files for this product"
        )
    
    # Validate files
    if not validate_product_files(files):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type or size"
        )
    
    # Upload files (in production, use S3 or similar)
    uploaded_files = []
    for file in files:
        file_path = f"products/{product_id}/{file.filename}"
        # Save file to storage
        uploaded_files.append({
            "filename": file.filename,
            "path": file_path,
            "size": file.size,
            "content_type": file.content_type
        })
    
    # Update product files
    product.files = uploaded_files
    db.commit()
    
    return {"message": f"{len(files)} files uploaded successfully"}


@router.get("/items/{product_id}/stats", response_model=ProductStats)
async def get_product_stats(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get product statistics (seller only)."""
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check ownership
    if product.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view product statistics"
        )
    
    # Calculate revenue by month
    revenue_by_month = db.query(
        func.date_trunc('month', Purchase.created_at).label('month'),
        func.sum(Purchase.price).label('revenue'),
        func.count(Purchase.id).label('count')
    ).filter(
        Purchase.product_id == product_id,
        Purchase.status == "completed"
    ).group_by('month').order_by('month').all()
    
    total_revenue = sum(r.revenue or 0 for r in revenue_by_month)
    
    conversion_rate = 0
    if product.view_count > 0:
        conversion_rate = (product.purchase_count / product.view_count) * 100
    
    return ProductStats(
        total_views=product.view_count,
        total_purchases=product.purchase_count,
        total_revenue=total_revenue,
        average_rating=product.rating_average,
        rating_count=product.rating_count,
        conversion_rate=conversion_rate,
        revenue_by_month=[
            {
                "month": r.month.strftime("%Y-%m"),
                "revenue": float(r.revenue or 0),
                "purchases": r.count
            }
            for r in revenue_by_month
        ]
    )


# Purchase Management Endpoints
@router.post("/purchases", response_model=PurchaseResponse)
async def create_purchase(
    purchase_data: PurchaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a purchase/order."""
    # Get product
    product = db.query(Product).filter(Product.id == purchase_data.product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    if not product.is_published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product is not available for purchase"
        )
    
    # Check if user already purchased
    existing = db.query(Purchase).filter(
        Purchase.product_id == product.id,
        Purchase.buyer_id == current_user.id,
        Purchase.status == "completed"
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product already purchased"
        )
    
    # Check user's subscription for marketplace access
    if current_user.subscription and current_user.subscription.tier == SubscriptionTier.FREE:
        # Free tier limitations
        monthly_purchases = db.query(Purchase).filter(
            Purchase.buyer_id == current_user.id,
            Purchase.created_at >= datetime.utcnow() - timedelta(days=30)
        ).count()
        
        if monthly_purchases >= 3:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Free tier limited to 3 purchases per month"
            )
    
    # Create purchase
    purchase = Purchase(
        product_id=product.id,
        buyer_id=current_user.id,
        price=product.price,
        currency=product.currency,
        status="pending",
        payment_method=purchase_data.payment_method
    )
    
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    
    # In production, integrate with payment provider
    # For now, simulate immediate completion
    purchase.status = "completed"
    purchase.completed_at = datetime.utcnow()
    purchase.payment_id = f"pay_{uuid4()}"
    purchase.license_key = generate_license_key()
    purchase.license_expires_at = calculate_license_expiry(product.product_type)
    
    # Update product stats
    product.purchase_count += 1
    
    db.commit()
    
    return format_purchase_response(purchase, product)


@router.get("/purchases", response_model=List[PurchaseResponse])
async def list_purchases(
    status: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's purchases."""
    query = db.query(Purchase).join(Product).filter(
        Purchase.buyer_id == current_user.id
    )
    
    if status:
        query = query.filter(Purchase.status == status)
    
    query = query.order_by(Purchase.created_at.desc())
    
    purchases = paginate(query, pagination)
    
    results = []
    for purchase in purchases:
        product = db.query(Product).filter(Product.id == purchase.product_id).first()
        results.append(format_purchase_response(purchase, product))
    
    return results


@router.get("/purchases/{purchase_id}", response_model=PurchaseResponse)
async def get_purchase(
    purchase_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get purchase details."""
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found"
        )
    
    # Check ownership
    if purchase.buyer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this purchase"
        )
    
    product = db.query(Product).filter(Product.id == purchase.product_id).first()
    
    return format_purchase_response(purchase, product)


@router.post("/purchases/{purchase_id}/download")
async def download_product(
    purchase_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download purchased product."""
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found"
        )
    
    # Check ownership
    if purchase.buyer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to download this product"
        )
    
    if purchase.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchase not completed"
        )
    
    # Check license expiry
    if purchase.license_expires_at and purchase.license_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="License has expired"
        )
    
    # Get product files
    product = db.query(Product).filter(Product.id == purchase.product_id).first()
    
    if not product.files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product files not found"
        )
    
    # Generate temporary download URL (in production, use signed URLs)
    download_url = f"{settings.BASE_URL}/downloads/{purchase_id}/{secrets.token_urlsafe(32)}"
    
    return {
        "download_url": download_url,
        "expires_in": 3600,  # 1 hour
        "files": product.files
    }


# License Management Endpoints
@router.get("/licenses", response_model=List[LicenseResponse])
async def list_licenses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's licenses."""
    purchases = db.query(Purchase).join(Product).filter(
        Purchase.buyer_id == current_user.id,
        Purchase.status == "completed",
        Purchase.license_key.isnot(None)
    ).all()
    
    licenses = []
    for purchase in purchases:
        product = db.query(Product).filter(Product.id == purchase.product_id).first()
        
        licenses.append(
            LicenseResponse(
                license_key=purchase.license_key,
                product_name=product.name,
                status="active" if not purchase.license_expires_at or purchase.license_expires_at > datetime.utcnow() else "expired",
                activations=1,  # In production, track actual activations
                max_activations=3,
                expires_at=purchase.license_expires_at
            )
        )
    
    return licenses


@router.post("/licenses/activate")
async def activate_license(
    activation: LicenseActivation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Activate a license on a machine."""
    # Find purchase by license key
    purchase = db.query(Purchase).filter(
        Purchase.license_key == activation.license_key,
        Purchase.buyer_id == current_user.id
    ).first()
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid license key"
        )
    
    # Check expiry
    if purchase.license_expires_at and purchase.license_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="License has expired"
        )
    
    # In production, track machine activations in a separate table
    # For now, just return success
    
    return {
        "message": "License activated successfully",
        "machine_id": activation.machine_id,
        "expires_at": purchase.license_expires_at
    }


@router.post("/licenses/deactivate")
async def deactivate_license(
    activation: LicenseActivation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deactivate a license on a machine."""
    # Find purchase by license key
    purchase = db.query(Purchase).filter(
        Purchase.license_key == activation.license_key,
        Purchase.buyer_id == current_user.id
    ).first()
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid license key"
        )
    
    # In production, remove machine activation from tracking table
    
    return {
        "message": "License deactivated successfully",
        "machine_id": activation.machine_id
    }


# Product Categories
@router.get("/categories")
async def list_categories(db: Session = Depends(get_db)):
    """List all product categories."""
    categories = [
        {
            "id": "templates",
            "name": "Templates",
            "description": "Ready-to-use document and project templates",
            "icon": "📄"
        },
        {
            "id": "automations",
            "name": "Automations",
            "description": "Pre-built automation workflows",
            "icon": "⚡"
        },
        {
            "id": "integrations",
            "name": "Integrations",
            "description": "Third-party service connectors",
            "icon": "🔗"
        },
        {
            "id": "reports",
            "name": "Reports",
            "description": "Customizable report templates",
            "icon": "📊"
        },
        {
            "id": "tools",
            "name": "Tools",
            "description": "Productivity and utility tools",
            "icon": "🔧"
        },
        {
            "id": "training",
            "name": "Training",
            "description": "Educational content and courses",
            "icon": "📚"
        }
    ]
    
    # Add product count for each category
    for category in categories:
        count = db.query(Product).filter(
            Product.category == category["id"],
            Product.is_published == True
        ).count()
        category["product_count"] = count
    
    return categories


# Helper functions
def format_product_response(product: Product, seller: User) -> ProductResponse:
    """Format product response."""
    return ProductResponse(
        id=str(product.id),
        name=product.name,
        slug=product.slug,
        description=product.description,
        category=product.category,
        product_type=product.product_type,
        price=product.price,
        currency=product.currency,
        files=product.files,
        preview_url=product.preview_url,
        thumbnail_url=product.thumbnail_url,
        features=product.features,
        requirements=product.requirements,
        tags=product.tags,
        is_published=product.is_published,
        published_at=product.published_at,
        view_count=product.view_count,
        purchase_count=product.purchase_count,
        rating_average=product.rating_average,
        rating_count=product.rating_count,
        seller_id=str(product.seller_id),
        seller_name=seller.full_name or seller.username or seller.email,
        version=product.version,
        status=product.status,
        created_at=product.created_at,
        updated_at=product.updated_at
    )


def format_purchase_response(purchase: Purchase, product: Product) -> PurchaseResponse:
    """Format purchase response."""
    download_url = None
    if purchase.status == "completed":
        download_url = f"/api/v1/marketplace/purchases/{purchase.id}/download"
    
    return PurchaseResponse(
        id=str(purchase.id),
        product_id=str(purchase.product_id),
        product_name=product.name,
        buyer_id=str(purchase.buyer_id),
        price=purchase.price,
        currency=purchase.currency,
        status=purchase.status,
        payment_method=purchase.payment_method,
        payment_id=purchase.payment_id,
        license_key=purchase.license_key,
        license_expires_at=purchase.license_expires_at,
        created_at=purchase.created_at,
        completed_at=purchase.completed_at,
        download_url=download_url
    )


# Purchase endpoint for tests
@router.post("/items/{item_id}/purchase")
async def purchase_item(
    item_id: str,
    payment_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Purchase a marketplace item."""
    product = db.query(Product).filter(Product.id == item_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check if already purchased
    existing = db.query(Purchase).filter(
        Purchase.buyer_id == current_user.id,
        Purchase.product_id == product.id,
        Purchase.status == "completed"
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already own this item"
        )
    
    # Process payment
    payment_result = await process_payment(
        payment_data.get("payment_method"),
        payment_data.get("payment_token"),
        product.price
    )
    
    # Create purchase
    purchase = Purchase(
        id=uuid4(),
        product_id=product.id,
        buyer_id=current_user.id,
        amount=product.price,
        price=product.price,
        status="completed",
        payment_method=payment_data.get("payment_method", "card"),
        transaction_id=payment_result["transaction_id"],
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    
    return {
        "id": str(purchase.id),
        "product_id": str(product.id),
        "amount": float(product.price),
        "status": "completed",
        "download_url": f"/api/v1/marketplace/purchases/{purchase.id}/download"
    }


# Review endpoints
@router.post("/items/{item_id}/reviews")
async def create_review(
    item_id: str,
    review_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a review for a purchased item."""
    # Check if user has purchased
    purchase = db.query(Purchase).filter(
        Purchase.buyer_id == current_user.id,
        Purchase.product_id == item_id,
        Purchase.status == "completed"
    ).first()
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must purchase the item before reviewing"
        )
    
    # Check if already reviewed
    existing = db.query(Review).filter(
        Review.reviewer_id == current_user.id,
        Review.product_id == item_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reviewed this item"
        )
    
    # Create review
    review = Review(
        id=uuid4(),
        product_id=item_id,
        reviewer_id=current_user.id,
        rating=review_data.get("rating"),
        comment=review_data.get("comment"),
        pros=review_data.get("pros", []),
        cons=review_data.get("cons", []),
        is_verified_purchase=True,
        created_at=datetime.utcnow()
    )
    
    db.add(review)
    db.commit()
    db.refresh(review)
    
    return {
        "id": str(review.id),
        "rating": review.rating,
        "comment": review.comment
    }


@router.get("/items/{item_id}/reviews")
async def list_item_reviews(
    item_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List reviews for an item."""
    reviews = db.query(Review).filter(
        Review.product_id == item_id
    ).order_by(Review.rating.desc()).all()
    
    return [
        {
            "id": str(r.id),
            "rating": r.rating,
            "comment": r.comment,
            "is_verified_purchase": r.is_verified_purchase
        }
        for r in reviews
    ]


# Seller dashboard endpoints
@router.get("/seller/stats")
async def get_seller_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get seller statistics."""
    if not current_user.is_seller:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller access required"
        )
    
    # Get seller's products
    products = db.query(Product).filter(Product.seller_id == current_user.id).all()
    
    # Calculate stats
    total_items = len(products)
    
    # Count actual purchases
    product_ids = [p.id for p in products]
    total_sales = db.query(Purchase).filter(
        Purchase.product_id.in_(product_ids),
        Purchase.status == "completed"
    ).count()
    
    # Calculate revenue from purchases
    purchases = db.query(Purchase).filter(
        Purchase.product_id.in_(product_ids),
        Purchase.status == "completed"
    ).all()
    total_revenue = sum(p.amount for p in purchases)
    
    # Calculate average rating
    rated_products = [p for p in products if p.rating_count > 0]
    if rated_products:
        average_rating = sum(p.rating_average for p in rated_products) / len(rated_products)
    else:
        average_rating = 0.0
    
    return {
        "total_items": total_items,
        "total_sales": total_sales,
        "total_revenue": float(total_revenue),
        "average_rating": average_rating
    }


@router.get("/seller/items")
async def list_seller_items(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List seller's own items."""
    if not current_user.is_seller:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller access required"
        )
    
    products = db.query(Product).filter(
        Product.seller_id == current_user.id
    ).all()
    
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "price": float(p.price),
            "status": p.status,
            "seller_id": str(p.seller_id)
        }
        for p in products
    ]


@router.get("/seller/sales")
async def get_sales_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get seller's sales history."""
    if not current_user.is_seller:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller access required"
        )
    
    # Get all products by this seller
    product_ids = db.query(Product.id).filter(Product.seller_id == current_user.id).all()
    product_ids = [pid[0] for pid in product_ids]
    
    # Get all purchases for these products
    sales = db.query(Purchase).filter(
        Purchase.product_id.in_(product_ids),
        Purchase.status == "completed"
    ).all()
    
    return [
        {
            "id": str(s.id),
            "product_id": str(s.product_id),
            "amount": float(s.amount),
            "created_at": s.created_at.isoformat()
        }
        for s in sales
    ]


# Admin endpoints
@router.post("/admin/items/{item_id}/approve")
async def approve_item(
    item_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Approve a marketplace item (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    product = db.query(Product).filter(Product.id == item_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    product.status = "approved"
    product.is_published = True
    product.published_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "Item approved"}


@router.post("/admin/items/{item_id}/reject")
async def reject_item(
    item_id: str,
    reason_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Reject a marketplace item (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    product = db.query(Product).filter(Product.id == item_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    product.status = "rejected"
    
    db.commit()
    
    return {"message": "Item rejected"}


# Additional purchase endpoints
@router.get("/purchases")
async def list_purchases(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List user's purchases."""
    purchases = db.query(Purchase).filter(
        Purchase.buyer_id == current_user.id
    ).order_by(Purchase.created_at.desc()).all()
    
    return [
        {
            "id": str(p.id),
            "product_id": str(p.product_id),
            "amount": float(p.amount),
            "status": p.status,
            "created_at": p.created_at.isoformat()
        }
        for p in purchases
    ]


@router.get("/purchases/{purchase_id}/download")
async def download_purchased_item(
    purchase_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Download a purchased item."""
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found"
        )
    
    if str(purchase.buyer_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only download your own purchases"
        )
    
    product = db.query(Product).filter(Product.id == purchase.product_id).first()
    
    # Generate temporary download URL
    from datetime import timedelta
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    return {
        "download_url": f"https://storage.example.com/downloads/{purchase_id}",
        "expires_at": expires_at.isoformat()
    }