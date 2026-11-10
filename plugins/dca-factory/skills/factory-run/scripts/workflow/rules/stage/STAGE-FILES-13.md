---
id: STAGE-FILES-13
part: told
why: a stage could quietly change what an older test expected and turn a contradiction green
section: Tests that existed before the story — `.dca-factory/evidence/<story>/.tests-baseline`
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/file-contracts.md
---

# STAGE-FILES-13

The plan gate runs before any stage of a story touches a test. In a git repository it records every
test file — found by name: `test_*.py`, `*Test.java`, `*Tests.cs`, `*IT.java`, `*.spec.ts`,
`*_spec.rb` and the like — as a git blob, once per story. The test, build and tidy gates compare
against it: a file that still holds every line it had, in order and outside a comment, has only
gained cases and passes. A file whose lines changed only around its assertions passes with a note: every
assertion statement it had — an `assert…`, `expect…`, `verify…` or `should…` call with its chain — is still
there, its words and literals in the same order, at most with more arguments (a type the test builds
gained a field) — or naming a type or a method the story renamed, under its new name. A rename is read from
the tree, never claimed: the old name was declared in the story's base tree and is declared in no source now,
the new one is declared now (without a base tree only a type counts); an old name that is still declared — an
alias — is no rename. The note names each pair and whether a context's glossary names the new one. A changed
expected value, a weaker matcher or a removed assertion is no such change, renamed or not. Any
other changed or removed line — or an added line that switches a test off, such
as `@Disabled`, `[Fact(Skip = …)]`, `@pytest.mark.skip`, `it.skip(` or `.only(` — fails `tests-kept`
unless it is **authorised**:
