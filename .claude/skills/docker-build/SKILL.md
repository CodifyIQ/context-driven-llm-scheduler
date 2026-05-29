---
name: "docker-build"
description: "Patterns for building Docker images using the fabric8 docker-maven-plugin with multi-platform buildx. Covers parent POM configuration, per-service image modules, Python/FastAPI Dockerfiles, Flutter/nginx Dockerfiles, Flyway migration images, and GCP Artifact Registry deployment."
metadata:
  tags: default
---

# Docker Build Patterns

## Docker Parent Module

Centralizes platform, tagging, and registry configuration for all Docker image modules.

```xml
<project>
    <artifactId>{project-name}-docker</artifactId>
    <packaging>pom</packaging>

    <properties>
        <!-- Default: ARM64 for Apple Silicon local dev -->
        <docker.platforms>linux/arm64</docker.platforms>
        <docker.image.run.skip>true</docker.image.run.skip>
        <!-- %l = "latest" for SNAPSHOTs, project version for releases -->
        <docker.image.tag>%l</docker.image.tag>
    </properties>

    <modules>
        <module>{project-name}-service-docker</module>
        <module>{project-name}-db-migration-docker</module>
        <!-- Optional: include only when you want a containerized nginx host for a Flutter web bundle -->
        <module>{project-name}-web-ui-docker</module>
    </modules>

    <profiles>
        <profile>
            <id>staging</id>
            <properties>
                <docker.push.registry>us-east1-docker.pkg.dev/{project-name}-staging/{project-name}-docker</docker.push.registry>
                <!-- Cloud Run requires linux/amd64 -->
                <docker.platforms>linux/amd64</docker.platforms>
                <docker.skip.push>true</docker.skip.push>
                <maven.build.timestamp.format>yyyy-MM-dd_HH-mm-ss</maven.build.timestamp.format>
                <docker.image.tag>${project.version}_${maven.build.timestamp}</docker.image.tag>
            </properties>
            <build>
                <pluginManagement>
                    <plugins>
                        <plugin>
                            <groupId>org.codehaus.mojo</groupId>
                            <artifactId>exec-maven-plugin</artifactId>
                            <executions>
                                <execution>
                                    <id>tag-image-with-artifact-registry</id>
                                    <phase>deploy</phase>
                                    <goals><goal>exec</goal></goals>
                                    <configuration>
                                        <executable>docker</executable>
                                        <arguments>
                                            <argument>tag</argument>
                                            <argument>${project.artifactId}:${docker.image.tag}</argument>
                                            <argument>${docker.push.registry}/${project.artifactId}:${docker.image.tag}</argument>
                                        </arguments>
                                    </configuration>
                                </execution>
                                <execution>
                                    <id>push-image-to-artifact-registry</id>
                                    <phase>deploy</phase>
                                    <goals><goal>exec</goal></goals>
                                    <configuration>
                                        <executable>docker</executable>
                                        <arguments>
                                            <argument>push</argument>
                                            <argument>${docker.push.registry}/${project.artifactId}:${docker.image.tag}</argument>
                                        </arguments>
                                    </configuration>
                                </execution>
                            </executions>
                        </plugin>
                    </plugins>
                </pluginManagement>
            </build>
        </profile>
        <profile>
            <id>prod</id>
            <properties>
                <docker.push.registry>us-east1-docker.pkg.dev/{project-name}-prod/{project-name}-docker</docker.push.registry>
                <!-- Cloud Run requires linux/amd64 -->
                <docker.platforms>linux/amd64</docker.platforms>
                <docker.skip.push>true</docker.skip.push>
                <maven.build.timestamp.format>yyyy-MM-dd_HH-mm-ss</maven.build.timestamp.format>
                <docker.image.tag>${project.version}_${maven.build.timestamp}</docker.image.tag>
            </properties>
            <build>
                <pluginManagement>
                    <plugins>
                        <plugin>
                            <groupId>org.codehaus.mojo</groupId>
                            <artifactId>exec-maven-plugin</artifactId>
                            <executions>
                                <execution>
                                    <id>tag-image-with-artifact-registry</id>
                                    <phase>deploy</phase>
                                    <goals><goal>exec</goal></goals>
                                    <configuration>
                                        <executable>docker</executable>
                                        <arguments>
                                            <argument>tag</argument>
                                            <argument>${project.artifactId}:${docker.image.tag}</argument>
                                            <argument>${docker.push.registry}/${project.artifactId}:${docker.image.tag}</argument>
                                        </arguments>
                                    </configuration>
                                </execution>
                                <execution>
                                    <id>push-image-to-artifact-registry</id>
                                    <phase>deploy</phase>
                                    <goals><goal>exec</goal></goals>
                                    <configuration>
                                        <executable>docker</executable>
                                        <arguments>
                                            <argument>push</argument>
                                            <argument>${docker.push.registry}/${project.artifactId}:${docker.image.tag}</argument>
                                        </arguments>
                                    </configuration>
                                </execution>
                            </executions>
                        </plugin>
                    </plugins>
                </pluginManagement>
            </build>
        </profile>
    </profiles>
</project>
```

