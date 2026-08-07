import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { getToken, me as apiMe, logout as apiLogout } from './api'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loggedIn, setLoggedIn] = useState(false)
  const [gateway, setGateway] = useState({ live: null, lat_ms: null, services: [] })
  const [toasts, setToasts] = useState([])
  const [booted, setBooted] = useState(false)
  const [navCollapsed, setNavCollapsed] = useState(false)

  /* 启动时：若有 token，拉取 /api/auth/me 恢复会话 */
  useEffect(() => {
    let on = true
    const boot = async () => {
      if (!getToken()) {
        if (on) setBooted(true)
        return
      }
      const r = await apiMe()
      if (on) {
        if (r.isSuccess && r.data) {
          setUser(r.data)
          setLoggedIn(true)
        } else {
          localStorage.removeItem('paseto_token')
        }
        setBooted(true)
      }
    }
    boot()
    return () => { on = false }
  }, [])

  /* 登录 / 登出 */
  const setAuth = useCallback((u) => {
    setUser(u)
    setLoggedIn(!!u)
  }, [])

  const logout = useCallback(async () => {
    await apiLogout()
    setUser(null)
    setLoggedIn(false)
  }, [])

  /* Toast */
  const toast = useCallback((message, type = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, message, type }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200)
  }, [])

  return (
    <AppContext.Provider
      value={{ user, loggedIn, booted, setAuth, logout, toast, toasts, gateway, setGateway, navCollapsed, setNavCollapsed }}
    >
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  return useContext(AppContext)
}
