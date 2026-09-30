# An integration level

An integration test has two shapes. The **port test** runs a use case through its input port in the wired
application: the real outgoing adapters, persistence as the project runs it in tests, an external system stubbed
at the protocol (`http-stub`) — the use case tested once, however many adapters call it. The **adapter test**
runs one incoming adapter against a stubbed input port: the request it turns into a command, the page or
response it makes of the result and of each refusal. It sits between a unit test, which proves one type, and an end-user test, which drives the
running application from outside. A delivery pipeline puts every scenario but a story's happy path here, so a
project without this level has nowhere to put them.

The level is its own source set or test project, with its own command: a unit-test run stays fast, and a
check can tell which command runs a given test by where the test lives. Versions are looked up (Maven
Central, NuGet), never recalled.

## Java — Gradle

A source set beside `src/test`, and a task of its own — in `build.gradle`, or where the project keeps its other
test levels (a `gradle/plugins/test-e2e.gradle` applied from `build.gradle`: then a `test-integration.gradle`
beside it, in the same style):

```groovy
sourceSets {
  testIntegration {
    java.srcDir file('src/test-integration/java')
    resources.srcDir file('src/test-integration/resources')
    compileClasspath += sourceSets.main.output
    runtimeClasspath += sourceSets.main.output
  }
}

configurations {
  testIntegrationImplementation.extendsFrom(testImplementation)
  testIntegrationRuntimeOnly.extendsFrom(testRuntimeOnly)
}

tasks.register('test-integration', Test) {
  description = 'Runs the integration tests from src/test-integration.'
  group = 'verification'
  testClassesDirs = sourceSets.testIntegration.output.classesDirs
  classpath = sourceSets.testIntegration.runtimeClasspath
  useJUnitPlatform()
}

tasks.named('check') { dependsOn 'test-integration' }
```

`extendsFrom(testImplementation)` gives the source set the unit tests' dependencies, test slices included.
A slice only the integration level needs goes into `testIntegrationImplementation` — with Spring Boot 4 the
starter per slice (`spring-boot-starter-webmvc-test` for a web application), not the old catch-all
`spring-boot-starter-test`; take the ids from the generator's metadata or the build `dca-new` wrote.

The command is `./gradlew test-integration`; compiling it is `./gradlew testIntegrationClasses`.

## Java — Maven

The same directory, added as a test source by `build-helper-maven-plugin`:

```xml
<plugin>
  <groupId>org.codehaus.mojo</groupId>
  <artifactId>build-helper-maven-plugin</artifactId>
  <executions>
    <execution>
      <id>add-integration-tests</id>
      <phase>generate-test-sources</phase>
      <goals><goal>add-test-source</goal></goals>
      <configuration>
        <sources><source>src/test-integration/java</source></sources>
      </configuration>
    </execution>
  </executions>
</plugin>
```

Surefire then runs both directories, so the command is `./mvnw test` and a single test is still selected
with `-Dtest=<Class>#<method>`. A Failsafe run of its own selects with `-Dit.test` instead — a project that
wants one says so in its profile, with the flag.

## The smoke test (Java)

One test that starts the wired application:

```java
@SpringBootTest
class ApplicationIntegrationTest {

  @Autowired ApplicationContext context;

  @Test
  void theApplicationStarts() {
    assertThat(context.getBeanDefinitionCount()).isPositive();
  }
}
```

Shown to fail once: create `src/test-integration/resources/application.yml` with the line
`spring.main.sources: does.not.Exist`, run the command, see it red because the context cannot start, delete
the file, see it green. Use `.yml` even where the application keeps `application.properties`: a test
`application.properties` would replace the main one, a `.yml` is read beside it.

The generator's `@SpringBootTest` context test in the unit source set stays where it is: on a fresh
skeleton it is the unit suite's only test, and a unit command that runs none fails a check that requires it.

## Starting clean — the project's reset convention (Java)

Integration tests share one application context and one test database, so each test starts by emptying
what it writes — a `@BeforeEach` that deletes the rows, in the test class or a small base class the
level's tests extend:

```java
@SpringBootTest
@AutoConfigureMockMvc
abstract class IntegrationTest {

  @Autowired JdbcClient jdbcClient;   // or the JPA repositories' deleteAll()

  @BeforeEach
  void startClean() {
    jdbcClient.sql("DELETE FROM <table>").update();   // one line per table the tests write
  }
}
```

