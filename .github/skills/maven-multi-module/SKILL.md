---
name: "maven-multi-module"
description: "Patterns for Maven multi-module project structure unifying Python/Habushu and Flutter/Dart builds. Covers root POM configuration, Habushu Python module setup, Flutter exec-maven-plugin integration, lifecycle phase mappings, and build commands. Use when creating a new service module, adding a UI module, or configuring the build lifecycle."
metadata:
  tags: default
---

# Maven Multi-Module Patterns

## Module Hierarchy

```
{project-name}/                              # Root POM (pom packaging)
├── {project-name}-service/                  # Python/FastAPI backend (habushu packaging)
├── {project-name}-ui/                       # Flutter/Dart frontend (pom packaging)
├── {project-name}-docker/                   # Docker build parent (pom packaging)
│   ├── {project-name}-service-docker/       # Service container (docker packaging)
│   ├── {project-name}-web-ui-docker/        # Optional: nginx + pre-built Flutter web bundle
│   └── {project-name}-db-migration-docker/  # Flyway migration container (docker packaging)
└── db-migration/                            # Flyway SQL scripts (not a Maven module)
```

---

## Root POM

Centralizes plugin version management. Child modules inherit consistent tooling.

```xml
<project>
    <groupId>com.example.{project-name}</groupId>
    <version>0.1.0-SNAPSHOT</version>
    <artifactId>{project-name}</artifactId>
    <packaging>pom</packaging>

    <modules>
        <module>{project-name}-ui</module>
        <module>{project-name}-service</module>
        <module>{project-name}-docker</module>
    </modules>

    <build>
        <pluginManagement>
            <plugins>
                <plugin>
                    <groupId>org.technologybrewery.habushu</groupId>
                    <artifactId>habushu-maven-plugin</artifactId>
                    <extensions>true</extensions>
                    <version>3.2.0</version>
                    <configuration>
                        <pythonVersion>3.12.9</pythonVersion>
                    </configuration>
                </plugin>
                <plugin>
                    <groupId>io.fabric8</groupId>
                    <artifactId>docker-maven-plugin</artifactId>
                    <version>0.46.0</version>
                    <extensions>true</extensions>
                </plugin>
                <plugin>
                    <artifactId>maven-resources-plugin</artifactId>
                    <version>3.3.1</version>
                </plugin>
                <plugin>
                    <groupId>org.codehaus.mojo</groupId>
                    <artifactId>exec-maven-plugin</artifactId>
                    <version>3.5.1</version>
                </plugin>
                <plugin>
                    <!-- Most modules skip deploy. Docker modules opt in explicitly. -->
                    <artifactId>maven-deploy-plugin</artifactId>
                    <version>3.1.4</version>
                    <configuration>
                        <skip>true</skip>
                    </configuration>
                </plugin>
            </plugins>
        </pluginManagement>
    </build>
</project>
```

**Key decisions:**
- `maven-deploy-plugin` skips by default — only Docker modules that push to a registry opt in with `<skip>false</skip>`
- `habushu-maven-plugin` with `<extensions>true</extensions>` — registers `habushu` packaging type so Maven recognizes it in child modules and dependency declarations
- `docker-maven-plugin` with `<extensions>true</extensions>` — registers `docker` packaging type

---

## Python/Habushu Module

`habushu` packaging wraps `uv` within Maven's lifecycle. Maps Maven phases to Python tooling.

```xml
<project>
    <parent>
        <groupId>com.example.{project-name}</groupId>
        <version>0.1.0-SNAPSHOT</version>
        <artifactId>{project-name}</artifactId>
    </parent>

    <artifactId>{project-name}-service</artifactId>
    <packaging>habushu</packaging>

    <build>
        <plugins>
            <plugin>
                <groupId>org.technologybrewery.habushu</groupId>
                <artifactId>habushu-maven-plugin</artifactId>
                <configuration>
                    <behaveOptions>--tags=-integration-test</behaveOptions>
                    <skipDeploy>true</skipDeploy>
                    <lint>false</lint>
                </configuration>
            </plugin>
        </plugins>
    </build>

    <profiles>
        <profile>
            <id>run-habushu-its</id>
            <build>
                <plugins>
                    <plugin>
                        <groupId>org.technologybrewery.habushu</groupId>
                        <artifactId>habushu-maven-plugin</artifactId>
                        <executions>
                            <execution>
                                <id>run-integration-tests</id>
                                <phase>integration-test</phase>
                                <goals>
                                    <goal>run-command-in-virtual-env</goal>
                                </goals>
                                <configuration>
                                    <runCommandArgs>behave ${project.basedir}/tests/features
                                        --format=kappa_maki.kappa_maki_formatter:PrettyCucumberJSONFormatter
                                        --outfile=${project.build.directory}/cucumber-reports/cucumber.json
                                        --format=progress2 --no-skipped --no-capture --no-capture-stderr --no-logcapture
                                        --tags=integration-test</runCommandArgs>
                                </configuration>
                            </execution>
                        </executions>
                    </plugin>
                </plugins>
            </build>
        </profile>
    </profiles>
</project>
```

**Behave BDD test strategy:**
- Default build (`mvn clean install`) — excludes `@integration-test` tagged features via `--tags=-integration-test`
- Integration tests (`mvn clean verify -Prun-habushu-its`) — activates `run-habushu-its` profile to run `@integration-test` scenarios during `integration-test` phase
- `kappa_maki` formatter produces Cucumber-compatible JSON for CI dashboards

