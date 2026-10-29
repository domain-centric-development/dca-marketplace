# The question pass

Part of the `factory-backlog` skill: the list its step 6 runs over a story before it is released — read the
story, the three files of the project description, the glossary and the code the story touches, then go through
every item. Ask the human what it turns up, while they are here — a question left for the plan stage stops a loop
later, when nobody is there to answer.

- **context:** is the story's context on the designed map? If not, it is a question about the
  description — a new context, a new relationship — asked now, not a story;
- **surface and actor:** does a trigger or an outcome need an entry point, a page or a message
  `## Surfaces` does not list, or an actor `## What and for whom` does not name? Who may reach
  it? (Ask *whether* a way exists, never *which* one to build.)
- **technical fit:** does the story need what `product/tech.md` excludes — a second persistence,
  a client framework where pages are server-rendered — or what the stack cannot do? That is a
  question about the technical description, not a detail of the story;
- **external dependency:** a system neither the designed map nor `## Integrations` carries is a
  question about the description, not a story. Its contract (endpoints, the request and answer
  bodies with each field's type — a money amount as a decimal string, never a JSON number — status
  codes, what counts as unavailable) goes into the description and the configuration once, never
  into the story. A shape the description leaves open is a question now: two implementations fill
  it differently;
- **inputs:** format, allowed range, and what happens at its edges. Every limit a rule names gets two
  scenarios, one on each side: the limit itself accepted and the first value past it refused — "1 to 200
  characters" is four (200 accepted, 201 refused, 1 accepted, an empty value refused), "at most 5" is two
  (5 accepted, 6 refused). A limit with only its refusal written leaves its acceptance untested, and the
  gate can only hold the tests to the scenarios there are;
- **examples:** the values of a rule's scenario sit where the rule differs from the obvious neighbour —
  a rounding exactly on the half cent, where rounding half up and half to even part; a limit on both
  sides of it. An example both rules answer alike proves neither;
- **malformed address:** an address that carries an id (`/tasks/{id}/…`) gets a scenario for an id that is
  not even well-formed, answered as the product answers an unknown one — not by the framework's default
  error;
- **position and order:** a rule about where an item stands — the order of a list, its place after a
  change — gets a scenario that changes an item in the middle, not only at the ends;
- **defaults:** one stated value, and where the user sees it;
- **failure of a dependency:** the behaviour, and after how long a slow answer counts as a failure;
- **state and lifecycle:** every transition a rule names, including the conflict case where two
  sources of the same value meet;
- **changed behaviour:** what looks different afterwards → `## Changed expectations`. Where the change alters
  a scenario the spec already holds (`product/spec/<context>/…/scenarios.md`) — its outcome, or only its
  example — the story also carries that scenario as a criterion: its `#### <key>` from the spec, with the
  new text. The spec takes a story's criteria by key; a change said only in prose leaves the old text
  standing, and the spec then contradicts the test that proves it;
- **already a story's:** compare every scenario with the scenarios of the delivered and adopted stories
  under the epics, and with the tests that assert them. A scenario another story already carries is
  not written again: name that story and leave it out. A whole story that is covered so is not
  written — or, where it exists already, is set `superseded` on the person's say-so;
- **already the system's behaviour:** a whole story whose scenarios the system already shows, and
  no story carries, is not a story to build but one to **adopt** — `status: adopted` (the backlog
  contract's "Adopted story"): the factory maps it to green tests, writes the missing ones with a
  break each, and records it as delivered with evidence. Offer it; on a brownfield project, offer
  once per new story to adopt the existing behaviour the new story depends on — never as a stop;
- **already green:** check every scenario whose outcome is an absence or a non-change — "no …
  is shown", "nothing changes", "… still works" — against the code as it is today. If it already
  holds (the element does not exist yet, so it is not shown), it is a guarantee, not a
  criterion: its test would be green before the build, and the gate refuses that. Take it out
  of the criteria and say so; the plan stage turns it into a guard for the existing tests. Keep
  it only when today's system does show what the scenario forbids;
- **repeated or abusive use:** a rule a user can probe or exhaust;
- **coverage:** a rule without a scenario, a scenario with two causes, a `Then` no test can observe;
- **out of scope:** what this story leaves to another → `## Out of scope`.
- **operations:** is every scenario's `When` an operation the glossary or the description names,
  with the word the code uses? Ask a missing one as its effect — what exists before the step and
  after it, and whose state changes (e.g. does the thing exist before, or does the step create it?
  is it gone afterwards, or kept with a state?) — never as a translation. Where the session can
  search, look up first how the field of the story's context names that operation (a standard, the
  vocabulary of widely used systems, the look-alike operations they keep apart) and offer what you
  find, with its source, as the options. The answer is an `answered:`
  assumption with both words (`anlegen (create)`); the plan proposes it for the glossary.
- **outcome:** is this the story after which the epic's outcome event (`metric:`) can happen — the
  step that completes the flow? Then it says so in its front matter, `publishes: <Event>`, with the
  event's name exactly as the epic's `metric:` writes it. The plan gate refuses a name the metric does
  not carry, and the document gate refuses the story while the code declares no such type or nothing
  the story changed raises it. Ask where it is not obvious: "After which story can the outcome happen?"

What the project description already answers is not asked again. Answers go into rules, scenarios or
`answered:` assumptions; what stays open is an `open:` assumption.
