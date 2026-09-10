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

function GameChip({ g, count, selected, onClick }: { g: GameInfo; count: number; selected: boolean; onClick: () => void }) {
  const live = g.state === 'in'
  const border = selected ? 'border-blue-400 ring-1 ring-blue-400/60' : live ? 'border-emerald-700/60' : 'border-slate-800'
  return (
    <button onClick={onClick} title={selected ? 'Show all players' : `Show my ${count} player${count === 1 ? '' : 's'} in this game`}
      className={`shrink-0 rounded-lg border px-3 py-2 text-left text-xs transition hover:border-slate-500 ${border} ${live ? 'bg-emerald-950/30' : 'bg-slate-900/60'}`}>
      <div className="flex items-center gap-2 font-semibold">
        <span className="text-slate-300">{g.away} {g.away_score}</span>
        <span className="text-slate-600">@</span>
        <span className="text-slate-300">{g.home} {g.home_score}</span>
        <span className="ml-auto rounded bg-slate-800 px-1.5 text-[10px] font-semibold text-slate-300">{count}</span>
      </div>
      <div className={live ? 'text-emerald-300' : 'text-slate-500'}>{live && <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />}{g.detail}</div>
    </button>
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
  const [gameId, setGameId] = useState<string | null>(null)
  const [params] = useSearchParams()
  // Debug: /activity?season=2025&week=1&date=20250907 replays a past week.
  const debug = ['season', 'week', 'date'].filter((k) => params.get(k)).map((k) => `&${k}=${params.get(k)}`).join('')
  const q = useQuery({ queryKey: ['activity', bench, debug], queryFn: () => api.activity(bench, debug), refetchInterval: POLL_MS })

  if (q.isLoading) return <p className="text-slate-400">Loading your players…</p>
  if (q.isError) return <p className="text-red-300">{(q.error as Error).message}</p>
  const a = q.data!
  const liveCount = a.games.filter((g) => g.state === 'in').length
  const countByGame = new Map<string, number>()
  for (const p of a.players) if (p.game) countByGame.set(p.game.event_id, (countByGame.get(p.game.event_id) ?? 0) + 1)
  const selectedGame = gameId ? a.games.find((g) => g.event_id === gameId) ?? null : null
  const players = selectedGame ? a.players.filter((p) => p.game?.event_id === selectedGame.event_id) : a.players
  const playerIds = new Set(players.map((p) => p.sleeper_id))
  const events = selectedGame ? a.events.filter((e) => playerIds.has(e.sleeper_id)) : a.events

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
          {a.games.map((g) => (
            <GameChip key={g.event_id} g={g} count={countByGame.get(g.event_id) ?? 0} selected={g.event_id === gameId}
              onClick={() => setGameId(g.event_id === gameId ? null : g.event_id)} />
          ))}
        </div>
      )}

      {selectedGame && (
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-blue-900/60 bg-blue-950/20 px-3 py-2 text-sm">
          <span>Showing <b>{players.length}</b> of your players in <b>{selectedGame.away} @ {selectedGame.home}</b>{selectedGame.detail ? ` · ${selectedGame.detail}` : ''}</span>
          <button onClick={() => setGameId(null)} className="ml-auto text-xs text-blue-300 hover:underline">Show all</button>
        </div>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-400">
              <tr><th className="px-3 py-2">Player</th><th className="px-3 py-2">Game</th><th className="px-3 py-2">Stats</th><th className="px-3 py-2">Leagues · pts</th></tr>
            </thead>
            <tbody>
              {players.map((p) => {
                const g = p.game
                const live = g?.state === 'in'
                return (
                  <tr key={p.sleeper_id} className={`border-t border-slate-800/80 align-top ${live ? 'bg-emerald-500/5' : ''}`}>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2 font-medium">{p.name}<span className="text-xs text-slate-400">{p.position} · {p.nfl_team}</span>{p.injury_status && <StatusPill p={{ ...p, on_bye: false, projected_points: 0, projection_source: 'none', opponent: null, platform_player_id: p.sleeper_id, actual_points: null, game_state: null }} />}</div>
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
              {players.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-sm text-slate-500">None of your players are in this game.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Recent points</div>
          {events.length === 0
            ? <p className="text-sm text-slate-500">{selectedGame ? 'No points yet for your players in this game.' : 'Nothing yet. Point changes and scoring plays for your players show up here while games are on.'}</p>
            : <ul>{events.map((e, i) => <EventRow key={`${e.ts}-${e.sleeper_id}-${i}`} e={e} />)}</ul>}
        </div>
      </div>
    </div>
  )
}
