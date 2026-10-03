import type { BoxProps, ButtonProps, ElementConstructor, InputProps, RenderElement, TextProps } from 'claude-code'

import type { StageRun } from '../types'
import { duration, rounds, short, tokens } from './parse'

// The cockpit's building blocks. Every view is drawn from these, so a change to a table, a link, a chip or the
// spacing reaches every tab and every detail at once. They take the surface's elements and ready callbacks —
// never `$`: what acts on the session stays in register.tsx.

// The domaincentric.dev palette in its two faces (website `:root`, branding/README.md). Paper is the site's page —
// beige `--paper`, `--ink` text, `--teal-dark` for what is read as a link, `--line` for rules. Deep is the site's hero
// and plates — `--deep`, `--mist` text, `--teal`, mist at 70 % for secondary text (the hero's sub-lines), mist at a
// third for lines. The cockpit follows Claude Code's theme:
// a button's label takes the terminal's own text colour, so only the face that matches the theme keeps every button
// readable. Amber, coral and indigo are the brand's accent alternatives, for waiting, refused and proposed; on the
// deep navy every colour reads at 4.3:1 or more, indigo lifted to a light lavender for it.
const PAPER = {
  bg: '#f7f6f3',
  text: '#1c2433',
  bright: '#1c2433',
  accent: '#0d6b70',
  done: '#2f7d4a',
  wait: '#9a6a17',
  fail: '#a9493a',
  info: '#4b47b8',
  muted: '#5b6472',
  line: '#dedbd3',
  onAccent: '#ffffff',
}
const DEEP = {
  bg: '#171d29',
  text: '#e8eaf0',
  bright: '#ffffff',
  accent: '#148f96',
  done: '#3f9d5b',
  wait: '#c9922e',
  fail: '#c96a5a',
  info: '#b3b0f2',
  muted: '#a9acb4',
  line: '#60656f',
  onAccent: '#ffffff',
}

export const C = { ...DEEP }

// The sign of an action Claude carries out in this session: a skill runs, files may change.
export const BY_CLAUDE = '✦'

export const MARK_GLYPH: Record<string, string> = { done: '✓', running: '▶', look: '!', question: '?', stopped: '✗', next: '→', none: '·' }
export const MARK_COLOR: Record<string, string> = {}

// Paper for a light theme, deep for a dark one; set before every drawing, so a change of theme shows at once.
export function applyPalette(isLight: boolean): void {
  Object.assign(C, isLight ? PAPER : DEEP)
  Object.assign(MARK_COLOR, {
    done: C.done,
    running: C.accent,
    look: C.wait,
    question: C.wait,
    stopped: C.fail,
    next: C.accent,
    none: C.muted,
  })
}
applyPalette(false)

export type Phase = { key: string; label: string; hotkey?: string; isOpen: boolean; mark?: { text: string; color: string }; onPress: () => void }

export type Field = { label: string; text: string; color?: string; bold?: boolean }

export type Column = { name: string; width: number; isNumber?: boolean }
export type Cell = { text?: string; color?: string; bold?: boolean; node?: RenderElement }

// The columns every table shares, one width and one alignment each.
export const COL = {
  mark: { name: '', width: 1 },
  story: (width: number): Column => ({ name: 'story', width }),
  state: { name: 'state', width: 20 },
  stage: { name: 'stage', width: 10 },
  passes: { name: 'passes', width: 6, isNumber: true },
  runs: { name: 'runs', width: 4, isNumber: true },
  started: { name: 'started UTC', width: 12 },
  delivered: { name: 'delivered UTC', width: 13 },
  asked: { name: 'asked UTC', width: 12 },
  worked: { name: 'worked', width: 12, isNumber: true },
  time: { name: 'time', width: 12, isNumber: true },
  tokens: { name: 'tokens', width: 8, isNumber: true },
  cost: { name: 'cost', width: 10, isNumber: true },
  epic: { name: 'epic', width: 22 },
  record: { name: 'record', width: 28 },
  what: { name: 'what', width: 48 },
  action: (width: number): Column => ({ name: '', width }),
} satisfies Record<string, Column | ((width: number) => Column)>

