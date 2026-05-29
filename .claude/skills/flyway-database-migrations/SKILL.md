---
name: "flyway-database-migrations"
description: "Patterns for Flyway database migrations — directory structure, multi-environment flyway.toml configuration, versioned script naming, SQL schema conventions, Cloud SQL support, and the Maven Docker module for building the migration image. Use when creating or modifying database migrations or the migration build/deployment setup."
metadata:
  tags: default
---

# Flyway Database Migration Patterns

## Directory Structure

Migration scripts live at the project root, outside any Maven module. They are copied into the Docker build context by `maven-resources-plugin`.

```
{project-name}/
├── db-migration/
│   ├── V1.0.0__initial_schema.sql
│   ├── V1.1.0__add_inventory_tables.sql
│   └── ...
└── {project-name}-docker/
    └── {project-name}-db-migration-docker/
        ├── pom.xml
        ├── Dockerfile
        └── flyway.toml
```

---

## flyway.toml Multi-Environment Config

```toml
[flyway]
locations = ["filesystem:/db-migration/"]

[environments.dev]
url = "jdbc:postgresql://db:5432/{db-name}"
user = "{db-user}"

[environments.staging]
url = "jdbc:postgresql:///{db-name}?cloudSqlInstance={gcp-project}-staging:{region}:{db-instance}&socketFactory=com.google.cloud.sql.postgres.SocketFactory"
user = "{db-user}"

[environments.prod]
url = "jdbc:postgresql:///{db-name}?cloudSqlInstance={gcp-project}-prod:{region}:{db-instance}&socketFactory=com.google.cloud.sql.postgres.SocketFactory"
user = "{db-user}"
```

**Environment details:**
- **dev**: Local Docker Compose — standard JDBC to the `db` service. Password injected via `FLYWAY_PASSWORD` Docker Compose environment variable.
- **staging/prod**: Cloud Run job with Cloud SQL JDBC Socket Factory for IAM auth. Password injected via `--set-env-vars="FLYWAY_PASSWORD=<password>"` in the `gcloud run jobs create` command. Flyway automatically uses the `FLYWAY_PASSWORD` environment variable without explicit configuration.

### Running Migrations

#### Local Development (Docker Compose)

```bash
# Automatically on docker compose up (db-migration service runs: migrate -environment=dev)
docker compose up
# Or (re)run only the db-migration service
docker compose up db-migration
```

#### Cloud Run Job (staging/prod)

Create a Cloud Run migration job that injects database credentials via `--set-env-vars`:

```bash
GCP_PROJECT={gcp-project}-staging
IMAGE_TAG=0.1.0_2025-01-15_14-30-00  # Timestamped deployment tag from docker build
DB_PASSWORD=<{db-user}-password>

gcloud run jobs create db-migration \
    --project=$GCP_PROJECT \
    --image=us-{region}-docker.pkg.dev/$GCP_PROJECT/{docker-registry}/{project-name}-db-migration-docker:$IMAGE_TAG \
    --region=us-{region} \
    --args=migrate,-environment=staging \
    --set-cloudsql-instances={db-instance} \
    --set-env-vars="FLYWAY_PASSWORD=$DB_PASSWORD"

# Execute the migration job
gcloud run jobs execute db-migration \
    --project=$GCP_PROJECT \
    --region=us-{region} \
    --wait
```

**Key points:**
- `--args=migrate,-environment=staging` passes the environment name to Flyway CLI
- `--set-cloudsql-instances` enables Cloud SQL JDBC Socket Factory for secure IAM auth
- `--set-env-vars="FLYWAY_PASSWORD=<password>"` injects the database user password; Flyway automatically reads it
- `--wait` blocks until the job completes

---

## Script Naming Convention

```
V{major}.{minor}.{patch}__{description}.sql
```

- **Semantic versioning** aligned with the application version
- **Double underscore** (`__`) separates version from description
- **snake_case** for the description
- Examples:
  - `V1.0.0__initial_schema.sql`
  - `V1.1.0__add_menu_items.sql`
  - `V1.1.1__add_menu_item_price_index.sql`

---

## Schema Conventions

### Primary Keys

UUID hex strings — SQLModel generates 32-char hex (UUID without hyphens):

```sql
id VARCHAR(32) PRIMARY KEY
```

