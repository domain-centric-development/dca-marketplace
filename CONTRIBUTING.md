# Contributing

Contributions are welcome: a defect report, a question the documentation leaves open, a proposal, a
pull request.

## Before a pull request

- **Open an issue first** for anything beyond a small fix. It says what is wrong or missing and
  what you propose, so the direction is agreed before the work is done.
- **Read `AGENTS.md`** in the repository root and the one of the plugin you change. They hold the
  conventions, the checks to run and what a change pulls along.
- **One change per pull request**, with conventional commits whose scope names the plugin or the
  skill: `fix(dca-factory): …`, `feat(dca-core): …`, `docs: …`.
- **A plugin change needs a version bump** in its `plugin.json` and a line in its changelog where
  the plugin keeps one.

## Licences

The repository carries two licences, one per kind of plugin:

| You change | Your contribution is published under |
|---|---|
| `plugins/dca-core/`, `plugins/dca-craft/`, anything outside `plugins/` | MIT — [LICENSE](LICENSE) |
| `plugins/dca-factory/`, `plugins/dca-factory-cockpit/` | PolyForm Shield 1.0.0 — [LICENSE.md](plugins/dca-factory/LICENSE.md) |

## Contributor Licence Agreement

Every contributor agrees to the [Contributor Licence Agreement](CLA.md) once, before the first pull
request is merged. You keep the copyright in what you contribute; the agreement gives the copyright
holder the right to publish it under the licence above and under other terms beside it, commercial
ones included. That is what keeps the project able to offer the factory on other terms without
asking every contributor again.

To agree, write the sentence at the end of `CLA.md` as a comment in your pull request.

Two things the agreement asks you to check before you do:

- **Your employer.** If you write in your working time, as part of your job or on your employer's
  equipment, the rights may be your employer's. Contribute only with their agreement.
- **AI assistance.** It is fine, and most of this repository was written that way. Review what the
  assistant produced, and say so in the pull request.
