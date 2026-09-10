export type Platform = 'sleeper' | 'espn' | 'yahoo'

export interface Player {
  sleeper_id: string | null
  platform_player_id: string
  name: string
  position: string
  nfl_team: string | null
  injury_status: string | null
  on_bye: boolean
  opponent: string | null
  projected_points: number
  projection_source: 'espn' | 'sleeper-exact' | 'sleeper-approx' | 'none'
  actual_points: number | null
  game_state: 'pre' | 'in' | 'post' | null
}

export interface RosterSlot { slot: string; player: Player | null }

export interface LeagueSummary {
  platform: Platform
  league_id: string
  name: string
  season: number
  week: number
  team_name: string
  record: string
  rank: number | null
  total_teams: number | null
  points_for: number | null
  opponent_name: string | null
  my_projected_total: number | null
  opp_projected_total: number | null
  my_actual_total: number | null
  opp_actual_total: number | null
  in_progress: boolean
  waiver_type: string | null
  faab_remaining: number | null
  waiver_priority: number | null
  scoring_label: string | null
  url: string | null
}

export interface LeagueError {
  platform: Platform
  league_id: string | null
  name: string | null
  error: string
  hint: string | null
}

export type LeagueRow = LeagueSummary | LeagueError
export const isError = (r: LeagueRow): r is LeagueError => 'error' in r

export interface LeagueDetail {
  summary: LeagueSummary
  roster: RosterSlot[]
  lineup_slots: string[]
  scoring: Record<string, number>
}

export interface LineupMove { slot: string; out: Player | null; in: Player; delta: number }

export interface LineupSuggestion {
  current_starters: RosterSlot[]
  suggested_starters: RosterSlot[]
  moves: LineupMove[]
  current_total: number
  suggested_total: number
  projected_gain: number
  flags: string[]
}

export interface WaiverTarget {
  player: Player
  score: number
  trending_adds: number
  lineup_gain: number
  suggested_drop: Player | null
  net_gain: number | null
}

export interface NflState { season: number; week: number; season_type: string }

export interface GameInfo {
  event_id: string
  name: string
  start: string | null
  state: 'pre' | 'in' | 'post'
  detail: string | null
  clock: string | null
  period: number | null
  home: string | null
  away: string | null
  home_score: string | null
  away_score: string | null
}

export interface ActivityLeague {
  league_key: string
  platform: Platform
  league_id: string
  league_name: string
  slot: string
  is_starter: boolean
  points: number
  projected: number
}

export interface ActivityPlay {
  id: string
  text: string
  summary: string | null
  scoring: boolean
  wallclock: string | null
  clock: string | null
  period: number | null
  league_points: { league_key: string; league_name: string; platform: Platform; delta: number }[]
}

export interface ActivityPlayer {
  sleeper_id: string
  name: string
  position: string
  nfl_team: string | null
  injury_status: string | null
  leagues: ActivityLeague[]
  stat_line: string
  updated_at: number | null
  game: GameInfo | null
  plays: ActivityPlay[]
  pts_ppr: number
}

export interface ActivityEvent {
  ts: string
  kind: 'stats' | 'play'
  sleeper_id: string
  name: string
  summary: string | null
  text: string | null
  stat_diff: { stat: string; delta: number }[]
  league_deltas: { league_key: string; league_name: string; platform: Platform; delta: number | null }[]
}

export interface Activity {
  updated_at: string
  season: number
  week: number
  games: GameInfo[]
  players: ActivityPlayer[]
  events: ActivityEvent[]
}
