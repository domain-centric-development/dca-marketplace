---
id: STAGE-TEST-6
part: told
why: a stub returning an empty answer made a test green before any code existed
stages:
- test
section: Do
order: 11
---

# STAGE-TEST-6

6. Write the types the tests need to compile; draw the line at **behaviour**. Structure is written whole (a record with
   fields and null guard, an enum, an interface, an exception type with its message). A method whose outcome a criterion
   observes (a validation, a state change, a query's answer, a use case body) is a stub that **throws**
   (`UnsupportedOperationException`, `NotImplementedException`) — never returns, not even empty or a default: where the
   expected answer *is* the empty case, a stub returning empty is green before any code exists and the criterion ships
   uncovered. Whatever a criterion observes, throws.