**Key decisions:**
- `docker.platforms` defaults to `linux/arm64` for Apple Silicon dev. Deployment environment profiles (`staging`, `prod`) override to `linux/amd64` for GCP Cloud Run.
- `%l` tag: fabric8 resolves to `latest` for SNAPSHOTs, project version for releases.
- **Registry push via CLI**: fabric8's push has compatibility issues with `gcloud` auth. Environment profiles skip plugin push and use `exec-maven-plugin` to run `docker tag` + `docker push` directly in the `deploy` phase.
- **Timestamped deployment tags**: `{version}_{timestamp}` (e.g., `0.1.0-SNAPSHOT_2025-01-15_14-30-00`) enables rollback to specific builds.
- **`{project-name}-web-ui-docker` is optional**: Useful for containerized web hosting scenarios, but unnecessary for Firebase Hosting flows where you deploy the Flutter web bundle directly.

---

## Docker Module Pattern (Per Service)

Declare a dependency on the source module, copy build artifacts to staging, configure fabric8.

```xml
<project>
    <artifactId>{project-name}-service-docker</artifactId>
    <packaging>docker</packaging>

    <dependencies>
        <!-- Ensures service module builds before this Docker module -->
        <dependency>
            <groupId>com.example.{project-name}</groupId>
            <artifactId>{project-name}-service</artifactId>
            <version>${project.version}</version>
            <type>habushu</type>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>io.fabric8</groupId>
                <artifactId>docker-maven-plugin</artifactId>
                <configuration>
                    <images>
                        <image>
                            <name>{project-name}-service-docker:${docker.image.tag}</name>
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
                        <id>copy-service-to-docker-build-context</id>
                        <phase>process-resources</phase>
                        <goals><goal>copy-resources</goal></goals>
                        <configuration>
                            <outputDirectory>${project.build.directory}/docker-build/{project-name}-service</outputDirectory>
                            <resources>
                                <resource>
                                    <directory>${project.basedir}/../../{project-name}-service</directory>
                                    <includes>
                                        <include>pyproject.toml</include>
                                        <include>uv.lock</include>
                                        <include>README.md</include>
                                        <include>src/**</include>
                                    </includes>
                                    <excludes>
                                        <exclude>**/*.pyc</exclude>
                                    </excludes>
                                </resource>
                            </resources>
                        </configuration>
                    </execution>
                </executions>
            </plugin>
            <plugin>
                <artifactId>maven-deploy-plugin</artifactId>
                <configuration><skip>false</skip></configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

**Build context strategy:** Source artifacts are copied into `target/docker-build/` via `maven-resources-plugin` at `process-resources`. This keeps Dockerfile `COPY` paths relative to the module dir and excludes dev artifacts from the image.

---

## Python/FastAPI Dockerfile

Two-phase uv install for optimized layer caching.

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app

# Phase 1: Install dependencies only (cached — only rebuilds when lock file changes)
RUN --mount=type=cache,target=/root/.cache/uv \
     --mount=type=bind,source=target/docker-build/{project-name}-service/uv.lock,target=uv.lock \
     --mount=type=bind,source=target/docker-build/{project-name}-service/pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev --no-managed-python --compile-bytecode --link-mode=copy

# Phase 2: Copy source and install project (rebuilds on code changes, fast since deps cached)
COPY target/docker-build/{project-name}-service/ /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-managed-python --compile-bytecode --link-mode=copy

FROM python:3.12-slim-bookworm
RUN useradd --create-home {project-name}-user
USER {project-name}-user
COPY --chown={project-name}-user:{project-name}-user --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
CMD ["fastapi", "run", "--host", "0.0.0.0", "--port", "8000", "/app/src/{project_name}_service/api.py"]
```

