import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Logo } from '../components/ui'
import { useApp } from '../lib/store'
import { login, register } from '../lib/api'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setAuth, toast } = useApp()
  const [mode, setMode] = useState('login') // login | register
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setErr(null)
    if (!phone || !password) {
      setErr('请输入手机号和密码')
      return
    }
    if (mode === 'register' && !name) {
      setErr('请输入昵称')
      return
    }
    setBusy(true)
    const r =
      mode === 'login' ? await login(phone, password) : await register(phone, name, password)
    setBusy(false)
    if (r.isSuccess && r.data) {
      setAuth(r.data.user || { phone })
      toast(mode === 'login' ? '登录成功' : '注册成功', 'success')
      navigate('/')
    } else {
      setErr(r.error || '操作失败，请重试')
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <Logo size={44} />
          <div>
            <div style={{ fontSize: 17, fontWeight: 700 }}>索克家居</div>
            <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)' }}>
              i-home.life · AI 智能装修平台
            </div>
          </div>
        </div>

        <div className="auth-tabs">
          <button
            type="button"
            className={`auth-tab${mode === 'login' ? ' auth-tab--active' : ''}`}
            onClick={() => setMode('login')}
          >
            登录
          </button>
          <button
            type="button"
            className={`auth-tab${mode === 'register' ? ' auth-tab--active' : ''}`}
            onClick={() => setMode('register')}
          >
            注册
          </button>
        </div>

        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {mode === 'register' && (
            <div className="field">
              <label>昵称</label>
              <input
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="您的称呼"
                maxLength={20}
              />
            </div>
          )}
          <div className="field">
            <label>手机号</label>
            <input
              className="input"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="11 位手机号"
              inputMode="tel"
              maxLength={11}
            />
          </div>
          <div className="field">
            <label>密码</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="密码"
            />
          </div>
          <button className="btn btn--primary" type="submit" disabled={busy} style={{ marginTop: 6 }}>
            {busy ? '请稍候…' : mode === 'login' ? '登 录' : '注册并登录'}
          </button>
        </form>

        {err && <div className="auth-err">{err}</div>}
      </div>

      {/* 备案号 Footer（公开可见，工信部合规：链接至备案管理系统） */}
      <footer
        className="app-footer"
        style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'transparent', borderTop: 'none' }}
      >
        <span className="app-footer-copy">© 2026 索克家居 · i-home.life</span>
        <span className="app-footer-beian">
          <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">
            滇ICP备2026015233号-2
          </a>
        </span>
      </footer>
    </div>
  )
}
