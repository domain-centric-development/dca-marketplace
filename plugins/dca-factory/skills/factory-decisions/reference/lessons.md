# A lesson — where a repeated correction belongs

A lesson is a decision record of its own kind (`kind: lesson`), a record of the project's own at
`product/decisions/lesson-<kind>-<key>.md`. The factory wrote it because something repeated across the stories —
counted, never guessed: the same kind of question (`tag:`) in the same context, the same judge finding under one
perspective and rule, the same coded correction at acceptance, the same answered assumption, the same flagged term.
`factory.sh lessons` lists the candidates with their counts; `factory-run/reference/file-contracts.md`, *A lesson*,
holds the record's shape.

## Explain it

Read the record's `## Evidence` and open what it names — the stories' decision records, the finding rows in
`<story>/findings.md`, the `## Assumptions` lines. Say what repeated, in how many stories, and what each place would
mean for the next story. The recommendation is the factory's count, marked as such; it is never the answer.

## Take the answer

The answer is a place, `not now` or `never`, and only the person gives it (step 4 of the skill). Show the block before
it is written, as for every record:

```
## Answer
answer: <the option's key>
by: <the person>
at: <now, UTC>
written: <the file the owning skill wrote, relative to the project>
```

- **`not now`, `never`** — write the block alone; nothing else is written. A press on the page writes it without a
  session. `never` keeps the same candidate from coming back; `not now` lets it back once more stories show it.
- **A place in the project** — the factory writes no rule and no knowledge itself. Run the skill that owns the place
  with the lesson's evidence, and let it write in its own way, on the person's confirmation of what it writes:

  | Place | Owner |
  |---|---|
  | `description` — a statement of the description | the description skill (`/dca-describe <change>`) |
  | `instructions` — a line of the agent instructions | the description skill, which owns that line |
  | `glossary` — an entry of the glossary | the glossary skill (`carrier.glossary`, else `/ubiquitous-language`) |
  | `knowledge-node`, `project-rule` — the project's own node or architecture rule | the method's skills (`/dca-modelling`) |
  | `profile-check` — a check the profile names | `/factory-setup` |
  | `criterion` — a criterion the stories of this kind lack | `/factory-backlog` |

  Then write the answer block with `written:` naming each file the skill changed, so the record links what was
  written. The next story's brief carries it like any other part of the project: the plan reads the description and
  the glossary, the gate runs the profile's checks and the rule suite.
- **`factory`, `rule-library`, `knowledge-catalog`** — the correction is the maintainers', not the project's: nothing
  in the project changes. Write the answer block; a person tells the maintainers. Nothing leaves the machine by
  itself, and you send nothing.

## Do not

- Do not write the place yourself, nor choose it: the owning skill writes, the person chooses.
- Do not edit the record's evidence or options — a lesson asked on other evidence is a new record the factory writes.
- Do not answer a lesson to unblock a story: none waits for it.
