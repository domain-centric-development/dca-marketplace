---
name: skill-writing
description: |
  Writes or rewrites an agent skill (SKILL.md and its reference files), or a rule or brief a model reads, as short
  as it can be with the same behaviour. Use when creating a skill, shortening one, reviewing one for size or
  focus, or when a skill, rule or brief text grew.
---

# /skill-writing

Reader: a model that already knows the field. Write only what it lacks. Not for prose a person reads.

## Keep / cut

| Keep | Cut |
|---|---|
| the project's decisions and conventions | what a term means (SOLID, DRY, TDD, a smell), why a practice is good |
| the output form a caller parses (headings, tables, ids) — byte for byte | intros, "this skill is…", restated description |
| boundaries: when not to apply, which skill does it instead | motivation, history, anecdotes |
| one example where a rule alone would be read wrong | a second example of the same point |
| thresholds, names, commands, paths | hedges, politeness, repetition across sections |
| **the reason behind a rule that needs judgement** ("the stub answers what you told it") — it lets the model catch a case that does not look like the example | the reason behind a mechanical rule (a path, a format, a command) |
| the negative half of a rule ("never after the change that led there") | |
| a named pattern or smell (Mystery Guest, Interacting Tests) — one word recalls the whole case | its definition |

Doubt whether a line carries a decision → keep it, shorter.

Measured (testing skill, 2026-11-15): dropping three reasons and one "never …" half brought back a defect class
the full text had removed, in two of two runs; 2 KB saved, a judge round lost.

## Form

- Imperative, bullets, tables. One line per rule.
- Example over rule list: a short bad/good pair beats five sentences.
- Freedom fits the task: heuristics for open judgement, a template for a preferred shape, an exact command for a
  fragile step.
- One job per skill. `description`: what it does + when it applies (the trigger words a caller uses), third person.
- Answer checkably: tables, ids, `file:line`, fixed headings — never only prose.
- What a check can enforce belongs in the check; the skill keeps what no check can (judgement).
- **Most important first.** Where a reviewer or judge finds the same defect classes again, put them at the top as a
  checklist the model ticks off: one row per class, ordered by how often it is found, a yes/no question and its fix.
  Say when to run it (when the thing is planned, before it is handed over).

## Size

- `SKILL.md` < 500 lines and < ~5,000 tokens (≈ 20,000 chars); aim far lower — a discipline fits in 4 KB.
- Detail a call does not always need → `reference/<topic>.md`, named from `SKILL.md` with when to read it. One level
  deep: a reference never sends on to another.
- Generated files stay as generated; change the source.

## Rewrite procedure

1. Note bytes and lines before.
2. Mark each line: ours (decision, convention, contract, boundary) or general knowledge.
3. Drop general knowledge; compress the rest into the form above. Keep parsed headings unchanged.
4. Diff old against new: every decision still present, or its removal named. Check each removed sentence: was it
   a reason for a judgement rule, a "never" half or a named pattern? Then it stays.
5. Note bytes and lines after. Measure behaviour (evaluation, bench) — do not assume it held.

## Sources

Anthropic, *Skill authoring best practices*; agentskills.io specification; OpenAI, *Codex skills*; Anthropic,
*Effective context engineering for AI agents*; Robert C. Martin, *ub-mode* (a whole discipline in ~4 KB).
