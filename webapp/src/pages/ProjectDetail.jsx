import React, { useEffect, useState, useCallback } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, MapPin, Ruler, Home, Calendar, Phone } from 'lucide-react'
import { Card, Badge, Stat, Spinner, Empty, ErrorBox } from '../components/ui'
import { getProject, getProjectTimeline } from '../lib/api'

// 项目状态 → 徽章映射（与 Projects.jsx 对齐）
const STATUS_META = {
  draft: { tone: 'amber', label: '草稿' },
  in_progress: { tone: 'sky', label: '进行中' },
  active: { tone: 'sky', label: '进行中' },
  completed: { tone: 'green', label: '已完成' },
  cancelled: { tone: 'gray', label: '已取消' },
}

// 阶段 phase → 中文文案
const PHASE_META = {
  initiation: '项目立项',
  design: '方案设计',
  budget: '预算规划',
  procurement: '物料采购',
  construction: '施工管理',
  quality: '质量验收',
  settlement: '结算交付',
  completed: '已完成',
  cancelled: '已取消',
}

// 阶段状态 → 文案/色相
const STAGE_STATUS = {
  completed: { label: '已完成', tone: 'green' },
  active: { label: '进行中', tone: 'sky' },
  pending: { label: '待启动', tone: 'gray' },
}

// 防御性日期格式化（非法值兜底为 —）
function fmtDate(v) {
  if (!v) return '—'
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('zh-CN')
}

// 各业务模块快捷入口（详情页汇总 → 对应页处理明细）
const MODULE_LINKS = [
  { to: '/budget', label: '预算', icon: '💰', desc: '预算明细与偏差' },
  { to: '/procurement', label: '采购', icon: '📦', desc: '采购订单与物流' },
  { to: '/construction', label: '施工', icon: '🔨', desc: '任务与进度' },
  { to: '/quality', label: '质检', icon: '✅', desc: '质量问题与整改' },
  { to: '/settlement', label: '结算', icon: '🏁', desc: '结算与里程碑' },
  { to: '/smart-home', label: '智能家居', icon: '💡', desc: '方案与设备' },
]

