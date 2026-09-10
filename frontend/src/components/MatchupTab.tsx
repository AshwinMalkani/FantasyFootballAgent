import type { LeagueDetail, Player, RosterSlot } from '../types'
import { ActualCell, StatusPill, fmt } from './PlayerCell'

const BENCH = new Set(['BN', 'IR', 'TAXI'])

/** Points a player is still expected to add: full projection before kickoff, nothing once his game is over. */
function remaining(p: Player | null): number {
  if (!p) return 0
  if (p.game_state === 'post') return 0
  if (p.game_state === 'in') return Math.max(0, p.projected_points - (p.actual_points ?? 0)) * 0.5
  return p.on_bye ? 0 : p.projected_points
}

function sideTotals(starters: RosterSlot[]) {
  const actual = starters.reduce((t, r) => t + (r.player?.actual_points ?? 0), 0)
  const left = starters.reduce((t, r) => t + remaining(r.player), 0)
  const played = starters.filter((r) => r.player?.game_state === 'post').length
  const live = starters.filter((r) => r.player?.game_state === 'in').length
  return { actual, left, expected: actual + left, played, live, total: starters.length }
}

function PlayerSide({ p, align }: { p: Player | null; align: 'left' | 'right' }) {
  if (!p) return <span className="text-slate-600 italic">Empty</span>
  const state = p.game_state
  return (
    <div className={`flex flex-col ${align === 'right' ? 'items-end text-right' : ''}`}>
      <span className="flex items-center gap-1.5 font-medium">
        {align === 'right' && <StatusPill p={p} />}
        {p.name}
        {align === 'left' && <StatusPill p={p} />}
      </span>
      <span className="text-[11px] text-slate-500">
        {p.position} · {p.nfl_team ?? 'FA'}{p.opponent ? ` vs ${p.opponent}` : ''}
        {state === 'post' ? ' · final' : state === 'in' ? ' · live' : ''}
      </span>
    </div>
  )
}

function Num({ p }: { p: Player | null }) {
  return (
    <div className="flex flex-col items-end tabular-nums">
      <ActualCell p={p} />
      <span className="text-[11px] text-slate-500">{p ? fmt(p.projected_points) : '–'}</span>
    </div>
  )
}

export default function MatchupTab({ detail }: { detail: LeagueDetail }) {
  const s = detail.summary
  const mine = detail.roster.filter((r) => !BENCH.has(r.slot))
  const theirs = (detail.opponent_roster ?? []).filter((r) => !BENCH.has(r.slot))

  if (!detail.opponent_roster) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-400">
        {s.opponent_name ? `Opponent roster isn't available from ${s.platform} for this league.` : 'No matchup this week (bye or playoffs not started).'}
      </div>
    )
  }

  // Align rows by slot template; if the opponent's lineup has a different shape, pad the shorter side.
  const rows = Math.max(mine.length, theirs.length)
  const me = sideTotals(mine)
  const op = sideTotals(theirs)
  const started = me.played + me.live + op.played + op.live > 0
  const myScore = started ? (s.my_actual_total ?? me.actual) : s.my_projected_total ?? me.expected
  const oppScore = started ? (s.opp_actual_total ?? op.actual) : s.opp_projected_total ?? op.expected
  const edge = me.expected - op.expected
  const winPct = Math.round(100 / (1 + Math.exp(-edge / 12)))

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div>
          <div className="text-xs text-slate-400">You</div>
          <div className="truncate text-lg font-semibold">{s.team_name}</div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{fmt(myScore)}</div>
          <div className="text-xs text-slate-500">{started ? `expected ${fmt(me.expected)} · ${fmt(me.left)} left` : 'projected'} · {me.played}/{me.total} done{me.live ? ` · ${me.live} live` : ''}</div>
        </div>
        <div className="text-center">
          <div className="text-xs uppercase tracking-wide text-slate-500">{s.in_progress ? 'live' : started ? 'week ' + s.week : 'projected'}</div>
          <div className={`mt-1 text-2xl font-bold ${winPct >= 50 ? 'text-emerald-300' : 'text-red-300'}`}>{winPct}%</div>
          <div className="text-[11px] text-slate-500">win chance</div>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-400">Opponent</div>
          <div className="truncate text-lg font-semibold">{s.opponent_name ?? 'Opponent'}</div>
          <div className="mt-1 text-3xl font-bold tabular-nums">{fmt(oppScore)}</div>
          <div className="text-xs text-slate-500">{started ? `expected ${fmt(op.expected)} · ${fmt(op.left)} left` : 'projected'} · {op.played}/{op.total} done{op.live ? ` · ${op.live} live` : ''}</div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-sm">
          <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-3 py-2 text-left">{s.team_name}</th>
              <th className="px-3 py-2 text-right">Pts</th>
              <th className="w-20 px-2 py-2 text-center">Slot</th>
              <th className="px-3 py-2 text-right">Pts</th>
              <th className="px-3 py-2 text-right">{s.opponent_name ?? 'Opponent'}</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: rows }, (_, i) => {
              const a = mine[i] ?? null
              const b = theirs[i] ?? null
              const pa = a?.player ?? null
              const pb = b?.player ?? null
              const aWins = (pa?.actual_points ?? pa?.projected_points ?? 0) >= (pb?.actual_points ?? pb?.projected_points ?? 0)
              return (
                <tr key={i} className="border-t border-slate-800/80 align-top">
                  <td className={`px-3 py-2 ${aWins ? '' : 'opacity-70'}`}><PlayerSide p={pa} align="left" /></td>
                  <td className="px-3 py-2"><Num p={pa} /></td>
                  <td className="px-2 py-2 text-center text-xs font-semibold text-slate-400">{a?.slot ?? b?.slot ?? ''}</td>
                  <td className="px-3 py-2"><Num p={pb} /></td>
                  <td className={`px-3 py-2 ${aWins ? 'opacity-70' : ''}`}><PlayerSide p={pb} align="right" /></td>
                </tr>
              )
            })}
          </tbody>
          <tfoot className="bg-slate-900/80 text-sm font-semibold">
            <tr>
              <td className="px-3 py-2 text-slate-400">Total</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmt(started ? me.actual : me.expected)}</td>
              <td />
              <td className="px-3 py-2 text-right tabular-nums">{fmt(started ? op.actual : op.expected)}</td>
              <td className="px-3 py-2 text-right text-slate-400">Total</td>
            </tr>
          </tfoot>
        </table>
        <p className="px-3 py-2 text-xs text-slate-500">Big number = actual points, small = projection. Win chance is a rough estimate from the gap between each side's expected final (actual so far plus remaining projections).</p>
      </div>
    </div>
  )
}
