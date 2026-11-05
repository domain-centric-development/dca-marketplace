# The checks, one per rule

The table the skill's section 15 names. Each row is one check; prefer the stylelint rule in brackets where the stack
has a Node toolchain, otherwise a plain test that reads the stylesheet and the render code as text.

| Rule | The check |
|---|---|
| tokens | no colour literal outside the token file (`color-no-hex`, `declaration-strict-value`) |
| flat specificity | no id selectors, no `!important` outside utilities (`selector-max-id`, `declaration-no-important`) |
| naming | by the chosen method: BEM — every class a known block, element or modifier (`selector-class-pattern`); native scoping — every `@scope` root a known component with a lower boundary at its slots |
| no reach-in | a selector naming two blocks sets placement only; no element of one block under another |
| state | no state word as a class; no class toggled by script; every `data-state` value is a product state |
| views compose | no visual class and no `style=` in view or controller code |
| fields | no bare input, select or textarea outside the form row |
| type floor | no font size below the floor |
| widths | the stylesheet uses only the named widths; the script's copy equals them |
| public set | the example theme and the token file list the same public tokens; no deprecated token read |
| gallery | every component appears in the pattern library |
| sanity | braces and parentheses balance (a broken rule silently unstyles the page) |
