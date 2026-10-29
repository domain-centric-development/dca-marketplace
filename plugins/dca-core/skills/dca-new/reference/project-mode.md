# Mode project — the steps

Part of the `dca-new` skill: what its *Mode project* step list points to — the decisions from the description, the
generator, git, `dca-init`, the formatter, the browser runner, the integration level, the proof and the report.

## 1. The decisions come from the project description

Read the technical and the product description where `dca.profile.yaml` puts them (`tech:`, `overview:`;
`product/tech.md` and `product/overview.md` by default, also where the file is missing). Where there is none, its entries are all open and asked in the one pass below; `dca-describe` then
writes the description from those answers and never invents one. Take from it:

- **the stack** — Spring Boot (Gradle or Maven, the Java line) or .NET (the SDK line);
- **the frontend approach** — server-rendered pages, a client application, or none;
- **the surfaces** — web pages, an HTTP API, a command line, events; which of them has pages decides the
  browser runner (step 6);
- **the persistence** — a data starter or package now, or in-memory until a later story.

**Every question in one pass, from the catalogue.** `reference/questions.md` lists every decision this mode
needs — the description's open entries (`dca-describe`'s catalogue), this mode's own (base package, formatter
style, browser runner, selector attribute) and `dca-init`'s entries
that apply to an empty directory — each with where its answer is looked up first. Look every answer up, then
ask **only the open ones — all at once, before the generator runs, in catalogue order, word for word**, with
the options and the default the catalogue gives; through a structured question tool where the harness has
one, in prose otherwise. Ask nothing the catalogue does not list, and nothing later in the run: a question
halfway stops the run with a skeleton on disk.

An answer goes where the catalogue says: a description entry into the description through `dca-describe`;
the formatter and browser answers to `dca-add formatter` and `dca-add browser`, which record them in the build
file and `dca.profile.yaml`; the rule sets to `dca-init`.

## 2. The skeleton comes from a generator

Versions, dependency ids and project layout come from the generator, never from memory — training data is
older than the current releases.

- **Spring Boot — Spring Initializr.** Read the metadata first: `curl -s -H 'Accept:
  application/vnd.initializr.v2.2+json' https://start.spring.io` lists the current Boot versions (take the
  default), the Java versions, the project types (`gradle-project`, `gradle-project-kotlin`,
  `maven-project`) and the dependency ids. Then generate into the directory:

  ```bash
  curl -s https://start.spring.io/starter.tgz \
    -d type=gradle-project -d language=java -d bootVersion=<default from the metadata> \
    -d javaVersion=<from the description or the metadata default> \
    -d groupId=<group> -d artifactId=<artifact> -d name=<name> -d packageName=<base package> \
    -d dependencies=<ids from the metadata: the web stack for the surfaces, a template engine for
    server-rendered pages, the data starter the description names> | tar -xzf -
  ```

  The base package is the one `dca-init` records as `DcaLayout.forBasePackage`.
- **.NET — `dotnet new`.** The installed SDK is the generator: check its line with `dotnet --list-sdks`
  against the description's version policy and say so when it is older. Create the solution and the host
  project from the template the frontend approach names (`web`, `webapp`, `mvc`, `webapi`), plus a unit-test
  project:

  ```bash
  dotnet new sln -n <Name>
  dotnet new <template> -n <Name>.Web -o src/<Name>.Web
  dotnet new xunit -n <Name>.Tests -o tests/<Name>.Tests
  dotnet sln add src/<Name>.Web tests/<Name>.Tests
  ```
- **Offline fallback (Java).** Where start.spring.io cannot be reached, write the Gradle build from
  `reference/greenfield-java-build.md` — Boot 4 renamed the web starter, split the test starters per slice and
  moved the slice annotations into technology packages, which training data does not know. The versions then
  come from Maven Central or from the person, still never from memory.

## 3. Git

`git init` where the directory has no repository, and a `.gitignore` for the build's outputs — Java/Gradle
`.gradle/` and `build/`, Maven `target/`, .NET `bin/`, `obj/` and `TestResults/`, plus `.idea/`, `.vs/`,
`*.iml`. A generator's `.gitignore` (Initializr ships one; `dotnet new gitignore` writes one) is kept: add only
the lines it lacks. Commit nothing — the first commit is the person's, after the proof.

## 4. The DCA part: `dca-init`

Run `dca-init` on the fresh skeleton. It adds the building blocks and rule packages, the architecture test with
`DCA-STR-012` on `warn` (no domain code yet — empty means green), `dca.profile.yaml` and the method's
section of `AGENTS.md`. Hand it the contexts the designed domain names (`domain:`, `product/domain.md` by default), so their roots are declared from the
start.

## 5. The formatter: `dca-add formatter`

Every project gets its formatter now, while the code base is only the skeleton — the one formatting run is
then trivial, and every later change touches only what it wrote.

## 6. The browser runner: `dca-add browser`

When the product description names a surface with pages (server-rendered or a client application), run
`dca-add browser`. It sets up the runner and one smoke test on the start page before the first feature, so the
first story's end-user test has something to run on.

## 6a. The integration level: `dca-add integration-tests`

Every project gets it, as it gets a formatter: a story's scenarios other than its happy path run at the
integration level, and a project without one stops at its first plan. It is set up now, on the skeleton, with
one smoke test that starts the application.

## 7. Proof

The project is done when all three hold — show each:

- **It starts.** `./gradlew bootRun` / `mvn spring-boot:run` / `dotnet run --project src/<Name>.Web`, one
  request to `/` answers, then stop it.
- **Every suite is green.** `./gradlew build` (runs `check`, `test-architecture` and `test-integration` included) and the browser
  suite (`./gradlew test-e2e`, `mvn verify`); `dotnet build` and `dotnet test` (Debug). The expected entries
  of a project without domain code — `DCA-STR-012` on `warn`, a freshly generated context map — are named,
  not hidden.
- **The browser smoke test can fail.** Empty the start page's `<title>`, run the browser suite, see it red,
  restore the title, see it green. A browser suite that stays green while the page is broken tests nothing.

## Report

The report is read from the disk, so it has the same sections and fields every time — Stack · Generator ·
DCA part · Formatter · Browser runner · Proof · Git · Open. Run `dca-init`'s report script from the project
root, with the generator you used and the result of each proof step:

```bash
python3 <dca-init skill folder>/scripts/dca-report.py --mode new --generator "start.spring.io" \
  --proof start=passed --proof suites=passed --proof smoke=passed
```

(`--generator "dotnet new"` or `"offline reference"`; a proof step that failed is `failed`, one not run is left
out and shows as open.) Show the output as it is and add nothing after it but this one line:

```
Next: the first commit is yours — then /factory-setup and /factory-backlog for a delivery pipeline, or /dca-new context | usecase | aggregate by hand.
```
