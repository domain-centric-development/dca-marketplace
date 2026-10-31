---
id: STAGE-TEST-6
part: told
stages:
- test
section: Do
order: 11
---

# STAGE-TEST-6

6. Write the types the tests need to compile — and draw the line at **behaviour**. A type with nothing a
   criterion observes is structure, and structure is written whole here: a record with its fields and a
   null guard, an enum with its values, an interface with its methods, an exception type with its
   message. A method whose outcome a criterion asserts — a validation, a state change, a query's
   answer, a use case's body — is a stub that **refuses to answer**: it throws
   (`UnsupportedOperationException`, `NotImplementedException`, whatever the language calls it). It
   never returns a value, not even an empty list or a default — for a criterion whose expected answer
   *is* the empty case, a stub returning empty makes the test green before any code exists, and a green
   test at this stage proves nothing. The gate refuses it, and rightly: the criterion would ship
   uncovered. The line in one sentence: whatever a criterion observes, throws.
