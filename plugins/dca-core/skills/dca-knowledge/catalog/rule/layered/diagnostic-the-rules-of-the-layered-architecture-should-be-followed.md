---
type: Rule
id: DCA-LAY-001
title: "Diagnostic: The rules of the Layered Architecture should be followed"
rule: "Traditional layering (application accessed only by incoming adapters) contradicts Ports and Adapters, where outgoing adapters implement application-level output ports; the hexagonal rules cover the intended dependency direction."
constraint: "Diagnostic: The rules of the Layered Architecture should be followed."
enforced_by: "LayeredRules#DCA-LAY-001"
status: informational
rule_set: layered
implementations: [java]
tags: [layered, archunit]
---

```java
DcaRule.check(
    "DCA-LAY-001",
    "Diagnostic: The rules of the Layered Architecture should be followed",
    "Traditional layering (application accessed only by incoming adapters) contradicts Ports"
        + " and Adapters, where outgoing adapters implement application-level output ports;"
        + " the hexagonal rules cover the intended dependency direction",
    arch -> {})
```
