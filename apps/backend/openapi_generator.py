"""
OpenAPI Documentation Generator for BrainOps ERP/CRM System.
Generates comprehensive API documentation for all 126+ endpoints.
"""

import json
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

from .main import app
from .core.settings import settings


class OpenAPIGenerator:
    """Generate and enhance OpenAPI documentation."""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.custom_tags = [
            {
                "name": "Authentication",
                "description": "User authentication and authorization endpoints"
            },
            {
                "name": "Users",
                "description": "User management and profile operations"
            },
            {
                "name": "Projects",
                "description": "Project management and collaboration"
            },
            {
                "name": "Tasks",
                "description": "Task creation, assignment, and tracking"
            },
            {
                "name": "ERP - Estimating",
                "description": "Construction estimating and bid management"
            },
            {
                "name": "ERP - Job Management",
                "description": "Job tracking, scheduling, and resource allocation"
            },
            {
                "name": "ERP - Field Capture",
                "description": "Field data capture and mobile operations"
            },
            {
                "name": "ERP - Compliance",
                "description": "Regulatory compliance and safety management"
            },
            {
                "name": "ERP - Financial",
                "description": "Financial management, invoicing, and payments"
            },
            {
                "name": "CRM - Leads",
                "description": "Lead generation and qualification"
            },
            {
                "name": "CRM - Opportunities",
                "description": "Sales opportunities and pipeline management"
            },
            {
                "name": "CRM - Analytics",
                "description": "Sales analytics and forecasting"
            },
            {
                "name": "CRM - Communication",
                "description": "Customer communication and engagement"
            },
            {
                "name": "AI - LangGraph",
                "description": "Multi-agent AI workflows and orchestration"
            },
            {
                "name": "AI - Chat",
                "description": "AI-powered chat and assistance"
            },
            {
                "name": "AI - Analysis",
                "description": "AI-driven analysis and insights"
            },
            {
                "name": "Integrations",
                "description": "Third-party service integrations"
            },
            {
                "name": "Weather",
                "description": "Weather data and forecasting for job planning"
            },
            {
                "name": "Files",
                "description": "File upload, storage, and management"
            },
            {
                "name": "Notifications",
                "description": "Real-time notifications and alerts"
            },
            {
                "name": "Admin",
                "description": "System administration and configuration"
            },
            {
                "name": "Health",
                "description": "System health and monitoring endpoints"
            }
        ]
        
        self.example_responses = {
            "400": {
                "description": "Bad Request",
                "content": {
                    "application/json": {
                        "example": {
                            "message": "Invalid request parameters",
                            "details": {"field": "error description"}
                        }
                    }
                }
            },
            "401": {
                "description": "Unauthorized",
                "content": {
                    "application/json": {
                        "example": {
                            "message": "Authentication required"
                        }
                    }
                }
            },
            "403": {
                "description": "Forbidden",
                "content": {
                    "application/json": {
                        "example": {
                            "message": "Insufficient permissions"
                        }
                    }
                }
            },
            "404": {
                "description": "Not Found",
                "content": {
                    "application/json": {
                        "example": {
                            "message": "Resource not found"
                        }
                    }
                }
            },
            "500": {
                "description": "Internal Server Error",
                "content": {
                    "application/json": {
                        "example": {
                            "message": "An unexpected error occurred",
                            "request_id": "req_123456"
                        }
                    }
                }
            }
        }
    
    def generate_openapi_schema(self) -> Dict[str, Any]:
        """Generate enhanced OpenAPI schema."""
        openapi_schema = get_openapi(
            title="BrainOps ERP/CRM API",
            version="1.0.0",
            description=self._get_api_description(),
            routes=self.app.routes,
            tags=self.custom_tags
        )
        
        # Add custom components
        openapi_schema["components"]["securitySchemes"] = {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token obtained from /api/v1/auth/login"
            },
            "apiKey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for service-to-service authentication"
            }
        }
        
        # Add servers
        openapi_schema["servers"] = [
            {
                "url": "http://localhost:8000",
                "description": "Local development server"
            },
            {
                "url": "https://api.brainops.weathercraft.com",
                "description": "Production server"
            },
            {
                "url": "https://staging-api.brainops.weathercraft.com",
                "description": "Staging server"
            }
        ]
        
        # Add external docs
        openapi_schema["externalDocs"] = {
            "description": "BrainOps API Documentation",
            "url": "https://docs.brainops.weathercraft.com"
        }
        
        # Enhance paths with examples and common responses
        self._enhance_paths(openapi_schema["paths"])
        
        # Add webhook definitions
        openapi_schema["webhooks"] = self._get_webhook_definitions()
        
        return openapi_schema
    
    def _get_api_description(self) -> str:
        """Get comprehensive API description."""
        return """
# BrainOps ERP/CRM API

A comprehensive Enterprise Resource Planning (ERP) and Customer Relationship Management (CRM) system designed specifically for the construction industry, with a focus on roofing contractors.

## Key Features

### 🏗️ ERP Modules
- **Estimating**: Create detailed estimates with material and labor calculations
- **Job Management**: Track projects from bid to completion
- **Field Capture**: Mobile-first data collection from job sites
- **Compliance**: Manage permits, inspections, and safety requirements
- **Financial**: Invoicing, payments, and accounting integration

### 💼 CRM Capabilities
- **Lead Management**: Track and qualify leads with automated scoring
- **Opportunity Pipeline**: Visual sales pipeline with stage management
- **Customer Analytics**: Lifetime value, churn prediction, and segmentation
- **Communication**: Email, SMS, and in-app notifications

### 🤖 AI Integration
- **LangGraph Orchestration**: Multi-agent workflows for complex business processes
- **Intelligent Analysis**: AI-driven insights and recommendations
- **Natural Language Processing**: Chat interface for system interaction
- **Predictive Analytics**: Forecast revenue, identify risks, and optimize operations

### 🔌 Integrations
- **Payment Processing**: Stripe and QuickBooks integration
- **Weather Services**: Real-time weather data for job planning
- **Document Generation**: Automated PDF creation for invoices and reports
- **Email/SMS**: Transactional and marketing communications

## Authentication

The API uses JWT bearer tokens for authentication. To get started:

1. Create an account or login at `/api/v1/auth/register` or `/api/v1/auth/login`
2. Include the token in the Authorization header: `Authorization: Bearer <token>`
3. Tokens expire after 24 hours by default

## Rate Limiting

- Anonymous requests: 10 requests per minute
- Authenticated requests: 100 requests per minute
- Enterprise plans: Custom rate limits available

## Pagination

List endpoints support pagination with the following parameters:
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20, max: 100)

## Error Handling

The API uses standard HTTP status codes and returns detailed error messages in JSON format:

```json
{
    "message": "Human-readable error message",
    "details": {...},
    "request_id": "unique-request-id"
}
```

## Versioning

The API is versioned via the URL path. The current version is v1. Breaking changes will result in a new version.

## Support

- Documentation: https://docs.brainops.weathercraft.com
- Email: api-support@weathercraft.com
- Status Page: https://status.brainops.weathercraft.com
"""
    
    def _enhance_paths(self, paths: Dict[str, Any]) -> None:
        """Enhance path definitions with examples and common responses."""
        for path, methods in paths.items():
            for method, definition in methods.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    # Add common responses if not present
                    if "responses" not in definition:
                        definition["responses"] = {}
                    
                    # Add standard error responses
                    for status_code, response in self.example_responses.items():
                        if status_code not in definition["responses"]:
                            definition["responses"][status_code] = response
                    
                    # Add security requirements based on path
                    if not path.startswith("/api/v1/auth/") and path != "/health":
                        definition["security"] = [{"bearerAuth": []}]
                    
                    # Add operation ID if not present
                    if "operationId" not in definition:
                        operation_id = f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"
                        definition["operationId"] = operation_id
                    
                    # Add examples for specific endpoints
                    self._add_endpoint_examples(path, method, definition)
    
    def _add_endpoint_examples(self, path: str, method: str, definition: Dict[str, Any]) -> None:
        """Add specific examples for key endpoints."""
        examples = {
            "/api/v1/auth/login": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "example": {
                                    "email": "user@example.com",
                                    "password": "SecurePassword123!"
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "example": {
                                        "access_token": "eyJhbGciOiJIUzI1NiIs...",
                                        "token_type": "bearer",
                                        "user": {
                                            "id": "user_123",
                                            "email": "user@example.com",
                                            "role": "contractor"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/v1/erp/estimates": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "example": {
                                    "customer_id": "cust_123",
                                    "property_address": "123 Main St",
                                    "roof_size_sqft": 2500,
                                    "material_type": "architectural_shingle",
                                    "labor_hours": 40,
                                    "markup_percentage": 20
                                }
                            }
                        }
                    }
                }
            },
            "/api/v1/crm/leads": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "example": {
                                        "items": [
                                            {
                                                "id": "lead_123",
                                                "name": "John Doe",
                                                "email": "john@example.com",
                                                "score": 85,
                                                "status": "qualified"
                                            }
                                        ],
                                        "total": 150,
                                        "page": 1,
                                        "limit": 20
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        # Apply examples if they exist for this endpoint
        if path in examples and method in examples[path]:
            example_data = examples[path][method]
            if "requestBody" in example_data and "requestBody" in definition:
                definition["requestBody"]["content"]["application/json"]["example"] = \
                    example_data["requestBody"]["content"]["application/json"]["example"]
            
            if "responses" in example_data:
                for status, response_data in example_data["responses"].items():
                    if status in definition["responses"]:
                        definition["responses"][status]["content"] = response_data["content"]
    
    def _get_webhook_definitions(self) -> Dict[str, Any]:
        """Define webhook schemas."""
        return {
            "projectStatusChanged": {
                "post": {
                    "requestBody": {
                        "description": "Project status change notification",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "event": {"type": "string", "example": "project.status_changed"},
                                        "project_id": {"type": "string"},
                                        "old_status": {"type": "string"},
                                        "new_status": {"type": "string"},
                                        "timestamp": {"type": "string", "format": "date-time"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "Webhook processed successfully"}
                    }
                }
            },
            "paymentReceived": {
                "post": {
                    "requestBody": {
                        "description": "Payment received notification",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "event": {"type": "string", "example": "payment.received"},
                                        "invoice_id": {"type": "string"},
                                        "amount_cents": {"type": "integer"},
                                        "payment_method": {"type": "string"},
                                        "timestamp": {"type": "string", "format": "date-time"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "Webhook processed successfully"}
                    }
                }
            }
        }
    
    def save_documentation(self, output_dir: str = "./docs/api") -> Dict[str, str]:
        """Save OpenAPI documentation in multiple formats."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate schema
        schema = self.generate_openapi_schema()
        
        # Save as JSON
        json_path = output_path / "openapi.json"
        with open(json_path, "w") as f:
            json.dump(schema, f, indent=2)
        
        # Save as YAML
        yaml_path = output_path / "openapi.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(schema, f, default_flow_style=False, sort_keys=False)
        
        # Generate endpoint summary
        summary_path = output_path / "endpoint_summary.md"
        with open(summary_path, "w") as f:
            f.write(self._generate_endpoint_summary(schema))
        
        # Generate Postman collection
        postman_path = output_path / "postman_collection.json"
        with open(postman_path, "w") as f:
            json.dump(self._convert_to_postman(schema), f, indent=2)
        
        return {
            "openapi_json": str(json_path),
            "openapi_yaml": str(yaml_path),
            "endpoint_summary": str(summary_path),
            "postman_collection": str(postman_path)
        }
    
    def _generate_endpoint_summary(self, schema: Dict[str, Any]) -> str:
        """Generate markdown summary of all endpoints."""
        summary = ["# BrainOps API Endpoint Summary\n"]
        summary.append(f"Generated: {datetime.now().isoformat()}\n")
        summary.append(f"Total Endpoints: {sum(len(methods) for methods in schema['paths'].values())}\n")
        
        # Group endpoints by tag
        endpoints_by_tag = {}
        for path, methods in schema["paths"].items():
            for method, definition in methods.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    tags = definition.get("tags", ["Uncategorized"])
                    for tag in tags:
                        if tag not in endpoints_by_tag:
                            endpoints_by_tag[tag] = []
                        
                        endpoints_by_tag[tag].append({
                            "method": method.upper(),
                            "path": path,
                            "summary": definition.get("summary", ""),
                            "description": definition.get("description", ""),
                            "operationId": definition.get("operationId", "")
                        })
        
        # Generate summary by tag
        for tag in sorted(endpoints_by_tag.keys()):
            summary.append(f"\n## {tag}\n")
            
            # Find tag description
            tag_desc = next((t["description"] for t in self.custom_tags if t["name"] == tag), "")
            if tag_desc:
                summary.append(f"{tag_desc}\n")
            
            summary.append("| Method | Path | Description |")
            summary.append("|--------|------|-------------|")
            
            for endpoint in sorted(endpoints_by_tag[tag], key=lambda x: (x["path"], x["method"])):
                desc = endpoint["summary"] or endpoint["description"] or "No description"
                summary.append(f"| {endpoint['method']} | `{endpoint['path']}` | {desc} |")
        
        # Add statistics
        summary.append("\n## Statistics\n")
        summary.append(f"- Total Endpoints: {sum(len(methods) for methods in schema['paths'].values())}")
        summary.append(f"- GET Endpoints: {sum(1 for p in schema['paths'].values() for m in p if m == 'get')}")
        summary.append(f"- POST Endpoints: {sum(1 for p in schema['paths'].values() for m in p if m == 'post')}")
        summary.append(f"- PUT Endpoints: {sum(1 for p in schema['paths'].values() for m in p if m == 'put')}")
        summary.append(f"- PATCH Endpoints: {sum(1 for p in schema['paths'].values() for m in p if m == 'patch')}")
        summary.append(f"- DELETE Endpoints: {sum(1 for p in schema['paths'].values() for m in p if m == 'delete')}")
        
        return "\n".join(summary)
    
    def _convert_to_postman(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert OpenAPI schema to Postman collection format."""
        collection = {
            "info": {
                "name": schema["info"]["title"],
                "description": schema["info"]["description"],
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "auth": {
                "type": "bearer",
                "bearer": [
                    {
                        "key": "token",
                        "value": "{{access_token}}",
                        "type": "string"
                    }
                ]
            },
            "variable": [
                {
                    "key": "base_url",
                    "value": "http://localhost:8000",
                    "type": "string"
                },
                {
                    "key": "access_token",
                    "value": "",
                    "type": "string"
                }
            ],
            "item": []
        }
        
        # Group by tags
        folders = {}
        for tag in self.custom_tags:
            folders[tag["name"]] = {
                "name": tag["name"],
                "description": tag["description"],
                "item": []
            }
        
        # Convert endpoints
        for path, methods in schema["paths"].items():
            for method, definition in methods.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    tags = definition.get("tags", ["Uncategorized"])
                    
                    request = {
                        "name": definition.get("summary", f"{method.upper()} {path}"),
                        "request": {
                            "method": method.upper(),
                            "header": [],
                            "url": {
                                "raw": "{{base_url}}" + path,
                                "host": ["{{base_url}}"],
                                "path": path.split("/")[1:]
                            }
                        }
                    }
                    
                    # Add request body if present
                    if "requestBody" in definition:
                        content = definition["requestBody"].get("content", {})
                        if "application/json" in content:
                            request["request"]["body"] = {
                                "mode": "raw",
                                "raw": json.dumps(
                                    content["application/json"].get("example", {}),
                                    indent=2
                                ),
                                "options": {
                                    "raw": {
                                        "language": "json"
                                    }
                                }
                            }
                            request["request"]["header"].append({
                                "key": "Content-Type",
                                "value": "application/json"
                            })
                    
                    # Add to appropriate folder
                    for tag in tags:
                        if tag in folders:
                            folders[tag]["item"].append(request)
        
        # Add folders to collection
        collection["item"] = list(folders.values())
        
        return collection


def generate_openapi_docs():
    """Generate OpenAPI documentation for the application."""
    generator = OpenAPIGenerator(app)
    
    print("Generating OpenAPI documentation...")
    files = generator.save_documentation()
    
    print("\nDocumentation generated successfully!")
    print(f"- OpenAPI JSON: {files['openapi_json']}")
    print(f"- OpenAPI YAML: {files['openapi_yaml']}")
    print(f"- Endpoint Summary: {files['endpoint_summary']}")
    print(f"- Postman Collection: {files['postman_collection']}")
    
    # Generate statistics
    with open(files['openapi_json'], 'r') as f:
        schema = json.load(f)
    
    total_endpoints = sum(len(methods) for methods in schema['paths'].values())
    print(f"\nTotal Endpoints: {total_endpoints}")
    
    return files


if __name__ == "__main__":
    generate_openapi_docs()