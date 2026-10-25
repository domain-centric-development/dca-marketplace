# Glossary — Bounded Context: discovery

Which problem is worth solving and how anyone will know it got better — before anything is planned. Discovery writes a
report and proposes epics; a person releases a proposal, and delivery takes it from there. It never edits the backlog
or the description itself.

Code: `dca_factory/discovery/`.

---

### Topic (topic)

**Definition:** What a discovery is about, the name of its folder under the project's discovery place.

**Type:** Concept

### Report (discovery.md)

**Definition:** One discovery's findings: the problem, the users and the evidence about them, the options with their
risks, the outcome to observe, and the proposed work — every statement citing its source.

**Type:** Concept

### Problem · Option · Outcome · Evidence · Source

**Definition:** The report's sections: the problem apart from its solution; the ways to solve it, each with its risk;
the change anyone could observe once it is solved; what is known and from where.

**Type:** Concept

### Proposal (proposal)

**Definition:** An epic worth doing, proposed under `## Proposed work` with its intent, goal, metric and domain
contact; or a proposed change of the project description.

**Type:** Concept

**Operations:** release (`release`) — a person's go: delivery creates the epic, linking the report
