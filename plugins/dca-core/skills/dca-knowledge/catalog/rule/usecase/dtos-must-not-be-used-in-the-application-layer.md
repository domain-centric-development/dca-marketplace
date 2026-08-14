---
type: Rule
title: DTOs must not be used in the Application Layer
rule: "Application layer should use Command/Query/Response models, not presentation DTOs (Clean Architecture)."
constraint: DTOs must not be used in the Application Layer.
enforced_by: "UseCasePatternsArchUnitTest#DTOs must not be used in the Application Layer"
status: enforced
test_class: UseCasePatternsArchUnitTest
tags: [usecase, archunit]
---

```groovy
expect:
noClasses()
  .that().resideInAnyPackage(PRODUCT_APPLICATION_PACKAGE, CART_APPLICATION_PACKAGE, CHECKOUT_APPLICATION_PACKAGE, ACCOUNT_APPLICATION_PACKAGE, INVENTORY_APPLICATION_PACKAGE, PRICING_APPLICATION_PACKAGE, BACKOFFICE_APPLICATION_PACKAGE)
  .should().dependOnClassesThat().haveSimpleNameEndingWith("Dto")
  .because("Application layer should use Command/Query/Response models, not presentation DTOs (Clean Architecture)")
  .allowEmptyShould(true)
  .check(allClasses)
```
