# Shared stages

Part of the `factory-run` skill: what its *Execution tier* says about the shared builder and the shared
verifier, in full.

**Plan to tidy in one context — the default.** The builder stages share a context ("shared builder")
unless the profile says `stages: separate`, the person asks for separate stages (`factory.sh run
--separate-stages`) or `FACTORY_SHARED_BUILDER=0` is set. In the runner, one process carries plan, test, build and tidy and runs each
stage's gate itself; the runner checks that the red proof exists and runs the build and tidy gates
again. In a session, the same variant is one subagent for plan to tidy, running the gate after each
stage and stopping on a refusal it cannot fix in three attempts; its window is marked as one stage,
`builder` — `--stage-start builder` before it, `--stage-end builder` after its last file — and the gate
reads that window as plan to tidy. After the end mark do what the runner does: check that
`.dca-factory/evidence/<story>/.tests-red` exists (a builder that never ran its test gate left no red proof; a
journey's or an adoption's test gate runs again instead), then run the build and tidy gates yourself —
they now check the hand-overs against `changed-builder.txt`. In both, the judge keeps a fresh context
of its own, and every stage still writes its own file, so the story can be resumed stage by stage. It
costs less — the stages build on what the one before read — and it gives up one thing: build knows how
the tests were written. With separate stages each of the four runs in a context of its own, as below.
Say in the report which variant ran.

**Judge and document in one context — the default.** The twin of the shared builder: "shared
verifier", separated by the same profile line, `--separate-stages` or `FACTORY_SHARED_VERIFIER=0`. One process
carries the judge and, only on `verdict: pass`, the document stage, which starts on what the judge
has just read instead of reading it again; the process runs the document gate itself and the runner
runs it again. The builder and the verifier are never one process — the judge's independence from the
builder is the point of the split; the verifier shares a context only with the stage after the verdict,
which writes no code. So a story runs in two contexts: one that builds, one that checks.
In a session the same variant is one subagent for judge and document, its window marked `verifier`
(`--stage-start verifier` … `--stage-end verifier`); after the end mark read the verdict as the runner
does and run the document gate yourself. An adoption's verifier is the judge alone.
