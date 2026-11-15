# freeze

The procedure for `dca-add freeze`. For late adopters; a new project has nothing to freeze.

1. Run the architecture test; list failing rules with violation counts.
2. Per rule, with the user: freeze, ignore by pattern, `warn`, or fix now. Record why in `dca.rule.<id>.reason`.
3. Write into `dca-archunit.properties` (same keys Java and .NET):

   **Baseline:**

   ```properties
   dca.rules.freeze        = DCA-ONI-002,DCA-HEX-003
   dca.rules.freeze.store  = arch/frozen
   ```

   First run records current violations and passes; later runs fail only on violations not in the store; a fixed
   one leaves it. **Commit the store** — otherwise the next checkout records a new baseline and hides
   everything. Code form (file form preferred, the report shows it):
   `DcaRuleSelection.all().frozen(...).withFreezeStore(Path.of(...))` in `additionalSelection()` (C#:
   `.Frozen(...).WithFreezeStore(...)`). Store per language: Java ArchUnit's text store, .NET `FrozenRules.json`
   — both stacks keep two. Only rules with `"freezable": true` in `rules.json` (same ids in both): the
   context-map set and rules iterating over bounded contexts fail naming themselves → `warn` or ignore instead.

   **Ignore pattern**, one regex per key:

   ```properties
   dca.rule.DCA-ONI-002.ignore   = .*\.Legacy\..*
   dca.rule.DCA-ONI-002.ignore.1 = .*ReportExporter.*
   ```

   The value is **one** expression, commas included; more go to `.ignore.1`, `.ignore.2`, …. Works for every
   rule (the documented exception); the baseline is the quick start that shrinks on its own.
4. Re-run: green, frozen/ignored/lowered rules named in the report.
