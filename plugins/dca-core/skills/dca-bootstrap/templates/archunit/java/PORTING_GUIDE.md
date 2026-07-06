# Spock+Groovy → JUnit5+Java Porting Guide

This directory ships **only the canonical `BaseArchUnitTest.java.tmpl`** as a worked example.
The other 10 ArchUnit test classes are **translated on the fly by the dca-bootstrap skill**
when the user picks the `junit5-java` test style.

That choice is intentional: porting all 10 statically would mean ~3000 lines of duplicated
mechanical translation. Translating at install time follows the "skills are instructions, not
generators" principle and adapts to project-specific quirks.

## Translation rules

When generating `*ArchUnitTest.java.tmpl` from the corresponding `*ArchUnitTest.groovy.tmpl`:

### Class declaration
- `class FooTest extends BaseArchUnitTest` → `class FooTest extends BaseArchUnitTest`
- Drop `extends Specification` if still present (the Groovy templates already drop it via inheriting from `BaseArchUnitTest extends Specification`).
- Add `package {{basePackage}};` (with the trailing semicolon).
- No `@Test` import needed at template level — it's added per-method.

### Test methods
- Spock: `def "Aggregate Roots must implement AggregateRoot<T, ID>"() { expect: ... }`
- JUnit5: `@Test @DisplayName("Aggregate Roots must implement AggregateRoot<T, ID>") void aggregateRootsMustImplementAggregateRoot() { ... }`
- Method body: drop the `expect:` label (the body is just statements).
- ArchUnit's `.check(allClasses)` already throws on failure — no extra assertion needed.

### Closures → lambdas
- Groovy: `{ JavaClass jc -> jc.getName().endsWith("Foo") }`
- Java: `(JavaClass jc) -> jc.getName().endsWith("Foo")`
- For multi-line closures, wrap in `(jc) -> { ... return ...; }`.
- Predicates: `DescribedPredicate.describe("...", { jc -> ... })` → `DescribedPredicate.describe("...", (JavaClass jc) -> ...)`.

### Collections
- Groovy: `[a: 1, b: 2]` → Java: `Map.of("a", 1, "b", 2)` or explicit `HashMap`.
- Groovy: `[1, 2, 3]` → Java: `List.of(1, 2, 3)`.
- Groovy: `list.collect { it * 2 }` → Java: `list.stream().map(x -> x * 2).collect(toList())`.
- Groovy: `list.findAll { it > 0 }` → Java: `list.stream().filter(x -> x > 0).collect(toList())`.
- Groovy: `list.each { ... }` → Java: `for (X x : list) { ... }` or `list.forEach(x -> ...)`.

### Strings
- Groovy GString: `"${BASE_PACKAGE}.foo"` → Java: `BASE_PACKAGE + ".foo"`.
- Triple-quoted Groovy strings: keep as Java text blocks `"""..."""` (Java 15+).

### Static initialization
- Groovy `@Shared` field → Java `static` field, initialized either inline (if cheap) or in a `@BeforeAll static` method.
- The `allClasses` import in `BaseArchUnitTest.java.tmpl` is already done correctly in `@BeforeAll` — derived classes inherit it.

### `where:` blocks (parameterized tests)
- Replace with `@ParameterizedTest` + `@MethodSource` or `@ValueSource`.
- Example:
  ```groovy
  def "rule for #context"() {
    expect: ...
    where: context << ['product', 'cart', 'checkout']
  }
  ```
  becomes
  ```java
  @ParameterizedTest @ValueSource(strings = {"product", "cart", "checkout"})
  void ruleFor(String context) { ... }
  ```

### Type declarations
- Groovy `def x = ...` → Java `var x = ...` (or explicit type).
- Method return types: explicit in Java.
- `def x` in field positions → explicit `Object x` or proper type.

### Imports

Standard JUnit5 imports to add at the top of every translated test class:
```java
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
// for parameterized tests:
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;

// ArchUnit static imports already present in source — keep:
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;
```

### Modifiers
- Groovy doesn't require `public` on classes/methods — Java does (or use package-private).
- Groovy `protected static final` → Java `protected static final` (same syntax, but explicit).

## Critical rules for all ported tests

### `allowEmptyShould(true)` is mandatory

Every ArchUnit rule chain MUST include `.allowEmptyShould(true)` before `.check(allClasses)`. Since ArchUnit 1.4.0, rules fail by default when the `that()` predicate matches zero classes. In practice, this happens frequently:
- Bounded contexts with no domain events yet
- No DTOs, no REST controllers, no factories, etc.
- Shared kernel packages with no domain model classes

Without `allowEmptyShould(true)`, these produce false-positive `AssertionError` failures that look like skill bugs rather than architecture findings.

**Pattern:**
```java
noClasses()
    .that()
    .resideInAnyPackage(...)
    .should()
    .dependOnClassesThat()
    .resideInAPackage(...)
    .because("reason")
    .allowEmptyShould(true)    // <-- ALWAYS add this
    .check(allClasses);
```

### Use shared-kernel-aware helpers for adapter checks

When porting rules that check `*Response`, `*Resource`, or other adapter-incoming patterns:
prefer `allIncomingAdapterPatterns()` over manual `discoverBoundedContextPackages()` mapping.
The helper includes the `@SharedKernel`-annotated module's adapter package automatically —
necessary because cross-cutting Response/error/base classes often live in the shared module
(e.g. `ErrorResponse`, generic `Response`). The same applies to `allOutgoingAdapterPatterns()`
for outgoing-adapter rules.

