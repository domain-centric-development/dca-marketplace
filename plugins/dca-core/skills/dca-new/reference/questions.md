# dca-new project — the questions

Every decision `dca-new project` needs, in the order it asks them. Before the generator runs, the skill
looks each answer up and asks **only the open ones — all at once, in this order, word for word**; nothing
is asked later in the run. An answer goes where the entry says, never into this run alone.

The pass has three parts, asked together:

1. **The description's open entries** — `dca-describe`'s catalogue (`dca-describe/reference/questions.md`),
   every entry that is open, in its order; where no description exists, all of them. `dca-describe` writes
   the description from these answers afterwards. `dca-new` needs DESC-STACK, DESC-FRONTEND, DESC-SURFACES
   and DESC-PERSISTENCE before the skeleton.
2. **This catalogue's entries** below, in their order.
3. **`dca-init`'s entries that apply to an empty project** — its catalogue
   (`dca-init/reference/questions.md`); on a directory without code only INIT-RULES is asked.

Each entry has the same fields: **look up** (where the answer already is — found there, the question is
not asked), **asked** (when the question is put at all), **question** (word for word), **options**,
**default** (the first choice offered, `—` where there is none) and **answer goes to**. A question that
depends on an answer still open in the same pass is asked with its condition in front ("Where the product
has pages: …") and its answer is dropped where the condition turns out false.

### NEW-BASE
- look up: `project/tech.md → ## Stack` naming a base package or root namespace
- asked: when not found
- question: Which base package (Java) or root namespace (.NET) does the code live under?
- options: the default
- default: Java `com.example.<name>`, .NET `<Name>` — `<name>` from the directory, lower case without separators; `<Name>` in PascalCase
- answer goes to: the generator call (`groupId`, `packageName` / the project names) and `DcaLayout.forBasePackage` / `ForRootNamespace`

### NEW-FORMAT
- look up: a formatter configuration already in the directory (`.editorconfig`, an IDE formatter profile)
- asked: when none is found
- question (Java): Which formatting style does Spotless apply?
- options (Java): `googleJavaFormat()` · `palantirJavaFormat()` · `eclipse()`
- default (Java): `googleJavaFormat()`
- question (.NET): `dotnet format` takes its rules from `.editorconfig`. Take the SDK's file (`dotnet new editorconfig`) as it is, or go through its severities first?
- options (.NET): as it is · go through the severities
- default (.NET): as it is
- answer goes to: the build file (the Spotless step) or `.editorconfig`; the commands as `format:` and `formatFix:` in the conventions file

### NEW-BROWSER-RUNNER
- look up: a browser-test dependency or source set (none exists in an empty directory)
- asked: when DESC-SURFACES names pages, or is itself open in this pass
- question: Where the product has pages: which browser runner do the end-user tests use?
- options: Playwright in the project's language · another runner (name it)
- default: Playwright in the project's language
- answer goes to: the build file; `browser:` in the conventions file

### NEW-SELECTOR
- look up: the conventions file (`selector:`)
- asked: when DESC-SURFACES names pages, or is itself open in this pass
- question: Where the product has pages: which attribute marks the elements the tests reach for?
- options: `data-test` · `data-testid` · another attribute
- default: `data-test`
- answer goes to: `selector:` in the conventions file

### NEW-APP-START
- look up: the conventions file (`appStart:`)
- asked: when DESC-SURFACES names pages, or is itself open in this pass
- question: Where the product has pages: does the browser suite start the application itself on a free port, or point at one that is already running?
- options: started by the suite on a free port · an application already running (name its base URL)
- default: started by the suite on a free port
- answer goes to: `appStart:` in the conventions file