### Timestamps

Always timezone-aware with automatic defaults:

```sql
created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
```

### Reserved Word Avoidance

Avoid PostgreSQL reserved words as table or column names. Common example: use `app_user` instead of `user`.

```sql
-- Bad: "user" is a reserved word in PostgreSQL
CREATE TABLE user ( ... );

-- Good
CREATE TABLE app_user ( ... );
```

### Foreign Keys

Always use named constraints with explicit referential actions. Named constraints produce meaningful error messages and can be dropped or modified by name.

```sql
restaurant_id VARCHAR(32),
CONSTRAINT fk_app_user_restaurant FOREIGN KEY (restaurant_id) REFERENCES restaurant(id) ON DELETE SET NULL
```

**Constraint naming convention:** `fk_{table}_{referenced_table}`

**Common referential actions:**
- `ON DELETE CASCADE` — delete child rows when the parent is deleted (use carefully)
- `ON DELETE SET NULL` — nullify the FK column when the parent is deleted (requires nullable column)
- `ON DELETE RESTRICT` — prevent parent deletion if child rows exist (PostgreSQL default, but state it explicitly for clarity)

### Validation Constraints

Use `CHECK` constraints to enforce valid values on enum-like columns:

```sql
role VARCHAR(50) NOT NULL DEFAULT 'OWNER',
CONSTRAINT ck_app_user_role CHECK (role IN ('OWNER', 'MEMBER', 'VIEWER'))
```

**Constraint naming conventions:**
- Foreign keys: `fk_{table}_{referenced_table}`
- Unique: `uq_{table}_{column}`
- Check: `ck_{table}_{column}`

---

## Example Initial Schema

```sql
-- V1.0.0__initial_schema.sql

CREATE TABLE restaurant (
    id          VARCHAR(32)  PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE app_user (
    id            VARCHAR(32)  PRIMARY KEY,
    firebase_uid  VARCHAR(128) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    display_name  VARCHAR(255),
    restaurant_id VARCHAR(32),
    role          VARCHAR(50)  NOT NULL DEFAULT 'OWNER',
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_app_user_firebase_uid UNIQUE (firebase_uid),
    CONSTRAINT fk_app_user_restaurant   FOREIGN KEY (restaurant_id) REFERENCES restaurant(id) ON DELETE SET NULL,
    CONSTRAINT ck_app_user_role         CHECK (role IN ('OWNER', 'MEMBER', 'VIEWER'))
);
```

**Notable patterns:**
- All constraints are named and declared at the end of the `CREATE TABLE` block for readability
- `UNIQUE` expressed as a named constraint rather than an inline column modifier — consistent style and droppable by name
- `role` column (not `user_role` — the table name already provides context) validated by `CHECK` constraint
- `ON DELETE SET NULL` on the nullable `restaurant_id` FK — explicit, not relying on the default behaviour

---

## Docker Module POM

Copies SQL scripts into the build context and builds the Flyway image with Cloud SQL driver support:

```xml
<project>
    <artifactId>{project-name}-db-migration-docker</artifactId>
    <packaging>docker</packaging>

    <build>
        <plugins>
            <plugin>
                <groupId>io.fabric8</groupId>
                <artifactId>docker-maven-plugin</artifactId>
                <configuration>
                    <images>
                        <image>
                            <name>{project-name}-db-migration-docker:${docker.image.tag}</name>
                            <build>
                                <dockerFile>${project.basedir}/Dockerfile</dockerFile>
                                <buildx>
                                    <platforms>
                                        <platform>${docker.platforms}</platform>
                                    </platforms>
                                </buildx>
                            </build>
                            <run><skip>${docker.image.run.skip}</skip></run>
                        </image>
                    </images>
                </configuration>
            </plugin>
            <plugin>
                <artifactId>maven-resources-plugin</artifactId>
                <executions>
                    <execution>
                        <id>copy-db-migrations-to-docker-build-context</id>
                        <phase>process-resources</phase>
                        <goals><goal>copy-resources</goal></goals>
                        <configuration>
                            <outputDirectory>${project.build.directory}/docker-build/db-migration</outputDirectory>
                            <resources>
                                <resource>
                                    <directory>${project.basedir}/../../db-migration</directory>
                                </resource>
                            </resources>
                        </configuration>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>
</project>
```
