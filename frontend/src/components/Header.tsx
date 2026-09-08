import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, NavLink } from 'react-router-dom'
import { api } from '../api'

export default function Header() {
  const qc = useQueryClient()
  const state = useQuery({ queryKey: ['state'], queryFn: api.state })
  const refresh = useMutation({
    mutationFn: api.refresh,
    onSuccess: () => qc.invalidateQueries(),
  })
  return (
    <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <Link to="/" className="text-lg font-bold tracking-tight">
          <span className="bg-gradient-to-r from-blue-400 via-violet-400 to-cyan-400 bg-clip-text text-transparent">Fantasy Hub</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          {[['/', 'Teams'], ['/activity', 'Live']].map(([to, label]) => (
            <NavLink key={to} to={to} end className={({ isActive }) => `rounded-md px-3 py-1.5 ${isActive ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-200'}`}>{label}</NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-4 text-sm text-slate-400">
          {state.data && <span>{state.data.season} · Week {state.data.week}</span>}
          <button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            className="rounded-md bg-slate-800 px-3 py-1.5 text-slate-200 ring-1 ring-slate-700 hover:bg-slate-700 disabled:opacity-50"
          >
            {refresh.isPending ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>
    </header>
  )
}
