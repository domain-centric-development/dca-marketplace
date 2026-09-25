---
name: factory-help
description: Explains the delivery pipeline in one fixed view — the flow from describing the project to accepting a story, where this project stands in it, every command in its agent and its shell form, the marks the views use, the files the pipeline reads and writes, and what to do next. Use when someone asks how the factory works, which command does what, what a mark means, where a file is, what to do first, or on "/factory-help". Works before the pipeline is installed; it changes nothing and starts nothing.
---

# Explain the factory

Input: the project's files, read by the gate. Output: the help view in the session. You write nothing and
start nothing.

## Do

1. **Run the one command.** From the project root:

   ```
   bash .agents/factory/factory.sh help --format md
   ```

   Where the project has no `.agents/factory/factory.sh` yet, run the plugin's runner instead — the
   `factory.sh` in this plugin's `factory-run/scripts/` folder, beside this skill's folder — with the same
   arguments; it explains the factory from the plugin's gate and marks every step as still to do.
2. **Show it as it is.** The view is the same text every time; only the marks in the flow and the Next line
   come from the project's files. Do not retell it, translate it, shorten it or add a summary; nothing comes
   after its Next line.
3. **Answer a follow-up from the view.** Asked what a step, a command or a mark means, answer from the row
   that names it, and point to the skill in its agent column.

## Do not

- Do not run a command the view lists — the help only explains; the person picks.
- Do not explain the factory from memory where the command runs: the view is the reference.
