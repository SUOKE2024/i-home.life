import React, { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Logo } from '../components/ui'
import { useApp } from '../lib/store'
import { login, register, demoLogin, DEMO_ACCOUNTS } from '../lib/api'

export default function LoginPage() {
  const [searchParams] = useSearchParams()
  const { setAuth, toast } = useApp()
  const [mode, setMode] = useState('login') // login | register
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [demoPhone, setDemoPhone] = useState(null)

  // 登录成功后的跳转目标：仅接受站内绝对路径（/xxx），拒绝外部 URL / 协议相对地址
  const afterAuth = (r, action, accountLabel) => {
    if (r.isSuccess && r.data) {
      setAuth(r.data.user || { phone })
      toast(action === 'demo' ? `已通过演示账号登录（${accountLabel}）` : action === 'login' ? '登录成功' : '注册成功', 'success')
      const redirectTo = searchParams.get('redirect') || '/'
      // 跨 SPA 跳转（如 /console/ 属独立控制台应用）：必须整页加载而非 React Router navigate，
      // 否则 webapp 路由无 /console/ 会被 catch-all 重定向回 '/'
      const safePath = redirectTo.startsWith('/') && !redirectTo.startsWith('//') ? redirectTo : '/'
      window.location.href = safePath
    } else {
      setErr(r.error || '操作失败，请重试')
    }
  }

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
    afterAuth(r, mode)
  }

  // 一键演示登录：点击演示账号直接登录（无需输入）
  const demoSubmit = async (account) => {
    setErr(null)
    setBusy(true)
    setDemoPhone(account.phone)
    const r = await demoLogin(account.phone)
    setBusy(false)
    setDemoPhone(null)
    afterAuth(r, 'demo', account.label)
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

        {/* 一键演示登录：无需注册，点击即体验 */}
        <div className="auth-demo">
          <div className="auth-demo-label">
            <span>无账号？一键体验演示</span>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text-dim)' }}>演示数据 · 密码 123456</span>
          </div>
          <div className="auth-demo-list">
            {DEMO_ACCOUNTS.map((a) => (
              <button
                key={a.phone}
                type="button"
                className="auth-demo-item"
                disabled={busy}
                onClick={() => demoSubmit(a)}
              >
                <b>{a.label}</b>
                <span className="auth-demo-hint">{a.hint}</span>
                <span className="auth-demo-go">{demoPhone === a.phone ? '登录中…' : '进入 →'}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 备案号 Footer（公开可见，工信部合规：链接至备案管理系统）+ 公开文档链接 */}
      <footer
        className="app-footer"
        style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'transparent', borderTop: 'none' }}
      >
        <span className="app-footer-copy">© 2026 索克家居 · i-home.life</span>
        <span className="app-footer-docs">
          <Link to="/guide">使用指南</Link>
          <Link to="/legal/privacy">隐私政策</Link>
          <Link to="/legal/terms">服务条款</Link>
        </span>
        <span className="app-footer-beian">
          <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">
            滇ICP备2026015233号-2
          </a>
        </span>
      </footer>
    </div>
  )
}
