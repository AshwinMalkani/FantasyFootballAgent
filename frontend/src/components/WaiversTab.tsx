import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '../api'
import PlayerCell, { fmt } from './PlayerCell'

export default function WaiversTab({ platform, leagueId }: { platform: string; leagueId: string }) {
  const q = useQuery({ queryKey: ['waivers', platform, leagueId], queryFn: () => api.waivers(platform, leagueId) })
  if (q.isLoading) return <p className="text-slate-400">Scanning free agents…</p>
  if (q.isError) return <p className="text-red-300">{(q.error as ApiError).message}</p>
  const rows = q.data!
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-400">
          <tr>
            <th className="px-3 py-2">#</th>
            <th className="px-3 py-2">Player</th>
            <th className="px-3 py-2 text-right">Proj</th>
            <th className="px-3 py-2 text-right">Lineup gain</th>
            <th className="px-3 py-2 text-right">Trending adds</th>
            <th className="px-3 py-2 text-right">Score</th>
            <th className="px-3 py-2">Suggested drop</th>
            <th className="px-3 py-2 text-right">Net</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t, i) => (
            <tr key={t.player.platform_player_id} className={`border-t border-slate-800/80 ${t.net_gain != null && t.net_gain > 0 ? 'bg-emerald-500/5' : ''}`}>
              <td className="px-3 py-2 text-slate-500">{i + 1}</td>
              <td className="px-3 py-2"><PlayerCell p={t.player} /></td>
              <td className="px-3 py-2 text-right tabular-nums">{fmt(t.player.projected_points)}</td>
              <td className={`px-3 py-2 text-right tabular-nums ${t.lineup_gain > 0 ? 'text-emerald-300' : 'text-slate-500'}`}>{t.lineup_gain > 0 ? `+${fmt(t.lineup_gain)}` : '–'}</td>
              <td className="px-3 py-2 text-right tabular-nums text-slate-400">{t.trending_adds ? t.trending_adds.toLocaleString() : '–'}</td>
              <td className="px-3 py-2 text-right tabular-nums font-semibold">{fmt(t.score)}</td>
              <td className="px-3 py-2"><PlayerCell p={t.suggested_drop} empty="—" /></td>
              <td className={`px-3 py-2 text-right tabular-nums ${t.net_gain != null && t.net_gain > 0 ? 'text-emerald-300' : 'text-slate-400'}`}>{t.net_gain == null ? '–' : `${t.net_gain > 0 ? '+' : ''}${fmt(t.net_gain)}`}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-3 py-2 text-xs text-slate-500">Score = lineup gain (how much your optimal lineup improves if you add them) + depth value (net gain over the suggested drop, weighted down for backup QB/K/DEF) + a trending-adds bonus (Sleeper add counts, last 24h, log-scaled, capped at +5).</p>
    </div>
  )
}
