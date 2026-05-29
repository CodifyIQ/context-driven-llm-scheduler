---
name: "fastapi-python-service"
description: "Patterns for building Python REST API services using FastAPI, SQLModel, Firebase JWT, and PostgreSQL. Use when creating or extending a Python backend service — covers project layout, endpoint patterns, database access, authentication, and streaming."
metadata:
  tags: default
---

# FastAPI Python Service Patterns

## Technology Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI (async) |
| ORM | SQLModel (SQLAlchemy + Pydantic) |
| Database | PostgreSQL (Cloud SQL or standard) |
| Authentication | Firebase JWT |
| Validation | Pydantic |
| Streaming | Server-Sent Events (SSE) |

---

## Project Structure

```
service-name/
├── src/service_name/
│   ├── api.py                    # Main FastAPI app & router registration
│   ├── cross_cutting/
│   │   ├── auth.py               # Authentication handlers
│   │   ├── db.py                 # Database config & transactions
│   │   ├── email_util.py         # Email integrations
│   │   └── sse_util.py           # Server-Sent Events utilities
│   └── domain_module/            # One directory per feature domain
│       ├── api.py                # REST endpoints
│       ├── db_models.py          # SQLModel entities (table=True)
│       ├── api_models.py         # Pydantic request/response DTOs
│       └── util.py               # Helper functions
├── tests/
├── pyproject.toml
└── README.md
```

### Naming Conventions

| File | Purpose |
|------|---------|
| `api.py` | REST API endpoints |
| `db_models.py` | SQLModel ORM entities |
| `api_models.py` | Pydantic request/response DTOs |
| `util.py` | Helper/utility functions |
| `*_workflow.py` | LangGraph workflow definitions |
| `*_prompts.py` | LLM prompt templates |

| Class Suffix | Purpose |
|--------------|---------|
| `*Public` | API response models (safe for external use) |
| `*Base` | Shared base (DB and API models inherit from this) |
| `*Request` | API request models |
| `*Enum` | Enumeration classes |
| `*Link` | Many-to-many association tables |

---

## Main Application Setup

```python
# api.py
import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from src.service_name.cross_cutting.auth import get_current_user_http, is_current_user_admin
from src.service_name.admin_module.api import router as admin_router
from src.service_name.domain_module.api import router as domain_router

app = FastAPI()

# ALLOW_ORIGINS is a comma-separated list of allowed origins.
# Use "*" for local development via Docker Compose; set explicit origins for staging/prod.
_allow_origins = []
if "ALLOW_ORIGINS" in os.environ:
    _allow_origins = os.environ["ALLOW_ORIGINS"].split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(domain_router, dependencies=[Depends(get_current_user_http)])
app.include_router(admin_router, dependencies=[Depends(is_current_user_admin)])
```

---

## REST Endpoint Patterns

```python
# domain_module/api.py
router = APIRouter(prefix="/api", tags=["domain"])

# GET single resource — no @transactional needed for read-only operations
@router.get("/entities/{entity_id}", response_model=EntityPublic)
async def get_entity(
    entity_id: str,
    current_user_info: ExtendedFirebaseClaims = Depends(get_current_user_http),
    session: Session = Depends(get_session),
) -> EntityPublic:
    entity = session.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    return EntityPublic(**entity.model_dump())

# POST create
@router.post("/entities", response_model=EntityPublic, status_code=status.HTTP_201_CREATED)
@transactional
async def create_entity(
    entity_data: EntityCreate,
    current_user_info: ExtendedFirebaseClaims = Depends(get_current_user_http),
    session: Session = Depends(get_session),
) -> EntityPublic:
    entity = Entity(**entity_data.model_dump())
    session.add(entity)
    session.flush()  # Get generated ID before returning
    return EntityPublic(**entity.model_dump())

# PUT update
@router.put("/entities/{entity_id}", response_model=EntityPublic)
@transactional
async def update_entity(
    entity_id: str,
    entity_data: EntityUpdate,
    current_user_info: ExtendedFirebaseClaims = Depends(get_current_user_http),
    session: Session = Depends(get_session),
) -> EntityPublic:
    entity = session.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    for key, value in entity_data.model_dump(exclude_unset=True).items():
        setattr(entity, key, value)
    session.add(entity)
    return EntityPublic(**entity.model_dump())

# DELETE
@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
@transactional
async def delete_entity(
    entity_id: str,
    current_user_info: ExtendedFirebaseClaims = Depends(get_current_user_http),
    session: Session = Depends(get_session),
):
    entity = session.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    session.delete(entity)
```

### Error Handling

```python
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete: resource has dependencies")
raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not have access to this resource")
```

