import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '../api'
import type { RosterSlot } from '../types'
import PlayerCell, { ActualCell, fmt } from './PlayerCell'

function Col({ title, rows, total, highlight }: { title: string; rows: RosterSlot[]; total: number; highlight: Set<string> }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-400">
          <tr><th className="px-3 py-2" colSpan={2}>{title}</th><th className="px-3 py-2 text-right">Actual</th><th className="px-3 py-2 text-right">Proj {fmt(total)}</th></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const hl = r.player && highlight.has(r.player.platform_player_id)
            return (
              <tr key={i} className={`border-t border-slate-800/80 ${hl ? 'bg-amber-500/10' : ''}`}>
                <td className="w-24 px-3 py-2 text-xs font-semibold text-slate-400">{r.slot}</td>
                <td className="px-3 py-2"><PlayerCell p={r.player} /></td>
                <td className="px-3 py-2 text-right"><ActualCell p={r.player} /></td>
                <td className="px-3 py-2 text-right tabular-nums text-slate-400">{r.player ? fmt(r.player.projected_points) : '–'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function LineupTab({ platform, leagueId }: { platform: string; leagueId: string }) {
  const q = useQuery({ queryKey: ['lineup', platform, leagueId], queryFn: () => api.lineup(platform, leagueId) })
  if (q.isLoading) return <p className="text-slate-400">Optimizing…</p>
  if (q.isError) return <p className="text-red-300">{(q.error as ApiError).message}</p>
  const s = q.data!
  const outs = new Set(s.moves.map((m) => m.out?.platform_player_id).filter(Boolean) as string[])
  const ins = new Set(s.moves.map((m) => m.in.platform_player_id))
  return (
    <div className="space-y-4">
      {s.moves.length === 0 ? (
        <div className="rounded-xl border border-emerald-900/60 bg-emerald-950/20 p-4 text-emerald-200">Your lineup is already optimal this week ({fmt(s.current_total)} projected).</div>
      ) : (
        <div className="rounded-xl border border-amber-900/60 bg-amber-950/20 p-4">
          <div className="font-semibold text-amber-200">{s.moves.length} suggested move{s.moves.length > 1 ? 's' : ''} · +{fmt(s.projected_gain)} projected ({fmt(s.current_total)} → {fmt(s.suggested_total)})</div>
          <ul className="mt-2 space-y-1 text-sm">
            {s.moves.map((m, i) => (
              <li key={i}>
                <span className="text-xs font-semibold text-slate-400">{m.slot}</span>{' '}
                Start <b>{m.in.name}</b>{m.out ? <> over <b>{m.out.name}</b></> : ' (slot was empty)'}{' '}
                <span className={m.delta >= 0 ? 'text-emerald-300' : 'text-red-300'}>({m.delta >= 0 ? '+' : ''}{fmt(m.delta)})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {s.flags.length > 0 && (
        <ul className="rounded-xl border border-slate-800 bg-slate-900/50 p-3 text-sm text-slate-300">
          {s.flags.map((f, i) => <li key={i}>⚠ {f}</li>)}
        </ul>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Col title="Current" rows={s.current_starters} total={s.current_total} highlight={outs} />
        <Col title="Suggested" rows={s.suggested_starters} total={s.suggested_total} highlight={ins} />
      </div>
    </div>
  )
}
