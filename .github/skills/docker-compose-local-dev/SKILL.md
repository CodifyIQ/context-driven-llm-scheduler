---
name: "docker-compose-local-dev"
description: "Patterns for local development orchestration using Docker Compose — typical stack includes web UI (optional), API service(s), database, and migrations; covers dependency ordering, health checks, environment variables, and Docker secrets. Use when setting up or modifying a compose.yaml for local development."
metadata:
  tags: default
---

# Docker Compose Local Dev Patterns

## Typical Service Stack

A typical full-stack application orchestrates these core services:
- **Web UI container** (optional; useful when testing containerized nginx builds)
- **One or more backend API services** (e.g., main service, worker/processor service)
- **PostgreSQL database**
- **Migration runner** (one-shot Flyway or Liquibase job)

The `{project-name}-web-ui` service is optional. For day-to-day local development, you typically run the database + backend services via Compose and use `flutter run` (CLI/IDE) for the frontend to leverage hot reload and fast iteration.

```yaml
services:
  {project-name}-web-ui:
    image: {project-name}-web-ui-docker:latest
    depends_on:
      - {project-name}-service
    ports:
      - "8080:8080"

  {project-name}-service:
    image: {project-name}-service-docker:latest
    depends_on:
      db-migration:
        condition: service_completed_successfully
      db:
        condition: service_healthy
    ports:
      - "8000:8000"
    environment:
      DB_URL: postgresql+pg8000://{db-user}:{db-password}@db:5432/{db-name}
      ALLOW_ORIGINS: "*"
      GOOGLE_APPLICATION_CREDENTIALS: "/run/secrets/dev-gcp-credentials"
      # Used by fastapi-cloudauth-lenient for Firebase JWT validation
      FIREBASE_PROJECT_ID: "{project-name}-dev"
    env_file:
      # NOT version controlled — must be created locally by each developer
      - dev-api-keys.env
    secrets:
      - dev-gcp-credentials

  db:
    image: postgres:18-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: {db-user}
      POSTGRES_PASSWORD: {db-password}
      POSTGRES_DB: {db-name}
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U {db-user} -d {db-name}"]
      interval: 10s
      retries: 5
      start_period: 30s
      timeout: 10s

  db-migration:
    image: {project-name}-db-migration-docker:latest
    depends_on:
      db:
        condition: service_healthy
    command: migrate -environment=dev
    restart: "no"
    environment:
      # Flyway automatically reads FLYWAY_PASSWORD for the active environment's password
      FLYWAY_PASSWORD: "{db-password}"

secrets:
  dev-gcp-credentials:
    file: ./dev-gcp-service-account-key.json

volumes:
  db_data:
```

---

## Startup Sequence

General dependency chain (services and conditions may vary by project):

```
db (PostgreSQL)
  ↓ service_healthy (pg_isready passes)
db-migration (Flyway or Liquibase)
  ↓ service_completed_successfully (migrations applied, exit 0)
{project-name}-service (FastAPI or similar)
  ↓ (potentially) additional services
  ↓ (optionally) {project-name}-web-ui (nginx, depends on main service)
```

### Dependency Conditions

| Condition | When to Use |
|-----------|-------------|
| `service_healthy` | Wait for DB to accept connections before running migrations or starting the API |
| `service_completed_successfully` | Gate API startup until migrations complete (exit code 0) |
| *(no condition)* | Simple ordering — start after dependency begins, don't wait for readiness |

The migration service uses `restart: "no"` to run once and exit cleanly.

---

## PostgreSQL Health Check

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U {db-user} -d {db-name}"]
  interval: 10s
  retries: 5
  start_period: 30s
  timeout: 10s
```

- `start_period: 30s` — gives PostgreSQL time to initialize before counting failures
- Always specify `-U` and `-d` to match your configured user and database

---

## Environment Configuration

### Direct Environment Variables

Use `environment` for non-sensitive config:

```yaml
environment:
  DB_URL: postgresql+pg8000://{db-user}:{db-password}@db:5432/{db-name}
  ALLOW_ORIGINS: "*"
  # Used by fastapi-cloudauth-lenient for Firebase JWT validation
  FIREBASE_PROJECT_ID: "{project-name}-dev"
```

- `ALLOW_ORIGINS: "*"` is appropriate for local dev — allows Flutter debug mode connections
- `DB_URL` uses `pg8000` driver (pure-Python, no native library dependencies)
- `FIREBASE_PROJECT_ID` configures `fastapi-cloudauth-lenient` and must match the Firebase project issuing client JWTs in that environment
- Service names (e.g., `db`) act as hostnames within Docker's internal network

### env_file for API Keys

```yaml
env_file:
  - dev-api-keys.env
```

Use `env_file` for values that must not be committed. Add to `.gitignore` and document required keys in onboarding docs.

### Docker Secrets for Credential Files

```yaml
secrets:
  dev-gcp-credentials:
    file: ./dev-gcp-service-account-key.json
```

File-based credentials (GCP service account keys) mount read-only at `/run/secrets/{secret-name}`. Reference via environment variable:

```yaml
environment:
  GOOGLE_APPLICATION_CREDENTIALS: "/run/secrets/dev-gcp-credentials"
```

### Files Not Version Controlled

Each developer must create these locally:
- `dev-api-keys.env` — API keys for third-party services
- `dev-gcp-service-account-key.json` — GCP service account credentials

---

## Named Volumes

```yaml
volumes:
  db_data:
```

Named volumes persist data across `docker compose down`. Removed only by `docker compose down -v`.

---

## Common Commands

```bash
# Build all images then start all services
mvn clean install && docker compose up

# Rebuild and restart a single service
mvn clean install -pl {project-name}-docker/{project-name}-service-docker -am \
  && docker compose up {project-name}-service

# Reset the database (destroys all data)
docker compose down -v && docker compose up
```
