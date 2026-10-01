# Test coverage over every suite

One report of line and branch coverage over the unit, integration and end-user suites together, and one per
suite. A browser test drives the application in the test's own process, so the coverage agent sees the page's
path as well; a report of the unit suite alone would call a use case untested that its port test runs.

Coverage is a reading, never a gate: **no threshold**. A number to reach invites tests written for the number.
What the report is for is the gap it shows — and in a domain-centric project the gap that matters is in the
domain: an uncovered branch in an aggregate, entity or value object is an invariant nobody named and nobody
tested (a guard against `null`, an untrimmed value, a range). It goes back as an invariant with a unit test, not
as a test written to colour the line.

Versions are looked up at setup time (Maven Central for `org.jacoco`, NuGet for `coverlet.collector` and
`dotnet-reportgenerator-globaltool`) — the latest stable release.

## Java — Gradle (JaCoCo)

The plugin, and one report per suite plus one over all of them — beside the test tasks, in `build.gradle` or
in the file that holds the other test levels (`gradle/plugins/coverage.gradle` applied from `build.gradle`):

```groovy
apply plugin: 'jacoco'
jacoco { toolVersion = '<version>' }

def suites = ['test', 'test-integration', 'test-e2e'].findAll { tasks.findByName(it) }

def coverageReport = { String name, List<String> from ->
  tasks.register(name, JacocoReport) {
    description = "Coverage of ${from.join(', ')}, from the suites' last run."
    group = 'verification'
    mustRunAfter suites
    executionData.setFrom(files(from.collect { layout.buildDirectory.file("jacoco/${it}.exec") }).filter { it.exists() })
    sourceSets sourceSets.main
    reports { html.required = true; xml.required = true; csv.required = true }
  }
}

suites.each { coverageReport("coverage-${it}", [it]) }
coverageReport('coverage', suites)
```

Each `Test` task writes `build/jacoco/<task>.exec` once the plugin is applied; a task named in `suites` that
the project does not have is left out. The command is `./gradlew test test-integration test-e2e coverage`; the
report is `build/reports/jacoco/coverage/html/index.html`.

## Java — Maven (JaCoCo)

```xml
<plugin>
  <groupId>org.jacoco</groupId>
  <artifactId>jacoco-maven-plugin</artifactId>
  <version><version></version>
  <executions>
    <execution><id>agent</id><goals><goal>prepare-agent</goal></goals></execution>
    <execution><id>report</id><phase>verify</phase><goals><goal>report</goal></goals></execution>
  </executions>
</plugin>
```

With the integration tests added as a test source (`integration-tests`), Surefire runs every suite in one
execution and one `jacoco.exec` holds them all; the report is `target/site/jacoco/index.html` after
`./mvnw verify`. A Failsafe run of its own needs `prepare-agent-integration` and `report-integration` beside
them, and `merge` for the one report over both.

## .NET (coverlet, ReportGenerator)

`coverlet.collector` is in the xUnit template already; a test project without it gets the package. Each test
project writes a Cobertura file, and ReportGenerator, as a local tool, merges them:

```bash
dotnet new tool-manifest            # where the repository has none
dotnet tool install dotnet-reportgenerator-globaltool
dotnet test --collect:"XPlat Code Coverage" --results-directory TestResults/coverage
dotnet reportgenerator -reports:"TestResults/coverage/**/coverage.cobertura.xml" -targetdir:TestResults/coverage/report -reporttypes:"Html;TextSummary"
```

The architecture test project is left out of the merge (`-assemblyfilters:-*.ArchitectureTests`): it loads the
assemblies to read them, it does not run them. The report is `TestResults/coverage/report/index.html`, the
numbers in `Summary.txt`.

## Shown to work

A report that cannot show a gap proves nothing: run the coverage command once, open the report and find the
domain's types in it with covered lines; then comment out one unit test of a value object's guard, run again,
and see that guard's branch reported missed. Restore the test.

## Recorded

A `## Coverage` section in the conventions file: `coverage: <the command>` and `coverageReport: <the report's
path>`, and the sentence that there is no threshold. The general skills read it there.