| uv Flag | Purpose |
|---------|---------|
| `--locked` | Fail if `uv.lock` is out of sync |
| `--no-install-project` | Install deps only (Phase 1) |
| `--no-dev` | Exclude dev dependencies |
| `--no-managed-python` | Use system Python from base image |
| `--compile-bytecode` | Pre-compile `.pyc` for faster startup |
| `--link-mode=copy` | Required with cache mounts |

---

## Optional Flutter/Nginx Dockerfile (`{project-name}-web-ui-docker`)

```dockerfile
FROM nginx:1.28-alpine
RUN addgroup -g 1001 -S {project-name}-ui && \
    adduser -S -D -H -u 1001 -h /var/cache/nginx -s /sbin/nologin -G {project-name}-ui -g {project-name}-ui {project-name}-ui
RUN rm -rf /usr/share/nginx/html/*
COPY nginx.conf /etc/nginx/nginx.conf
COPY target/docker-build/{project-name}-web-ui/ /usr/share/nginx/html
RUN mkdir -p /var/cache/nginx /var/run/nginx && \
    chown -R {project-name}-ui:{project-name}-ui /var/cache/nginx /var/run/nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html
USER {project-name}-ui
CMD ["nginx", "-g", "daemon off;"]
```

This image is an alternative for serving a pre-built Flutter web bundle behind nginx. It does **not** build Flutter code; it only copies already-built static assets into nginx.

Expected workflow for this module:
1. Build Flutter web first (`flutter build web ...`)
2. Copy build artifacts into Docker build context
3. Build `{project-name}-web-ui-docker` image

For local development, prefer `flutter run` (CLI or IDE) to leverage hot reload and incremental builds. Rebuilding Maven + Docker for every UI change is intentionally discouraged for day-to-day iteration.

For Firebase Hosting (or similar static hosting), this Docker module is typically unnecessary; deploy the `build/web` output directly.

Key nginx.conf elements:
- Register `.mjs` MIME type — **required** for Flutter WASM builds
- Gzip compression for all text/JS/JSON types
- Security headers: `X-Frame-Options`, `X-XSS-Protection`, `X-Content-Type-Options`, `Referrer-Policy`
- API reverse proxy: `location /api/` → `http://{project-name}-service:8000`
- SPA routing: `try_files $uri $uri/ /index.html`
- Health check: `location /health` returns 200

---

## Flyway/Cloud SQL Dockerfile

```dockerfile
# Build Cloud SQL JDBC Socket Factory (run on host native arch — JARs cross stages safely)
FROM --platform=$BUILDPLATFORM maven:3.9-eclipse-temurin-17 AS builder
RUN git clone --branch v1.25.3 https://github.com/GoogleCloudPlatform/cloud-sql-jdbc-socket-factory.git /build
WORKDIR /build
RUN mvn -P jar-with-dependencies clean package -DskipTests

FROM flyway/flyway:latest
COPY --from=builder /build/jdbc/postgres/target/postgres-socket-factory-*-jar-with-dependencies.jar /flyway/drivers/
COPY flyway.toml /flyway/conf/
RUN mkdir /db-migration
COPY target/docker-build/db-migration /db-migration
```

`--platform=$BUILDPLATFORM` ensures the Maven build runs natively on the host. JARs are platform-independent and safely cross stages.

---

## Security Practices

- **Non-root users in all containers** — Each Dockerfile creates a dedicated user and switches before `CMD`
- **Minimal runtime images** — `python:3.12-slim-bookworm`, `nginx:1.28-alpine`, `flyway/flyway:latest`
- **Security headers in nginx** — `X-Frame-Options`, `X-XSS-Protection`, `X-Content-Type-Options`, `Referrer-Policy`
- **No secrets in images** — Credentials injected at runtime via environment variables and secrets
