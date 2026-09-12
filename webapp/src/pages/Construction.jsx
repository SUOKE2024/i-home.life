import React, { useEffect, useState, useCallback } from 'react'
import { Plus, Hammer, X } from 'lucide-react'
import { Card, Badge, Stat, Spinner, Empty, ErrorBox } from '../components/ui'
import GaussianViewer from '../components/GaussianViewer'
import {
  listProjects, getConstructionTasks, createConstructionTask,
  getConstructionSnapshots, uploadConstructionSnapshot,
} from '../lib/api'
import { useApp } from '../lib/store'

// 任务状态 → 徽章颜色/文案映射
const STATUS_META = {
  pending: { tone: 'amber', label: '待执行' },
  in_progress: { tone: 'sky', label: '进行中' },
  completed: { tone: 'green', label: '已完成' },
  delayed: { tone: 'red', label: '已延期' },
  cancelled: { tone: 'gray', label: '已取消' },
}

// 施工阶段（phase）→ 中文文案（对齐后端 TaskResponse.phase 枚举）
const PHASE_META = {
  preparation: { label: '准备阶段' },
  demolition: { label: '拆改阶段' },
  water_electricity: { label: '水电阶段' },
  waterproof: { label: '水电防水' },
  masonry: { label: '泥瓦阶段' },
  carpentry: { label: '木工阶段' },
  painting: { label: '油漆阶段' },
  installation: { label: '安装阶段' },
  inspection: { label: '验收阶段' },
}

// 施工存档阶段（stage）→ 中文文案（对齐后端 construction_snapshot_service.STAGES，P3）
const STAGE_META = {
  preparation: '准备阶段',
  demolition: '拆改阶段',
  water_electricity: '水电阶段',
  electrical: '电气阶段',
  waterproof: '防水阶段',
  masonry: '泥瓦阶段',
  mep: '机电阶段',
  carpentry: '木工阶段',
  painting: '油漆阶段',
  installation: '安装阶段',
  completion: '竣工阶段',
  inspection: '验收阶段',
}

// 防御性日期格式化（非法值兜底为 —）
function fmtDate(v) {
  if (!v) return '—'
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('zh-CN')
}

// 本地今日日期字符串 YYYY-MM-DD（用于逾期判断）
function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// 逾期：截止日期早于今天且未完成
function isOverdue(task) {
  if (!task.end_date || task.status === 'completed') return false
  return String(task.end_date).slice(0, 10) < todayStr()
}

