---
name: e2e-testing
description: The craft of end-user browser tests — Page Object Pattern, stable data-test selectors, one flow per test, explicit waits instead of sleeps, and a diagnosis-first protocol when a test breaks — and a setup mode that puts a browser runner into a project that has none, ending in a smoke test shown to fail. Use when adding or extending an end-user test, when fixing a flaky one, when a delivery stage needs the project's end-user testing craft, or to set up a browser runner where there is none ("set up Playwright", "add browser tests to this project", "we have no end-user tests yet"). Library-agnostic discipline; Playwright as the default when the project has no runner yet.
---

# End-user tests that stay stable

## Read the project first

1. **Conventions**, in this order: a path given to you, the configuration file `AGENTS.md` names
   (``- configuration: `<file>` ``), `AGENTS.md`, `CLAUDE.md`. Find: the e2e source set, base URL and how the app
   starts for tests, base test / base page classes, the stable-selector attribute (`data-test`, `data-testid`,
   `data-qa`), framework, commands.
2. **Existing tests and Page Objects**: adopt the idiom — base classes, selector naming, URL check on construction,
   chaining through return values.
3. **Nothing yet**: no test until there is a runner — setup mode, a stack decision with the person, never inside a
   story.

Default to **Playwright** in any binding; on Cypress, Selenium or WebDriverIO adapt and say which you target.

## Setup mode: a browser runner where there is none

Knowledge in `reference/setup.md` (Gradle, Maven, .NET, JavaScript; external-system stubs; fake clock;
permissions; smoke test). Order:

1. **Confirm there is none**: browser-test source set, Playwright/Cypress/Selenium/WebDriverIO dependency,
   `playwright.config`, browser-test project. One exists → no second runner, write in its idiom; if it drives an
   app someone must start first, change only its base test to start the app itself (`reference/setup.md`, "A suite
   that needs a running application").
2. **Agree the defaults with the person**: Playwright in the project's language, Page Objects, one selector
   attribute (`data-test` unless the markup uses another), the project's unit-test framework. The app always starts
   inside the test on a free port. Ask before writing anything — unless the caller hands these defaults over as
   already agreed.
3. **Wire the build** per `reference/setup.md`: own source set or test project, browser installed by the build, one
   command that runs the suite and writes a report.
4. **Base test**: app on a free port, fresh browser context per test, fake clock installed and paused at a fixed
   start, the store emptied before each test through the app's own reset where the suite shares one app. External
   systems: a stub started before the app, its address handed in by configuration (`reference/setup.md`, "External
   systems"). A base-URL property may point the tests at a deployment; without it the suite starts its own app.
5. **Give the start page a title** where it has none — a static page if no feature serves `/` yet.
6. **Smoke test**: start page loads, title not empty; run the suite: green.
7. **Show that it fails**: empty the title, see red, restore, see green. Report both runs.
8. **Report** the suite command, the report location, the selector attribute and the base test.

## Time and permissions belong to the test

- Counting, polling, expiring pages: fake clock installed before load at a fixed time, **paused** there
  (`install` alone runs on at real speed), moved with `runFor`. Never a sleep or real wait.
- Browser APIs whose answer is the user's (notifications, geolocation, clipboard): replaced before load by a
  stand-in that records what it is asked and answers as the test decides. Both in `reference/setup.md`.
- Reading the page's script or markup as text to infer browser behaviour is not a browser test.

## 1. Stable selectors only

By an explicit test attribute — never CSS class, id, XPath, structural navigation, or visible text (unless the text
*is* the behaviour).

```java
// ✓
page.locator("[data-test='basket-line']").count();
// ✗ class / text / structure
page.locator(".btn-primary").click();
page.getByText("Proceed to Checkout").click();
page.locator("nav > ul > li:nth-child(3) > a").click();
```

No attribute → add it **in the template first**, then the test.

## 2. One user flow per test

- One business-meaningful flow, summarisable in one sentence; otherwise split. "Every button on this page" is a
  unit-test concern.
- **Assert the element, not the page** — by selector, role or field, never the page's whole text.
- **Each test brings its own state**; passes alone and in any order. Start from the app's own reset or data unique
  to the test, asserting only about that data — never what an earlier test left.
- Seeded data is shared: a test that changes a seeded record or needs an exact value creates its own record through
  the app and reads only that. Where the scenario itself names the seeded record and its exact value, the test runs
  on its own app started from the seed. A flow that only reads seeded data without exact values stays on the shared
  app.
- Run the **whole** suite once before handing over; passes alone, fails in the suite = not done.

## 3. Page Object Pattern

Tests talk to Page Objects, never to the page.

```java
public class BasketPage extends BasePage {
    private static final String URL_PATTERN = "/basket**";
    private static final String BASKET_LINE = "basket-line";          // selector keys as constants
    private static final String CHECKOUT_LINK = "basket-checkout-link";

    public BasketPage(Page page) { super(page, URL_PATTERN); }        // URL verified on construction

    public static BasketPage navigateTo(Page page) {
        page.navigate(BASE_URL + "/basket");
        return new BasketPage(page);
    }

    public int lineCount() {                                          // query: returns data
        return page.locator("[data-test='" + BASKET_LINE + "']").count();
    }

    public AddressPage proceedToCheckout() {                          // action: returns the next Page Object
        waitFor(BASKET_LINE);
        click(CHECKOUT_LINK);
        return new AddressPage(page);
    }
}
```

- One file per page; a huge page splits into page plus fragment classes.
- Selector keys as constants, never inline. Queries return data; actions return the next Page Object.
- Constructor validates the URL.

## 4. Test structure

- One test method = one flow, chained through Page Objects (Arrange / Act / Assert).
- No selector strings in the test; assertions on what the user sees.
- Explicit waits — `waitFor(...)` inside the Page Object; never a sleep.

## Adding a flow

1. Name it in one sentence.
2. Walk it in the browser; note pages and elements.
3. Per page: reuse or write the Page Object.
4. Verify or add the selector attributes in the templates, first.
5. Write the test through Page Objects only.
6. Run it; fix flakiness before moving on.
7. Complex flow: run three times. One flake = flaky.

## When a test breaks — diagnose before patching

| Cause | Repair |
|---|---|
| real regression | fix the production code, leave the test alone |
| a template change broke a selector | restore the attribute or fix the Page Object constant — not the test logic |
| timing race | add an explicit wait; never a sleep |
| the flow legitimately changed | update the Page Object; update the test only if the *user* flow changed |

A test "fixed" three times in a month with no production change hides something. Two causes look like flakiness:

- **Stub slower than the timeout**: an in-process stub shares the machine with a parallel suite and can answer after
  the app's production timeout. The app under test takes a generous timeout for stubbed partners from the suite's
  configuration; its own default stays.
- **Missed load event**: after a form redirect the runner's URL wait can miss the load event and time out on a
  loaded page (it waits for a load state even when the URL already matches). Poll the page's URL yourself until it
  matches, then wait for the document's ready state — one helper every Page Object uses.

## Refuse

- Selectors by CSS class, XPath or text; sleeps; DOM access outside a Page Object.
- Actions not returning the next Page Object; constructors without URL validation.
- A test method calling other "test" methods; one test as another's setup (use a helper or per-test hook).
- Repository or database assertions (integration-test territory).
- A visual snapshot as the primary assertion.

## Running

The project's own commands. Locally: start the app, run the suite. CI: the app starts inside the test lifecycle
(containers, in-process web host, the runner's web-server config). Selector-based Page Objects can drive two
implementations of the same application.

## Boundaries

- One layer, not a replacement for unit or integration tests; not for driving design.
- Never generate Page Objects from a screenshot or URL — inspect the markup.
- Change templates only to add selector attributes.
- Page Objects are production code, reviewed as such.