```java
// PREFER:
.should().resideInAnyPackage(allIncomingAdapterPatterns())

// AVOID (misses shared-kernel adapter):
.should().resideInAnyPackage(
    discoverBoundedContextPackages().keySet().stream()
        .map(p -> p + ".adapter.in..")
        .toArray(String[]::new))
```

### Short-form constant aliases

The Groovy templates use short names like `DOMAIN_MODEL_PACKAGE`, `APPLICATION_PACKAGE`, `ADAPTER_PACKAGE`, `INCOMING_ADAPTER_PACKAGE`, `OUTGOING_ADAPTER_PACKAGE`. The Java `BaseArchUnitTest.java.tmpl` defines these as `*_PATTERN` suffixed names. Short-form aliases are provided — use the short names in ported tests to stay consistent with the Groovy originals.

### Multi-module ImportOption

The BaseArchUnitTest uses custom `ImportOption` implementations (`DoNotIncludeTestCode`, `OnlyProjectJars`) instead of `DO_NOT_INCLUDE_JARS`/`DO_NOT_INCLUDE_ARCHIVES`. If a Groovy template creates its own `ClassFileImporter` (e.g., `OnionArchitectureArchUnitTest`, `LayeredArchitectureArchUnitTest`), **do not port that** — replace it with the shared `allClasses` instance from BaseArchUnitTest.

### `discoverBoundedContextPackages()` return type

The Groovy templates use `Map<String, ?>` or `Map<String, BOUNDED_CONTEXT_ANNOTATION>`. In Java, use `Map<String, BoundedContext>` — the method returns typed `BoundedContext` annotation instances. When iterating, you can call `.name()` on the value to get the context's display name.

### `package-info.java` for bounded context discovery

The `discoverBoundedContextPackages()` method finds bounded contexts by looking for `@BoundedContext` annotations on `package-info.java` files. These must exist in each bounded context's root package. If the project doesn't have them yet, the dca-bootstrap skill creates them in Phase 3.

## Per-test notes

### `BaseArchUnitTest.java.tmpl` (canonical, already translated)
- Verifies the configuration block, derived patterns, discovery utilities, and import setup.
- Other tests rely on its constants and helper methods.

### `PackageCyclesArchUnitTest`
- Trivial port: 4 `slices().matching(...).should().beFreeOfCycles()` calls. Each becomes a `@Test` method.

### `HexagonalArchitectureArchUnitTest`, `LayeredArchitectureArchUnitTest`, `OnionArchitectureArchUnitTest`, `NamingConventionsArchUnitTest`
- Straight rule chains. Each `def "..."() { expect: ... }` → `@Test @DisplayName("...")`.
- **7 rules missing `allowEmptyShould(true)` in the Groovy source** — add it to every rule during porting.
- Uses short-form constants (`DOMAIN_MODEL_PACKAGE`, `APPLICATION_PACKAGE`, etc.) — these are aliases defined in BaseArchUnitTest.

### `DddTacticalPatternsArchUnitTest`, `DddAdvancedPatternsArchUnitTest`
- Several rules iterate over `allClasses` and inspect fields/types using closures. Convert closures to lambdas; iteration becomes `for (JavaClass jc : allClasses) { ... }`.
- Watch for `it.isAssignableTo(SOME_MARKER)` — already uses constants from the base class, so no adaptation needed.

### `DddStrategicPatternsArchUnitTest`
- The `discoverBoundedContextPackages()` calls and the dynamic for-each over context pairs need to be rewritten as nested for-loops in Java (Groovy uses `each` and Map iteration ergonomics).
- References `OPEN_HOST_SERVICE_ANNOTATION` — this constant is defined in BaseArchUnitTest.
- Uses `IntegrationEvent` directly in two rules — replace with `INTEGRATION_EVENT_MARKER` constant.
- Has a local `extractContextName()` helper — this is now in BaseArchUnitTest, so omit the local definition.

### `UseCasePatternsArchUnitTest`
- Naming-rule heavy. Translate string suffix predicates directly.

### Templates with hardcoded bounded context names
The Groovy templates for `OnionArchitectureArchUnitTest`, `LayeredArchitectureArchUnitTest`, and `UseCasePatternsArchUnitTest` contain hardcoded bounded context package arrays (e.g., `product`, `cart`, `checkout`...). During porting, **replace these with `discoverBoundedContextPackages()` calls**. Never hardcode context names — they are project-specific.

### Templates with separate ClassFileImporter
`OnionArchitectureArchUnitTest.groovy.tmpl` and `LayeredArchitectureArchUnitTest.groovy.tmpl` create their own `ClassFileImporter` with only `DO_NOT_INCLUDE_TESTS`. During porting, remove this and use the inherited `allClasses` field from BaseArchUnitTest instead.

### `SpringModulithVerificationTest`
- Trivial port: load `ApplicationModules.of(BASE_PACKAGE)` in `@BeforeAll`, then `@Test void verify() { modules.verify(); }`.

## After translation

The bootstrap skill MUST run a syntactic sanity check before declaring success:
```bash
./gradlew compileTestArchitectureJava   # or equivalent
```
Compile errors in any translated file are a porting bug — fix and retry.
