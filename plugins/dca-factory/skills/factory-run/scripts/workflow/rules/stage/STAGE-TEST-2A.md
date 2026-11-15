---
id: STAGE-TEST-2A
part: told
why: an adapter test stubbed a refusal the use case never raises, proving a page for a case that cannot happen
stages:
- test
section: Do
order: 3
---

# STAGE-TEST-2A

2a. **Integration tests** take the shape the plan wrote, in the `test.<name>:` source set:
   - `integration (port)`: the use case through its input port, wired app, real outgoing adapters and test
     persistence; assert what the use case returns, stores or publishes; external systems stubbed at the protocol
     (`http.stub:`). A bare `integration` in an older plan = port.
   - `integration (adapter: <Adapter>, test: <Class>#<method>)`: the adapter's translation against a stubbed input
     port answering with the outcome, under exactly the plan's name, mapped to that criterion (`tests-planned`). A round
     that renames, splits or drops it writes `- `<old>` → `<new>` — <why>` under `## Plan changes` in tests.md, never
     into plan.md.
   - A refusal the stub answers with is the one the criterion's port test proves, in the `## Context` style (returned:
     the same case; thrown: the very failure type); both tests stand in the criterion's rows.
   - **A stored-state clause is never asserted at the adapter level** — the stub answers what you told it, so the test
     reads back its stub; the gate refuses it (`clauses`). Assert it through the input port with the real store, or end
     to end.
   - Every adapter the plan changes is passed by at least one mapped integration test; a case it handles that no
     scenario names gets a test outside the table, named under `## Notes`.
   - Why an adapter test shows a state and never replays the change, and each level's other rules: the testing craft
     (`reference/adapter.md`, `reference/port.md`).
