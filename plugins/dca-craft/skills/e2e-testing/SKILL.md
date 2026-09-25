---
name: e2e-testing
description: The craft of end-user browser tests — Page Object Pattern, stable data-test selectors, one flow per test, explicit waits instead of sleeps, and a diagnosis-first protocol when a test breaks — and a setup mode that puts a browser runner into a project that has none, ending in a smoke test shown to fail. Use when adding or extending an end-user test, when fixing a flaky one, when a delivery stage needs the project's end-user testing craft, or to set up a browser runner where there is none ("set up Playwright", "add browser tests to this project", "we have no end-user tests yet"). Library-agnostic discipline; Playwright as the default when the project has no runner yet.
---

# End-user tests that stay stable

End-to-end tests earn their bad reputation when they are flaky, slow and entangled with markup.
Everything below exists to keep them from being those things: stable selectors, focused flows, Page
Objects that hide the DOM, assertions on what a user can see.

## Read the project first

Before writing a test, gather the facts — never assume a layout:

1. **The project's conventions**, searched in this order: an explicit path given to you, the
   conventions file the project instructions name (a ``- conventions: `<path>` `` line in
   `AGENTS.md`), `AGENTS.md`, `CLAUDE.md`. Look for
   the end-user test source set, the base URL and how the application is started for tests, any
   existing base test or base page class, the stable-selector attribute (`data-test`,
   `data-testid`, `data-qa`), the test framework, and the commands.
2. **The existing tests and Page Objects.** Adopt the local idiom: shared base classes, the
   selector naming convention, whether Page Objects validate the URL on construction, whether tests
   chain through return values.
3. **A project with nothing yet**: there is no test to write until there is a runner. That is the
   setup mode below — a stack decision, taken with the person, never inside a story.

## Setup mode: a browser runner where there is none

A project that shows a page and has no browser runner gets one before its first end-user test. The
knowledge is in `reference/setup.md`; this is the order.

1. **Confirm there is none.** Look for a browser-test source set, a Playwright, Cypress, Selenium or
   WebDriverIO dependency, a `playwright.config`, a browser-test project. Where one exists, stop:
   write tests in its idiom instead of adding a second runner.
2. **Agree the defaults with the person**: Playwright in the project's language, Page Objects, one
   stable-selector attribute (`data-test` unless the markup already uses another), the project's
   unit-test framework, and whether the application starts inside the test or the suite points at a
   running one (`reference/setup.md` names the trade-off). Ask before writing anything.
3. **Wire the build** as `reference/setup.md` shows for the build tool — its own source set or test
   project, the browser installed by the build, one command that runs the suite and writes a report.
4. **Write the base test**: the application started on a free port (or the base URL read from a
   property), a fresh browser context per test, the fake clock installed and paused at a fixed start.
5. **Give the start page a title** where it has none, as a static page if no feature serves `/` yet.
6. **Write the smoke test** — the start page loads and its title is not empty — and run the suite:
   green.
7. **Show that it fails.** Empty the start page's title, run the smoke test, see it red, restore the
   title, see it green again. A runner that stays green while the page is broken is not testing the
   page; report both runs.
8. **Report** the command that runs the suite, where its report lands, the selector attribute and the
   base test, so the project's instructions and any pipeline profile can name them.

The discipline below is library-agnostic; the API specifics are not. Default to **Playwright** in
any binding; where the project uses Cypress, Selenium or WebDriverIO, adapt and say which you
target.

## Time and permissions belong to the test

A page that counts, polls or expires is tested with the fake clock, never with a sleep or a real wait:
install it before the page loads at a fixed time, **pause it there** (`install` alone lets time run on at
real speed), and move it with `runFor`. A browser API whose answer is the user's —
notifications, geolocation, the clipboard — is replaced before the page loads with a stand-in that
records what it is asked and answers as the test decides. Both are in `reference/setup.md`. A test that
reads the page's script or markup as text to infer what the browser would do is not a browser test: it
proves the wording, not the behaviour.

## 1. Stable selectors only

Locate elements by an explicitly test-stable attribute. Never by CSS class, id, XPath, structural
sibling navigation or visible text — unless the text *is* the behaviour under test.

```java
// ✓ Stable
clickTestElement("basket-checkout-link");
page.locator("[data-test='basket-line']").count();

// ✗ Class names change with styling refactors
page.locator(".btn-primary").click();

// ✗ Text changes with copywriting or translation
page.getByText("Proceed to Checkout").click();

// ✗ DOM structure changes with markup refactors
page.locator("nav > ul > li:nth-child(3) > a").click();
```

An element without a stable selector gets one **in the template first**, then the test. Never trade
selector stability for not touching markup.

## 2. One user flow per test

