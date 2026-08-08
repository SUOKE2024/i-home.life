import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserCircle, Phone, ShieldCheck, CalendarDays, LogOut, Info } from 'lucide-react'
import { Card, Badge, Empty } from '../components/ui'
import { useApp } from '../lib/store'

/* 角色映射：后端 role → 中文展示，未收录的原样显示 */
const ROLE_MAP = {
  homeowner: '业主',
  admin: '管理员',
  designer: '设计师',
  worker: '施工人员',
}

/* 日期格式化：YYYY-MM-DD */
function fmtDate(v) {
  if (!v) return '—'
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('zh-CN')
}

export default function ProfilePage() {
  const { user, logout, toast } = useApp()
  const navigate = useNavigate()

  /* 退出登录：调用 logout 后跳转登录页 */
  const handleLogout = async () => {
    await logout()
    toast('已退出登录', 'info')
    navigate('/auth')
  }

  /* 防御性访问：user 可能为空 */
  const u = user || {}
  const roleLabel = ROLE_MAP[u.role] || u.role || '—'
  const initial = (u.name || '索')[0] || '索'

  return (
    <div>
      <div className="page-head">
        <h2>我的</h2>
        <div className="desc">账号信息与系统信息</div>
      </div>

      {!user ? (
        <Empty message="未获取到用户信息，请重新登录" />
      ) : (
        <>
          <div className="grid-2">
            {/* 用户信息卡片 */}
            <Card title="个人信息" icon={<UserCircle size={16} className="ico" />}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 18 }}>
                <AvatarText text={initial} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{u.name || '未命名用户'}</div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                    ID: {u.id || '—'}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <InfoRow icon={<Phone size={15} />} label="手机号" value={u.phone || '—'} />
                <InfoRow
                  icon={<ShieldCheck size={15} />}
                  label="角色"
                  value={<Badge tone={roleTone(u.role)}>{roleLabel}</Badge>}
                />
                <InfoRow
                  icon={<CalendarDays size={15} />}
                  label="注册时间"
                  value={fmtDate(u.created_at)}
                />
              </div>

              <div style={{ marginTop: 20 }}>
                <button className="btn btn--ghost" onClick={handleLogout}>
                  <LogOut size={15} /> 退出登录
                </button>
              </div>
            </Card>

            {/* 系统信息卡片（诚实标注） */}
            <Card title="系统信息" icon={<Info size={16} className="ico" />}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <InfoRow label="系统版本" value={<span className="mono">v1.10.0</span>} />
                <InfoRow label="平台" value="索克家居 · i-home.life" />
                <InfoRow label="备案号" value="滇ICP备2026015233号-2" />
                <div className="dim" style={{ fontSize: 12, marginTop: 4 }}>
                  本页面展示账号与系统基础信息，业务数据请前往对应模块查看。
                </div>
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

/* 角色 → Badge 色调（防御性兜底） */
function roleTone(role) {
  switch (role) {
    case 'admin':
      return 'violet'
    case 'designer':
      return 'sky'
    case 'worker':
      return 'amber'
    case 'homeowner':
      return 'green'
    default:
      return undefined
  }
}

/* 首字母头像 */
function AvatarText({ text }) {
  return (
    <span
      style={{
        width: 56,
        height: 56,
        minWidth: 56,
        borderRadius: '50%',
        background: 'var(--bg-elev-2)',
        border: '1px solid var(--border-strong)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 24,
        fontWeight: 600,
        color: 'var(--accent-text)',
      }}
    >
      {text}
    </span>
  )
}

/* 信息行：图标 + 标签 + 值 */
function InfoRow({ icon, label, value }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13 }}>
      <span style={{ color: 'var(--text-dim)', display: 'inline-flex' }}>{icon}</span>
      <span style={{ color: 'var(--text-sub)', minWidth: 64 }}>{label}</span>
      <span style={{ color: 'var(--text)', wordBreak: 'break-all' }}>{value}</span>
    </div>
  )
}
