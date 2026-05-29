---
name: "Python Standards"
description: "Coding conventions for all Python files — naming, type hints, imports, docstrings, and formatting"
applyTo: "**/*.py"
---

# Python Coding Conventions

## Naming

- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private/internal: `_leading_underscore`
- Use descriptive names — avoid single-letter variables in all scenarios

## Type Hints

- Required on all function signatures (parameters and return type)
- Required on all class-level attributes
- Prefer built-in generic types (`list[str]`, `dict[str, int]`) over `typing.List`, `typing.Dict` (Python 3.10+)
- Use `Optional[X]` or `X | None` for nullable values — be explicit, not implicit

```python
def get_user(user_id: str) -> User | None:
    ...

def create_entity(name: str, description: str | None = None) -> Entity:
    ...
```

## Imports

Organize in three groups separated by blank lines:

1. Standard library (`os`, `json`, `datetime`)
2. Third-party packages (`fastapi`, `sqlmodel`, `loguru`)
3. Local/project modules (`from src.service.models import Entity`)

- One import per line for explicit imports
- Never use `from module import *`
- Always use absolute imports (`from src.service.models import Entity`), never relative imports

```python
import os
from datetime import datetime, UTC

from fastapi import FastAPI, Depends
from sqlmodel import Session

from src.service.cross_cutting.auth import get_current_user_http
from src.service.domain.db_models import Entity
```

## Docstrings

- Required on all public functions, methods, and classes
- Google-style format
- One-line summary → blank line → detailed description if needed → Args → Returns → Raises

```python
def calculate_area(radius: float) -> float:
    """
    Calculate the area of a circle given the radius.

    Args:
        radius: The radius of the circle.

    Returns:
        The area of the circle, calculated as π * radius².

    Raises:
        ValueError: If radius is negative.
    """
    if radius < 0:
        raise ValueError("Radius must be non-negative")
    import math
    return math.pi * radius ** 2
```

## Code Style and Formatting

- Follow **PEP 8** — enforced via `ruff`
- Indentation: 4 spaces per level (never tabs)
- Maximum line length: 120 characters
- Use blank lines to separate functions, classes, and logical blocks within functions
- Prefer `f-strings` over `.format()` or `%` formatting

## Error Handling

- Handle edge cases explicitly — never silently swallow exceptions
- Use specific exception types, not bare `except:`
- Let exceptions propagate with meaningful messages — don't log and re-raise (causes duplicate log entries in production)
- Catch and handle only when you can meaningfully recover

```python
# Bad: logging then re-raising causes duplicate entries in production
# try:
#     result = process_data(payload)
# except ValueError as e:
#     logger.error(f"Invalid payload: {e}")
#     raise

# Good: let meaningful exceptions propagate
try:
    result = process_data(payload)
except ValueError as e:
    raise ValueError(f"Failed to process: invalid payload format") from e

# Good: catch and handle when you can recover
try:
    user = get_user_from_cache(user_id)
except CacheError:
    user = get_user_from_database(user_id)  # fallback
```

## General Guidelines

- Prioritize readability — code is read more than it is written
- Write concise, idiomatic Python — prefer list comprehensions and generators over verbose loops where clarity is maintained
- Break complex functions into smaller, single-responsibility functions
- Include comments explaining *why*, not *what*, when the reasoning is non-obvious
- Write code with maintainability in mind: future readers should understand design decisions without asking the original author
