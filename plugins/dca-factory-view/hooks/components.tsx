import type { BoxProps, ButtonProps, ElementConstructor, InputProps, MarkdownProps, RenderElement, TextProps } from 'claude-code'

import type { StageRun } from '../types'
import { duration, rounds, short, tokens } from './parse'

// The cockpit's building blocks. Every view is drawn from these, so a change to a table, a link, a chip or the
// spacing reaches every tab and every detail at once. They take the surface's elements and ready callbacks —
// never `$`: what acts on the session stays in register.tsx.

// The DCA brand palette (branding/README.md): teal is the accent, amber, coral and indigo share its tone.
export const C = {
  accent: '#148f96',
  done: '#3f9d5b',
  wait: '#c9922e',
  fail: '#c96a5a',
  info: '#5f5bd0',
  muted: 'gray',
  onAccent: '#ffffff',
}

export const MARK_GLYPH: Record<string, string> = { done: '✓', running: '▶', look: '!', question: '?', stopped: '✗', next: '→', none: '·' }
export const MARK_COLOR: Record<string, string> = {
  done: C.done,
  running: C.accent,
  look: C.wait,
  question: C.wait,
  stopped: C.fail,
  next: C.accent,
  none: C.muted,
}

export type Phase = { key: string; label: string; hotkey?: string; isOpen: boolean; mark?: { text: string; color: string }; onPress: () => void }

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
  Markdown: ElementConstructor<MarkdownProps>
  Input: ElementConstructor<InputProps> | null
}

export function components({ Box, Text, Button, Markdown, Input }: Elements) {
  const divider = <Text color={C.muted}> │ </Text>

  const tableCell = (column: Column, value: Cell) => (
    <Box width={column.width} flexShrink={0} justifyContent={column.isNumber ? 'flex-end' : 'flex-start'}>
      {value.node ?? (
        <Text color={value.color} bold={value.bold} wrap="truncate">
          {value.text ?? ''}
        </Text>
      )}
    </Box>
  )

  const line = (columns: Column[], row: Cell[]) => (
    <Box>{columns.flatMap((column, index) => [...(index > 0 ? [divider] : []), tableCell(column, row[index] ?? {})])}</Box>
  )

  return {
    // A heading with a hint beside it; the space above it is the one rhythm between parts.
    section: (title: string, hint?: string) => (
      <Box marginTop={1} gap={1}>
        <Text bold color={C.accent}>
          {title}
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
        <Box flexDirection="column" borderStyle="round" borderColor={C.muted} paddingX={1} marginTop={1}>
          {line(columns, columns.map(column => ({ text: column.name, bold: true, color: C.accent })))}
          <Text color={C.muted}>{columns.map(column => '─'.repeat(column.width)).join('─┼─')}</Text>
          {rows.map(row => line(columns, row))}
        </Box>
      ),

    // A word that opens something: a story, a record, a file, a topic.
    link: (key: string, label: string, onPress: () => void) => <Button key={key} label={label} plain onPress={onPress} />,

    // A mark and the link beside it — how a story appears in every table.
    marked: (mark: string, key: string, label: string, onPress: () => void) => (
      <Box gap={1}>
        <Text bold color={MARK_COLOR[mark] ?? C.muted}>
          {MARK_GLYPH[mark] ?? '·'}
        </Text>
        <Button key={key} label={label} plain onPress={onPress} />
      </Box>
    ),

    // The stages as chips, the running one filled.
    chips: (stages: StageRun[], now: number, prefix?: string) => (
      <Box flexWrap="wrap" columnGap={1} marginTop={1}>
        {prefix !== undefined && <Text color={C.muted}>{prefix}</Text>}
        {stages.length === 0 && <Text color={C.muted}>Not run yet.</Text>}
        {stages.flatMap((run, index) => [
          ...(index > 0 ? [<Text color={C.muted}>›</Text>] : []),
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

    button: (key: string, label: string, onPress: () => void, options: { hotkey?: string; isPrimary?: boolean } = {}) => (
      <Button key={key} label={label} hotkey={options.hotkey} variant={options.isPrimary ? 'primary' : 'secondary'} onPress={onPress} />
    ),

    // A framed box for text that is not a table: a file, the worker's output.
    framed: (children: RenderElement | RenderElement[]) => (
      <Box borderStyle="round" borderColor={C.muted} paddingX={1} flexDirection="column" marginTop={1}>
        {children}
      </Box>
    ),

    markdown: (text: string) => <Markdown text={text} />,

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
        <Input key={key} label={label} placeholder={placeholder} submitLabel="send" onSubmit={(value: string) => onSend(value)} />
      ) : (
        <Button key={key} label={label} onPress={onFill} />
      ),

    // An epic's head: its title, progress and the buttons that act on it; its goal and outcome below.
    epicHead: (epic: { title: string; delivered: number; total: number; tokens: number; goal?: string; metric?: string; discovery?: string }, buttons: (RenderElement | false)[]) => (
      <Box flexDirection="column" marginTop={2}>
        <Box gap={1} flexWrap="wrap">
          <Text bold color={epic.total > 0 && epic.delivered === epic.total ? C.done : undefined}>
            {epic.title}
          </Text>
          <Text color={C.done}>{'█'.repeat(epic.total > 0 ? Math.round((epic.delivered / epic.total) * 10) : 0).padEnd(10, '░')}</Text>
          <Text color={C.muted}>
            {epic.delivered} of {epic.total} delivered
            {epic.tokens > 0 ? ` · ${tokens(epic.tokens)} tokens` : ''}
          </Text>
          {buttons.filter((button): button is RenderElement => Boolean(button))}
        </Box>
        {epic.goal && (
          <Text color={C.muted} wrap="truncate">
            goal: {epic.goal}
          </Text>
        )}
        {epic.metric && (
          <Text color={C.info} wrap="truncate">
            outcome: {epic.metric}
          </Text>
        )}
        {epic.discovery && (
          <Text color={C.muted} wrap="truncate">
            from discovery: {epic.discovery}
          </Text>
        )}
      </Box>
    ),

    // The phases as a flow: the foundation, then the cycle with an arrow between its steps. The open phase sits in
    // a teal frame; a phase that needs the person carries a mark (what waits, what runs).
    phases: (
      foundation: Phase[],
      cycle: Phase[],
    ) => {
      const step = (phase: Phase) => (
        <Box borderStyle="round" borderColor={phase.isOpen ? C.accent : C.muted} borderDimColor={!phase.isOpen} paddingX={1} gap={1}>
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
          <Text color={C.muted}>once</Text>
          {foundation.map(step)}
          <Text color={C.muted}> ┃ cycle</Text>
          {cycle.flatMap((phase, index) => [...(index > 0 ? [<Text color={C.muted}>›</Text>] : []), step(phase)])}
        </Box>
      )
    },

    // The keys that work now, at the foot of every view.
    keys: (isFocused: boolean, hint: string) => (
      <Box marginTop={1}>
        <Text color={C.muted}>{isFocused ? `${hint} · 0 describe · 1–5 cycle · Tab/↑↓ move · Enter choose · Esc prompt` : 'ctrl+x tab — steer the cockpit'}</Text>
      </Box>
    ),
  }
}
