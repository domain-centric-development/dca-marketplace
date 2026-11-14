# Adopt the rules on existing code — scope, warn, ignore or freeze — digest

Node: `/recipe/adopt-the-rules-on-existing-code.md` — cite it by that path; read it in full only for a decision this digest leaves open.

An existing code base switches the rule catalog on and the first run is red, often by hundreds of violations.

## Steps (first sentence each)

1. **Run the whole catalog once and count per rule.** The report names every rule with its violations.
2. **Fix the handful now.** A rule with two or three violations is cheaper to meet than to configure.
3. **Decide per remaining rule, with the team:** - **Scope** (`dca.rules.sets`): leave a whole set out for now when the code is far from it — adopt the sets in stages, the cycles and layer rules first.
4. **Commit the configuration and the baseline.** The file (`dca-archunit.properties`) and the freeze store belong in version control: they are the record of what the team accepted and why.
5. **Run again: green.** The report lists the warned, ignored and frozen rules with their reasons.
