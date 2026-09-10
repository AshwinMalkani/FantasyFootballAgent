import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { LeagueError, LeagueSummary } from '../types'
import PlatformBadge from './PlatformBadge'
import { Scoreline, fmt } from './PlayerCell'

export function ErrorCard({ e }: { e: LeagueError }) {
  return (
    <div className="rounded-xl border border-red-900/60 bg-red-950/20 p-4">
      <div className="mb-2 flex items-center justify-between">
        <PlatformBadge platform={e.platform} />
        <span className="text-xs text-red-300">unavailable</span>
      </div>
      <div className="font-semibold">{e.name ?? `${e.platform} league`}</div>
      <p className="mt-1 text-sm text-red-200/90">{e.error}</p>
      {e.hint && <p className="mt-2 text-xs text-slate-400">How to fix: {e.hint}</p>}
    </div>
  )
}

export default function LeagueCard({ s }: { s: LeagueSummary }) {
  const lineup = useQuery({ queryKey: ['lineup', s.platform, s.league_id], queryFn: () => api.lineup(s.platform, s.league_id) })
  const waivers = useQuery({ queryKey: ['waivers', s.platform, s.league_id], queryFn: () => api.waivers(s.platform, s.league_id) })
  const moves = lineup.data?.moves.length
  const top = waivers.data?.[0]

  return (
    <Link to={`/league/${s.platform}/${s.league_id}`} className="block rounded-xl border border-slate-800 bg-slate-900/70 p-4 transition hover:border-slate-600 hover:bg-slate-900">
      <div className="mb-2 flex items-center justify-between">
        <PlatformBadge platform={s.platform} />
        <span className="text-xs text-slate-400">{s.scoring_label}</span>
      </div>
      <div className="truncate text-base font-semibold">{s.name}</div>
      <div className="truncate text-sm text-slate-400">{s.team_name}</div>

      <div className="mt-3 flex items-baseline gap-3">
        <span className="text-2xl font-bold">{s.record}</span>
        {s.rank && <span className="text-sm text-slate-400">#{s.rank}{s.total_teams ? ` of ${s.total_teams}` : ''}</span>}
        {s.points_for != null && <span className="ml-auto text-xs text-slate-500">{fmt(s.points_for)} PF</span>}
      </div>

      <div className="mt-3 rounded-lg bg-slate-800/60 p-2 text-sm">
        <div className="text-xs text-slate-400">Week {s.week}{s.opponent_name ? ` vs ${s.opponent_name}` : ''}</div>
        <div className="mt-0.5">
          <Scoreline my={s.my_actual_total} opp={s.opp_actual_total} myProj={s.my_projected_total} oppProj={s.opp_projected_total} live={s.in_progress} />
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg bg-slate-800/40 p-2">
          <div className="text-slate-400">Lineup</div>
          {lineup.isLoading ? <div className="text-slate-500">…</div>
            : lineup.isError ? <div className="text-red-300">error</div>
            : moves ? <div className="font-semibold text-amber-300">{moves} move{moves > 1 ? 's' : ''} · +{fmt(lineup.data!.projected_gain)}</div>
            : <div className="font-semibold text-emerald-300">Optimal</div>}
        </div>
        <div className="rounded-lg bg-slate-800/40 p-2">
          <div className="text-slate-400">Top waiver</div>
          {waivers.isLoading ? <div className="text-slate-500">…</div>
            : waivers.isError ? <div className="text-red-300">error</div>
            : top ? <div className="truncate font-semibold">{top.player.name} <span className="text-slate-400">{top.player.position} · {fmt(top.player.projected_points)}</span></div>
            : <div className="text-slate-500">none</div>}
        </div>
      </div>

      <div className="mt-2 text-[11px] text-slate-500">
        {s.waiver_type === 'FAAB' ? `FAAB $${s.faab_remaining ?? '?'}` : s.waiver_priority ? `Waiver #${s.waiver_priority}` : ''}
      </div>
    </Link>
  )
}
