import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { wechatLogin } from '../lib/api'

// 与登录页 DEMO_ACCOUNTS landing 口径一致：业主/管理员回 WebApp，其余直达控制台模块
const LANDING_BY_ROLE = {
  homeowner: '/',
  admin: '/',
  designer: '/console/',
  supplier: '/console/procurement',
  contractor: '/console/quality',
}

/**
 * 微信扫码登录回调页（路由 /wechat-callback）。
 * 微信 qrconnect 成功后携带 code + state 跳回本页：
 * code/state 交由后端换 PASETO Token，成功按角色跳转，失败回登录页。
 */
export default function WeChatCallback() {
  const navigate = useNavigate()
  const [status, setStatus] = useState('微信登录处理中…')
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true

    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const state = params.get('state')
    if (!code || !state) {
      setStatus('微信登录失败：缺少回调参数，正在返回登录页…')
      setTimeout(() => navigate('/auth'), 2500)
      return
    }

    ;(async () => {
      const r = await wechatLogin(code, state)
      if (r.isSuccess && r.data && r.data.user) {
        const role = r.data.user.role || 'homeowner'
        const target = LANDING_BY_ROLE[role] || '/'
        const safePath = target.startsWith('/') && !target.startsWith('//') ? target : '/'
        // 跨 SPA 跳转（/console/ 属独立控制台应用）必须整页加载
        window.location.href = safePath
      } else {
        setStatus(`${r.error || '微信登录失败，请重试'}，正在返回登录页…`)
        setTimeout(() => navigate('/auth'), 2500)
      }
    })()
  }, [navigate])

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <div style={{ fontSize: 17, fontWeight: 700 }}>索克家居</div>
        </div>
        <p style={{ textAlign: 'center', marginTop: 24, color: 'var(--text-dim)' }}>{status}</p>
      </div>
    </div>
  )
}
