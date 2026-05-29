# Java / Cucumber

## Project Structure

```
src/test/
├── resources/
│   └── features/
│       └── domain_feature.feature        # Gherkin feature files
└── java/com/example/
    ├── steps/
    │   └── DomainFeatureSteps.java       # One step class per feature file
    ├── hooks/
    │   └── TestHooks.java                # @Before/@After hooks
    └── CucumberTestRunner.java           # JUnit runner configuration
```

One step class per feature file. Name the step class to match its feature file (e.g., `wine_classification.feature` → `WineClassificationSteps.java`).

---

## Maven Dependencies

```xml
<!-- pom.xml -->
<dependencies>
    <dependency>
        <groupId>io.cucumber</groupId>
        <artifactId>cucumber-java</artifactId>
        <version>${cucumber.version}</version>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>io.cucumber</groupId>
        <artifactId>cucumber-junit-platform-engine</artifactId>
        <version>${cucumber.version}</version>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>com.h2database</groupId>
        <artifactId>h2</artifactId>
        <scope>test</scope>
    </dependency>
</dependencies>
```

---

## Test Runner

```java
// CucumberTestRunner.java
import org.junit.platform.suite.api.ConfigurationParameter;
import org.junit.platform.suite.api.IncludeEngines;
import org.junit.platform.suite.api.SelectClasspathResource;
import org.junit.platform.suite.api.Suite;

import static io.cucumber.junit.platform.engine.Constants.GLUE_PROPERTY_NAME;
import static io.cucumber.junit.platform.engine.Constants.PLUGIN_PROPERTY_NAME;

@Suite
@IncludeEngines("cucumber")
@SelectClasspathResource("features")
@ConfigurationParameter(key = GLUE_PROPERTY_NAME, value = "com.example.steps,com.example.hooks")
@ConfigurationParameter(key = PLUGIN_PROPERTY_NAME, value = "pretty, html:target/cucumber-reports.html")
public class CucumberTestRunner {
}
```

---

## Test Hooks

Use Cucumber hooks for database setup/teardown. The H2 in-memory database replaces the production database so tests run without a database server. One-time setup uses `@BeforeAll` so the framework manages the lifecycle — no static flags needed:

```java
// hooks/TestHooks.java
import io.cucumber.java.Before;
import io.cucumber.java.BeforeAll;
import io.cucumber.java.After;
import jakarta.persistence.EntityManager;
import jakarta.persistence.EntityManagerFactory;
import jakarta.persistence.Persistence;
import java.util.Map;

public class TestHooks {

    private static EntityManagerFactory emf;
    private EntityManager em;

    @BeforeAll
    public static void setUpFactory() {
        emf = Persistence.createEntityManagerFactory("test", Map.of(
            "jakarta.persistence.jdbc.url", "jdbc:h2:mem:testdb;DB_CLOSE_DELAY=-1",
            "jakarta.persistence.jdbc.driver", "org.h2.Driver",
            "hibernate.hbm2ddl.auto", "create-drop"
        ));
    }

    @Before
    public void setUp() {
        em = emf.createEntityManager();
        em.getTransaction().begin();
        ScenarioContext.setEntityManager(em);
    }

    @After
    public void tearDown() {
        if (em != null) {
            em.getTransaction().rollback();
            em.close();
        }
    }
}
```

---

## Scenario Context

Share state between step classes using a thread-safe context holder:

```java
// hooks/ScenarioContext.java
import jakarta.persistence.EntityManager;
import java.util.HashMap;
import java.util.Map;

public class ScenarioContext {

    private static final ThreadLocal<Map<String, Object>> CONTEXT =
        ThreadLocal.withInitial(HashMap::new);

    public static void set(String key, Object value) {
        CONTEXT.get().put(key, value);
    }

    @SuppressWarnings("unchecked")
    public static <T> T get(String key, Class<T> type) {
        return (T) CONTEXT.get().get(key);
    }

    public static void setEntityManager(EntityManager em) {
        set("entityManager", em);
    }

    public static EntityManager getEntityManager() {
        return get("entityManager", EntityManager.class);
    }

    public static void clear() {
        CONTEXT.get().clear();
    }
}
```

