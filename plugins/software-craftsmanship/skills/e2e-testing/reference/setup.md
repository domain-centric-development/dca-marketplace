# Setting up a browser runner

A project that shows a page needs a way to test it in a browser before its first story. Otherwise every
test of that page falls back to reading markup or script text, which proves the wording but not the
behaviour. Setting the runner up is a stack decision, taken once — by the bootstrap, by a human, or by
a scoping step — never inside a story. This page is how to take it: Playwright, headless, started from the
build, writing a test report a CI job or a gate can read.

Four things make a browser suite usable from the first day:

1. **The application starts inside the test**, on a free port. Nothing has to be running first, so the
   suite runs the same on a laptop, in CI and in an agent's shell.
2. **The browser is installed by the build**, once per machine, before the first test.
3. **Time is controlled.** A page that counts, polls or expires is tested with a fake clock that moves
   only when the test moves it — five minutes of waiting become one call.
4. **Browser permissions are controlled.** Notifications, geolocation or the clipboard are replaced before
   the page loads, with the answer the test chooses, so "the user allowed it" and "the user refused it"
   are two tests, not a manual click.

## Gradle (Java or Kotlin) — verified

`gradle/plugins/test-e2e.gradle`, applied from `build.gradle` with
`apply from: "gradle/plugins/test-e2e.gradle"`:

```groovy
sourceSets {
  testE2e {
    java.srcDir file("src/test-e2e/java")
    resources.srcDir file("src/test-e2e/resources")
    compileClasspath += sourceSets.main.output
    runtimeClasspath += sourceSets.main.output
  }
}

configurations {
  testE2eImplementation.extendsFrom(implementation, testImplementation)
  testE2eRuntimeOnly.extendsFrom(runtimeOnly, testRuntimeOnly)
}

dependencies {
  testE2eImplementation "com.microsoft.playwright:playwright:1.62.0"
}

// The browser build Playwright drives; downloaded once into the user's cache, a no-op afterwards.
tasks.register("installE2eBrowser", JavaExec) {
  classpath = sourceSets.testE2e.runtimeClasspath
  mainClass = "com.microsoft.playwright.CLI"
  args "install", "chromium"
}

tasks.register("test-e2e", Test) {
  testClassesDirs = sourceSets.testE2e.output.classesDirs
  classpath = sourceSets.testE2e.runtimeClasspath
  useJUnitPlatform()
  dependsOn "installE2eBrowser"
  shouldRunAfter "test"
}
```

`./gradlew test-e2e` then installs Chromium on first use and runs the suite. A single test is selected
with `--tests <class>.<method>`, and the JUnit XML report lands in `build/test-results/test-e2e/`.

A base class starts the application and one browser per test class. With Spring Boot:

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
abstract class BrowserTest {
  private static Playwright playwright;
  private static Browser browser;
  @LocalServerPort private int port;
  private BrowserContext context;
  protected Page page;

  @BeforeAll static void launchBrowser() { playwright = Playwright.create(); browser = playwright.chromium().launch(); }
  @AfterAll static void closeBrowser() { playwright.close(); }

  @BeforeEach void openContext() {
    context = browser.newContext();       // a fresh context per test: no cookies or storage carried over
    page = context.newPage();
    page.clock().install();               // time moves only when the test moves it
  }
  @AfterEach void closeContext() { context.close(); }

  protected String baseUrl() { return "http://localhost:" + port; }
}
```

Without Spring Boot, start the application's server on port 0 in `@BeforeAll` and read the port it bound.

## Maven

The same shape with the Failsafe plugin: the `com.microsoft.playwright:playwright` test dependency, the
browser installed by `exec-maven-plugin` running `com.microsoft.playwright.CLI install chromium` in
`pre-integration-test`, and the browser tests named `*IT` so Failsafe runs them in `integration-test`.
Not verified in this form.

## .NET

The `Microsoft.Playwright` package in the end-user test project. The browser is installed through the
package's own entry point, `Microsoft.Playwright.Program.Main(new[] { "install", "chromium" })`, called once
before the first test (a fixture, or a build step running the project's `playwright.ps1 install`).
`dotnet test <project> --logger trx` writes the report. The application must listen on a real port for the
browser to reach it: `WebApplicationFactory`'s default test server is in-memory, so either host Kestrel from
the factory or start the application as a process. Not verified end to end here.

## JavaScript

`@playwright/test` as a dev dependency, `npx playwright install chromium`, and the `junit` reporter in
`playwright.config` so a report exists (`reporter: [['junit', { outputFile: 'test-results/e2e.xml' }]]`). The
application is started by the config's `webServer` entry. Not verified in this form.

## Time: the fake clock

Install the clock before the page loads; after that, timers and `Date.now()` stand still until the test
moves them:

```java
page.clock().install();
page.navigate(baseUrl() + "/");
page.locator("[data-test='start-button']").click();
page.clock().runFor(3_000);                       // three seconds of timers fire, in order
assertThat(page.locator("[data-test='remaining']")).hasText("04:57");
```

`runFor` fires every timer due in that span, so a countdown ticks as it would in real time. A test of
something that happens after an hour takes milliseconds.

## Permissions: a stand-in, chosen by the test

For notifications, replace the browser's `Notification` before any page script runs. It then records what
would have been shown and answers the permission question the way the test chose:

```java
page.addInitScript("""
    window.__notifications = [];
    class RecordedNotification {
      constructor(title) { window.__notifications.push(title); }
      static requestPermission() { return Promise.resolve(RecordedNotification.permission); }
    }
    RecordedNotification.permission = '%s';
    window.Notification = RecordedNotification;
    """.formatted("denied"));
```

`page.evaluate("() => window.__notifications")` then lists what the page announced. The same pattern holds
for any browser API whose answer is the user's: replace it before the page loads, record what it is asked,
and answer as the test decides. Playwright's own `context.grantPermissions(...)` sets the permission, but
headless browsers show no notification, so a stand-in is what makes the notification itself observable.

## Proving the runner works

Before the first story, one smoke test opens the start page and asserts one visible element. Then break
that element on purpose and see the test fail. A browser suite that stays green while the page is broken
is not testing the page.
