import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import LeagueCard, { ErrorCard } from '../components/LeagueCard'
import { isError } from '../types'
import type { LeagueRow } from '../types'

const LIVE_POLL_MS = 45_000

export default function Dashboard() {
  // Only poll while something is actually being played. The per-card lineup/waiver
  // queries have no interval of their own, so they stay put.
  const q = useQuery({
    queryKey: ['leagues'],
    queryFn: api.leagues,
    refetchInterval: (query) =>
      (query.state.data as LeagueRow[] | undefined)?.some((r) => !isError(r) && r.in_progress) ? LIVE_POLL_MS : false,
  })
  if (q.isLoading) return <p className="text-slate-400">Loading leagues… (first load downloads the player database)</p>
  if (q.isError) return <p className="text-red-300">Backend unreachable: {(q.error as Error).message}. Is uvicorn running on :8000?</p>
  const rows = q.data ?? []
  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">My teams</h1>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((r, i) => (isError(r) ? <ErrorCard key={i} e={r} /> : <LeagueCard key={`${r.platform}-${r.league_id}`} s={r} />))}
      </div>
    </div>
  )
}
