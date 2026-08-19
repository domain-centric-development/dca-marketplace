---
type: Rule
title: Domain must not have dependencies on Infrastructure
rule: "Domain should not depend on infrastructure concerns (Dependency Inversion Principle)."
constraint: Domain must not have dependencies on Infrastructure.
enforced_by: "LayeredArchitectureArchUnitTest#Domain must not have dependencies on Infrastructure"
status: enforced
test_class: LayeredArchitectureArchUnitTest
tags: [layered, archunit]
---

```groovy
expect:
noClasses()
  .that().resideInAnyPackage(DOMAIN_PACKAGE)
  .should().dependOnClassesThat().resideInAPackage(INFRASTRUCTURE_PACKAGE)
  .because("Domain should not depend on infrastructure concerns (Dependency Inversion Principle)")
  .check(allClasses)
```
