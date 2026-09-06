# DCA Marketplace für Claude Code, Codex, Antigravity und OpenCode

Stand: 3. September 2026

## Ziel

`dca-core` und `software-craftsmanship` sollen aus **einer fachlichen Quelle**
gebaut und in vier Agent-Harnesses genutzt werden können:

- Claude Code
- OpenAI Codex
- Google Antigravity
- OpenCode

Der gemeinsame Nenner ist das offene Agent-Skills-Format: ein Verzeichnis pro
Skill mit einer `SKILL.md`, YAML-Frontmatter (`name`, `description`) und
optionalen Referenzen, Skripten, Templates und Assets. Die heutigen Skills sind
deshalb die richtige kanonische Quelle. Marketplace-Manifeste, Agent-Metadaten,
Installationspfade und einige Tool-Namen sind dagegen harness-spezifisch und
müssen als dünne Adapter behandelt werden.

## Kurzfassung

| Bestandteil | Claude Code | Codex | Antigravity | OpenCode |
|---|---|---|---|---|
| `skills/<name>/SKILL.md` | nativ | nativ | nativ | nativ |
| Bestehendes Claude-Marketplace-Manifest | nativ | importierbar | nein | nein |
| Eigenes Plugin-Manifest | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` | `plugin.json` | nur für JS/TS-Lifecycle-Plugins; für DCA nicht nötig |
| Marketplace/Katalog | `.claude-plugin/marketplace.json` | `.agents/plugins/marketplace.json` oder Claude-kompatibler Import | derzeit lokale/globale Plugins, kein gleichwertiger Git-Marketplace-Workflow dokumentiert | kein gleichwertiges Skill-Marketplace-Manifest; Git/Installer oder npm nur für Code-Plugins |
| Eigene Agents | `agents/*.md` | nicht als portable Plugin-Komponente einplanen; Verhalten in Skills überführen | `agents/*.md` mit eigenem Frontmatter | `.opencode/agents/*.md` mit eigenem Frontmatter |
| Projektanweisungen | `CLAUDE.md` | `AGENTS.md` | Rules unter `.agents/rules/`, global `~/.gemini/GEMINI.md` | `AGENTS.md`, mit `CLAUDE.md` als Fallback |

**Empfehlung:** Das Repository bleibt ein Monorepo mit kanonischem Inhalt und
generierten Distributionen. Fachliche Texte werden nicht viermal gepflegt.

## Aktueller Ausgangspunkt und konkrete Lücken

Bereits gut portierbar sind:

- alle zehn Skills unter `plugins/*/skills/`;
- deren Referenzdateien, Templates und der vendorte OKF-Katalog;
- die Trennung in `dca-core` und `software-craftsmanship`;
- die vorhandenen Claude-Manifeste und der Claude-Marketplace.

Vor einer Multi-Harness-Veröffentlichung müssen folgende Kopplungen beseitigt
oder über Adapter aufgelöst werden:

1. Mehrere Skills sprechen explizit von `Claude` oder verlangen Claude-Tools
   wie `AskUserQuestion` bzw. einen `Explore`-Agenten.
2. Konfiguration wird fest in `.claude/dca/conventions.md` und danach in
   `CLAUDE.md` gesucht.
3. `dca-knowledge` verwendet `${CLAUDE_PLUGIN_ROOT}` und
   `.claude/dca/catalog/` als Auflösungspfade.
4. `dca-bootstrap` erzeugt ausschließlich `CLAUDE.md`- und
   `.claude/dca/`-Artefakte.
5. Die fünf Agents verwenden Claude-Toolnamen (`Read`, `Glob`, `Grep`,
   `Bash`, `WebFetch`), deren Namen und Frontmatter nicht portabel sind.
6. README-Texte und Ausgaben setzen Claude-Slash-Commands und die Claude-
   Installationssyntax voraus.

## Zielstruktur

Die risikoärmste Struktur ist eine kanonische Quelle plus generierte Adapter:

```text
dca-marketplace/
├── plugins/                         # kanonischer, providerneutraler Inhalt
│   ├── dca-core/
│   │   ├── skills/
│   │   ├── agents/                 # kanonische Agent-Prompts
│   │   └── .claude-plugin/plugin.json
│   └── software-craftsmanship/
├── .claude-plugin/marketplace.json
├── .agents/plugins/marketplace.json       # Codex-Katalog
├── adapters/
│   ├── codex/<plugin>/.codex-plugin/plugin.json
│   ├── antigravity/<plugin>/plugin.json
│   └── opencode/<plugin>/
│       ├── skills/
│       └── agents/
├── scripts/build-distributions.sh
├── scripts/check-portability.sh
└── dist/                            # generiert, nicht manuell editieren
    ├── claude/
    ├── codex/
    ├── antigravity/
    └── opencode/
