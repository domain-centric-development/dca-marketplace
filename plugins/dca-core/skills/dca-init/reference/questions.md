# dca-init — the questions

Every decision `dca-init` may need, in the order it asks them. After the inspection (Phase 1) the skill
looks each answer up and asks **only the open ones — all at once, in this order, word for word**; a
question with a placeholder (`<type>`) is asked once per thing found, in the order the inspection found
them. An answer goes where the entry says.

Each entry has the same fields: **look up** (where the answer already is — found there, the question is
not asked), **asked** (when the question is put at all), **question** (word for word), **options**,
**default** (the first choice offered, `—` where there is none) and **answer goes to**. An entry marked
*never asked* is decided by its rule; the report names the result, and the person changes it afterwards
where they want another.

What detection settles is not a question: a layout that maps onto `DcaLayout` (`adapter/in`, other contract
package names, a framework preset) becomes builder calls, and a single consistent suffix becomes a suffix
call. The summary before the questions names them.

### INIT-MARKERS
- look up: Phase 1 item 6 — the marker-like types
- asked: once per marker-like type found
- question: `<type>` (<n> types use it) — migrate it to the package marker, or keep it as an alias of the package marker?
- options: Alias — keep the type, make it extend the package marker · Migrate — replace it, delete the old type
- default: Alias
- answer goes to: the edits of Phase 3 (Java step 6, .NET step 6)

### INIT-LAYOUT
- look up: Phase 1 item 5 — folders the layout cannot express (`service/` instead of `application/`, a flat `controller/`–`service/`–`repository/`)
- asked: when such folders exist
- question: The folders `<folders>` do not map onto domain, application and adapter. Adopt the DCA names later — with violations until the code moves — or leave the affected rule sets out for now?
- options: adopt the DCA names later · leave the affected sets out
- default: adopt the DCA names later
- answer goes to: `dca.rules.sets` (leave out) or nothing (adopt)

### INIT-SUFFIX
- look up: Phase 1 items 4 and 5 — the suffixes the code uses
- asked: once per role where the code uses two suffixes for it (use case, MVC controller, REST adapter)
- question: `<role>` classes end in `<a>` and in `<b>`. Which one does the `naming` set hold the project to?
- options: `<a>` · `<b>`
- default: the one more classes use
- answer goes to: `DcaLayout` (`withUseCaseSuffix`, `withControllerSuffix`, `withRestControllerSuffix`)

### INIT-RULES
- look up: an existing `dca-archunit.properties` (`dca.rules.sets`)
- asked: always, where none exists
- question: Which rule sets does the architecture test run? `cycles` always runs, and `dotnet` always on .NET.
- options: the whole catalog · the recommendation for this project from `reference/module-selection-guide.md` · a selection of `layered`, `onion`, `hexagonal`, `naming`, `tactical`, `strategic`, `contextmap`, `advanced`, `usecase`, `errors`
- default: the whole catalog for a new project (`dca-new`); the guide's profile for an existing one — the profile named in the question
- answer goes to: `dca.rules.sets` in `dca-archunit.properties` (the key omitted for the whole catalog)

### INIT-MODULITH
- look up: Phase 1 item 1 — Spring Modulith on the class path
- asked: when Spring Modulith is present (Java)
- question: Spring Modulith is on the class path. Add `dca-archunit-spring-modulith` and a second test that runs Modulith's own analyzer?
- options: yes · no
- default: yes
- answer goes to: the test dependencies and `ModulithTest`

### INIT-CONTEXT-MAP
- *never asked* — rule: `ContextMapDocumentationTest` is installed when more than one context is declared, not with one
- answer goes to: the test next to the architecture test; `docs/architecture/context-map.md`

### INIT-CATALOG
- *never asked* — rule: the catalog vendored with the plugin; a live catalog is `catalog_path:` in the conventions file, set by hand
- answer goes to: the conventions file
