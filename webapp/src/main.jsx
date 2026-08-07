import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { setOnUnauthorized } from './lib/api'
import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'
import './styles/pages.css'

/* 全局 401：清登录态 → 回登录页 */
setOnUnauthorized(() => {
  if (!window.location.pathname.startsWith('/auth')) {
    window.location.href = '/auth'
  }
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
