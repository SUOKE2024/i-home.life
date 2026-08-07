import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderKanban, Wallet, TrendingUp, HardHat, ShieldCheck, Bot, ArrowRight } from 'lucide-react'
import { Card, Stat, Badge, Spinner, Empty, ErrorBox } from '../components/ui'
import { getDashboardOverview, listProjects } from '../lib/api'

const STATUS_MAP = {
  draft: ['草稿', 'amber'],
  in_progress: ['进行中', 'sky'],
  completed: ['已完成', 'green'],
}

const QUICK_LINKS = [
  { to: '/projects', label: '项目管理', icon: FolderKanban },
  { to: '/budget', label: '预算管理', icon: Wallet },
  { to: '/construction', label: '施工管理', icon: HardHat },
  { to: '/quality', label: '质检验收', icon: ShieldCheck },
  { to: '/ai', label: 'AI 管家', icon: Bot },
]

export default function DashboardPage() {
  const nav = useNavigate()
  const [overview, setOverview] = useState(null)
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    const [ov, pr] = await Promise.all([getDashboardOverview(), listProjects()])
    if (!ov.isSuccess) {
      setError(ov.error || '仪表盘加载失败')
      setLoading(false)
      return
    }
    setOverview(ov.data || {})
    setProjects(pr.isSuccess ? (pr.data || []) : [])
    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) return <Spinner label="正在加载看板…" />
  if (error) return <ErrorBox message={error} onRetry={load} />

  const p = overview.projects || {}
  const b = overview.budget || {}

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>聚合看板</h2>
          <div className="desc">全链路家装项目总览 · 设计→预算→采购→施工→质检→结算</div>
        </div>
      </div>

      {/* 核心指标 */}
      <div className="stat-grid">
        <Card>
          <Stat label="项目总数" value={p.total ?? 0} hint={`草稿 ${p.draft ?? 0} · 进行中 ${p.in_progress ?? 0} · 已完成 ${p.completed ?? 0}`} tone="amber" />
        </Card>
        <Card>
          <Stat label="预算预估" value={`¥${fmtNum(b.total_estimated)}`} hint="全部项目预算合计" tone="sky" />
        </Card>
        <Card>
          <Stat label="实际支出" value={`¥${fmtNum(b.total_actual)}`} hint="已发生成本合计" />
        </Card>
        <Card>
          <Stat label="预算执行率" value={`${Math.round((b.utilization ?? 0) * 100)}%`} hint="实际 / 预估" tone={b.utilization > 1 ? 'red' : 'green'} />
        </Card>
      </div>

      <div className="grid-2">
        {/* 最近项目 */}
        <Card title="最近项目" icon={<FolderKanban size={16} className="ico" />} sub={`${projects.length} 个`} actions={
          <button className="btn btn--ghost" onClick={() => nav('/projects')} style={{ padding: '4px 10px', fontSize: 12 }}>
            全部 <ArrowRight size={12} />
          </button>
        }>
          {projects.length === 0 ? (
            <Empty message="暂无项目，去「项目管理」创建第一个项目" />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {projects.slice(0, 6).map((pr) => {
                const st = STATUS_MAP[pr.status] || ['未知', null]
                return (
                  <div key={pr.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {pr.name || '未命名项目'}
                      </div>
                      <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                        {(pr.total_area != null ? `${pr.total_area}㎡` : '—')}
                        {pr.address ? ` · ${pr.address}` : ''}
                      </div>
                    </div>
                    {st[1] && <Badge tone={st[1]}>{st[0]}</Badge>}
                  </div>
                )
              })}
            </div>
          )}
        </Card>

        {/* 快捷入口 */}
        <Card title="快捷入口" icon={<TrendingUp size={16} className="ico" />} sub="QUICK ACCESS">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10 }}>
            {QUICK_LINKS.map(({ to, label, icon: Icon }) => (
              <button
                key={to}
                className="btn btn--ghost"
                onClick={() => nav(to)}
                style={{ flexDirection: 'column', gap: 8, padding: '16px 10px', height: 'auto' }}
              >
                <Icon size={22} className="amber-text" />
                <span>{label}</span>
              </button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}

function fmtNum(v) {
  const n = Number(v || 0)
  return Number.isFinite(n) ? n.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) : '0'
}
