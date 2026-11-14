---
type: Section
title: Testing
chapter: "References & Further Reading"
source: guide
tags: [guide, section]
---

**Books:**
- **[xUnit Test Patterns: Refactoring Test Code](http://xunitpatterns.com/)** by Gerard Meszaros (2007)
  - The names for a test's state and its smells: Fresh Fixture, Shared Fixture, Minimal Fixture,
    Interacting Tests, Mystery Guest
- **[Software Engineering at Google](https://abseil.io/resources/swe-book)** edited by Titus Winters, Tom Manshreck
  and Hyrum Wright (2020), chapters 11–13 on testing
  - No logic in a test, DAMP over DRY, flaky tests, test doubles and the preference for real implementations
- **Clean Code** by Robert C. Martin (2008), chapter 9
  - The F.I.R.S.T. properties of a unit test: fast, independent, repeatable, self-validating, timely

**Articles:**
- **[Test Desiderata](https://testdesiderata.com/)** by Kent Beck (2019)
  - The properties a test can have and trade against each other, structure-insensitive among them
- **[Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html)** by Martin Fowler (2007)
  - State against behaviour verification, the classical and the mockist style
- **[When to Mock](https://enterprisecraftsmanship.com/posts/when-to-mock/)** by Vladimir Khorikov (2020)
  - A dependency the application owns stays real; one it does not own is replaced at its boundary
- **[The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)** by Ham Vocke (2018)
- **[Write tests. Not too many. Mostly integration.](https://kentcdodds.com/blog/write-tests)** by Kent C. Dodds (2019)
