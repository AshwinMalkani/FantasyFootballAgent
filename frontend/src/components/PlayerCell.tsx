import type { Player } from '../types'

const POS_COLOR: Record<string, string> = {
  QB: 'text-rose-300', RB: 'text-emerald-300', WR: 'text-sky-300', TE: 'text-amber-300', K: 'text-slate-300', DEF: 'text-slate-300',
}

export function StatusPill({ p }: { p: Player }) {
  if (p.on_bye) return <span className="rounded bg-slate-700 px-1.5 py-0.5 text-[10px] font-semibold text-slate-200">BYE</span>
  const s = (p.injury_status || '').toUpperCase()
  if (!s) return null
  const bad = ['OUT', 'O', 'IR', 'INJURY_RESERVE', 'DOUBTFUL', 'D', 'SUS', 'PUP', 'NA'].includes(s)
  const short = s === 'QUESTIONABLE' ? 'Q' : s === 'INJURY_RESERVE' ? 'IR' : s === 'DOUBTFUL' ? 'D' : s === 'OUT' ? 'O' : s
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${bad ? 'bg-red-500/20 text-red-300' : 'bg-amber-500/20 text-amber-300'}`}>{short}</span>
  )
}

export default function PlayerCell({ p, empty = 'Empty' }: { p: Player | null; empty?: string }) {
  if (!p) return <span className="text-slate-500 italic">{empty}</span>
  return (
    <span className="flex items-center gap-2">
      <span className="font-medium">{p.name}</span>
      <span className={`text-xs font-semibold ${POS_COLOR[p.position] ?? 'text-slate-400'}`}>{p.position}</span>
      <span className="text-xs text-slate-500">{p.nfl_team ?? 'FA'}{p.opponent ? ` vs ${p.opponent}` : ''}</span>
      <StatusPill p={p} />
    </span>
  )
}

export const fmt = (n: number | null | undefined) => (n == null ? '–' : n.toFixed(1))

/** Actual points, or a dash before the game; dims the number when the game is over. */
export function ActualCell({ p }: { p: Player | null }) {
  if (!p || p.actual_points == null) return <span className="text-slate-600">–</span>
  const live = p.game_state === 'in'
  return (
    <span className={`tabular-nums ${live ? 'font-semibold text-emerald-300' : 'text-slate-100'}`}>
      {live && <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400 align-middle" />}
      {fmt(p.actual_points)}
    </span>
  )
}

export function Scoreline({ my, opp, myProj, oppProj, live }: { my: number | null; opp: number | null; myProj: number | null; oppProj: number | null; live: boolean }) {
  const hasActual = my != null
  const a = hasActual ? my : myProj
  const b = hasActual ? opp : oppProj
  const winning = a != null && b != null && a >= b
  return (
    <div className="flex items-baseline gap-2">
      <span className={`font-semibold ${winning ? 'text-emerald-300' : 'text-slate-200'}`}>{fmt(a)}</span>
      <span className="text-slate-500">–</span>
      <span className={`font-semibold ${!winning && b != null ? 'text-red-300' : 'text-slate-200'}`}>{fmt(b)}</span>
      {hasActual
        ? <span className="text-xs text-slate-500">{live && <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400 align-middle" />}{live ? 'live' : 'actual'} · proj {fmt(myProj)}–{fmt(oppProj)}</span>
        : <span className="text-xs text-slate-500">projected</span>}
    </div>
  )
}