### Logging

```python
from loguru import logger
logger.info(f"User {user.email} created entity {entity.id}")
logger.error(f"Failed to process request: {error}")
```

---

## Authentication & Authorization

Use [`fastapi-cloudauth-lenient`](https://github.com/CodifyIQ/fastapi-cloudauth-lenient) as the default Firebase auth integration for FastAPI services.

```python
# cross_cutting/auth.py
import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi_cloudauth.firebase import FirebaseClaims
from fastapi_cloudauth_lenient import FirebaseCurrentUserLenient
from pydantic import Field

class ExtendedFirebaseClaims(FirebaseClaims):
    name: Optional[str] = Field(None, alias="name")
    admin: Optional[bool] = Field(None, alias="admin")
    auth_time: Optional[int] = Field(None, alias="auth_time")

get_current_user_http = FirebaseCurrentUserLenient(
    project_id=os.getenv("FIREBASE_PROJECT_ID"),
    iat_grace_period_seconds=5,
    auth_time_grace_period_seconds=5,
)
get_current_user_http.user_info = ExtendedFirebaseClaims

async def is_current_user_admin(
    current_user_info: ExtendedFirebaseClaims = Depends(get_current_user_http),
) -> ExtendedFirebaseClaims:
    if not current_user_info.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user_info
```

`FIREBASE_PROJECT_ID` is required and must match the Firebase project that issues client JWTs for that environment (`dev`, `staging`, `prod`).

### Role-Based Access Control

```python
def validate_resource_access(user: User, resource_id: str, session: Session):
    match user.user_type:
        case UserTypeEnum.ADMIN:
            return  # Admins access everything
        case UserTypeEnum.MANAGER:
            resource = session.get(Resource, resource_id)
            if resource.org_id != user.org_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        case UserTypeEnum.USER:
            resource = session.get(Resource, resource_id)
            if resource.owner_id != user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
```

---

## Persistence Patterns

Use [`sqlmodel-gcp-postgres`](https://github.com/CodifyIQ/sqlmodel-gcp-postgres) as the standard SQLModel integration layer for Cloud SQL, local PostgreSQL, and SQLite test databases.

### Required Python Dependencies (`pyproject.toml`)

```toml
[project]
dependencies = [
  "sqlmodel-gcp-postgres",
  "fastapi-cloudauth-lenient",
]
```

### Database Configuration (`sqlmodel-gcp-postgres`)

```python
# cross_cutting/db.py
from sqlmodel_gcp_postgres import get_session, transactional

# Re-export for consistent imports throughout the service
__all__ = ["get_session", "transactional"]
```

The library chooses connection mode from environment variables:
- **Cloud SQL mode** (`USE_CLOUD_SQL=true`): uses Google Cloud SQL Connector + `pg8000`
- **Standard mode** (`USE_CLOUD_SQL=false` or unset): uses `DB_URL` for local PostgreSQL or SQLite

### Environment-Specific Setup

#### Cloud SQL (staging/prod)

```bash
USE_CLOUD_SQL=true
CLOUD_SQL_INSTANCE_CONNECTION_NAME=your-project:region:instance-name
DB_USER=postgres-user
DB_PASS=postgres-password
DB_NAME=database-name
# Optional: force private IP
CLOUD_SQL_PRIVATE_IP=true
```

#### Local PostgreSQL (Docker Compose)

```bash
USE_CLOUD_SQL=false
DB_URL=postgresql+pg8000://{db-user}:{db-password}@db:5432/{db-name}
```

#### SQLite (tests)

```python
import os

os.environ["USE_CLOUD_SQL"] = "false"
os.environ["DB_URL"] = "sqlite:///test.db"
```

### Transaction Decorator (`@transactional`)

`sqlmodel-gcp-postgres` provides `@transactional` for automatic commit on success and rollback on exception. Use it on **write** operations (POST, PUT, DELETE). Read-only GET endpoints do not need it — omitting it avoids an unnecessary transaction wrapper.

```python
from fastapi import Depends
from sqlmodel import Session
from sqlmodel_gcp_postgres import get_session, transactional

@router.post("/entities", response_model=EntityPublic, status_code=status.HTTP_201_CREATED)
@transactional
async def create_entity(
    entity_data: EntityCreate,
    current_user_info: ExtendedFirebaseClaims = Depends(get_current_user_http),
    session: Session = Depends(get_session),
) -> EntityPublic:
    entity = Entity(**entity_data.model_dump())
    session.add(entity)
    session.flush()
    return EntityPublic(**entity.model_dump())
```

### Entity Definition

```python
# domain_module/db_models.py
class StatusEnum(str, Enum):  # Inherit from str for JSON serialization
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"

class EntityBase(SQLModel):
    """Base: shared fields. Do NOT set table=True here."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True, index=True)
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=SAColumn(SADateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=SAColumn(SADateTime(timezone=True), nullable=False),
    )

class Entity(EntityBase, table=True):
    status: StatusEnum = Field(
        default=StatusEnum.PENDING,
        sa_column=SAColumn(SAEnum(StatusEnum, values_callable=lambda x: [e.value for e in x], native_enum=False), nullable=False),
    )
    owner_id: str = Field(foreign_key="user.id", index=True)
    items: List["Item"] = Relationship(back_populates="entity", cascade_delete=True)
    content: Optional[str] = Field(default=None, sa_column=SAColumn(SAText))
```

### API Models (DTOs)

```python
class EntityPublic(EntityBase):
    status: StatusEnum
    items: List["ItemPublic"] = []

class EntityCreate(BaseModel):
    name: str
    description: Optional[str] = None

class EntityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[StatusEnum] = None
```

### Query Patterns

```python
# By ID
entity = session.get(Entity, entity_id)

# Conditional
entities = session.exec(
    select(Entity)
    .where(Entity.status == StatusEnum.ACTIVE)
    .where(Entity.owner_id == user_id)
    .order_by(Entity.created_at.desc())
).all()

# Case-insensitive search
entities = session.exec(select(Entity).where(col(Entity.name).ilike(f"%{term}%"))).all()

# Pagination
entities = session.exec(select(Entity).order_by(Entity.created_at.desc()).offset(offset).limit(limit)).all()

# Count
count = session.exec(select(func.count(Entity.id)).where(Entity.owner_id == user_id)).first()

# Eager load relationships
entities = session.exec(select(Entity).options(selectinload(Entity.items))).all()
```

---

## Streaming Responses (SSE)

```python
# cross_cutting/sse_util.py
def to_sse_format(event: str, data: Union[dict, BaseModel, str]) -> str:
    if isinstance(data, BaseModel):
        json_data = data.model_dump_json()
    elif isinstance(data, dict):
        json_data = json.dumps(data)
    else:
        json_data = json.dumps({"message": data})
    return f"event: {event}\ndata: {json_data}\n\n"

@router.post("/stream")
async def stream_response(request_data: StreamRequest, ...) -> StreamingResponse:
    async def event_generator():
        yield to_sse_format("start", {"status": "processing"})
        async for chunk in process_stream(request_data):
            yield to_sse_format("data", {"content": chunk})
        yield to_sse_format("complete", {"status": "done"})
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## Environment Variables

| Variable | Purpose | Required When |
|----------|---------|---------------|
| `ALLOW_ORIGINS` | Comma-separated list of allowed CORS origins | Always; no default — set to `"*"` in Docker Compose for local dev |
| `USE_CLOUD_SQL` | Selects DB mode in `sqlmodel-gcp-postgres` | Set to `true` for Cloud SQL; `false` (or unset) for standard mode |
| `CLOUD_SQL_INSTANCE_CONNECTION_NAME` | Cloud SQL instance identifier (`project:region:instance`) | `USE_CLOUD_SQL=true` |
| `DB_USER` / `DB_PASS` / `DB_NAME` | Database credentials for Cloud SQL connector | `USE_CLOUD_SQL=true` |
| `CLOUD_SQL_PRIVATE_IP` | Forces private IP connection to Cloud SQL | Optional, with `USE_CLOUD_SQL=true` |
| `DB_URL` | Standard SQLAlchemy URL (local PostgreSQL or SQLite tests) | `USE_CLOUD_SQL=false` or unset |
| `FIREBASE_PROJECT_ID` | Firebase project used by `fastapi-cloudauth-lenient` for JWT issuer/audience validation | Required for auth configuration |

---

## Best Practices

1. **Separate DB and API models** — DB models have `table=True`; API models are pure Pydantic
2. **Use base classes** — Share common fields between DB and API models via `*Base` classes
3. **Decorator order matters** — `@transactional` must be closest to the function definition
4. **Dependency injection** — `Depends()` for sessions, auth, and reusable logic
5. **Type everything** — Full annotations on parameters and return types
6. **Async endpoints** — Use `async def` for all endpoints
7. **UUID hex IDs** — `uuid.uuid4().hex` gives clean 32-char strings
8. **Timezone-aware datetimes** — `datetime.now(UTC)` + `SADateTime(timezone=True)`
9. **Enums inherit from str** — `class MyEnum(str, Enum)` for JSON serialization
10. **Docstrings on all endpoints** — Document args, returns, and raises
