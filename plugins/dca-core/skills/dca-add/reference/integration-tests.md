# An integration level

An integration test runs a use case through the wired application: its input port or its HTTP surface,
the real adapters, persistence as the project runs it in tests, an external system stubbed at the protocol
(`http-stub`). It sits between a unit test, which proves one type, and an end-user test, which drives the
running application from outside. A delivery pipeline puts every scenario but a story's happy path here, so a
project without this level has nowhere to put them.

The level is its own source set or test project, with its own command: a unit-test run stays fast, and a
check can tell which command runs a given test by where the test lives. Versions are looked up (Maven
Central, NuGet), never recalled.

## Java — Gradle

A source set beside `src/test`, and a task of its own. In `build.gradle`:

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

The test slice the application needs goes into `testIntegrationImplementation` — with Spring Boot 4 the
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

Shown to fail once: add `spring.main.sources: does.not.Exist` to
`src/test-integration/resources/application.yml` (create the file for it), run the command, see it red
because the context cannot start, remove the line, see it green.

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

## Recorded

`integration: src/test-integration` (Gradle, Maven) or `integration: <Name>.IntegrationTests` (.NET) in the
conventions file. A delivery pipeline's setup detects the task, the added test source or the project
and proposes its `test.integration:` line.
