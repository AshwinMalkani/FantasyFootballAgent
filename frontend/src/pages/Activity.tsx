import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { StatusPill, fmt } from '../components/PlayerCell'
import type { ActivityEvent, ActivityPlayer, GameInfo } from '../types'

const POLL_MS = 30_000

function ago(iso: string | number | null): string {
  if (!iso) return ''
  const t = typeof iso === 'number' ? iso : Date.parse(iso)
  const s = Math.max(0, Math.round((Date.now() - t) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function GameChip({ g, mine }: { g: GameInfo; mine: string | null }) {
  const live = g.state === 'in'
  return (
    <div className={`rounded-lg border px-3 py-2 text-xs ${live ? 'border-emerald-700/60 bg-emerald-950/30' : 'border-slate-800 bg-slate-900/60'}`}>
      <div className="flex items-center gap-2 font-semibold">
        <span className={g.away === mine ? 'text-white' : 'text-slate-400'}>{g.away} {g.away_score}</span>
        <span className="text-slate-600">@</span>
        <span className={g.home === mine ? 'text-white' : 'text-slate-400'}>{g.home} {g.home_score}</span>
      </div>
      <div className={live ? 'text-emerald-300' : 'text-slate-500'}>{live && <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />}{g.detail}</div>
    </div>
  )
}

function LeagueChips({ p }: { p: ActivityPlayer }) {
  return (
    <div className="flex flex-wrap gap-1">
      {p.leagues.map((l) => (
        <Link key={l.league_key} to={`/league/${l.platform}/${l.league_id}`} title={`${l.league_name} · ${l.slot} · proj ${fmt(l.projected)}`}
          className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] ring-1 ${l.is_starter ? 'bg-slate-800 ring-slate-700' : 'bg-slate-900 ring-slate-800 text-slate-500'}`}>
          <span className={l.platform === 'sleeper' ? 'text-indigo-300' : l.platform === 'espn' ? 'text-red-300' : 'text-purple-300'}>{l.league_name}</span>
          <span className="font-semibold tabular-nums">{fmt(l.points)}</span>
          {!l.is_starter && <span className="text-slate-500">BN</span>}
        </Link>
      ))}
    </div>
  )
}

function EventRow({ e }: { e: ActivityEvent }) {
  return (
    <li className="border-t border-slate-800/80 py-2 text-sm first:border-t-0">
      <div className="flex items-baseline justify-between gap-2">
        <span><span className="font-semibold">{e.name}</span> <span className="text-amber-200">{e.summary ?? e.text}</span></span>
        <span className="shrink-0 text-[11px] text-slate-500">{ago(e.ts)}</span>
      </div>
      {e.kind === 'play' && e.text && <div className="mt-0.5 line-clamp-1 text-[11px] text-slate-500" title={e.text}>{e.text}</div>}
      <div className="mt-1 flex flex-wrap gap-1">
        {e.league_deltas.map((d) => (
          <span key={d.league_key} className="rounded bg-slate-800 px-1.5 py-0.5 text-[11px]">
            <span className={d.platform === 'sleeper' ? 'text-indigo-300' : d.platform === 'espn' ? 'text-red-300' : 'text-purple-300'}>{d.league_name}</span>
            {d.delta != null && <span className={`ml-1 font-semibold ${d.delta >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>{d.delta >= 0 ? '+' : ''}{fmt(d.delta)}</span>}
          </span>
        ))}
      </div>
    </li>
  )
}

export default function Activity() {
  const [bench, setBench] = useState(false)
  const [params] = useSearchParams()
  // Debug: /activity?season=2025&week=1&date=20250907 replays a past week.
  const debug = ['season', 'week', 'date'].filter((k) => params.get(k)).map((k) => `&${k}=${params.get(k)}`).join('')
  const q = useQuery({ queryKey: ['activity', bench, debug], queryFn: () => api.activity(bench, debug), refetchInterval: POLL_MS })

  if (q.isLoading) return <p className="text-slate-400">Loading your players…</p>
  if (q.isError) return <p className="text-red-300">{(q.error as Error).message}</p>
  const a = q.data!
  const liveCount = a.games.filter((g) => g.state === 'in').length

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Live · Week {a.week}</h1>
        <div className="flex items-center gap-4 text-xs text-slate-400">
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={bench} onChange={(e) => setBench(e.target.checked)} /> include bench</label>
          <span>{liveCount ? `${liveCount} live` : 'no games in progress'} · updated {ago(a.updated_at)} · auto-refresh 30s</span>
        </div>
      </div>

      {a.games.length > 0 && (
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
          {a.games.map((g) => <GameChip key={g.event_id} g={g} mine={null} />)}
        </div>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-400">
              <tr><th className="px-3 py-2">Player</th><th className="px-3 py-2">Game</th><th className="px-3 py-2">Stats</th><th className="px-3 py-2">Leagues · pts</th></tr>
            </thead>
            <tbody>
              {a.players.map((p) => {
                const g = p.game
                const live = g?.state === 'in'
                return (
                  <tr key={p.sleeper_id} className={`border-t border-slate-800/80 align-top ${live ? 'bg-emerald-500/5' : ''}`}>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2 font-medium">{p.name}<span className="text-xs text-slate-400">{p.position} · {p.nfl_team}</span>{p.injury_status && <StatusPill p={{ ...p, on_bye: false, projected_points: 0, projection_source: 'none', opponent: null, platform_player_id: p.sleeper_id }} />}</div>
                      {p.plays[0] && <div className="mt-1 max-w-md text-xs text-slate-400" title={p.plays[0].text}>↳ {p.plays[0].summary ?? p.plays[0].text}</div>}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-xs">
                      {g ? <><div className={live ? 'text-emerald-300' : 'text-slate-300'}>{g.away} @ {g.home}</div><div className="text-slate-500">{g.detail}</div></> : <span className="text-slate-500">—</span>}
                    </td>
                    <td className="px-3 py-2 text-xs text-slate-300">
                      {p.stat_line}
                      {p.updated_at && <div className="text-[10px] text-slate-500">{ago(p.updated_at)}</div>}
                    </td>
                    <td className="px-3 py-2"><LeagueChips p={p} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Recent points</div>
          {a.events.length === 0
            ? <p className="text-sm text-slate-500">Nothing yet. Point changes and scoring plays for your players show up here while games are on.</p>
            : <ul>{a.events.map((e, i) => <EventRow key={`${e.ts}-${e.sleeper_id}-${i}`} e={e} />)}</ul>}
        </div>
      </div>
    </div>
  )
}
