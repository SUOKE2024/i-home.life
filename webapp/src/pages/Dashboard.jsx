import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderKanban, Wallet, HardHat, ShieldCheck, Bot, Home, BellRing } from 'lucide-react'
import { Card, Badge, Spinner, Empty, ErrorBox } from '../components/ui'
import A2UICard from '../components/A2UICard'
import {
  getDashboardOverview,
  listProjects,
  getFloorplans,
  getFloorplan,
  getProgressAlerts,
  getMilestones,
  getFeedCards,
} from '../lib/api'

const STATUS_MAP = {
  draft: ['草稿', 'amber'],
  in_progress: ['进行中', 'sky'],
  completed: ['已完成', 'green'],
}

// 生命线 7 节点
const LIFELINE = ['量房', '设计', '预算', '施工', '质检', '结算', '入住']

// 健康分扣分（按未解决预警严重度，前端估算）
const SEVERITY_PENALTY = { critical: 28, high: 14, medium: 6, low: 2 }

// 阶段 → 色相
const SEVERITY_TONE = { critical: 'red', high: 'amber', medium: 'amber', low: 'green' }

// 房间状态 → 色相 / 文案（空间即导航）
const ROOM_TONE = { completed: 'green', in_progress: 'amber', attention: 'red', not_started: 'sky' }
const ROOM_LABEL = { completed: '已完成', in_progress: '施工中', attention: '需关注', not_started: '未开始' }

// 户型 data JSON → rooms 列表
const roomsOf = (plan) => {
  if (!plan || typeof plan.data !== 'string' || !plan.data) return []
  try {
    const p = JSON.parse(plan.data)
    return Array.isArray(p.rooms) ? p.rooms : []
  } catch {
    return []
  }
}
const roomStatusOf = (plan) =>
  plan && plan.room_status && typeof plan.room_status === 'object' ? plan.room_status : {}