// One way to write each kind of value; a dash where there is none.
export const fmt = {
  time: (seconds: number) => (seconds > 0 ? duration(seconds) : '—'),
  tokens: (count: number) => (count > 0 ? tokens(count) : '—'),
  cost: (usd: number) => (usd > 0 ? `${usd.toFixed(2)} USD` : '—'),
  when: (at: string | null | undefined) => (at ? short(at) : '—'),
}

export function stageLabel(run: StageRun, now: number): string {
  const gate = run.gates.length === 0 ? '' : run.gates[run.gates.length - 1] ? ' ✓' : ' ✗'
  const more = run.rounds > 1 ? ` · ${rounds(run.rounds)}` : ''
  const time = run.runningSince ? ` · ▶ ${duration((now - Date.parse(run.runningSince)) / 1000)}` : ` · ${duration(run.seconds)}`
  return `${run.stage}${gate}${more}${time}`
}

export function stageColor(run: StageRun): string {
  if (run.runningSince) return C.accent
  if (run.gates.length > 0 && !run.gates[run.gates.length - 1]) return C.fail
  return C.done
}

export type Elements = {
  Box: ElementConstructor<BoxProps>
  Text: ElementConstructor<TextProps>
  Button: ElementConstructor<ButtonProps>
  Input: ElementConstructor<InputProps> | null
}

