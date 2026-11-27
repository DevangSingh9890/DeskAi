import { useCallback, useEffect, useState } from 'react'
import { Dashboard } from './components/Dashboard'
import { AdminWorkspace } from './pages/AdminWorkspace'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import type { AppRoute } from './types/navigation'
import './App.css'

function App() {
  const [path, setPath] = useState(window.location.pathname)

  useEffect(() => {
    function syncPath() {
      setPath(window.location.pathname)
    }

    window.addEventListener('popstate', syncPath)
    return () => window.removeEventListener('popstate', syncPath)
  }, [])

  const navigate = useCallback((destination: AppRoute) => {
    if (window.location.pathname !== destination) {
      window.history.pushState(null, '', destination)
    }
    setPath(destination)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  if (path === '/') {
    return <LandingPage onNavigate={navigate} />
  }
  if (path === '/login') {
    return <LoginPage onNavigate={navigate} />
  }
  if (path === '/admin') {
    return <AdminWorkspace />
  }
  if (path === '/assistant' || path === '/dashboard') {
    return <Dashboard onNavigate={navigate} />
  }
  return <LandingPage onNavigate={navigate} />
}

export default App
