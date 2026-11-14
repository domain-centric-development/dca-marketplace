# Isolate the data of integration tests — digest

Node: `/recipe/isolate-the-data-of-integration-tests.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Integration tests run the application against a real database.

## Steps (first sentence each)

1. **One database server per test run**, started in a container with the engine production runs.
2. **Migrate once.** The template (or the shared database) is migrated by the same migrations production runs.
3. **Choose the shape** from the table, and put it in one place: a test listener or extension for the reset, a factory for the per-instance database.
4. **Seed as production starts:** the same seeder, which fills an empty store only, and a start that is ready when the seeding's events are delivered ([a seeded system is taken as ready before its events are delivered](/pitfall/a-seeded-system-is-ready-before-its-events-are-delivered.md)).
5. **Remove once-per-class setup** (a static "already done" flag, a set-up that runs before all tests): with a reset per test, data set up once is gone for the second test.
6. **Switch off background jobs that act on stored state** (scheduled redelivery, clean-ups) in the shared application; the tests about them switch them on in an application of their own.
7. **Measure the suite before and after** — application starts and wall time.
