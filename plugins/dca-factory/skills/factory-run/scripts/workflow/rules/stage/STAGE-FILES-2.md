---
id: STAGE-FILES-2
part: told
section: The journal — `.dca-factory/evidence/<story>/journal.tsv`
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/file-contracts.md
---

# STAGE-FILES-2

One line per event, tab-separated: `<UTC time>\t<kind>\t<name>\t<field>=<value>…\tseq=<n>`. The sequence
number orders the events, never the clock (after a union merge repeated a number, the time decides between the two): two events in one second are told apart by it, and which hand-over
belongs to the story's current pass is read from it alone — no file time is compared. Every line is appended
through one function of the gate, under the journal's lock (the folder `journal.tsv.lock`); the runner composes
its lines and pipes them through `factory-cli.py --journal-line <story>`. Nothing else writes the file, and
nothing rewrites it. A line without `seq=` takes its position in the file.
