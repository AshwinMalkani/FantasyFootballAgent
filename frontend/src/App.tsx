import { Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import League from './pages/League'
import Header from './components/Header'

export default function App() {
  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/league/:platform/:leagueId" element={<League />} />
        </Routes>
      </main>
    </div>
  )
}
