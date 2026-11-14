# Add a browser runner to an existing project — digest

Node: `/recipe/add-a-browser-runner.md` — cite it by that path; read it in full only for a decision this digest leaves open.

A project shows pages and has no way to drive a browser in its tests.

## Steps (first sentence each)

1. **Pick the runner the build already speaks** — a test dependency for a JVM or .NET build, a package for a JavaScript build; pin the version and install the browser builds that release expects.
2. **Give the browser tests their own source set or test project and one command**, apart from the fast unit suite, and decide whether the application is started by the test or beside it (the guide's *Where the application runs*).
3. **Write one smoke test** — open the start page, assert its title through a stable `data-test` selector, through the Page Object and base class later tests share.
4. **Show that it can fail** — empty the title, see the smoke test red, restore it, see it green.
5. **Record the command and the runner's name** where the project keeps its build facts, so the next plan takes browser tests as the shape for a page.
