import { useCallback, useEffect, useState } from 'react'
import { Dashboard } from './components/Dashboard'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
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

  const navigate = useCallback((destination: '/' | '/login' | '/dashboard') => {
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
  return <Dashboard onNavigate={navigate} />
}

export default App
