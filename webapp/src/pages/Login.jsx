import React, { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Logo } from '../components/ui'
import { useApp } from '../lib/store'
import { login, register, demoLogin, DEMO_ACCOUNTS, getOneClickAuthToken, oneClickH5Login } from '../lib/api'

// 注册可选主角色（对齐后端 User.role 主角色，不含 admin——管理员不可自注册）
const REGISTER_ROLES = [
  { value: 'homeowner', label: '业主' },
  { value: 'designer', label: '设计师' },
  { value: 'contractor', label: '施工方 / 服务商' },
  { value: 'supplier', label: '供应商' },
]

export default function LoginPage() {
  const [searchParams] = useSearchParams()
  const { setAuth, toast } = useApp()
  const [mode, setMode] = useState('login') // login | register
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('homeowner')
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [demoPhone, setDemoPhone] = useState(null)

  // 登录成功后的跳转目标：仅接受站内绝对路径（/xxx），拒绝外部 URL / 协议相对地址
  const afterAuth = (r, action, accountLabel, fallbackPath = '/') => {
    if (r.isSuccess && r.data) {
      setAuth(r.data.user || { phone })
      toast(action === 'demo' ? `已通过演示账号登录（${accountLabel}）` : action === 'login' ? '登录成功' : '注册成功', 'success')
      const redirectTo = searchParams.get('redirect') || fallbackPath
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
      mode === 'login' ? await login(phone, password) : await register(phone, name, password, role)
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
    // 按账号 landing 落点跳转：业主/管理员回 WebApp 首页，设计师/供应商/服务商直达控制台对应模块
    afterAuth(r, 'demo', account.label, account.landing || '/')
  }

  // 运营商一键登录（H5）：后端取鉴权 Token → JS SDK 拉起授权页拿 spToken → 换 PASETO Token。
  // 页面需通过 <script> 引入阿里云 numberAuth-web-sdk.js（挂载 window.PhoneNumberServer），
  // 未引入时优雅降级提示，不影响密码登录。
  const oneClickSubmit = async () => {
    setErr(null)
    setBusy(true)
    try {
      const auth = await getOneClickAuthToken()
      if (!auth.isSuccess) {
        setErr(auth.error || '一键登录鉴权失败')
        return
      }
      const { access_token: accessToken, jwt_token: jwtToken } = auth.data || {}
      if (!window.PhoneNumberServer) {
        setErr('本机号码一键登录需引入阿里云 H5 SDK（页面未加载 numberAuth-web-sdk.js）')
        return
      }
      const fmtErr = (res, fallback) => {
        if (!res || typeof res !== 'object') return fallback
        const c = res.carrier && typeof res.carrier === 'object' ? res.carrier : {}
        const bits = [res.code, res.vender, c.carrierSdkCode, c.carrierSdkMsg].filter(Boolean)
        if (Array.isArray(res.content)) {
          for (const e of res.content) {
            if (e && typeof e === 'object') {
              bits.push([e.vender, e.code, e.msg].filter(Boolean).join('/'))
            }
          }
        }
        return `${res.msg || fallback}${bits.length ? `（${bits.join(' · ')}）` : ''}`
      }
      const spToken = await new Promise((resolve, reject) => {
        const server = new window.PhoneNumberServer()
        server.checkLoginAvailable({
          accessToken,
          jwtToken,
          success: () => {
            server.getLoginToken({
              authPageOption: {},
              success: (res) => resolve(res && typeof res === 'object' ? res.spToken : undefined),
              error: (res) => {
                console.error('[oneclick] getLoginToken error:', res)
                reject(new Error(fmtErr(res, '授权失败')))
              },
            })
          },
          error: (res) => {
            console.error('[oneclick] checkLoginAvailable error:', res)
            reject(new Error(fmtErr(res, '鉴权失败')))
          },
        })
      })
      if (!spToken) {
        setErr('一键登录未获取到授权 Token')
        return
      }
      const r = await oneClickH5Login(spToken)
      afterAuth(r, 'login')
    } catch (e) {
      setErr(e instanceof Error ? e.message : '一键登录失败')
    } finally {
      setBusy(false)
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
          {mode === 'register' && (
            <div className="field">
              <label>角色</label>
              <select
                className="select"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                data-testid="auth-register-role"
              >
                {REGISTER_ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
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

        {/* 运营商一键登录（H5） */}
        <button
          type="button"
          className="btn"
          onClick={oneClickSubmit}
          disabled={busy}
          style={{ marginTop: 12 }}
        >
          {busy ? '请稍候…' : '本机号码一键登录'}
        </button>

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
