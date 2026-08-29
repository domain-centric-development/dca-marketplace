---
type: Rule
id: DCA-TAC-015
title: Repository Implementations must reside in adapter.outgoing package
rule: Repository implementations are outgoing adapters in bounded contexts.
constraint: Repository Implementations must reside in adapter.outgoing package.
enforced_by: "TacticalPatternRules#DCA-TAC-015"
status: enforced
rule_set: tactical
implementations: [java]
tags: [tactical, archunit]
---

```java
DcaRule.of(
    "DCA-TAC-015",
    "Repository Implementations must reside in adapter.outgoing package",
    "Repository implementations are outgoing adapters in bounded contexts",
    arch ->
        classes()
            .that()
            .areNotInterfaces()
            .and()
            .areAssignableTo(Repository.class)
            .should()
            .resideInAPackage(layout.outgoingAdapterPattern())
            .allowEmptyShould(true))
```

## Applies to markers

- [Repository<T, ID>](/marker/port-out/repository.md)
