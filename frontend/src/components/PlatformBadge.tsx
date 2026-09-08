import type { Platform } from '../types'

const STYLES: Record<Platform, string> = {
  sleeper: 'bg-indigo-500/20 text-indigo-300 ring-indigo-500/40',
  espn: 'bg-red-500/20 text-red-300 ring-red-500/40',
  yahoo: 'bg-purple-500/20 text-purple-300 ring-purple-500/40',
}
const LABEL: Record<Platform, string> = { sleeper: 'Sleeper', espn: 'ESPN', yahoo: 'Yahoo' }

export default function PlatformBadge({ platform }: { platform: Platform }) {
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ${STYLES[platform]}`}>
      {LABEL[platform]}
    </span>
  )
}
