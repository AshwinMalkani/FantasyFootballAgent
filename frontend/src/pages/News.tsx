import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { NewsItem, NewsLeague, NewsPlayer } from '../types'

function ago(iso: string | null): string {
  if (!iso) return ''
  const s = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 1000))
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  const d = Math.round(s / 86400)
  return d === 1 ? 'yesterday' : `${d}d ago`
}

const TYPE_STYLE: Record<string, string> = {
  Rotowire: 'bg-amber-500/15 text-amber-300',
  Story: 'bg-sky-500/15 text-sky-300',
  Media: 'bg-violet-500/15 text-violet-300',
}
const PLATFORM_TEXT = { sleeper: 'text-indigo-300', espn: 'text-red-300', yahoo: 'text-purple-300' } as const

function LeagueChips({ leagues }: { leagues: NewsLeague[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {leagues.map((l) => (
        <Link key={`${l.platform}-${l.league_id}`} to={`/league/${l.platform}/${l.league_id}`}
          className={`rounded-md bg-slate-800 px-1.5 py-0.5 text-[11px] ring-1 ring-slate-700 ${l.is_starter ? '' : 'text-slate-500'}`}>
          <span className={PLATFORM_TEXT[l.platform]}>{l.league_name}</span> <span className="text-slate-500">{l.slot}</span>
        </Link>
      ))}
    </div>
  )
}

function PlayerLine({ p }: { p: NewsPlayer }) {
  const bad = ['OUT', 'IR', 'DOUBTFUL', 'SUS', 'PUP'].includes((p.injury_status || '').toUpperCase())
  return (
    <>
      <span className="font-semibold">{p.name}</span>
      <span className="text-xs text-slate-400">{p.position} · {p.nfl_team ?? 'FA'}</span>
      {p.injury_status && <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${bad ? 'bg-red-500/20 text-red-300' : 'bg-amber-500/20 text-amber-300'}`}>{p.injury_status}</span>}
    </>
  )
}

function Item({ n }: { n: NewsItem }) {
  const [open, setOpen] = useState(false)
  const body = n.story || n.description
  const long = body.length > 220
  const players = n.players?.length ? n.players : [{ ...n.player, leagues: n.leagues }]
  return (
    <li className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <PlayerLine p={players[0]} />
        {players.length > 1 && <span className="text-xs text-slate-500">+{players.length - 1} more</span>}
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${TYPE_STYLE[n.type] ?? 'bg-slate-700 text-slate-300'}`}>{n.type === 'Rotowire' ? 'Player note' : n.type}</span>
        <span className="ml-auto text-xs text-slate-500">{ago(n.published)}</span>
      </div>
      <div className="mt-1.5 font-medium">{n.link ? <a href={n.link} target="_blank" rel="noreferrer" className="hover:underline">{n.headline} ↗</a> : n.headline}</div>
      {body && body !== n.headline && (
        <p className="mt-1 text-sm leading-relaxed text-slate-300">
          {open || !long ? body : body.slice(0, 220) + '…'}
          {long && <button onClick={() => setOpen(!open)} className="ml-2 text-xs text-blue-300 hover:underline">{open ? 'less' : 'more'}</button>}
        </p>
      )}
      <div className="mt-2 space-y-1.5">
        {players.map((p, i) => (
          <div key={p.espn_id} className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {/* The first player is already named in the header; the rest get their own line. */}
            {i > 0 && <span className="flex items-center gap-2 text-xs"><PlayerLine p={p} /></span>}
            <LeagueChips leagues={p.leagues} />
          </div>
        ))}
      </div>
    </li>
  )
}

export default function NewsPage() {
  const [days, setDays] = useState(7)
  const [bench, setBench] = useState(true)
  const [type, setType] = useState<'all' | 'Rotowire' | 'Story'>('all')
  const [search, setSearch] = useState('')
  const q = useQuery({ queryKey: ['news', days, bench], queryFn: () => api.news(days, bench), staleTime: 15 * 60_000 })

  const items = useMemo(() => {
    const list = q.data?.items ?? []
    const s = search.trim().toLowerCase()
    return list.filter((n) => (type === 'all' || (type === 'Story' ? n.type !== 'Rotowire' : n.type === type))
      && (!s || n.headline.toLowerCase().includes(s)
        || (n.players ?? [n.player]).some((p) => p.name.toLowerCase().includes(s))))
  }, [q.data, type, search])

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">News</h1>
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Filter by player or headline"
            className="rounded-md bg-slate-900 px-2 py-1 text-slate-200 ring-1 ring-slate-700 placeholder:text-slate-600" />
          <select value={type} onChange={(e) => setType(e.target.value as typeof type)} className="rounded-md bg-slate-900 px-2 py-1 text-slate-200 ring-1 ring-slate-700">
            <option value="all">All types</option>
            <option value="Rotowire">Player notes</option>
            <option value="Story">Stories & video</option>
          </select>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-md bg-slate-900 px-2 py-1 text-slate-200 ring-1 ring-slate-700">
            {[1, 3, 7, 14, 30].map((d) => <option key={d} value={d}>Last {d}d</option>)}
          </select>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={bench} onChange={(e) => setBench(e.target.checked)} /> include bench</label>
        </div>
      </div>

      {q.isLoading && <p className="mt-4 text-slate-400">Fetching news for your players…</p>}
      {q.isError && <p className="mt-4 text-red-300">{(q.error as Error).message}</p>}
      {q.data && (
        <>
          <p className="mt-2 text-xs text-slate-500">
            {items.length} items for {q.data.players} players
            {q.data.unmapped.length > 0 && <> · no feed for: {q.data.unmapped.join(', ')}</>}
          </p>
          {items.length === 0
            ? <p className="mt-6 text-slate-500">Nothing in this window.</p>
            : <ul className="mt-4 grid gap-3 lg:grid-cols-2">{items.map((n) => <Item key={n.id} n={n} />)}</ul>}
        </>
      )}
    </div>
  )
}
