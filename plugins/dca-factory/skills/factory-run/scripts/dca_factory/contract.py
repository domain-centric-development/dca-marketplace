"""The pipeline's version stamp — two numbers, nothing else, read by name: `factory.sh` takes them out of this file
(`gate_field`), and so does an installed copy of any older or newer release comparing itself with this one.

CONTRACT is the version of the *files* the gate reads and writes: the stack profile's keys, the `gate:tests` table, the
red ledger, the shape of a document claim. It goes up only when an older or newer artefact would be read wrongly —
that is what makes a mismatch a refusal.

VERSION is where this copy came from. The gate is *copied* into a project (`.agents/factory/`), so a project can be
governed by a release older than the pipeline it was installed from without anything being incompatible. That is an
update to offer, never a reason to refuse, and only the installer can see it — it is the one place that holds both
files.
"""

CONTRACT = 26


VERSION = "0.97.1"
