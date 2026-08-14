---
type: Rule
title: Converters must reside in portadapter package
rule: Converters/Mappers translate between layers and should be in adapters.
constraint: Converters must reside in portadapter package.
enforced_by: "NamingConventionsArchUnitTest#Converters must reside in portadapter package"
status: enforced
test_class: NamingConventionsArchUnitTest
tags: [naming, archunit]
---

```groovy
expect:
classes()
  .that().haveSimpleNameEndingWith("Converter")
  .and().resideInAnyPackage(BASE_PACKAGE + "..")
  .should().resideInAPackage(ADAPTER_PACKAGE)
  .because("Converters/Mappers translate between layers and should be in adapters")
  .allowEmptyShould(true)
  .check(allClasses)
```