This is how tests here start clean — **not** `@DirtiesContext` per test method, which rebuilds the whole
Spring context for every test and makes the level slow for nothing, and not a random schema per test.
Write the convention into the skeleton with the smoke test, even before there is a table: a test stage
follows the layout it finds, and a project without a reset convention gets whichever one the first
story's author reaches for.

## The two shapes (Java, Spring)

The port test takes the input port from the wired application and asserts the outcome on what the use case
returns and what persistence holds — no request, no page:

```java
class AddTaskIntegrationTest extends IntegrationTest {

  @Autowired AddTaskInputPort addTask;

  @Test
  void aTrimmedTitleIsStored() {
    addTask.execute(new AddTaskCommand("  Milch kaufen "));
    assertThat(jdbcClient.sql("SELECT title FROM tasks").query(String.class).single()).isEqualTo("Milch kaufen");
  }
}
```

The adapter test runs the controller in the web slice with the input port stubbed, and asserts what only the
page shows — the result's and each refusal's translation:

```java
@WebMvcTest(TaskController.class)
class TaskControllerIntegrationTest {

  @Autowired MockMvc mvc;
  @MockitoBean AddTaskInputPort addTask;

  @Test
  void aRefusedTitleShowsTheMessageAndKeepsTheInput() throws Exception {
    when(addTask.execute(any())).thenThrow(new TitleLengthViolated(201));
    mvc.perform(post("/tasks").param("title", "x".repeat(201)))
        .andExpect(status().isOk())
        .andExpect(content().string(containsString("höchstens 200 Zeichen")));
  }
}
```

The `IntegrationTest` base class below is the port tests' (the wired application, the reset); an adapter test
starts only its slice and needs no reset, because it writes nothing.

## .NET

A test project of its own, named `<Solution>.IntegrationTests`, that hosts the application in memory:

```bash
dotnet new xunit -n <Name>.IntegrationTests -o tests/<Name>.IntegrationTests
dotnet sln add tests/<Name>.IntegrationTests
dotnet add tests/<Name>.IntegrationTests reference src/<Name>.Web
dotnet add tests/<Name>.IntegrationTests package Microsoft.AspNetCore.Mvc.Testing
```

`WebApplicationFactory<Program>` needs the host's `Program` to be visible: a line `public partial class
Program;` at the end of `Program.cs`. The smoke test:

```csharp
public class ApplicationTests(WebApplicationFactory<Program> factory) : IClassFixture<WebApplicationFactory<Program>>
{
    [Fact]
    public async Task TheApplicationStarts()
    {
        var response = await factory.CreateClient().GetAsync("/");
        response.EnsureSuccessStatusCode();
    }
}
```

Shown to fail once: change `"/"` to a path the application does not serve, run
`dotnet test tests/<Name>.IntegrationTests`, see it red, restore it, see it green. A project with no page
at `/` asks for an endpoint it has instead.

**The two shapes (.NET):** the port test resolves the input port from the factory's services
(`factory.Services.CreateScope().ServiceProvider.GetRequiredService<IAddTask>()`) and asserts on its result and
the store; the adapter test replaces the port in the host (`factory.WithWebHostBuilder(b =>
b.ConfigureTestServices(s => s.AddSingleton<IAddTask>(stub)))`) and asserts on the response's status and body.

**Starting clean (.NET):** one `WebApplicationFactory<Program>` per class (`IClassFixture`), and a reset of
what the tests write before each test — a `DELETE` through the host's connection, or the in-memory
store's `Clear()` resolved from the factory's services — in the test's constructor or a shared base
class. Not a new factory per test method: that is the same context rebuild the Java note warns about.

## Recorded

An `## Integration tests` section in the conventions file, with the source set, the command and the
reset convention: `integration: src/test-integration`, `integrationTest: ./gradlew test-integration`
(Maven: `./mvnw test`; .NET: `integration: tests/<Name>.IntegrationTests`, `integrationTest: dotnet test
tests/<Name>.IntegrationTests`) and `reset: each test empties the tables it writes in @BeforeEach
(IntegrationTest base class); never a context per test`. A delivery pipeline's setup detects the task, the added test source or the project
and proposes its `test.integration:` line.