---

## Running Tests

```bash
# Run all local tests (excludes @integration-test)
mvn test -Dcucumber.filter.tags="not @integration-test"

# Run only integration tests
mvn test -Dcucumber.filter.tags="@integration-test"

# Run a specific feature
mvn test -Dcucumber.features="src/test/resources/features/wine_classification.feature"
```

---

## Step Definition Patterns

### Singular/Plural Step Variants

```java
@Then("^(\\d+) wines? (?:is|are) returned$")
public void assertWineCount(int count) {
    assertEquals(count, wines.size());
}
```

### Optional Columns in Data Tables

```java
@Given("a wine with the following attributes")
public void buildWine(DataTable table) {
    Map<String, String> row = table.asMaps().get(0);
    Wine.Builder builder = Wine.builder();

    if (row.containsKey("vineyard")) builder.vineyard(row.get("vineyard"));
    if (row.containsKey("name"))     builder.name(row.get("name"));
    if (row.containsKey("year"))     builder.year(Integer.parseInt(row.get("year")));
    if (row.containsKey("region"))   builder.region(row.get("region"));
    if (row.containsKey("varietal")) builder.varietal(row.get("varietal"));

    wine = builder.build();
}
```

### Caching Expensive Calls

Store the cache in a static `ConcurrentHashMap` so it's shared across scenarios within the test run and handles parallel execution safely:

```java
private static final Map<String, TastingNotes> TASTING_CACHE = new ConcurrentHashMap<>();

@When("tasting notes are generated")
public void generateTastingNotes() throws Exception {
    byte[] labelBytes = ScenarioContext.get("wineLabelBytes", byte[].class);
    String hash = sha256(labelBytes);

    TastingNotes notes = TASTING_CACHE.computeIfAbsent(hash, k -> {
        SommelierService sommelier = ScenarioContext.get("sommelier", SommelierService.class);
        return sommelier.generateNotes(labelBytes);
    });

    ScenarioContext.set("tastingNotes", notes);
}
```

### Fuzzy Assertions

```java
import org.apache.commons.text.similarity.LevenshteinDistance;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import static org.junit.jupiter.api.Assertions.fail;

public class FuzzyAssertions {

    private static final Logger log = LoggerFactory.getLogger(FuzzyAssertions.class);

    public static void assertFuzzyMatch(String expected, String actual) {
        assertFuzzyMatch(expected, actual, 0.75, 0.50);
    }

    public static void assertFuzzyMatch(String expected, String actual,
                                         double strictThreshold, double warnThreshold) {
        int maxLen = Math.max(expected.length(), actual.length());
        if (maxLen == 0) return;

        int distance = LevenshteinDistance.getDefaultInstance().apply(expected, actual);
        double ratio = 1.0 - ((double) distance / maxLen);

        if (ratio >= strictThreshold) {
            // close enough
        } else if (ratio >= warnThreshold) {
            log.warn("Fuzzy match {:.2f} for '{}' vs '{}'", ratio, expected, actual);
        } else {
            fail(String.format("Match ratio %.2f too low for '%s' vs '%s'", ratio, expected, actual));
        }
    }
}
```

Usage in step definitions:

```java
@Then("the tasting note describes {string}")
public void assertTastingNote(String expected) {
    TastingNotes notes = ScenarioContext.get("tastingNotes", TastingNotes.class);
    FuzzyAssertions.assertFuzzyMatch(expected, notes.getSummary());
}
```

### Assertion Messages

```java
assertTrue(result.isValid(),
    "Expected valid but got errors: " + result.getErrors());
assertNotNull(wine,
    "Could not find wine for query '" + query + "'!");
```
