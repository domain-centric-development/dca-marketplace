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

2a. **An integration test** has the shape the plan wrote after its level, in the source set a `test.<name>:` key
   declares. `integration (port)`: the use case through its input port in the wired application, with real
   outgoing adapters and persistence as the project runs it in tests — the scenario's outcome asserted on what the
   use case returns, stores or publishes; an external system stubbed at the protocol with the stub the profile
   names (`http.stub:`). `integration (adapter: <Adapter>, test: <Class>#<method>)`: that incoming adapter's
   translation against a stubbed input port that answers with the outcome — the test written under the name the
   plan gave it, unchanged, and mapped to that criterion (`tests-planned`). A refusal its stub answers with is the
   one the port test of the criterion proves, in the style the plan's `## Context` names (returned: the same case;
   thrown: the very failure type), and both tests stand in the criterion's rows. **A clause about what is
   stored** is never asserted at the adapter level — the gate refuses it (`clauses`); assert it through the input
   port with the real store, or end to end. A plan line with the bare `integration` of an older plan is the port
   shape. Every adapter the plan lists as changed is passed by at least one mapped integration test; a case it
   handles that no scenario names gets a test outside the table, named under `## Notes`. Why an adapter test shows
   a state and never replays the change, and the other rules of each level: the testing craft
   (`reference/adapter.md`, `reference/port.md`).