export default function ProjectDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [project, setProject] = useState(null)
  const [timeline, setTimeline] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    const [pr, tl] = await Promise.all([getProject(id), getProjectTimeline(id)])
    if (!pr.isSuccess) {
      setError(pr.error || '加载项目详情失败')
    } else {
      setProject(pr.data)
      setTimeline(tl.isSuccess ? tl.data : null)
    }
    setLoading(false)
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <Spinner label="加载项目详情…" />
  if (error) return <ErrorBox message={error} onRetry={load} />
  if (!project) return <Empty message="项目不存在或已删除" />

  const st = STATUS_META[project.status] || {}
  const area = Number(project.total_area)
  const stages = timeline?.stages || []
  const stats = timeline?.stats || {}
  const phaseLabel = PHASE_META[project.phase] || project.phase || '—'

  return (
    <div>
      <div className="page-head">
        <div>
          <Link to="/projects" className="back-link" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12.5, color: 'var(--text-dim)' }}>
            <ArrowLeft size={14} /> 返回项目列表
          </Link>
          <h2 style={{ marginTop: 4 }}>{project.name || '未命名项目'}</h2>
          <div className="desc">
            <span style={{ marginRight: 10 }}>
              {st.tone ? <Badge tone={st.tone}>{st.label}</Badge> : <Badge>{project.status || '未知'}</Badge>}
            </span>
            阶段：{phaseLabel}
            {project.house_type && <span style={{ marginLeft: 10 }}>户型：{project.house_type}</span>}
          </div>
        </div>
      </div>

      {/* 基本信息 */}
      <Card title="项目信息" sub="GET /api/projects/:id" icon={<Home size={15} className="ico" />} style={{ marginBottom: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10, fontSize: 13 }}>
          <div className="mono" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <MapPin size={14} className="ico" /> {project.address || '—'}
          </div>
          <div className="mono" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Ruler size={14} className="ico" /> {area > 0 ? `${area} ㎡` : '—'}
          </div>
          <div className="mono" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Calendar size={14} className="ico" /> 创建于 {fmtDate(project.created_at)}
          </div>
          {project.contact_name && (
            <div className="mono" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Phone size={14} className="ico" /> {project.contact_name}
              {project.contact_phone ? ` · ${project.contact_phone}` : ''}
            </div>
          )}
        </div>
        {project.description && (
          <div className="dim" style={{ marginTop: 10, fontSize: 12.5 }}>{project.description}</div>
        )}
      </Card>

      {/* 关键统计 */}
      <div className="stat-grid">
        <Stat label="当前阶段" value={phaseLabel} />
        <Stat label="全链路进度" value={stats.progress_pct != null ? `${stats.progress_pct}%` : '—'} tone="sky" />
        <Stat label="施工任务" value={stats.construction_tasks ?? '—'} tone="amber" />
        <Stat label="预算" value={stats.has_budget ? '已生成' : '未生成'} tone={stats.has_budget ? 'green' : undefined} />
        <Stat label="结算" value={stats.has_settlement ? '已生成' : '未生成'} tone={stats.has_settlement ? 'green' : undefined} />
      </div>

      {/* 全链路 7 阶段 timeline */}
      <Card
        title="全链路进度"
        sub={timeline?.project_phase ? `phase: ${timeline.project_phase}` : undefined}
        icon={<Home size={15} className="ico" />}
        style={{ marginTop: 16 }}
      >
        {stages.length === 0 ? (
          <Empty message="暂无阶段进度数据" />
        ) : (
          <>
            {/* 进度条 */}
            <div style={{ marginBottom: 14 }}>
              <div
                style={{
                  height: 8, borderRadius: 6, background: 'var(--bg-dim)',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%', width: `${Math.min(100, stats.progress_pct ?? 0)}%`,
                    background: 'linear-gradient(90deg, var(--accent), var(--green))',
                    borderRadius: 6, transition: 'width .4s ease',
                  }}
                />
              </div>
              <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 6 }}>
                已完成 {stats.completed_stages ?? 0} / {stats.total_stages ?? 7} 阶段
                {stats.active_stage ? ` · 当前第 ${stats.active_stage} 阶段` : ''}
              </div>
            </div>
            {/* 阶段节点 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 8 }}>
              {stages.map((s) => {
                const ss = STAGE_STATUS[s.status] || { label: s.status || '—', tone: 'gray' }
                return (
                  <div
                    key={s.id}
                    style={{
                      padding: '10px 12px', borderRadius: 10,
                      border: `1px solid var(--${ss.tone})`,
                      background: s.status === 'active' ? 'var(--sky-dim)' : 'var(--card-bg)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 16 }}>{s.icon}</span>
                      <b style={{ flex: 1, fontWeight: 600, fontSize: 13 }}>{s.name}</b>
                      <Badge tone={ss.tone}>{ss.label}</Badge>
                    </div>
                    <div className="dim" style={{ fontSize: 11, marginTop: 4 }}>{s.substeps}</div>
                  </div>
                )
              })}
            </div>
          </>
        )}
      </Card>

      {/* 模块快捷入口 */}
      <Card title="业务模块" sub="点击进入对应管理页" style={{ marginTop: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 8 }}>
          {MODULE_LINKS.map((m) => (
            <Link
              key={m.to}
              to={m.to}
              className="btn btn--ghost"
              style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 2, height: 'auto', padding: '10px 12px' }}
            >
              <span style={{ fontSize: 15 }}>{m.icon} {m.label}</span>
              <span className="dim" style={{ fontSize: 11 }}>{m.desc}</span>
            </Link>
          ))}
        </div>
        <div style={{ marginTop: 14, display: 'flex', gap: 10 }}>
          <button className="btn btn--ghost" onClick={() => navigate('/ai', { state: { projectId: id } })}>
            🤖 问 AI 管家项目进度
          </button>
          <Link to="/diagnostics" className="btn btn--ghost">🩺 全链路诊断</Link>
        </div>
      </Card>
    </div>
  )
}
