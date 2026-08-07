import React, { useEffect, useState, useCallback } from 'react'
import { Plus, Hammer } from 'lucide-react'
import { Card, Badge, Stat, Spinner, Empty, ErrorBox } from '../components/ui'
import { listProjects, getConstructionTasks, createConstructionTask } from '../lib/api'
import { useApp } from '../lib/store'

// 任务状态 → 徽章颜色/文案映射
const STATUS_META = {
  pending: { tone: 'amber', label: '待执行' },
  in_progress: { tone: 'sky', label: '进行中' },
  completed: { tone: 'green', label: '已完成' },
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
  if (!task.due_date || task.status === 'completed') return false
  return String(task.due_date).slice(0, 10) < todayStr()
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

  // 项目切换时重新加载任务
  useEffect(() => {
    if (projectId) {
      loadTasks(projectId)
    } else {
      setTasks([])
    }
  }, [projectId, loadTasks])

  const currentProject = projects.find((p) => p.id === projectId)

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
      title: form.title.trim(),
      task_type: form.task_type.trim() || undefined,
      assignee: form.assignee.trim() || undefined,
      due_date: form.due_date || undefined,
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
                    return (
                      <tr key={t.id ?? t.title}>
                        <td>{t.title || '—'}</td>
                        <td>{t.task_type || '—'}</td>
                        <td>{t.assignee || '—'}</td>
                        <td>{fmtDate(t.planned_date)}</td>
                        <td>
                          {fmtDate(t.due_date)}
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
            )}
          </Card>
        </>
      )}
    </div>
  )
}
