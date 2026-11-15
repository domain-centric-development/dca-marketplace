# First ADR: record the practice itself

Read when `/adr new` runs in a repository with no ADRs: offer this meta-ADR as `0001` first.

```
# 0001. Record architecture decisions

- Status: Accepted
- Date: <today>
- Tags: meta, process

## Context
Wir treffen regelmäßig architektonische Entscheidungen ohne strukturierte
Dokumentation. Das macht es schwer für neue Teammitglieder zu verstehen,
warum bestimmte Pfade gewählt wurden.

## Decision
Wir dokumentieren architektonische Entscheidungen mit Architecture Decision
Records (ADRs) im Michael-Nygard-Format unter `docs/adr/`, verwaltet via
`/adr`-Skill.

## Consequences
+ Nachvollziehbarkeit von Entscheidungen über die Zeit.
+ Onboarding-Material entsteht als Nebeneffekt.
- Disziplin erforderlich; ADRs verfallen, wenn nicht gepflegt.
- Kleine Entscheidungen können nicht alle dokumentiert werden — Schwelle
  setzen.

## References
- https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
```
