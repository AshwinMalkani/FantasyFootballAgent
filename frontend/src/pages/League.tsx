import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import PlatformBadge from '../components/PlatformBadge'
import { fmt } from '../components/PlayerCell'
import RosterTab from '../components/RosterTab'
import LineupTab from '../components/LineupTab'
import WaiversTab from '../components/WaiversTab'

const TABS = ['Roster', 'Lineup', 'Waivers'] as const
type Tab = (typeof TABS)[number]

export default function League() {
  const { platform = '', leagueId = '' } = useParams()
  const [tab, setTab] = useState<Tab>('Lineup')
  const detail = useQuery({ queryKey: ['detail', platform, leagueId], queryFn: () => api.detail(platform, leagueId) })

  if (detail.isLoading) return <p className="text-slate-400">Loading league…</p>
  if (detail.isError) {
    const e = detail.error as ApiError
    return (
      <div className="rounded-xl border border-red-900/60 bg-red-950/20 p-4">
        <p className="text-red-200">{e.message}</p>
        {e.hint && <p className="mt-2 text-xs text-slate-400">How to fix: {e.hint}</p>}
        <Link to="/" className="mt-3 inline-block text-sm text-blue-300">← Back</Link>
      </div>
    )
  }
  const d = detail.data!
  const s = d.summary
  return (
    <div>
      <Link to="/" className="text-sm text-slate-400 hover:text-slate-200">← All teams</Link>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <PlatformBadge platform={s.platform} />
        <h1 className="text-xl font-semibold">{s.name}</h1>
        <span className="text-slate-400">{s.team_name}</span>
        {s.url && <a href={s.url} target="_blank" rel="noreferrer" className="text-xs text-blue-300 hover:underline">open on {s.platform} ↗</a>}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-300">
        <span><b>{s.record}</b>{s.rank ? ` · #${s.rank}${s.total_teams ? ` of ${s.total_teams}` : ''}` : ''}</span>
        <span>Week {s.week}{s.opponent_name ? ` vs ${s.opponent_name}` : ''}: <b>{fmt(s.my_projected_total)}</b> – {fmt(s.opp_projected_total)}</span>
        <span>{s.scoring_label}</span>
        <span>{s.waiver_type === 'FAAB' ? `FAAB $${s.faab_remaining ?? '?'}` : s.waiver_priority ? `Waiver priority #${s.waiver_priority}` : ''}</span>
      </div>

      <div className="mt-5 flex gap-1 border-b border-slate-800">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium ${tab === t ? 'border-b-2 border-blue-400 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
            {t}
          </button>
        ))}
      </div>
      <div className="mt-4">
        {tab === 'Roster' && <RosterTab detail={d} />}
        {tab === 'Lineup' && <LineupTab platform={platform} leagueId={leagueId} />}
        {tab === 'Waivers' && <WaiversTab platform={platform} leagueId={leagueId} />}
      </div>
    </div>
  )
}
