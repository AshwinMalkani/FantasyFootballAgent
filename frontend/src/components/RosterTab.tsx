import type { LeagueDetail, RosterSlot } from '../types'
import PlayerCell, { fmt } from './PlayerCell'

const BENCH = new Set(['BN', 'IR', 'TAXI'])

function Table({ title, rows }: { title: string; rows: RosterSlot[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-400">
          <tr><th className="px-3 py-2" colSpan={2}>{title}</th><th className="px-3 py-2 text-right">Proj</th></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-slate-800/80">
              <td className="w-20 px-3 py-2 text-xs font-semibold text-slate-400">{r.slot}</td>
              <td className="px-3 py-2"><PlayerCell p={r.player} /></td>
              <td className="px-3 py-2 text-right tabular-nums">{r.player ? fmt(r.player.projected_points) : '–'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function RosterTab({ detail }: { detail: LeagueDetail }) {
  const starters = detail.roster.filter((r) => !BENCH.has(r.slot))
  const bench = detail.roster.filter((r) => BENCH.has(r.slot))
  const src = detail.roster.find((r) => r.player)?.player?.projection_source
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Table title="Starters" rows={starters} />
      <Table title="Bench / IR" rows={bench} />
      <p className="text-xs text-slate-500 lg:col-span-2">
        Projections: {src === 'espn' ? 'ESPN (league scoring)' : src === 'sleeper-exact' ? 'Sleeper stat projections × this league\'s scoring' : 'Sleeper projections, approximated to this league\'s reception scoring'}.
      </p>
    </div>
  )
}
