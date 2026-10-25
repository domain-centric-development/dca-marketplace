# Glossary — Bounded Context: spec

What holds: the living spec of a project, per context and feature, each criterion proven by one test. It knows no
story, no epic and no way of delivery — two implementations of the same backlog end in the same spec. Delivery hands
it a story's criteria and the plan's delta; spec merges them.

Code: `dca_factory/spec/`.

---

### Living spec (spec)

**Definition:** Every context's `scenarios.md` per feature under the project's spec folder, and `journeys.md`: what
the product does, written by the gate that delivers and by nothing else.

**Type:** Concept

### Feature (feature)

**Definition:** A lasting term of a context's language, a folder of the spec and a glossary entry `Type: Feature`;
born in a story's plan.

**Type:** Concept

### Rule (rule)

**Definition:** A heading `### Rule:` that groups criteria within a feature; renamed only by a plan's delta.

**Type:** Concept

### Criterion (criterion)

**Definition:** One statement of what holds, under its key — unique across the context — with exactly one `Test:`
line. No state, no story id, no happy-path mark.

**Type:** Value Object

**Identity:** its key (`CriterionKey`)

### Scenario (scenario)

**Definition:** A criterion written as given / when / then.

**Type:** Concept

### Test line (Test:)

**Definition:** The test that proves a criterion, written by the gate alone once it ran red and then green.

**Type:** Value Object

### Journey (journey)

**Definition:** An end-to-end path the spec keeps in `journeys.md`, with the test that proves it.

**Type:** Concept

**Operations:** prove (`proven`) — asked by delivery: is journey X there and proven?

### Delta (delta)

**Definition:** What a plan changes in the spec: criteria added, changed, removed, moved, renamed.

**Type:** Concept

**Operations:** merge (`merge`) — the delta merged into what holds
