# Classify the findings from before contract 39

Once per project, on `/factory-decisions findings classify` or the request `classify-findings`. The judge classes every
finding from contract 39 on; this gives the older rows the same three cells, so lessons and the Quality card count
them alike.

## The lists

Read them where the judge reads them: `.agents/factory/workflow/rules/stage/STAGE-JUDGE-6A.md` — `Target`, `Type`,
`Qualifier`. Never a word outside them.

## Do

1. `factory-cli.py --unclassed-findings` says how many rows wait. Open every `findings.md` of the stories and every
   file under `product/findings/`.
2. Per row whose last three cells are empty (or missing — a ten-cell row): read its perspective, `File:line`, severity,
   `In plain words`, `Defect`, `Fix`, and the story's `judge.md` row where it still lies in the run folder. Decide as the
   judge would:
   - **Target** — what has to change to correct it (the file at `File:line` is a hint, not the answer: a test helper
     copied into every class is `test`; a plan that named no invariant is `plan`).
   - **Type** — the kind of correction; a `domain-…:` code the `Defect` opens with is its type.
   - **Qualifier** — `missing` (something must be added), `incorrect` (something there is wrong), `extraneous`
     (something must go: a copy, dead code, an unplanned guard).
   - Where no value of a list fits, write `—` in all three cells. Never force a value.
3. Write the three cells at the end of the row (a ten-cell row gains them; the header gains `| Target | Type |
   Qualifier |` and its rule three columns). Change no other cell, no row's order, add or remove no row.
4. Add to the file's front matter one line: `classes: backfilled <today> by request <id> (<n> rows, <m> without a
   fitting value)` — by hand `by <the person>` in place of the request.
5. Say per file how many rows you classed and how many took `—`.

## What the factory checks afterwards

For a request: every file it wrote is compared with the last commit — only empty class cells filled, each from its list
or `—` in all three, the `classes:` line, nothing else. A file that does more is put back and the request fails with
the reason. By hand the same holds: the person reviews the diff and commits it.

## Do not

- Do not rewrite `Defect`, `Fix`, `In plain words` or `Status`, nor re-judge a finding.
- Do not class a row that has a class.
- Do not commit: the factory commits a request's work; by hand, the person does.
