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

   It starts no tool. Where the project has no pipeline yet, `install --tool <claude|codex|opencode>`
   instead.
2. **Report what it says, in this order:** the versions (`updated A → B`), the file contract, and
   whether the stack profile's `contract:` line has to be raised. Raising that line is the human's
   edit — the profile belongs to the project — so show the line and do not change it.
3. **Say how the skills are held.** Links point into the plugin or a checkout and follow it live; they
   belong in `.gitignore`. Copies are the project's pinned pipeline: they belong in the repository,
   and the update listed which it copied, which of the project's own it kept and which it removed.
4. **Name what to commit:** `.agents/factory/`, `.githooks/pre-commit`, `.gitattributes`, the
   `AGENTS.md` section, and the skill copies where the project keeps copies.

**Speak in skills.** You run the commands; the person gets the result and, for a next step, the
skill that does it. You may run `factory.sh` for everything that starts no tool, never `run` or
`backlog`.

## Do not

- Do not run `factory.sh run` or `backlog`.
- Do not commit, push or change the stack profile.
- Do not update from a folder the human did not name or this skill does not belong to.