export function components({ Box, Text, Button, Input }: Elements) {
  const divider = <Text color={C.line}> │ </Text>

  const tableCell = (column: Column, value: Cell) => (
    <Box width={column.width} flexShrink={0} justifyContent={column.isNumber ? 'flex-end' : 'flex-start'}>
      {value.node ?? (
        <Text color={value.color ?? C.text} bold={value.bold} wrap="truncate">
          {value.text ?? ''}
        </Text>
      )}
    </Box>
  )

  const line = (columns: Column[], row: Cell[]) => (
    <Box>{columns.flatMap((column, index) => [...(index > 0 ? [divider] : []), tableCell(column, row[index] ?? {})])}</Box>
  )

  // Labelled values: the label as a kicker in a fixed column, the value beside it; `perRow` places several pairs
  // side by side. Empty values are left out.
const fields = (items: (Field | false | null | undefined | '' | 0)[], perRow = 1) => {
    const present = items.filter((item): item is Field => typeof item === 'object' && item !== null && Boolean(item.text))
    const rowsOf: Field[][] = []
    for (let index = 0; index < present.length; index += perRow) rowsOf.push(present.slice(index, index + perRow))
    return (
      <Box flexDirection="column" marginTop={1}>
        {rowsOf.map(pairs => (
          <Box gap={3}>
            {pairs.map(item => (
              <Box gap={1} width={perRow > 1 ? 44 : undefined} flexShrink={perRow > 1 ? 0 : 1}>
                <Box width={10} flexShrink={0}>
                  <Text bold color={C.accent}>
                    {item.label.toUpperCase()}
                  </Text>
                </Box>
                <Text color={item.color ?? C.text} bold={item.bold} wrap="truncate">
                  {item.text}
                </Text>
              </Box>
            ))}
          </Box>
        ))}
      </Box>
    )
  }

  // A word that opens something — a story, a record, a file, a topic. A teal `›` says it can be chosen before the
  // focus is on it, and the row lights under the pointer.
  const link = (key: string, label: string, onPress: () => void) => (
    <Box key={`link-${key}`} gap={0} hover={{ backgroundColor: C.line }}>
      <Button key={key} label={label} plain onPress={onPress} />
      <Text color={C.accent}> ›</Text>
    </Box>
  )

  return {
    // A heading as the site's kicker — upper case, teal — with a hint beside it; the space above it is the one
    // rhythm between parts.
    section: (title: string, hint?: string) => (
      <Box marginTop={1} gap={2}>
        <Text bold color={C.accent}>
          {title.toUpperCase()}
        </Text>
        {hint && <Text color={C.muted}>{hint}</Text>}
      </Box>
    ),

    // A table drawn as one: a frame, a bold header, a rule under it, a thin bar between the columns.
    table: (columns: Column[], rows: Cell[][], empty = 'Nothing yet.') =>
      rows.length === 0 ? (
        <Box marginTop={1}>
          <Text color={C.muted}>{empty}</Text>
        </Box>
      ) : (
        <Box flexDirection="column" borderStyle="round" borderColor={C.line} paddingX={1} marginTop={1}>
          {line(columns, columns.map(column => ({ text: column.name.toUpperCase(), bold: true, color: C.accent })))}
          <Text color={C.line}>{columns.map(column => '─'.repeat(column.width)).join('─┼─')}</Text>
          {rows.map(row => line(columns, row))}
        </Box>
      ),

    // A word that opens something: a story, a record, a file, a topic.
    link,

    // A mark and the link beside it — how a story appears in every table.
    marked: (mark: string, key: string, label: string, onPress: () => void) => (
      <Box gap={1}>
        <Text bold color={MARK_COLOR[mark] ?? C.muted}>
          {MARK_GLYPH[mark] ?? '·'}
        </Text>
        {link(key, label, onPress)}
      </Box>
    ),

    // The stages as chips, the running one filled.
    chips: (stages: StageRun[], now: number, prefix?: string) => (
      <Box flexWrap="wrap" columnGap={1} marginTop={1}>
        {prefix !== undefined && <Text color={C.muted}>{prefix}</Text>}
        {stages.length === 0 && <Text color={C.muted}>Not run yet.</Text>}
        {stages.flatMap((run, index) => [
          ...(index > 0 ? [<Text color={C.line}>›</Text>] : []),
          <Text backgroundColor={run.runningSince ? C.accent : undefined} color={run.runningSince ? C.onAccent : stageColor(run)} bold={run.runningSince !== null}>
            {` ${stageLabel(run, now)} `}
          </Text>,
        ])}
      </Box>
    ),

    // Short facts in one wrapping row: `state · epic · worked …`.
    facts: (items: (Cell | false | null | undefined | '' | 0)[]) => (
      <Box gap={2} flexWrap="wrap">
        {items
          .filter((item): item is Cell => typeof item === 'object' && item !== null && Boolean(item.text))
          .map(item => (
            <Text color={item.color ?? C.muted} bold={item.bold}>
              {item.text}
            </Text>
          ))}
      </Box>
    ),

    // A row of buttons with room above it.
    actions: (buttons: (RenderElement | false | null | undefined)[]) => (
      <Box gap={1} marginTop={1} flexWrap="wrap">
        {buttons.filter((button): button is RenderElement => Boolean(button))}
      </Box>
    ),

    // A button. `byClaude` marks one that hands the work to Claude in this session — a skill runs, files may change
    // — with the one sign every such button carries.
    button: (key: string, label: string, onPress: () => void, options: { hotkey?: string; isPrimary?: boolean; byClaude?: boolean } = {}) => (
      <Button key={key} label={options.byClaude ? `${BY_CLAUDE} ${label}` : label} hotkey={options.hotkey} variant={options.isPrimary ? 'primary' : 'secondary'} onPress={onPress} />
    ),

    // A framed box for text that is not a table: a file, the worker's output.
    framed: (children: RenderElement | RenderElement[]) => (
      <Box borderStyle="round" borderColor={C.line} paddingX={1} flexDirection="column" marginTop={1}>
        {children}
      </Box>
    ),

    // A Markdown file drawn line by line in the palette's colours — the surface's own Markdown takes the terminal's
    // text colour, which the painted background would swallow.
    doc: (text: string) => {
      let isCode = false
      return text.split('\n').map(raw => {
        if (raw.startsWith('```')) {
          isCode = !isCode
          return <Text color={C.line}>{raw}</Text>
        }
        if (isCode) return <Text color={C.muted}>{raw || ' '}</Text>
        const heading = /^(#{1,6})\s+(.*)$/.exec(raw)
        if (heading) {
          return (
            <Box marginTop={heading[1] && heading[1].length <= 2 ? 1 : 0}>
              <Text bold color={C.accent}>
                {heading[1] && heading[1].length <= 2 ? (heading[2] ?? '').toUpperCase() : heading[2]}
              </Text>
            </Box>
          )
        }
        if (/^\s*\|/.test(raw)) return <Text color={C.muted}>{raw}</Text>
        if (/^\s*[-*]\s/.test(raw)) return <Text color={C.text}>{raw.replace(/^(\s*)[-*]\s/, '$1• ')}</Text>
        if (/^---\s*$/.test(raw)) return <Text color={C.line}>{'─'.repeat(40)}</Text>
        return <Text color={C.text}>{raw.replace(/\*\*(.+?)\*\*/g, '$1').replace(/`([^`]+)`/g, '$1') || ' '}</Text>
      })
    },

    // A banner in one colour, for what waits and what is behind.
    banner: (color: string, lines: string[]) => (
      <Box borderStyle="round" borderColor={color} paddingX={1} flexDirection="column" marginTop={1}>
        {lines.map(text => (
          <Text bold color={color}>
            {text}
          </Text>
        ))}
      </Box>
    ),

    // A field that sends what is typed; where the surface has none (mobile), a button that fills the prompt.
    ask: (key: string, label: string, placeholder: string, onSend: (value: string) => void, onFill: () => void) =>
      Input ? (
        <Input key={key} label={`${BY_CLAUDE} ${label}`} placeholder={placeholder} submitLabel="send to Claude" onSubmit={(value: string) => onSend(value)} />
      ) : (
        <Button key={key} label={`${BY_CLAUDE} ${label}`} onPress={onFill} />
      ),

    // An epic's head: its title, progress and the buttons that act on it; its goal and outcome below.
    fields,

    // A card: a title with what counts beside it and the buttons that act on it, labelled values below, in one
    // quiet frame — an epic in the backlog, a topic in discovery.
    card: (head: { title: string; color?: string; progress?: { done: number; total: number }; meta?: string }, buttons: (RenderElement | false)[], items: (Field | false | null | undefined | '' | 0)[]) => (
      <Box flexDirection="column" borderStyle="round" borderColor={C.line} paddingX={1} marginTop={2}>
        <Box gap={1} flexWrap="wrap">
          <Text bold color={head.color ?? C.bright}>
            {head.title}
          </Text>
          {head.progress && (
            <Text color={C.done}>
              {'█'.repeat(head.progress.total > 0 ? Math.round((head.progress.done / head.progress.total) * 10) : 0).padEnd(10, '░')}
            </Text>
          )}
          {head.meta && <Text color={C.muted}>{head.meta}</Text>}
          {buttons.filter((button): button is RenderElement => Boolean(button))}
        </Box>
        {fields(items)}
      </Box>
    ),

    // The phases as a flow: the foundation, then the cycle with an arrow between its steps. The open phase sits in
    // a teal frame; a phase that needs the person carries a mark (what waits, what runs).
    phases: (
      foundation: Phase[],
      cycle: Phase[],
    ) => {
      const step = (phase: Phase) => (
        <Box borderStyle="round" borderColor={phase.isOpen ? C.accent : C.line} paddingX={1} gap={1}>
          <Button key={phase.key} label={phase.label} hotkey={phase.hotkey} plain variant={phase.isOpen ? 'primary' : 'secondary'} onPress={phase.onPress} />
          {phase.mark && (
            <Text bold color={phase.mark.color}>
              {phase.mark.text}
            </Text>
          )}
        </Box>
      )
      return (
        <Box flexWrap="wrap" alignItems="center" columnGap={1}>
          <Text color={C.accent}>ONCE</Text>
          {foundation.map(step)}
          <Text color={C.line}> ┃ </Text>
          <Text color={C.accent}>CYCLE</Text>
          {cycle.flatMap((phase, index) => [...(index > 0 ? [<Text color={C.line}>›</Text>] : []), step(phase)])}
        </Box>
      )
    },

    // The keys that work now, at the foot of every view.
    keys: (isFocused: boolean, hint: string) => (
      <Box marginTop={1}>
        <Text color={C.muted}>{isFocused ? `${hint} · ${BY_CLAUDE} Claude does it in this session · 0 describe · 1–5 cycle · Enter choose · q close · Esc prompt` : 'ctrl+x tab — steer the cockpit · /factory-view close'}</Text>
      </Box>
    ),
  }
}
