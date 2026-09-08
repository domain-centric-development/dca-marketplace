# Greenfield Java build: Spring Boot 4 on Gradle

What a fresh Spring Boot 4 build needs before the DCA packages go in. Training data knows Boot 3
builds; several of those habits fail or mislead on Boot 4. Every coordinate below was checked
against Maven Central for Boot `4.0.x` — re-check the version at bootstrap time as always, the
artifact names are stable within the 4.x line.

## Plugins

`org.springframework.boot` is the only Gradle plugin a Boot 4 build needs. Both it and
`io.spring.dependency-management` are resolved by `plugins { id ... version ... }` through Gradle's
plugin marker artifacts, which Spring publishes to the Gradle Plugin Portal **and** to Maven Central —
either repository in `pluginManagement { repositories { ... } }` works, the default (Plugin Portal)
included. Do not add them as `buildscript` classpath dependencies.

Prefer to leave the dependency-management plugin out and import Boot's BOM as a Gradle platform
instead — one plugin less, plain Gradle dependency semantics, and the BOM version follows the plugin:

```groovy
// build.gradle (Groovy DSL)
plugins {
  id 'java'
  id 'org.springframework.boot' version '{{springBootVersion}}'
}

dependencies {
  implementation platform(org.springframework.boot.gradle.plugin.SpringBootPlugin.BOM_COORDINATES)
  implementation 'org.springframework.boot:spring-boot-starter-webmvc'
  // ...
}
```

```kotlin
// build.gradle.kts (Kotlin DSL)
import org.springframework.boot.gradle.plugin.SpringBootPlugin

plugins {
  java
  id("org.springframework.boot") version "{{springBootVersion}}"
}

dependencies {
  implementation(platform(SpringBootPlugin.BOM_COORDINATES))
  implementation("org.springframework.boot:spring-boot-starter-webmvc")
  // ...
}
```

A project that already uses `io.spring.dependency-management` keeps it — it is not wrong, just not
required. Do not install both mechanisms.

With the platform on `implementation`, every configuration that extends it inherits the managed
versions. The `test-architecture.gradle` template's `testArchitectureImplementation` does
(`extendsFrom(implementation)`), so `org.junit.jupiter:junit-jupiter` may be declared **without**
`{{junitVersion}}` there; keep the explicit version only when no Boot BOM is in play.

## Starters that Boot 4 renamed or split

| Need | Boot 3 habit | Boot 4 |
|---|---|---|
| Spring MVC | `spring-boot-starter-web` | `spring-boot-starter-webmvc` (`spring-boot-starter-web` still exists in 4.0, marked deprecated in favour of the new name) |
| `@Transactional` on use cases without a data starter | came transitively | `org.springframework:spring-tx` must be declared — no web starter brings it. `DCA-USE-012` demands the annotation on every use case that publishes events, so a greenfield project hits this before it has persistence |
| Test core: JUnit 5, AssertJ, Mockito, `@SpringBootTest`, `@MockitoBean` | `spring-boot-starter-test` | `spring-boot-starter-test` — unchanged, but it no longer carries the slice annotations |
| MVC slice: `@WebMvcTest`, `@AutoConfigureMockMvc`, `MockMvc`, `MockMvcTester` | in `spring-boot-starter-test` | `spring-boot-starter-webmvc-test` |
| JDBC slice: `@JdbcTest` | in `spring-boot-starter-test` | `spring-boot-starter-jdbc-test` |
| JPA slice: `@DataJpaTest` | in `spring-boot-starter-test` | `spring-boot-starter-data-jpa-test` |

The pattern: one `spring-boot-starter-<technology>-test` per slice, on top of `spring-boot-starter-test`.

## Slice annotations moved packages

The technology-specific test annotations now live under the technology's own package, not under
`org.springframework.boot.test.autoconfigure.*`:

| Annotation | Boot 3 package | Boot 4 package |
|---|---|---|
| `@SpringBootTest` | `org.springframework.boot.test.context` | unchanged |
| `@WebMvcTest`, `@AutoConfigureMockMvc` | `org.springframework.boot.test.autoconfigure.web.servlet` | `org.springframework.boot.webmvc.test.autoconfigure` |
| `@JdbcTest`, `@AutoConfigureJdbc` | `org.springframework.boot.test.autoconfigure.jdbc` | `org.springframework.boot.jdbc.test.autoconfigure` |
| `@DataJpaTest` | `org.springframework.boot.test.autoconfigure.orm.jpa` | `org.springframework.boot.data.jpa.test.autoconfigure` |
| `@MockitoBean` (replaces `@MockBean`) | — | `org.springframework.test.context.bean.override.mockito` (Spring Framework) |

A controller slice test for a server-rendered page controller, Boot 4 imports:

```java
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(TaskPage.class)
class TaskPageTest {
  @Autowired MockMvc mockMvc;
  @MockitoBean CreateTaskInputPort createTask;
  // ...
}
```

The `@WebMvcTest` slice needs a view resolver only when a view is rendered; a controller returning a
view name whose path equals the request path fails with a circular-view-path `ServletException` — name
views by content (`task-list`), not by URL.

## Minimal greenfield `build.gradle` with DCA

```groovy
plugins {
  id 'java'
  id 'org.springframework.boot' version '{{springBootVersion}}'
}

java {
  toolchain { languageVersion = JavaLanguageVersion.of({{javaVersion}}) }
}

repositories {
  mavenCentral()
}

apply from: "gradle/plugins/test-architecture.gradle"   // from templates/gradle/

dependencies {
  implementation platform(org.springframework.boot.gradle.plugin.SpringBootPlugin.BOM_COORDINATES)
  implementation 'org.springframework.boot:spring-boot-starter-webmvc'
  implementation 'org.springframework:spring-tx'
  implementation 'dev.domaincentric:dca-building-blocks:{{dcaJavaVersion}}'

  testImplementation 'org.springframework.boot:spring-boot-starter-test'
  testImplementation 'org.springframework.boot:spring-boot-starter-webmvc-test'
  testRuntimeOnly 'org.junit.platform:junit-platform-launcher'
}

tasks.withType(Test).configureEach { useJUnitPlatform() }
```

`dca-archunit` enters through the `test-architecture.gradle` template, not here. This exact build,
with one bounded context (aggregate, use case, repository port and in-memory adapter, page controller
named `*Page` and `withControllerSuffix("Page")` in the layout), runs the full catalog green and the
`@WebMvcTest` slice test with it.
