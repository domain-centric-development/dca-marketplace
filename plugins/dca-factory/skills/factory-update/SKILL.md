---
name: factory-update
description: Brings this project's copy of the delivery pipeline — gate, runner, commit hook and, where the project keeps them, its skill copies — up to the newest pipeline installed on this machine, for the tools the project already uses, keeping links as links and copies as copies. Use when the factory reports that the project was installed from an older pipeline, after the plugin or marketplace was updated, or on "/factory-update". It commits nothing and never rewrites the stack profile.
---

# Update the project's pipeline

Input: the project and the pipeline this skill belongs to. Output: the project's copies replaced, and
a report of what changed. You commit nothing; the human reviews and commits.

## Do

1. **Run the update from this skill's pipeline.** This skill's folder sits beside `factory-run`, so
   the plugin's runner is `<this skill's folder>/../factory-run/scripts/factory.sh`. From the project
   root:

   ```
   bash <this skill's folder>/../factory-run/scripts/factory.sh update --from <this skill's folder>/..
   ```

   It starts no tool. It hands over to the newest pipeline's runner, which replaces the gate, the
   runner, the observer, the commit hook, the permissions and the `AGENTS.md` section, and leaves the
   stack profile's lines alone. Where the project has no pipeline yet, that is `/factory-setup`'s, not
   this skill's.
2. **Report the migration, where there was one.** A project from before the layout with one owner per
   place is moved once, and every move is printed (`factory: migrated …`): the stack profile from
   `.agents/factory/` to `dca-factory.profile.yaml` at the root, its `backlog:` line to `epics:`,
   `project/backlog/` to `project/epics/`, each decision record from `.agents/factory/decisions/` to
   `<story>.decisions/` beside its story, each `tasks/<story>/` that carries factory marks to
   `.dca-factory/runs/<story>/` — anything else under `tasks/` is the project's and stays — and the
   delivery mark into the story as `status: delivered` and `delivered:`. Show the moves; a second run
   moves nothing. A `backlog/` at the project root from before `project/` is named, not moved.
3. **Report what else it says, in this order:** the versions (`updated A → B`), the file contract,
   and whether the stack profile's `contract:` line has to be raised (the migration raises it when
   it rewrites the profile anyway; otherwise that is the human's edit — the profile belongs to the
   project — so show the line and do not change it).
4. **Say how the skills are held.** `.dca-factory-skills` beside them says it. Links point into a
   checkout and follow it live; the install keeps them out of git itself, one `.gitignore` line per
   link. Copies are the project's pinned pipeline: they belong in the repository, and the update listed
   which it copied, which of the project's own it kept and which it removed. The update keeps the
   mode; `--copy` or `--link` switches it on the person's word — name it when the update warns that
   links point into a plugin cache (its versions are removed after an update).
   **A method skill the install did not copy** — `dca-modelling`, `ubiquitous-language` and the like, copied by
   hand or by `dca-new` — is named as `kept the project's own … has another version`. Show each one and ask
   whether to take it over; on the person's yes run the update again with `--adopt <skill>,…` (or `--adopt
   all`). From then on every update refreshes it. A copy byte for byte the plugin's is taken over without a
   question; one the person edited on purpose stays theirs.
5. **Name what to commit:** `.agents/factory/`, `.githooks/pre-commit`, `.gitattributes`, the
   `AGENTS.md` section, `.dca-factory-skills` in each skill folder, the skill copies where the
   project keeps copies — and after a migration the moved files: the profile at the root, `project/epics/`
   with the records beside the stories, and `.dca-factory/runs/` where the project commits its history.
6. **Name what was renamed.** The method plugins renamed skills (`review-domain` → `review-ddd`,
   `review-boundaries` → `review-hexagonal`, `review-craft` → `review-clean-code`, `ddd-modelling` →
   `dca-modelling`, `dca-bootstrap` → `dca-init`, `dca-scaffold` → `dca-new`). The update removes a
   copy under an old name that is byte for byte the old plugin's own and keeps one the project
   edited; it names each profile line that still uses an old name with its new form. Show those
   lines — the profile is the human's to change, and a run stops on an old name until it is.
7. **End with what the project gained since.** Run `bash .agents/factory/factory.sh setup --check`
   and show its lines: detected keys the profile lacks, values that differ from detection, and — where
   the method's conventions file names a `verify_command:` — whether the profile's `architecture:` still
   says the same (a difference is named with both commands; which one is right is the human's call).
   You write nothing into the profile — the human adds a line, or confirms `setup --write`.

**Speak in skills.** You run the commands; the person gets the result and, for a next step, the
skill that does it. You may run `factory.sh` for everything that starts no tool, never `run`.

## Do not

- Do not run `factory.sh run`.
- Do not commit, push or change the stack profile — `setup --write` is the human's to confirm.
- Do not update from a folder the human did not name or this skill does not belong to.
