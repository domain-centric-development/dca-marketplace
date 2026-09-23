---
name: factory-update
description: Tells whether this project's copy of the delivery pipeline — gate, runner, commit hook, skill copies — is behind the pipeline installed on this machine, and gives the person the one shell command that updates it. Use when the factory reports that the project was installed from an older pipeline, after the plugin or marketplace was updated, or on "/factory-update". It runs no installer itself: `factory.sh` is the person's, in a shell.
---

# Is the project's pipeline current?

Input: the project's `.agents/factory/gate.installed` and the pipeline this skill belongs to. Output:
an answer, and the command the person runs. You change nothing.

## Do

1. **Read both versions.** The project's: `version:` and `contract:` in
   `.agents/factory/gate.installed`. This pipeline's: `VERSION` and `CONTRACT` in
   `<this skill's folder>/../factory-run/scripts/story-gate.py`. Where the project has no stamp, the
   pipeline is not installed there — say so and give the install command instead (step 3).
2. **Say what differs.** The same version: nothing to do. A newer pipeline: the versions, and — when
   the contract differs — that the stack profile's `contract:` line has to be raised after the
   update, by hand, because the profile belongs to the project.
3. **Give the one command, for a shell.** From the project root:

   ```
   bash <this skill's folder>/../factory-run/scripts/factory.sh update --from <this skill's folder>/..
   ```

   (for a project without the pipeline: `… factory.sh install --tool <claude|codex|opencode>`).
   Fill in the real path. It updates for the tools the project already uses, keeps links as links
   and copies as copies, and commits nothing.
4. **Say what to commit afterwards:** `.agents/factory/`, `.githooks/pre-commit`, `.gitattributes`,
   the `AGENTS.md` section, and the skill copies where the project keeps copies.

**Speak in skills.** You run the reading; the person gets the result and, for a next step, the
skill that does it — except this one step, the update itself, which is a shell command they run.

## Do not

- Do not run `factory.sh` — not `update`, not `install`, not anything else. It is the person's.
- Do not change the stack profile, commit or push.
