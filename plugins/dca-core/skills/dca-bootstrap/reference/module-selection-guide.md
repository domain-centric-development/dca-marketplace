# ArchUnit Module Selection Guide

Use this guide to recommend modules during the bootstrap workflow.

## By project profile

| Profile | Recommended modules |
|---|---|
| **Greenfield DCA project** (designing for full DCA from day 1) | All except SpringModulithVerification (unless using Modulith) |
| **Brownfield retrofit** (introducing DCA into legacy code) | Mandatory + Hexagonal + Naming + UseCase. Skip strict DDD-tactical until classes have been refactored to use the markers. |
| **CRUD app, layered but not DDD** | Mandatory + Layered + Onion + Naming + Hexagonal. Skip DDD-Tactical/Strategic/Advanced unless you actually use aggregates and bounded contexts. |
| **Spring Modulith project** | Same as greenfield + SpringModulithVerification |
| **Microservice (single bounded context)** | Mandatory + Hexagonal + Layered + Onion + Naming + UseCase. Skip DddStrategic (it's about cross-context). |
| **Mono-repo monolith with multiple contexts** | All recommended + DDD-Strategic. SpringModulithVerification if using Modulith. |
| **Just want layer enforcement, no DDD jargon** | Mandatory + Layered + Onion + Hexagonal + Naming |

## By subdomain type

Pattern choice per subdomain (record it in a pattern-selection ADR, cf. ADR-025 in the DCA reference implementation):

| Subdomain type | Recommended modules |
|---|---|
| **Core** (competitive differentiator — full tactical DDD) | All modules |
| **Supporting** (transaction script / active record is fine) | Mandatory + Layered + Onion + Hexagonal + Naming. Skip DDD-Tactical/Advanced — structural baseline only. |
| **Generic** (buy/adopt off-the-shelf, thin integration) | Mandatory + Hexagonal + Naming — boundary protection only. |

## By concern

> "I want to keep my domain framework-free"
- Onion + Layered

> "I want to ensure adapters and domain don't bleed"
- Hexagonal + Layered

> "I want naming consistency across the team"
- Naming

> "I want to make sure use cases follow Command/Query/Result pattern"
- UseCase

> "I want to enforce aggregate boundaries"
- DDD-Tactical

> "I want to ensure bounded contexts don't leak into each other"
- DDD-Strategic + Hexagonal (rule 6)

> "I want events to follow conventions (records, timestamps, versioning)"
- DDD-Advanced

## Order of strictness

If you can only run one module to start: **PackageCycles**. It's the cheapest and catches the worst structural problems.

Add in this order if you're slowly raising the bar:

1. PackageCycles
2. Hexagonal (rules 1–4)
3. Layered (rule 1: domain free of infrastructure)
4. Naming
5. UseCase
6. Onion
7. DDD-Tactical
8. DDD-Strategic
9. DDD-Advanced

## Common reasons to NOT install a module

- **DDD-Tactical**: Your classes don't extend marker interfaces yet. Either install the markers and migrate, or skip until they do.
- **DDD-Strategic**: You only have one bounded context. The rules will be no-ops.
- **SpringModulithVerification**: `spring-modulith-starter-test` isn't on the classpath. Will fail to compile.
- **Naming**: Your team has firm conventions that differ (e.g. `*Endpoint` instead of `*Resource`). Either edit the rule or skip.

## After install

Run once to see the baseline: `./gradlew test-architecture --info`

Expect failures in retrofit projects — those failures are findings, not bugs. Use `/dca-review`
to triage and `/dca-scaffold` for new code that should comply from the start.
