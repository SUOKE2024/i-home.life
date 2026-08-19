import React, { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Plus, FolderOpen } from 'lucide-react'
import { Card, Badge, Stat, Spinner, Empty, ErrorBox } from '../components/ui'
import { listProjects, createProject } from '../lib/api'
import { useApp } from '../lib/store'

// 项目状态 → 徽章颜色/文案映射
const STATUS_META = {
  draft: { tone: 'amber', label: '草稿' },
  in_progress: { tone: 'sky', label: '进行中' },
  active: { tone: 'sky', label: '进行中' },
  completed: { tone: 'green', label: '已完成' },
  cancelled: { tone: 'gray', label: '已取消' },
}

// 防御性日期格式化（非法值兜底为 —）
function fmtDate(v) {
  if (!v) return '—'
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('zh-CN')
}

export default function ProjectsPage() {
  const { toast } = useApp()
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false) // 新建项目内联表单显隐
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({ name: '', total_area: '', address: '' })

  // 加载项目列表（错误重试复用）
  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const r = await listProjects()
    if (r.isSuccess) {
      setProjects(Array.isArray(r.data) ? r.data : [])
    } else {
      setError(r.error || '加载项目列表失败')
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // 提交新建项目，成功后刷新列表
  const submit = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) {
      toast('请输入项目名称', 'error')
      return
    }
    setSubmitting(true)
    const r = await createProject({
      name: form.name.trim(),
      total_area: Number(form.total_area) || undefined,
      address: form.address.trim() || undefined,
    })
    setSubmitting(false)
    if (r.isSuccess) {
      toast('项目创建成功', 'success')
      setShowForm(false)
      setForm({ name: '', total_area: '', address: '' })
      load()
    } else {
      toast(r.error || '创建项目失败', 'error')
    }
  }

  // 统计：总数 / 进行中 / 已完成 / 总面积
  const total = projects.length
  const inProgress = projects.filter((p) => p.status === 'in_progress').length
  const completed = projects.filter((p) => p.status === 'completed').length
  const totalArea = projects.reduce((s, p) => s + (Number(p.total_area) || 0), 0)

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>项目管理</h2>
          <div className="desc">项目全生命周期管理（草稿 / 进行中 / 已完成）</div>
        </div>
        <button className="btn btn--primary" onClick={() => setShowForm((v) => !v)}>
          <Plus size={15} /> 新建项目
        </button>
      </div>

      {/* 新建项目内联表单 */}
      {showForm && (
        <Card
          title="新建项目"
          sub="POST /api/projects"
          icon={<Plus size={15} className="ico" />}
          style={{ marginBottom: 16 }}
        >
          <form
            onSubmit={submit}
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}
          >
            <div className="field">
              <label>项目名称 *</label>
              <input
                className="input"
                value={form.name}
                maxLength={60}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="如：三居室整装"
              />
            </div>
            <div className="field">
              <label>面积（㎡）</label>
              <input
                className="input"
                type="number"
                min="0"
                value={form.total_area}
                onChange={(e) => setForm({ ...form, total_area: e.target.value })}
                placeholder="如：120"
              />
            </div>
            <div className="field">
              <label>地址</label>
              <input
                className="input"
                value={form.address}
                maxLength={120}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                placeholder="项目地址"
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

      {/* 统计行 */}
      <div className="stat-grid">
        <Stat label="项目总数" value={total} />
        <Stat label="进行中" value={inProgress} tone="sky" />
        <Stat label="已完成" value={completed} tone="green" />
        <Stat label="总面积" value={totalArea ? `${totalArea.toLocaleString('zh-CN')} ㎡` : '—'} hint="单位：㎡" />
      </div>

      {/* 四态：加载中 / 错误 / 空态 / 数据 */}
      {loading ? (
        <Spinner label="加载项目列表…" />
      ) : error ? (
        <ErrorBox message={error} onRetry={load} />
      ) : projects.length === 0 ? (
        <Empty
          message="暂无项目"
          description="创建第一个项目，即可开启设计、预算、施工、质检到结算的全流程装修管理"
        />
      ) : (
        <Card title="项目列表" sub={`${total} 个`} icon={<FolderOpen size={15} className="ico" />}>
          <div className="table-wrap">
            <table className="table">
            <thead>
              <tr>
                <th>名称</th>
                <th>状态</th>
                <th>面积</th>
                <th>地址</th>
                <th>创建时间</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => {
                const meta = STATUS_META[p.status] || {}
                const area = Number(p.total_area)
                return (
                  <tr key={p.id ?? p.name}>
                    <td>
                      <Link to={`/projects/${p.id}`} style={{ color: 'var(--accent)', fontWeight: 500 }}>
                        {p.name || '未命名项目'}
                      </Link>
                      {/* 后端可能返回 phase 字段，防御性展示 */}
                      {p.phase && (
                        <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                          阶段：{p.phase}
                        </div>
                      )}
                    </td>
                    <td>
                      {meta.tone ? <Badge tone={meta.tone}>{meta.label}</Badge> : <Badge>{p.status || '未知'}</Badge>}
                    </td>
                    <td>{area > 0 ? `${area} ㎡` : '—'}</td>
                    <td>{p.address || '—'}</td>
                    <td>{fmtDate(p.created_at)}</td>
                    <td>
                      <Link to={`/projects/${p.id}`} className="btn btn--ghost" style={{ padding: '2px 10px', fontSize: 12 }}>
                        详情 →
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
