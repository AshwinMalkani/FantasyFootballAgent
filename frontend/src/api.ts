import type { Activity, LeagueDetail, LeagueRow, LineupSuggestion, NflState, WaiverTarget } from './types'

export class ApiError extends Error {
  hint: string | null
  constructor(message: string, hint: string | null = null) {
    super(message)
    this.hint = hint
  }
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path)
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    let hint: string | null = null
    try {
      const body = await r.json()
      if (body?.detail?.error) { msg = body.detail.error; hint = body.detail.hint ?? null }
      else if (typeof body?.detail === 'string') msg = body.detail
    } catch { /* ignore */ }
    throw new ApiError(msg, hint)
  }
  return r.json()
}

export const api = {
  state: () => get<NflState>('/api/state'),
  leagues: () => get<LeagueRow[]>('/api/leagues'),
  detail: (p: string, id: string) => get<LeagueDetail>(`/api/leagues/${p}/${id}`),
  lineup: (p: string, id: string) => get<LineupSuggestion>(`/api/leagues/${p}/${id}/lineup`),
  waivers: (p: string, id: string) => get<WaiverTarget[]>(`/api/leagues/${p}/${id}/waivers`),
  activity: (bench: boolean, debug = '') => get<Activity>(`/api/activity?bench=${bench}${debug}`),
  refresh: async () => { const r = await fetch('/api/refresh', { method: 'POST' }); return r.json() },
}
