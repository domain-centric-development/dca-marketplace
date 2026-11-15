# Setting up a browser runner

A stack decision, taken once — by a person, the project's setup skill or a scoping step — never inside a story.
Playwright, headless, started from the build, writing a report a CI job or gate can read.

- **The app starts inside the test** on a free port, with an external system as a stub started first and the
  database the app's tests already use. A base-URL property may point the tests at a deployment; without it the
  suite starts its own.
- **The build installs the browser**, once per machine.
- **Time is controlled**: a fake clock that moves only when the test moves it.
- **Browser permissions are controlled**: notifications, geolocation, clipboard replaced before load, answered as
  the test chooses ("allowed" and "refused" are two tests).

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

`classes =` names the `@SpringBootApplication` class — required when it sits below the test's package (e.g. a
main class in `<base>.infrastructure`), else "Unable to find a @SpringBootConfiguration". `START` is a base-class
constant, e.g. `"2026-01-05T08:00:00Z"`.

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

The web project ends `Program.cs` with `public partial class Program;`. `WebApplicationFactory`'s default server
is in-memory; the browser needs a real port, so host Kestrel with `UseKestrel(0)` (ASP.NET Core 10). The browser is
installed through the package's own entry point, once per run — no PowerShell:

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

## External systems: a stub the suite owns

The app reaches an external system through an adapter whose base URL is configuration. The suite starts an HTTP
stub on a free port **before** the app, once, and hands its URL in; each test arranges the stub's answer.

Java, Spring Boot (the stub on a free port, its URL a property of the application under test):

```java
@SpringBootTest(classes = Application.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
abstract class BrowserTest {
  static final WireMockServer provider = new WireMockServer(wireMockConfig().dynamicPort());
  static { provider.start(); }

  @DynamicPropertySource
  static void provider(DynamicPropertyRegistry registry) {
    registry.add("<the adapter's base-url property>", provider::baseUrl);
  }
  @BeforeEach void resetProvider() { provider.resetAll(); }   // each test arranges its own answer
}
```

.NET (the stub started before the factory, its URL a setting of the host):

```csharp
provider = WireMockServer.Start();
factory = new WebApplicationFactory<Program>().WithWebHostBuilder(builder =>
    builder.UseSetting("<the adapter's base-url key>", provider.Url));
factory.UseKestrel(0);
factory.StartServer();
```

A test needing the real system does not belong here; a test against a deployment sets the base-URL property and
arranges nothing.

## A suite that needs a running application

Convert the base test alone: without the base-URL property it starts the app on a free port — once per run,
shared by every test class — and returns that address; with it, it keeps the named app. Remove skip conditions
that only asked "is the base URL set?". Tests unchanged. Then run the whole suite with nothing started: green, same
test count as before.

## Time: the fake clock

Install before load at a fixed time and **pause** there. `install()` alone keeps `Date.now()` and intervals
running at real speed (measured: 1 s real moved `Date.now()` 1,010 ms, fired a 100 ms interval ten times). After
`pauseAt` nothing moves until the test moves it:

```java
page.clock().install(new Clock.InstallOptions().setTime("2026-01-05T08:00:00Z"));
page.clock().pauseAt("2026-01-05T08:00:00Z");
page.navigate(baseUrl() + "/");
page.locator("[data-test='start-button']").click();
page.clock().runFor(3_000);                       // three seconds of timers fire, in order
assertThat(page.locator("[data-test='remaining']")).hasText("04:57");
```

`runFor` fires every timer due in that span, in order. .NET: the same with `Async`:
`Page.Clock.InstallAsync(new() { TimeString = … })`, `PauseAtAsync(…)`, `RunForAsync(…)`.

## Permissions: a stand-in, chosen by the test

Replace `Notification` before any page script runs; it records what would be shown and answers permission as the
test chose:

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

`page.evaluate("() => window.__notifications")` lists what the page announced. Same pattern for any browser API
whose answer is the user's. `context.grantPermissions(...)` alone is not enough: headless browsers show no
notification, so only a stand-in makes it observable.

## Proving the runner works

One smoke test before the first story.

- **The page exists without code** — no controller just to be tested. A static start page with a `<title>`:
  `src/main/resources/static/index.html` (Spring Boot serves it at `/`); `wwwroot/index.html` with
  `UseDefaultFiles()` + `UseStaticFiles()` (ASP.NET Core); a JavaScript app's start page. The first feature mapping
  `/` replaces it.
- **Assert what every start page keeps**: it loads, title not empty — never the placeholder's text, so the first
  real page leaves it green.

```java
@Test                                     // with Maven: in a class named `*IT`
void theStartPageOpensInTheBrowser() {
  Response response = page.navigate(baseUrl() + "/");
  assertThat(response.status()).isEqualTo(200);
  assertThat(page.title()).isNotBlank();
}
```

Then empty the title, see it fail, restore it.
