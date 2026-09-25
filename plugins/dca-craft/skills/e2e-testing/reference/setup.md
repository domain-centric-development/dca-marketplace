# Setting up a browser runner

A project that shows a page needs a way to test it in a browser before its first story. Otherwise every
test of that page falls back to reading markup or script text, which proves the wording but not the
behaviour. Setting the runner up is a stack decision, taken once — by a person, by the skill that sets the
project up, or by a scoping step — never inside a story. This page is how to take it: Playwright, headless, started from the
build, writing a test report a CI job or a gate can read.

Four things make a browser suite usable from the first day:

1. **The application starts inside the test**, on a free port. Nothing has to be running first, so the
   suite runs the same on a laptop, in CI and in an agent's shell. (The other variant — the suite points at
   an application someone started, its base URL in a property or an environment variable — suits a system
   that needs a database or other services up first. Pick one per project and say which; a suite that does
   both by accident starts one application and tests another.)
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
  // `Playwright.create()` would otherwise download every browser build — Firefox and WebKit too — on a
  // machine that has none; the one this suite drives comes from installE2eBrowser.
  environment "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1"
  dependsOn "installE2eBrowser"
  shouldRunAfter "test"
}
```

`./gradlew test-e2e` then installs Chromium on first use and runs the suite. A single test is selected
with `--tests <class>.<method>`, and the JUnit XML report lands in `build/test-results/test-e2e/`.

A base class starts the application and one browser per test class. With Spring Boot:

```java
@SpringBootTest(classes = Application.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
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
    page.clock().install(new Clock.InstallOptions().setTime(START));   // a fixed start, the same every run
    page.clock().pauseAt(START);          // and time stands still until the test moves it (see below)
  }
  @AfterEach void closeContext() { context.close(); }

  protected String baseUrl() { return "http://localhost:" + port; }
}
```

`classes =` names the `@SpringBootApplication` class. Without it the test finds its configuration only when
that class sits in the test's package or above it — a main class in `<base>.infrastructure`, the composition
root, is below the base package, and the suite fails before its first test with "Unable to find a
@SpringBootConfiguration". `START` is a constant of the base class, e.g. `"2026-01-05T08:00:00Z"`.

Without Spring Boot, start the application's server on port 0 in `@BeforeAll` and read the port it bound.

## Maven

The same shape with the Failsafe plugin: the `com.microsoft.playwright:playwright` test dependency, the
browser installed by `exec-maven-plugin` running `com.microsoft.playwright.CLI install chromium` in
`pre-integration-test`, `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` in Failsafe's `environmentVariables`, and every
browser test — the smoke test too — named `*IT`, because Failsafe runs nothing else. `mvn verify` runs the
suite. Not verified in this form.

## .NET (ASP.NET Core 10, xUnit) — verified

An end-user test project `tests/<Solution>.E2eTests` with a project reference to the web project and the
packages `Microsoft.Playwright` and `Microsoft.AspNetCore.Mvc.Testing`:

```xml
<ItemGroup>
  <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="10.0.*" />
  <PackageReference Include="Microsoft.Playwright" Version="1.62.0" />
  <!-- plus the test SDK and xUnit the solution's other test projects use -->
</ItemGroup>
```

The web project ends `Program.cs` with `public partial class Program;` so the factory can name it. The browser
must reach a real port, and `WebApplicationFactory`'s default server is in-memory, so the factory hosts
Kestrel (`UseKestrel(0)`, new in ASP.NET Core 10) on a free port. The browser is installed through the
package's own entry point, once per test run — no PowerShell needed:

```csharp
public abstract class BrowserTest : IAsyncLifetime
{
    private static readonly Lazy<int> BrowserInstalled =
        new(() => Microsoft.Playwright.Program.Main(["install", "chromium"]));