```

`dist/` darf alternativ nur als Release-Artefakt entstehen und muss dann nicht
eingecheckt werden. Wichtig ist, dass Symlinks nicht die Distributionsstrategie
bilden: Installations-Caches und Archive kopieren oft nur den jeweiligen
Plugin-Unterbaum.

## 1. Kanonische Inhalte providerneutral machen

### Sprache und Tool-Abstraktion

In allen `SKILL.md` und Referenzen:

- `Claude` durch `der Agent`, `das Modell` oder `der Coding-Agent` ersetzen,
  sofern tatsächlich kein Claude-spezifisches Verhalten gemeint ist;
- keine konkreten Toolnamen fordern; stattdessen die Absicht beschreiben,
  beispielsweise „frage den Benutzer gebündelt nach den offenen
  Entscheidungen“ statt „use `AskUserQuestion`“;
- Delegation semantisch formulieren: „verwende, falls verfügbar, einen
  read-only Recherche-Subagenten“ statt einen `Explore`-Agenten vorauszusetzen;
- Slash-Command-Namen als optionale manuelle Aufrufe behandeln. Skills müssen
  auch durch automatische Intent-Erkennung korrekt funktionieren;
- keine feste Modellfamilie in den Fachanweisungen nennen.

OpenAI empfiehlt bei der Konvertierung eines Claude-Plugins genau diese
Neutralisierung und verlangt, Verhalten aus `commands/` und `agents/` für eine
portable Veröffentlichung in Skills zu überführen. Siehe
[Submit your Claude Code plugin to OpenAI](https://developers.openai.com/plugins/guides/submit-claude-plugin).

### Portables Konfigurationsprotokoll

Alle Skills und Agents sollten dieselbe Suchreihenfolge verwenden:

1. expliziter Pfad aus der Benutzeranfrage;
2. `<project-root>/.agents/dca/conventions.md` als kanonischer,
   harness-neutraler Pfad;
3. Legacy-Fallback `<project-root>/.claude/dca/conventions.md`;
4. `AGENTS.md`;
5. `CLAUDE.md` als Claude-/OpenCode-Kompatibilitätsfallback;
6. dokumentierte DCA-Defaults.

Neue Installationen schreiben `.agents/dca/conventions.md`. Bestehende
Claude-Projekte bleiben durch Schritt 3 kompatibel. `dca-bootstrap` muss bei
Projektanweisungen die vorhandene Datei respektieren und je Harness anbieten:

- Claude: `CLAUDE.md`
- Codex und OpenCode: `AGENTS.md`
- Antigravity: `.agents/rules/dca.md`

Der Benutzer wählt das Ziel oder `all`; vorhandene Dateien werden ergänzt,
nicht ersetzt.

### Portable Ressourcenauflösung

`dca-knowledge` darf nicht von `${CLAUDE_PLUGIN_ROOT}` abhängen. Die
Suchreihenfolge sollte sein:

1. `catalog_path` aus `.agents/dca/conventions.md` bzw. Legacy-Konfiguration;
2. ein vom Harness bereitgestellter Plugin-/Skill-Basispfad, falls vorhanden;
3. relativ zur geladenen `SKILL.md`: `./catalog/`;
4. `<project-root>/.agents/dca/catalog/`;
5. Legacy-Fallback `<project-root>/.claude/dca/catalog/`.

Alle für einen Skill notwendigen Dateien müssen innerhalb seines Plugin- oder
Skill-Verzeichnisses liegen. Relative Querverweise zwischen den beiden Plugins
sind zu vermeiden.

## 2. Claude Code

Claude bleibt die Referenzdistribution. Die vorhandene Struktur entspricht
bereits dem nativen Modell: `.claude-plugin/marketplace.json`, je Plugin eine
`.claude-plugin/plugin.json`, dazu `skills/` und `agents/`. Claude Plugins
können Skills, Agents, Hooks und MCP-Server enthalten; Marketplace-Installationen
werden in einen Cache kopiert. Siehe
[Claude Plugins reference](https://code.claude.com/docs/en/plugins-reference)
und
[Create and distribute a plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces).

Zu tun:

1. Bestehende Struktur behalten.
2. Providerneutrale Skill-Texte aus dem gemeinsamen Kern verwenden.
3. Claude-Agentdateien weiterhin aus den kanonischen Prompts erzeugen; die
   bestehenden Toollisten dürfen nur im Claude-Adapter stehen.
4. Installation lokal und aus GitHub testen:

   ```text
   /plugin marketplace add ./dca-marketplace
   /plugin install dca-core@dca-marketplace
   /plugin install software-craftsmanship@dca-marketplace
   /reload-plugins
   ```

5. Optional beide Plugins separat beim offiziellen Anthropic-Marketplace
   einreichen. Das eigene Marketplace-Repository bleibt unabhängig davon
   nutzbar.

## 3. OpenAI Codex

### Schnellster kompatibler Weg

Codex kann einen Claude-kompatiblen Marketplace aus GitHub importieren. Der
bestehende `.claude-plugin/marketplace.json` ist deshalb bereits ein sinnvoller
Einstieg für interne Workspace-Verteilung. OpenAI dokumentiert als unterstützte
Formate sowohl `.agents/plugins/marketplace.json` als auch
`.claude-plugin/marketplace.json` und eigenständige Claude-Manifeste. Siehe
[Codex plugin management](https://learn.chatgpt.com/docs/enterprise/plugin-management).

Das bedeutet jedoch nicht, dass jede Claude-Komponente semantisch identisch
läuft. Insbesondere sollten die heutigen `agents/` nicht als portable Codex-
Plugin-Komponente vorausgesetzt werden. Ihre wiederverwendbaren Verfahren
müssen zusätzlich als Skills vorliegen.

### Native Codex-Distribution

Für eine langfristig klare Distribution zusätzlich erzeugen:

```text
.agents/plugins/marketplace.json
plugins/dca-core/.codex-plugin/plugin.json
plugins/software-craftsmanship/.codex-plugin/plugin.json
```

Der Codex-Marketplace verwendet für lokale Einträge Objekte wie:

```json
{
  "name": "dca-marketplace",
  "interface": { "displayName": "DCA Marketplace" },
  "plugins": [
    {
      "name": "dca-core",
      "source": { "source": "local", "path": "./plugins/dca-core" }
    },
    {
      "name": "software-craftsmanship",
      "source": {
        "source": "local",
        "path": "./plugins/software-craftsmanship"
      }
    }
  ]
}
```

Die nativen Manifeste erhalten mindestens `name`, `version`, `description`,
`author` und sinnvolle `interface`-Metadaten. Skills bleiben unter
`skills/<name>/SKILL.md`.

Zu tun:

1. Claude-spezifische Formulierungen und Pfade neutralisieren.
2. Die fünf Agent-Prompts fachlich auf Skills abbilden. Praktisch bieten sich
   fünf zusätzliche Review-/Build-Skills an oder eine Integration ihrer
   Perspektiven in `dca-review`, `dca-scaffold` und `tdd`.
3. Native Codex-Manifeste und Marketplace-Datei generieren.
4. Beide Wege testen: Claude-kompatibler Import und native Codex-Distribution.
5. Für eine öffentliche Aufnahme jedes Plugin separat über das OpenAI-Portal
   einreichen. Claude-Marketplace-Freigaben werden nicht übernommen. Skills,
   Referenzen und Assets können übernommen werden; Agents werden für die
   Einreichung in Skills konvertiert.

## 4. Google Antigravity

Antigravity unterstützt Skills im gleichen Verzeichnisformat und native
Plugin-Bundles mit `plugin.json`, `skills/`, `agents/`, `rules/`, optional
`mcp_config.json` und `hooks.json`. Workspace-Plugins liegen unter
`.agents/plugins/`, globale unter `~/.gemini/config/plugins/`. Siehe
[Antigravity Plugins](https://antigravity.google/docs/plugins/),
[Antigravity Skills](https://antigravity.google/docs/skills) und
[Antigravity Subagents](https://antigravity.google/docs/subagents).

Pro DCA-Plugin erzeugen:

```text
dca-core/
├── plugin.json
├── skills/<name>/SKILL.md
└── agents/<name>.md
```

Minimalmanifest:

```json
{
  "$schema": "https://antigravity.google/schemas/v1/plugin.json",
  "name": "dca-core",
  "description": "Domain-Centric Architecture skills and review agents."
}
```

Die Agent-Bodies können kanonisch bleiben, das Frontmatter muss aber erzeugt
werden. Wichtige Felder sind `name`, `description`, `tools`, `mainAgent`,
`subagent`, `model`, `commandExecutionPolicy` und optional `skills`. Die
Claude-Toolnamen müssen auf echte Antigravity-Tools wie `view_file`,
`grep_search`, `replace_file_content` und `run_command` abgebildet werden.

Zu tun:

1. Pro Plugin ein Antigravity-`plugin.json` generieren.
2. Skills unverändert aus dem neutralisierten Kern kopieren.
3. Fünf Antigravity-Agentadapter mit korrekten Toolnamen und bewusstem
   `mainAgent`/`subagent`-Verhalten erzeugen.
4. Optional eine Always-on-Rule erzeugen, die nur erklärt, wann DCA-Skills
   anzuwenden sind; keine großen Fachtexte dauerhaft in den Kontext laden.
5. Lokal unter `.agents/plugins/` sowie global unter
   `~/.gemini/config/plugins/` testen.
6. Solange kein gleichwertiger, offizieller Git-Marketplace-Ablauf dokumentiert
   ist, Releases als ZIP/Tarball plus Installationsskript oder Git-basierte
   Kopieranleitung anbieten. Diese Einschränkung im README klar benennen.

## 5. OpenCode

OpenCode entdeckt Skills nativ in `.opencode/skills/`, `.claude/skills/` und
`.agents/skills/`; projektweit und global. Damit kann die neutrale Skill-
Distribution direkt unter `.agents/skills/` installiert werden. Siehe
[OpenCode Agent Skills](https://opencode.ai/docs/skills).

OpenCode-Agents sind Markdown-Dateien unter `.opencode/agents/` bzw.
`~/.config/opencode/agents/`. Ihr Frontmatter nutzt unter anderem `description`,
`mode` und `permission`; `mode: subagent` entspricht einem spezialisierten
Subagenten. Siehe [OpenCode Agents](https://opencode.ai/docs/agents).

Zu tun:

1. Skills nach `.agents/skills/<name>/` installieren. Dieser Pfad funktioniert
   zugleich für Codex-/Agent-Skills und Antigravity und ist deshalb der beste
   portable Projektmodus.
2. Fünf OpenCode-Agentadapter nach `.opencode/agents/*.md` erzeugen. Toollisten
   nicht kopieren, sondern als OpenCode-`permission`-Regeln ausdrücken.
3. Optional `.opencode/commands/*.md` als manuelle Slash-Command-Aliase
   erzeugen. Sie sollten lediglich den passenden Skill und `$ARGUMENTS`
   referenzieren; die fachliche Anleitung bleibt in `SKILL.md`. Siehe
   [OpenCode Commands](https://opencode.ai/docs/commands).
4. Kein JavaScript/TypeScript-Plugin bauen, solange keine Lifecycle-Hooks oder
   neuen Tools benötigt werden. OpenCode-„Plugins“ sind Code-Erweiterungen, die
   lokal oder als npm-Paket geladen werden, und nicht das passende
   Distributionsformat für reine DCA-Skills. Siehe
   [OpenCode Plugins](https://opencode.ai/docs/plugins/).
5. Mangels gleichwertigem Skill-Marketplace einen kleinen, versionierten
   Installer anbieten, der Skills und Agents aus einem Git-Release in die
   gewünschte Projekt- oder Benutzerkonfiguration kopiert.

## 6. Build- und Release-Automation

Ein Generator soll Metadaten abbilden und Inhalte kopieren, aber fachliche
Texte nicht transformieren. Empfohlene Eingabe ist eine kleine neutrale Datei,
zum Beispiel `plugins.yaml`, mit Pluginname, Beschreibung, Version, Skills und
Agents. Daraus entstehen alle Manifeste und Agent-Frontmatter.

Der Build muss mindestens prüfen:

- jede Skill-ID ist eindeutig und stimmt mit ihrem Verzeichnisnamen überein;
- jede `SKILL.md` hat `name` und `description`;
- alle relativen Links und referenzierten Dateien bleiben innerhalb der
  Distribution auflösbar;
- es gibt keine unzulässigen Strings wie `${CLAUDE_PLUGIN_ROOT}`,
  `AskUserQuestion` oder fest verdrahtete `.claude/dca/`-Schreibziele im
  neutralen Kern;
- vendorter Katalog und Templates sind in jeder Distribution bytegleich;
- generierte Manifeste sind valides JSON und entsprechen, soweit Schemas
  erreichbar sind, den jeweiligen Schemas;
- `dist/` ist reproduzierbar: zweimaliger Build erzeugt denselben Inhalt;
- Versionsnummern der beiden Plugins sind in allen Manifesten gleich.

Empfohlene Release-Artefakte:

```text
dca-core-<version>-claude.zip
dca-core-<version>-codex.zip
dca-core-<version>-antigravity.zip
dca-core-<version>-opencode.zip
software-craftsmanship-<version>-<harness>.zip
checksums.txt
```

Ein Git-Tag sollte alle Artefakte derselben fachlichen Revision markieren.

## 7. End-to-End-Testmatrix

Ein Plugin gilt erst als portiert, wenn nicht nur Discovery, sondern reales
Verhalten getestet wurde.

| Test | Claude | Codex | Antigravity | OpenCode |
|---|---:|---:|---:|---:|
| Plugin/Skills werden aus frischer Installation erkannt | ☐ | ☐ | ☐ | ☐ |
| `dca-discipline` wird automatisch passend aktiviert | ☐ | ☐ | ☐ | ☐ |
| manueller Skill-Aufruf mit Argumenten funktioniert | ☐ | ☐ | ☐ | ☐ |
| `dca-knowledge` findet den vendorten Katalog | ☐ | ☐ | ☐ | ☐ |
| Referenzlinks und Templates werden gefunden | ☐ | ☐ | ☐ | ☐ |
| `dca-bootstrap` schreibt die richtigen Harness-Dateien | ☐ | ☐ | ☐ | ☐ |
| Review-Agent bzw. gleichwertiger Review-Skill läuft read-only | ☐ | ☐ | ☐ | ☐ |
| Schreibender `ddd-expert`/E2E-Workflow kann Dateien ändern und testen | ☐ | ☐ | ☐ | ☐ |
| fehlende Konfiguration fällt auf dokumentierte Defaults zurück | ☐ | ☐ | ☐ | ☐ |
| Deinstallation entfernt nur installierte Adapter, keine Projektdaten | ☐ | ☐ | ☐ | ☐ |

Die Tests sollten in kleinen Fixture-Repositories laufen: leeres Repository,
Java/Gradle-Projekt, .NET-Projekt und ein Projekt mit bestehender Legacy-
`.claude/dca/conventions.md`.

## 8. Empfohlene Reihenfolge

### Phase 1 – Portabler Kern

- [ ] Harness-spezifische Begriffe in Skills inventarisieren.
- [ ] Providerneutrale Sprache und intent-basierte Toolanweisungen einführen.
- [ ] `.agents/dca/conventions.md` als kanonischen Konfigurationspfad einführen.
- [ ] Relative Katalogauflösung statt `${CLAUDE_PLUGIN_ROOT}` implementieren.
- [ ] `dca-bootstrap` für `AGENTS.md`, `CLAUDE.md` und Antigravity Rules
      parametrisieren.

### Phase 2 – Skills auf allen Harnesses

- [ ] Bestehende Claude-Distribution regressionsprüfen.
- [ ] Native Codex-Manifeste und Marketplace-Datei erzeugen.
- [ ] Antigravity-Plugin-Bundles erzeugen.
- [ ] OpenCode-/`.agents/skills`-Distribution und Installer erzeugen.
- [ ] Alle zehn Skills in jedem Harness smoke-testen.

### Phase 3 – Agents

- [ ] Fachlichen Body und Harness-Frontmatter jedes Agents trennen.
- [ ] Claude-Agentadapter beibehalten.
- [ ] Antigravity- und OpenCode-Agentadapter erzeugen.
- [ ] Für Codex jedes unverzichtbare Agent-Verfahren als Skill verfügbar machen.
- [ ] Read-only- und Schreibberechtigungen je Harness testen.

### Phase 4 – Distribution

- [ ] Reproduzierbaren Build und Portability-Lint in CI aufnehmen.
- [ ] Versionierte Archive und Checksums veröffentlichen.
- [ ] Harness-spezifische Installation im Haupt-README dokumentieren.
- [ ] Claude- und OpenAI-Verzeichnis-Einreichungen separat durchführen.
- [ ] Antigravity und OpenCode zunächst über Git-Releases/Installer verteilen
      und deren künftige Registry-/Marketplace-Unterstützung beobachten.

## Definition of Done

Die Multi-Harness-Portierung ist abgeschlossen, wenn:

1. jede fachliche Anweisung genau eine kanonische Quelle hat;
2. alle zehn Skills in allen vier Harnesses entdeckt und ausgeführt werden;
3. die fünf spezialisierten Agent-Perspektiven über native Agents oder
   gleichwertige Skills verfügbar sind;
4. der OKF-Katalog ohne absoluten oder Claude-spezifischen Pfad gefunden wird;
5. kein Skill einen nicht vorhandenen Harness-Toolnamen voraussetzt;
6. Installieren, Aktualisieren und Entfernen dokumentiert und getestet ist;
7. CI Divergenz zwischen den Distributionen verhindert;
8. die README nicht mehr behauptet, das Repository sei ausschließlich ein
   Claude-Code-Marketplace.

## Quellen

- [Claude Code: Plugins reference](https://code.claude.com/docs/en/plugins-reference)
- [Claude Code: Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [OpenAI: Claude-Code-Plugin für OpenAI konvertieren](https://developers.openai.com/plugins/guides/submit-claude-plugin)
- [Codex/ChatGPT Work: Plugin management](https://learn.chatgpt.com/docs/enterprise/plugin-management)
- [Antigravity: Plugins](https://antigravity.google/docs/plugins/)
- [Antigravity: Skills](https://antigravity.google/docs/skills)
- [Antigravity: Subagents](https://antigravity.google/docs/subagents)
- [OpenCode: Agent Skills](https://opencode.ai/docs/skills)
- [OpenCode: Agents](https://opencode.ai/docs/agents)
- [OpenCode: Commands](https://opencode.ai/docs/commands)
- [OpenCode: Plugins](https://opencode.ai/docs/plugins/)