**Python project layout expected by Habushu:**
```
{project-name}-service/
├── pom.xml
├── pyproject.toml         # Dependencies managed by uv
├── uv.lock
├── src/
│   └── {project_name}_service/
└── tests/
    └── features/          # Behave BDD feature files
```

---

## Flutter/Maven Module

`pom` packaging with `exec-maven-plugin` for Flutter project setup and code generation.

Platform package builds (web/mobile) are intentionally run with direct Flutter CLI commands, not mapped into Maven phases.

```xml
<project>
    <artifactId>{project-name}-ui</artifactId>
    <packaging>pom</packaging>

    <build>
        <plugins>
            <plugin>
                <groupId>org.codehaus.mojo</groupId>
                <artifactId>exec-maven-plugin</artifactId>
                <configuration>
                    <!-- Working directory points into the Flutter project subdirectory -->
                    <workingDirectory>${project.basedir}/{project_name}_ui</workingDirectory>
                </configuration>
                <executions>
                    <execution>
                        <id>flutter-clean</id>
                        <phase>clean</phase>
                        <goals><goal>exec</goal></goals>
                        <configuration>
                            <executable>flutter</executable>
                            <arguments><argument>clean</argument></arguments>
                        </configuration>
                    </execution>
                    <execution>
                        <id>flutter-pub-get</id>
                        <phase>initialize</phase>
                        <goals><goal>exec</goal></goals>
                        <configuration>
                            <executable>flutter</executable>
                            <arguments><argument>pub</argument><argument>get</argument></arguments>
                        </configuration>
                    </execution>
                    <execution>
                        <id>dart-code-generator</id>
                        <phase>generate-sources</phase>
                        <goals><goal>exec</goal></goals>
                        <configuration>
                            <executable>dart</executable>
                            <arguments>
                                <argument>run</argument>
                                <argument>build_runner</argument>
                                <argument>build</argument>
                                <argument>--delete-conflicting-outputs</argument>
                            </arguments>
                        </configuration>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>
</project>
```

### Phase Mapping

| Maven Phase | Flutter/Dart Command | Purpose |
|-------------|----------------------|---------|
| `clean` | `flutter clean` | Remove build artifacts |
| `initialize` | `flutter pub get` | Resolve Dart dependencies |
| `generate-sources` | `dart run build_runner build` | Generate Freezed, Riverpod, JSON code |

### Flutter Package Builds (Recommended via Flutter CLI)

Use Flutter CLI directly for platform-specific packages. `FLUTTER_FLAVOR` controls the build variant (e.g., `dev`, `staging`, `prod`).

```bash
export FLUTTER_FLAVOR=dev  # or staging, prod
export PROJECT_SERVICE_URL=https://your-service-url

# Web: --flavor is unsupported on web; pass FLAVOR as a dart-define so Dart can read it
# at compile time via String.fromEnvironment('FLAVOR')
flutter build web --wasm --release \
    --dart-define=FLAVOR=$FLUTTER_FLAVOR \
    --dart-define=HTTP_SERVICE_URL="${PROJECT_SERVICE_URL}"

# Android / iOS: --flavor sets the built-in appFlavor variable automatically;
# no --dart-define=FLAVOR needed
flutter build appbundle --flavor=$FLUTTER_FLAVOR --release \
    --dart-define=HTTP_SERVICE_URL="${PROJECT_SERVICE_URL}"

flutter build ipa --flavor=$FLUTTER_FLAVOR --release \
    --dart-define=HTTP_SERVICE_URL="${PROJECT_SERVICE_URL}"
```

**`--flavor` vs `--dart-define=FLAVOR`:**
- `FLUTTER_FLAVOR` is a **shell variable** — it holds the flavor name you want to build (`dev`, `staging`, `prod`) and is used when constructing the CLI commands above
- `--flavor` (iOS/Android only) drives native Android product flavors / iOS schemes and automatically sets the built-in Dart `appFlavor` compile-time variable
- `--dart-define=FLAVOR=` explicitly bakes the flavor name into the binary as a compile-time constant, readable in Dart via `String.fromEnvironment('FLAVOR')` — required for web (no `--flavor` support) and consumed by the app's flavor resolution logic at startup
- All `--dart-define` values are **compile-time** constants, not runtime config — they are embedded in the binary at build time and cannot change after the build

### Flutter Directory Layout

```
{project-name}-ui/
├── pom.xml
└── {project_name}_ui/          # Flutter project root (workingDirectory)
    ├── pubspec.yaml
    ├── lib/
    └── build/web/              # Generated when running `flutter build web` (used by optional web-ui Docker module)
```

---

## Build Commands

```bash
# Full build: backend + shared orchestration tasks
mvn clean install

# Build Flutter packages directly via Flutter CLI (recommended)
flutter build web --wasm --release --dart-define=FLAVOR=$FLUTTER_FLAVOR --dart-define=HTTP_SERVICE_URL="${PROJECT_SERVICE_URL}"
flutter build appbundle --flavor=$FLUTTER_FLAVOR --release --dart-define=HTTP_SERVICE_URL="${PROJECT_SERVICE_URL}"
flutter build ipa --flavor=$FLUTTER_FLAVOR --release --dart-define=HTTP_SERVICE_URL="${PROJECT_SERVICE_URL}"

# Run integration tests
mvn clean verify -Prun-habushu-its

# Build and push Docker artifacts for an environment profile
mvn clean install deploy -Pstaging
mvn clean install deploy -Pprod

# Rebuild a single module
mvn clean install -pl {project-name}-service
```