    private WebApplicationFactory<Program>? factory;
    private IPlaywright? playwright;
    private IBrowser? browser;
    private IBrowserContext? context;
    protected IPage Page = null!;
    protected string BaseUrl = "";

    public async Task InitializeAsync()
    {
        if (BrowserInstalled.Value != 0) throw new InvalidOperationException("playwright install chromium failed");
        factory = new WebApplicationFactory<Program>();
        factory.UseKestrel(0);                       // a real port on the loopback, chosen free
        factory.StartServer();
        BaseUrl = factory.ClientOptions.BaseAddress.ToString().TrimEnd('/');
        playwright = await Playwright.CreateAsync();
        browser = await playwright.Chromium.LaunchAsync();
        context = await browser.NewContextAsync();   // a fresh context per test
        Page = await context.NewPageAsync();
        await Page.Clock.InstallAsync(new() { TimeString = Start });   // a fixed start
        await Page.Clock.PauseAtAsync(Start);                          // time stands still
    }

    public async Task DisposeAsync()
    {
        if (context is not null) await context.CloseAsync();
        if (browser is not null) await browser.CloseAsync();
        playwright?.Dispose();
        if (factory is not null) await factory.DisposeAsync();
    }
}
```

`dotnet test tests/<Solution>.E2eTests --logger trx` runs the suite and writes the report. Before ASP.NET Core
10, host Kestrel yourself in a factory subclass or start the application as a process.

## JavaScript

`@playwright/test` as a dev dependency, `npx playwright install chromium`, and the `junit` reporter in
`playwright.config` so a report exists (`reporter: [['junit', { outputFile: 'test-results/e2e.xml' }]]`). The
application is started by the config's `webServer` entry. Not verified in this form.

## Time: the fake clock

Install the clock before the page loads, at a fixed time, and **pause** it there. `install()` alone only
replaces the clock: `Date.now()` and every interval go on running at real speed (measured: one second of
real time moved `Date.now()` by 1,010 ms and fired a 100 ms interval ten times), so a countdown test
depends on how fast the machine is. After `pauseAt`, nothing moves until the test moves it:

```java
page.clock().install(new Clock.InstallOptions().setTime("2026-01-05T08:00:00Z"));
page.clock().pauseAt("2026-01-05T08:00:00Z");
page.navigate(baseUrl() + "/");
page.locator("[data-test='start-button']").click();
page.clock().runFor(3_000);                       // three seconds of timers fire, in order
assertThat(page.locator("[data-test='remaining']")).hasText("04:57");
```

`runFor` fires every timer due in that span, in order, so a countdown ticks as it would in real time. A test
of something that happens after an hour takes milliseconds. The .NET calls are the same with `Async`:
`Page.Clock.InstallAsync(new() { TimeString = … })`, `PauseAtAsync(…)`, `RunForAsync(…)`.

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

Before the first story, one smoke test proves that the browser reaches the application.

- **The page it opens exists without code.** A new project has no controller yet, and it should not get
  one just to be tested — a controller needs a place in the architecture that no feature has decided.
  A static start page does the job: `src/main/resources/static/index.html` with Spring Boot, which serves
  it at `/` by itself; `wwwroot/index.html` with ASP.NET Core and `UseDefaultFiles()` + `UseStaticFiles()`;
  the start page of a JavaScript app. Give it a `<title>`. The first feature that maps `/` takes over, and
  the placeholder can go.
- **It asserts what every start page keeps:** the page loads and its title is not empty — never the
  placeholder's text. The first real page then leaves the smoke test green, instead of turning it into a
  test the first story has to change.

```java
@Test                                     // with Maven: in a class named `*IT`
void theStartPageOpensInTheBrowser() {
  Response response = page.navigate(baseUrl() + "/");
  assertThat(response.status()).isEqualTo(200);
  assertThat(page.title()).isNotBlank();
}
```

Then empty the title on purpose and watch the test fail, and restore it. A browser suite that stays green
while the page is broken is not testing the page.
