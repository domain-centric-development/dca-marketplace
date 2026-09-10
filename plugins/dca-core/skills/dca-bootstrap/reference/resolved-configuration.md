# Resolved configuration shared by bootstrap and scaffold

Bootstrap writes a `## Resolved configuration` section in `.claude/dca/conventions.md` for every project,
including projects using the vendored catalog. Scaffold reads this section and the current architecture test
and properties before rendering. Preserve unrelated conventions. If dependencies or overrides changed, refresh
this section from the actual resolved preset report; never infer Spring from Java alone.

Record: language, base package/root namespace, actual framework preset and detection/explicit origin, exact
injectable and transactional annotation FQNs (or empty), transaction mode (declarative/explicit/none), configured
operation containers, and verification command. Role overrides in DcaLayout take precedence over preset defaults.
Use the installed preset's literal role lists, including third-party providers; do not guess an annotation.

For Java use-case templates:

| Value | spring, declarative write | none, constructor wiring |
|---|---|---|
| injectableImport | `import org.springframework.stereotype.Service;` | empty |
| injectableAnnotation | `@Service` | empty |
| transactionalImport | `import org.springframework.transaction.annotation.Transactional;` | empty |
| transactionalAnnotation | `@Transactional` | empty |
| wiring | component scan or explicit configuration | render `Configuration.java.tmpl`; host calls its factory |

Queries and explicit-boundary writes leave transactional import/annotation empty. A command that publishes
still needs a real transaction implementation: for none, draw an explicit boundary around load/mutate/save/publish.
An annotation only supplies metadata; configure the runtime transaction manager separately. NAM-002 is diagnostic.
Other presets use their resolved role FQNs; if injectable is empty, use explicit constructor wiring as with none.
`.NET` uses constructor injection and the project's registration style; write operations use ITransactionBoundary.

Render placeholders, conditionals and imports completely; unresolved placeholders fail the smoke check.