export default function ConstructionPage() {
  const { toast } = useApp()
  const [projects, setProjects] = useState([])
  const [projectsLoading, setProjectsLoading] = useState(true)
  const [projectsError, setProjectsError] = useState(null)
  const [projectId, setProjectId] = useState('')
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false) // 新建任务内联表单显隐
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({ title: '', task_type: '', assignee: '', due_date: '' })

  // P3 施工 3DGS 数字存档：时间线 + 上传 + 回看
  const [snapshots, setSnapshots] = useState([])
  const [snapLoading, setSnapLoading] = useState(false)
  const [snapError, setSnapError] = useState(null)
  const [snapStage, setSnapStage] = useState('masonry')
  const [snapRoom, setSnapRoom] = useState('')
  const [snapFile, setSnapFile] = useState(null)
  const [snapUploading, setSnapUploading] = useState(false)
  const [viewingSnapshot, setViewingSnapshot] = useState(null) // 3DGS 回看弹窗

  // 加载可选项目（下拉选项）
  const loadProjects = useCallback(async () => {
    setProjectsLoading(true)
    setProjectsError(null)
    const r = await listProjects()
    if (r.isSuccess) {
      setProjects(Array.isArray(r.data) ? r.data : [])
    } else {
      setProjectsError(r.error || '加载项目列表失败')
    }
    setProjectsLoading(false)
  }, [])

  useEffect(() => {
    loadProjects()
  }, [loadProjects])

  // 加载选中项目的施工任务
  const loadTasks = useCallback(async (id) => {
    setLoading(true)
    setError(null)
    const r = await getConstructionTasks(id)
    if (r.isSuccess) {
      setTasks(Array.isArray(r.data) ? r.data : [])
    } else {
      setError(r.error || '加载施工任务失败')
    }
    setLoading(false)
  }, [])

  // P3：加载施工 3DGS 存档时间线
  const loadSnapshots = useCallback(async (id) => {
    setSnapLoading(true)
    setSnapError(null)
    const r = await getConstructionSnapshots(id)
    if (r.isSuccess) {
      setSnapshots(Array.isArray(r.data) ? r.data : [])
    } else {
      setSnapError(r.error || '加载施工存档失败')
    }
    setSnapLoading(false)
  }, [])

  // 项目切换时重新加载任务 + 存档
  useEffect(() => {
    if (projectId) {
      loadTasks(projectId)
      loadSnapshots(projectId)
    } else {
      setTasks([])
      setSnapshots([])
    }
  }, [projectId, loadTasks, loadSnapshots])

  const currentProject = projects.find((p) => p.id === projectId)

  // P3：上传施工节点 3DGS 快照
  const submitSnapshot = async () => {
    if (!projectId || !snapFile || snapUploading) return
    setSnapUploading(true)
    const r = await uploadConstructionSnapshot(projectId, snapStage, snapFile, {
      roomName: snapRoom.trim() || undefined,
    })
    setSnapUploading(false)
    if (r.isSuccess) {
      toast('施工存档上传成功', 'success')
      setSnapRoom('')
      setSnapFile(null)
      loadSnapshots(projectId)
    } else {
      toast(r.error || '上传失败', 'error')
    }
  }

  // 提交新建任务，成功后刷新任务列表
  const submit = async (e) => {
    e.preventDefault()
    if (!projectId) {
      toast('请先选择项目', 'error')
      return
    }
    if (!form.title.trim()) {
      toast('请输入任务标题', 'error')
      return
    }
    setSubmitting(true)
    const r = await createConstructionTask(projectId, {
      name: form.title.trim(),
      phase: form.task_type.trim() || undefined,
      assigned_to: form.assignee.trim() || undefined,
      end_date: form.due_date || undefined,
    })
    setSubmitting(false)
    if (r.isSuccess) {
      toast('任务创建成功', 'success')
      setShowForm(false)
      setForm({ title: '', task_type: '', assignee: '', due_date: '' })
      loadTasks(projectId)
    } else {
      toast(r.error || '创建任务失败', 'error')
    }
  }

  // 统计：总数 / 进行中 / 已完成 / 逾期数
  const total = tasks.length
  const inProgress = tasks.filter((t) => t.status === 'in_progress').length
  const completed = tasks.filter((t) => t.status === 'completed').length
  const overdue = tasks.filter(isOverdue).length

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>施工管理</h2>
          <div className="desc">按项目跟踪施工任务与进度</div>
        </div>
        <button
          className="btn btn--primary"
          disabled={!projectId}
          title={!projectId ? '请先选择项目' : undefined}
          onClick={() => setShowForm((v) => !v)}
        >
          <Plus size={15} /> 新建任务
        </button>
      </div>

      {/* 项目选择 */}
      <div className="toolbar">
        {projectsLoading ? (
          <Spinner label="加载项目列表…" />
        ) : projectsError ? (
          <ErrorBox message={projectsError} onRetry={loadProjects} />
        ) : (
          <select className="select" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
            <option value="">请选择项目</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name || p.id}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* 新建任务内联表单 */}
      {showForm && projectId && (
        <Card
          title="新建施工任务"
          sub={`项目：${currentProject?.name || projectId}`}
          icon={<Plus size={15} className="ico" />}
          style={{ marginBottom: 16 }}
        >
          <form
            onSubmit={submit}
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}
          >
            <div className="field">
              <label>任务标题 *</label>
              <input
                className="input"
                value={form.title}
                maxLength={60}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="如：水电改造"
              />
            </div>
            <div className="field">
              <label>任务类型</label>
              <input
                className="input"
                value={form.task_type}
                maxLength={40}
                onChange={(e) => setForm({ ...form, task_type: e.target.value })}
                placeholder="如：拆除 / 泥瓦"
              />
            </div>
            <div className="field">
              <label>负责人</label>
              <input
                className="input"
                value={form.assignee}
                maxLength={40}
                onChange={(e) => setForm({ ...form, assignee: e.target.value })}
                placeholder="负责人姓名"
              />
            </div>
            <div className="field">
              <label>截止日期</label>
              <input
                className="input"
                type="date"
                value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
              <button className="btn btn--primary" type="submit" disabled={submitting}>
                {submitting ? '创建中…' : '创建'}
              </button>
              <button className="btn btn--ghost" type="button" onClick={() => setShowForm(false)}>
                取消
              </button>
            </div>
          </form>
        </Card>
      )}

      {/* 四态：未选项目 / 加载中 / 错误 / 数据 */}
      {!projectId ? (
        <Empty message="请先选择项目" />
      ) : loading ? (
        <Spinner label="加载施工任务…" />
      ) : error ? (
        <ErrorBox message={error} onRetry={() => loadTasks(projectId)} />
      ) : (
        <>
          {/* 统计行 */}
          <div className="stat-grid">
            <Stat label="任务总数" value={total} />
            <Stat label="进行中" value={inProgress} tone="sky" />
            <Stat label="已完成" value={completed} tone="green" />
            <Stat label="逾期任务" value={overdue} tone={overdue > 0 ? 'red' : undefined} hint="截止日期已过且未完成" />
          </div>

          {/* 任务表格 */}
          <Card title="任务列表" sub={`${total} 项`} icon={<Hammer size={15} className="ico" />}>
            {tasks.length === 0 ? (
              <Empty message="暂无施工任务" />
            ) : (
              <div className="table-wrap">
                <table className="table">
                <thead>
                  <tr>
                    <th>标题</th>
                    <th>类型</th>
                    <th>负责人</th>
                    <th>计划日期</th>
                    <th>截止日期</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((t) => {
                    const meta = STATUS_META[t.status] || {}
                    const phaseMeta = PHASE_META[t.phase] || {}
                    return (
                      <tr key={t.id ?? t.name}>
                        <td>{t.name || '—'}</td>
                        <td>{phaseMeta.label || t.phase || '—'}</td>
                        <td>{t.assigned_to || '—'}</td>
                        <td>{fmtDate(t.start_date)}</td>
                        <td>
                          {fmtDate(t.end_date)}
                          {isOverdue(t) && (
                            <span style={{ marginLeft: 6 }}>
                              <Badge tone="red">逾期</Badge>
                            </span>
                          )}
                        </td>
                        <td>
                          {meta.tone ? <Badge tone={meta.tone}>{meta.label}</Badge> : <Badge>{t.status || '—'}</Badge>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* P3 施工 3DGS 数字存档 */}
          <Card title="施工 3DGS 存档" sub={`${snapshots.length} 个节点快照`} icon={<Hammer size={15} className="ico" />} style={{ marginTop: 16 }}>
            {/* 上传表单 */}
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 10 }}>
              <select className="select" value={snapStage} onChange={(e) => setSnapStage(e.target.value)} style={{ width: 130 }}>
                {Object.entries(STAGE_META).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
              <input
                className="input"
                style={{ width: 160 }}
                placeholder="房间名（可选）"
                value={snapRoom}
                onChange={(e) => setSnapRoom(e.target.value)}
              />
              <input
                type="file"
                accept=".spz,.ply,.glb"
                onChange={(e) => setSnapFile(e.target.files?.[0] || null)}
              />
              <button className="btn btn--primary" disabled={!snapFile || snapUploading} onClick={submitSnapshot}>
                {snapUploading ? '上传中…' : '上传快照'}
              </button>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 14 }}>
              施工节点实景扫描存档（.spz/.ply/.glb），形成施工时间线，支持竣工验收比对与业主远程查看。
            </div>

            {/* 时间线 */}
            {snapLoading ? (
              <Spinner label="加载施工存档…" />
            ) : snapError ? (
              <ErrorBox message={snapError} onRetry={() => loadSnapshots(projectId)} />
            ) : snapshots.length === 0 ? (
              <Empty message="暂无施工存档" />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {snapshots.map((s) => (
                  <div
                    key={s.id}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
                      border: '1px solid var(--border)', borderRadius: 8,
                    }}
                  >
                    <Badge tone="sky">{STAGE_META[s.stage] || s.stage}</Badge>
                    <span style={{ flex: 1, fontSize: 13 }}>{s.room_name || '未标注房间'}</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text-dim)' }}>{fmtDate(s.captured_at)}</span>
                    {s.notes && <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{s.notes}</span>}
                    <button className="btn btn--ghost" onClick={() => setViewingSnapshot(s)}>回看 3D</button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}

      {/* 3DGS 回看弹窗 */}
      {viewingSnapshot && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(10,10,12,0.92)',
            display: 'flex', flexDirection: 'column',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', padding: '10px 16px', color: '#fff' }}>
            <b style={{ flex: 1 }}>
              施工存档回看 · {STAGE_META[viewingSnapshot.stage] || viewingSnapshot.stage}
              {viewingSnapshot.room_name ? ` · ${viewingSnapshot.room_name}` : ''}
            </b>
            <button
              className="icon-btn"
              style={{ color: '#fff', background: 'rgba(255,255,255,0.12)' }}
              onClick={() => setViewingSnapshot(null)}
              title="关闭"
            >
              <X size={18} />
            </button>
          </div>
          <div style={{ flex: 1 }}>
            <GaussianViewer
              splatUrl={viewingSnapshot.splat_url}
              onFallback={() => setViewingSnapshot(null)}
            />
          </div>
        </div>
      )}
    </div>
  )
}