A test verifies one business-meaningful flow end to end. "A guest completes an order" is one test.
"A returning visitor keeps the items chosen while signed out" is one test. "Test the page and the
form and the list" is three tests, and "test every button on this page" is a unit-test concern.

If you cannot summarise a test in one sentence, split it.

## 3. Page Object Pattern

Hide the DOM behind classes that represent pages or significant fragments. Tests talk to Page
Objects, never to the page.

```java
public class BasketPage extends BasePage {
    private static final String URL_PATTERN = "/basket**";

    // Selector keys as constants at the top — one source of truth
    private static final String BASKET_LINE = "basket-line";
    private static final String CHECKOUT_LINK = "basket-checkout-link";

    public BasketPage(Page page) {
        super(page, URL_PATTERN);   // verify the URL on construction
    }

    public static BasketPage navigateTo(Page page) {
        page.navigate(BASE_URL + "/basket");
        return new BasketPage(page);
    }

    // Query methods return data, never side effects
    public boolean hasLines() {
        return exists(BASKET_LINE);
    }

    public int lineCount() {
        return page.locator("[data-test='" + BASKET_LINE + "']").count();
    }

    // Action methods return the NEXT Page Object
    public AddressPage proceedToCheckout() {
        waitFor(BASKET_LINE);
        click(CHECKOUT_LINK);
        return new AddressPage(page);
    }
}
```

Rules: one file per page, splitting a huge page into page plus fragment classes rather than one
giant class; selector keys as constants, never inline strings; query methods return data; action
methods return the next Page Object so a test chains the way a user moves; the constructor
validates the URL, so a wrong-page failure points at the wrong page.

## 4. Test structure

```java
class GuestOrderE2ETest extends BaseE2ETest {

    @Test
    void completesAnOrderAsGuest() {
        // Arrange — the starting state
        CataloguePage catalogue = CataloguePage.navigateTo(page);

        // Act — chain the flow through Page Objects
        ItemPage item = catalogue.viewFirstItem();
        item.addToBasket();

        ConfirmationPage confirmation = BasketPage.navigateTo(page)
            .proceedToCheckout()
            .fillContact("guest@example.com", "Test", "Guest")
            .continueToDelivery()
            .selectStandardDelivery()
            .reviewAndConfirm();

        // Assert — the user-visible outcome
        assertTrue(confirmation.isDisplayed());
        assertEquals("Order confirmed", confirmation.headline());
    }
}
```

One test method equals one flow; the test contains no selector strings; assertions are about what
the user sees, not internal state; waits are explicit — `waitFor(...)` inside the Page Object is
fine, a sleep never is.

## Adding a flow

1. Name the flow in one sentence.
2. Walk it manually in the browser and note the pages and elements it touches.
3. For each page: reuse its Page Object or write one (URL pattern, selector constants, query and
   action methods).
4. Verify or add the stable-selector attributes on every element you will touch — in the templates,
   first.
5. Write the test through Page Objects only.
6. Run it. Fix flakiness immediately, before moving on.
7. Run it three times when the flow is complex. One flake means flaky.

## When a test breaks — diagnose before patching

A red end-user test means one of four things, and each has exactly one right repair:

| Cause | Repair |
|---|---|
| real regression | fix the production code, leave the test alone |
| a template change broke a selector | restore the attribute or fix the Page Object constant — not the test logic |
| timing race | add an explicit wait; never a sleep |
| the flow legitimately changed | update the Page Object; update the test only if the *user* flow changed |

A test "fixed" three times in a month with no production change is hiding something.

## Refuse

- Selectors by CSS class, XPath or text.
- Sleeps in place of waits.
- Tests touching the DOM directly instead of through a Page Object.
- Action methods that do not return the next Page Object — the chain breaks.
- Page Object constructors without URL validation.
- One test method calling five other "test" methods in sequence.
- Repository or database assertions — that is integration-test territory.
- A visual snapshot as the primary assertion; assert element presence and data instead.
- Reusing one test as the setup of another; factor setup into a helper or a per-test hook.

## Running

Use the project's own commands, read from its conventions or its build file. End-user tests run
**against a running application**; they are not isolated. Two terminals — start the app, run the
suite — is fastest locally. For CI, start the application inside the test lifecycle (containers, an
in-process web host, or the runner's own web-server configuration). Page Objects written against
stable-selector attributes are portable across stacks: the same suite can drive two
implementations of the same application.

## Boundaries

End-user tests are one layer, not a replacement for unit or integration tests, and they are not the
place to drive design: write them once the behaviour works end to end and you want a regression
guard. Do not generate Page Objects from a screenshot or a URL — inspect the actual markup. Do not
change templates beyond adding stable-selector attributes; deeper markup rework is someone else's
call. Page Objects are production code and may be reviewed as such.
