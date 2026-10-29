# First run in a project

Part of the `factory-run` skill: what its *First run in a project* step points to — what `/factory-setup` installs,
how the stack profile is detected, and how a capability is added later.

The entry is `/factory-setup`: it checks the project description, git, the runner and the stack
profile, and does only what is missing. Where you are asked to run a story in a project without a
pipeline, say so and hand over to it. What it runs:

0. The project has an architecture to gate on — a rule suite and the building blocks its code
   implements — or the architecture check is skipped and named. Installing one is the method's
   (in a DCA project `/dca-init`), once per project; the factory delivers stories and calls no skill
   that writes code.
1. Run the pipeline's setup from this skill's folder, for the tool you are:
   `bash <this skill's folder>/scripts/factory.sh setup --tool <claude|codex|opencode>`, and report
   what it printed. It starts no tool, and it stops with one line where the directory is not a git
   repository. It puts the gate, the runner and the observer under `.agents/factory/`, the commit
   hook under `.githooks/`, `.gitattributes`, the `.gitignore` lines for `.DS_Store` and `Thumbs.db`
   (a file manager's drop would otherwise stop a run as an unclaimed change) and for `/.dca-factory/*`, the
   pipeline's protocol, with the story journals let in (left out where the `.gitignore` already names it), the pipeline's section in `AGENTS.md` and, for Claude
   Code, the gate's permission and a SessionStart hook; it writes the stack profile first, from what
   it detects. The hook runs `factory.sh check --staged`: tool hooks and deny rules do not port
   between agent tools, but every tool commits through git, so that is where the guard belongs.
2. Check the stack profile setup wrote (`dca-factory.profile.yaml`, from
   `templates/factory.profile.yaml.tmpl`), and add the `required:` line with what the human says
   must hold for every change. Where a command is wrong or missing, fix it there.
   **Detected, not assumed:** the commands come from the presets in `templates/presets/` — one flat
   file per build tool, browser runner, formatter or rule package the setup can recognise, each with
   the files that give it away and the profile lines it writes. What no preset recognises stays out
   of the profile. Leave a command out when the project has none: the gate then skips that check
   and names it — which is honest, whereas gating on a command that does not exist turns governance
   off after the second red run.
3. Adding a capability later means one more line in the profile, not an edit to any stage: a
   formatter under `format:` and `formatFix:`, a rule suite under `architecture:` (both run by the
   build gate), a further review perspective under `reviews:`, the reviewer for an existing
   perspective under `review.<perspective>:` (both read by `stage-judge`), or the skill that carries
   a stage's craft under `carrier.<stage>:` (read by that stage). Where the project set the
   capability up since — a browser runner, a formatter —
   `bash .agents/factory/factory.sh setup --check` names the lines detection would add, and
   `setup --write` adds them once the human agrees; a value the human wrote is never overwritten.
