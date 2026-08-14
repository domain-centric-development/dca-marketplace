---
type: Rule
title: Repository Implementations must reside in portadapter.outgoing package
rule: "Repository implementations are secondary adapters (outgoing ports)."
constraint: Repository Implementations must reside in portadapter.outgoing package.
enforced_by: "HexagonalArchitectureArchUnitTest#Repository Implementations must reside in portadapter.outgoing package"
status: enforced
test_class: HexagonalArchitectureArchUnitTest
tags: [hexagonal, archunit]
---

```groovy
expect:
ArchRuleDefinition.classes()
  .that().haveSimpleNameEndingWith("Repository")
  .and().areNotInterfaces()
  .should().resideInAPackage(OUTGOING_ADAPTER_PACKAGE)
  .because("Repository implementations are secondary adapters (outgoing ports)")
  .check(allClasses)
```

## Applies to markers

- [Repository<T, ID>](/marker/port-out/repository.md)