export default function DashboardPage() {
  const nav = useNavigate()
  const [overview, setOverview] = useState(null)
  const [projects, setProjects] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [floorplans, setFloorplans] = useState([])
  const [alerts, setAlerts] = useState([])
  const [milestones, setMilestones] = useState([])
  const [feedCards, setFeedCards] = useState([])
  const [activePlan, setActivePlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async (projectId) => {
    setLoading(true)
    setError(null)
    const [ov, pr] = await Promise.all([getDashboardOverview(), listProjects()])
    if (!ov.isSuccess) {
      setError(ov.error || '仪表盘加载失败')
      setLoading(false)
      return
    }
    setOverview(ov.data || {})
    const list = pr.isSuccess && Array.isArray(pr.data) ? pr.data : []
    setProjects(list)
    const target =
      projectId ||
      (list.find((p) => p.status === 'in_progress')?.id) ||
      list[0]?.id ||
      ''
    setSelectedId(target)
    if (target) {
      const [fp, al, ms, feed] = await Promise.all([
        getFloorplans(target),
        getProgressAlerts(target),
        getMilestones(target),
        getFeedCards(target),
      ])
      const plans = fp.isSuccess && Array.isArray(fp.data) ? fp.data : []
      setFloorplans(plans)
      setAlerts(al.isSuccess && Array.isArray(al.data) ? al.data : [])
      setMilestones(ms.isSuccess && Array.isArray(ms.data) ? ms.data : [])
      setFeedCards(
        feed.isSuccess && feed.data && Array.isArray(feed.data.cards) ? feed.data.cards : []
      )
      // 空间即导航：拉取激活户型详情（data JSON 含 rooms 几何）
      const active = plans.find((x) => x.is_active) || plans[0]
      if (active) {
        const det = await getFloorplan(active.id)
        setActivePlan(det.isSuccess && det.data ? det.data : null)
      } else {
        setActivePlan(null)
      }
    } else {
      setFloorplans([])
      setAlerts([])
      setMilestones([])
      setFeedCards([])
      setActivePlan(null)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const switchProject = (id) => {
    if (!id) return
    setSelectedId(id)
    load(id)
  }

  if (loading) return <Spinner label="正在加载看板…" />
  if (error) return <ErrorBox message={error} onRetry={() => load(selectedId)} />

  const b = overview?.budget || {}
  const project = projects.find((x) => x.id === selectedId) || null
  const status = project?.status || 'draft'

  // 生命线节点推断（与移动端一致：项目状态 + 户型存在 + 里程碑完成度）
  const hasPlan = floorplans.length > 0
  const doneMs = milestones.filter((m) => m.actual_date).length
  const msRatio = milestones.length ? doneMs / milestones.length : 0
  const completed = status === 'completed'
  const inProgress = status === 'in_progress'
  const nodeDone = [
    hasPlan,
    hasPlan,
    inProgress || completed,
    inProgress || completed,
    completed || (inProgress && msRatio >= 0.6),
    completed || (inProgress && msRatio >= 0.9),
    completed,
  ]
  const currentIdx = nodeDone.indexOf(false)

  // 健康分估算
  const unresolved = alerts.filter((a) => a.status !== 'resolved')
  const penalty = unresolved.reduce((s, a) => s + (SEVERITY_PENALTY[a.severity] ?? 6), 0)
  const health = Math.max(0, Math.min(100, Math.round(100 - penalty)))
  const healthTone = health >= 80 ? 'green' : health >= 50 ? 'amber' : 'red'

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>家的生命线</h2>
          <div className="desc">空间智能 × 时间叙事 · 进度由现有数据推断，仅供参考</div>
        </div>
        <select
          className="select"
          value={selectedId}
          onChange={(e) => switchProject(e.target.value)}
          style={{ width: 240 }}
        >
          {projects.map((pr) => (
            <option key={pr.id} value={pr.id}>
              {pr.name || pr.id}
            </option>
          ))}
        </select>
      </div>

      <div className="bento">
        {/* ── 左：当前项目 + 空间状态 ── */}
        <div className="b-col">
          <Card title="当前项目" icon={<FolderKanban size={16} className="ico" />}>
            {project ? (
              <div>
                <div style={{ fontSize: 15, fontWeight: 700 }}>{project.name || '未命名项目'}</div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                  {(project.total_area != null ? `${project.total_area} ㎡` : '—')}
                  {project.address ? ` · ${project.address}` : ''}
                </div>
                <div style={{ marginTop: 8 }}>
                  {STATUS_MAP[status] && <Badge tone={STATUS_MAP[status][1]}>{STATUS_MAP[status][0]}</Badge>}
                </div>
              </div>
            ) : (
              <Empty message="暂无项目，去「项目管理」创建" />
            )}
          </Card>

          <Card title="空间状态" icon={<Home size={16} className="ico" />} sub="户型方案 · 逐房间状态">
            {floorplans.length === 0 ? (
              <Empty message="暂无户型方案，可让 AI 管家协助量房" />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {activePlan && (
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>
                      户型图{' '}
                      <span style={{ fontWeight: 400, color: 'var(--text-dim)', fontSize: 10 }}>
                        逐房间状态 · 按现有数据标注
                      </span>
                    </div>
                    {(() => {
                      const rsm = roomStatusOf(activePlan)
                      const rooms = roomsOf(activePlan)
                      const tiles = rooms.length
                        ? rooms
                        : Object.keys(rsm).map((k) => ({ name: k }))
                      return (
                        <>
                          <div
                            style={{
                              display: 'grid',
                              gridTemplateColumns: 'repeat(auto-fill, minmax(84px, 1fr))',
                              gap: 6,
                              marginTop: 8,
                            }}
                          >
                            {tiles.slice(0, 9).map((r, i) => {
                              const st = rsm[r.name] || r.status
                              const tone = ROOM_TONE[st] || 'sky'
                              return (
                                <div
                                  key={`${r.name}-${i}`}
                                  style={{
                                    padding: '6px 8px',
                                    borderRadius: 9,
                                    border: `1px solid var(--${tone})`,
                                    background: `var(--${tone}-dim)`,
                                    fontSize: 11,
                                  }}
                                >
                                  <div style={{ fontWeight: 700, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {r.name || '房间'}
                                  </div>
                                  <div style={{ color: `var(--${tone})`, fontSize: 10, marginTop: 1 }}>
                                    {r.area != null ? `${r.area} ㎡ · ` : ''}
                                    {ROOM_LABEL[st] || st || '待标注'}
                                  </div>
                                </div>
                              )
                            })}
                          </div>
                          {Object.keys(rsm).length === 0 && (
                            <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 6 }}>
                              房间施工状态暂未标注，可在 AI 管家对话中更新
                            </div>
                          )}
                        </>
                      )
                    })()}
                  </div>
                )}
                {floorplans.slice(0, 4).map((fp) => (
                  <div key={fp.id}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12.5 }}>
                      <span className="ico" style={{ color: 'var(--accent)' }}>
                        <Home size={15} />
                      </span>
                      <b style={{ flex: 1, fontWeight: 600 }}>{fp.name || '户型'}</b>
                      <span className="mono" style={{ color: 'var(--text-dim)', fontSize: 11 }}>
                        {fp.room_count ?? 0} 间 · {fp.total_area ?? 0} ㎡
                      </span>
                      {fp.is_active && <Badge tone="green">当前</Badge>}
                    </div>
                    {(() => {
                      const rsm = roomStatusOf(fp)
                      if (!fp.is_active && Object.keys(rsm).length > 0) {
                        return (
                          <div
                            style={{
                              fontSize: 10.5,
                              color: 'var(--text-dim)',
                              marginLeft: 25,
                              marginTop: 2,
                            }}
                          >
                            {Object.entries(rsm)
                              .slice(0, 4)
                              .map(([k, v]) => `${k}·${ROOM_LABEL[v] || v}`)
                              .join('  ')}
                          </div>
                        )
                      }
                      return null
                    })()}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* ── 中：生命线 + 管家主动卡片流 ── */}
        <div className="b-col">
          <Card title="家的生命线" icon={<Wallet size={16} className="ico" />} sub="阶段概览">
            <div className="lifeline">
              {LIFELINE.map((label, i) => {
                const isDone = nodeDone[i]
                const isNow = i === currentIdx
                return (
                  <div key={label} className={`lifeline-node ${isDone ? 'done' : ''} ${isNow ? 'now' : ''}`}>
                    <span className="dot">{isDone ? '✓' : i + 1}</span>
                    <span className="label">{label}</span>
                  </div>
                )
              })}
            </div>
            <div style={{ fontSize: 12, marginTop: 10 }}>
              {currentIdx >= 0 ? (
                <span style={{ color: 'var(--accent-text)', fontWeight: 700 }}>当前阶段 · {LIFELINE[currentIdx]}</span>
              ) : (
                <span style={{ color: 'var(--green)', fontWeight: 700 }}>全流程已完成，欢迎入住新家</span>
              )}
            </div>
          </Card>

          <Card title="管家主动卡片" icon={<BellRing size={16} className="ico" />} sub="A2UI · HEALTH OS">
            {feedCards.length === 0 ? (
              unresolved.length === 0 ? (
                <Empty message="暂无待处理事项，一切正常" />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {unresolved.slice(0, 5).map((a) => (
                    <div key={a.id} className="feed-card">
                      <div className="feed-icon" style={{ background: `var(--${SEVERITY_TONE[a.severity]}-dim)` }}>
                        <BellRing size={14} style={{ color: `var(--${SEVERITY_TONE[a.severity]})` }} />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Badge tone={SEVERITY_TONE[a.severity]}>
                            {{ critical: '严重', high: '高', low: '低' }[a.severity] || '中'}
                          </Badge>
                          {a.phase && <span className="mono" style={{ fontSize: 10, color: 'var(--text-dim)' }}>{a.phase}</span>}
                        </div>
                        <div style={{ fontSize: 12.5, marginTop: 4, lineHeight: 1.5 }}>{a.message}</div>
                        {a.suggestion && (
                          <div style={{ fontSize: 11.5, color: 'var(--text-sub)', marginTop: 2, lineHeight: 1.5 }}>
                            建议：{a.suggestion}
                          </div>
                        )}
                        <div className="feed-meta">
                          <span>进度预警 · Health OS 自动生成</span>
                          <button className="btn btn--ghost" style={{ padding: '4px 10px', fontSize: 11.5 }} onClick={() => nav('/ai')}>
                            问管家
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {feedCards.slice(0, 6).map((c, i) => (
                  <A2UICard key={c.id || i} card={c} onAction={() => nav('/ai')} />
                ))}
                <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>
                  卡片由项目现有数据按 A2UI 协议生成，仅供导航参考
                </div>
              </div>
            )}
          </Card>
        </div>

        {/* ── 右：健康 & 信任 ── */}
        <div className="b-col">
          <Card title="健康 & 信任" icon={<ShieldCheck size={16} className="ico" />} sub="ESTIMATED">
            <div className="health-row">
              <svg viewBox="0 0 72 72" width="72" height="72">
                <circle cx="36" cy="36" r="30" fill="none" stroke="var(--border)" strokeWidth="8" />
                <circle
                  cx="36" cy="36" r="30" fill="none"
                  stroke={`var(--${healthTone})`} strokeWidth="8" strokeLinecap="round"
                  strokeDasharray={2 * Math.PI * 30}
                  strokeDashoffset={2 * Math.PI * 30 * (1 - health / 100)}
                  transform="rotate(-90 36 36)"
                />
                <text x="36" y="40" textAnchor="middle" fontSize="16" fontWeight="800" fill="var(--text)">
                  {health}
                </text>
              </svg>
              <div style={{ flex: 1, fontSize: 12, color: 'var(--text-sub)', lineHeight: 1.6 }}>
                <b style={{ color: 'var(--text)', display: 'block', fontSize: 13 }}>施工健康分</b>
                由 {unresolved.length} 条未解决进度预警按严重度估算，仅供参考。
              </div>
            </div>
            <div className="kpi-row">
              <div>
                <div className="lab">预算执行率</div>
                <div className="val">
                  {Math.round((b.utilization ?? 0) * 100)}%<small> 实际/预估</small>
                </div>
              </div>
              <div>
                <div className="lab">待处理预警</div>
                <div className="val">{unresolved.length}</div>
              </div>
            </div>
          </Card>

          <Card title="资金节点" icon={<Wallet size={16} className="ico" />} sub="MILESTONES">
            {milestones.length === 0 ? (
              <Empty message="暂无里程碑记录" />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {milestones.slice(0, 6).map((m) => {
                  const done = !!m.actual_date
                  return (
                    <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12.5 }}>
                      <span className={`escrow-st ${done ? 'ok' : 'wait'}`}>{done ? '✓' : '…'}</span>
                      <b style={{ flex: 1, fontWeight: 500 }}>{m.name || m.milestone_code}</b>
                      {m.payment_ratio != null && (
                        <span className="mono" style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                          {Math.round(m.payment_ratio * 100)}%
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </Card>

          <Card title="快捷入口" icon={<Bot size={16} className="ico" />}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10 }}>
              {[
                { to: '/budget', label: '预算管理', icon: Wallet },
                { to: '/construction', label: '施工管理', icon: HardHat },
                { to: '/quality', label: '质检验收', icon: ShieldCheck },
                { to: '/ai', label: 'AI 管家', icon: Bot },
              ].map(({ to, label, icon: Icon }) => (
                <button key={to} className="feature-card" onClick={() => nav(to)}>
                  <Icon size={20} className="ico" />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
