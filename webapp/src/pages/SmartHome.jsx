import React, { useEffect, useState, useCallback } from 'react'
import { Plus, X, Home } from 'lucide-react'
import { Card, Badge, Stat, Spinner, Empty, ErrorBox } from '../components/ui'
import { useApp } from '../lib/store'
import { listProjects, getSmartHomeSchemes, createSmartHomeScheme } from '../lib/api'

/* 方案状态 → Badge 映射 */
const STATUS_MAP = {
  draft: { tone: 'amber', label: '草稿' },
  planned: { tone: 'sky', label: '规划中' },
  active: { tone: 'green', label: '启用中' },
  installing: { tone: 'amber', label: '安装中' },
  completed: { tone: 'green', label: '已完成' },
  disabled: { tone: 'red', label: '已停用' },
}

/* 房间类型 → 中文文案 */
const ROOM_META = {
  living_room: '客厅',
  bedroom: '卧室',
  kitchen: '厨房',
  bathroom: '卫生间',
  study: '书房',
  balcony: '阳台',
  dining_room: '餐厅',
}

export default function SmartHomePage() {
  const { toast } = useApp()
  const [projects, setProjects] = useState([]) // 项目列表
  const [projectId, setProjectId] = useState('') // 当前选中的项目
  const [schemes, setSchemes] = useState([]) // 智能家居方案列表
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [loadingSchemes, setLoadingSchemes] = useState(false)
  const [projectsError, setProjectsError] = useState(null)
  const [schemesError, setSchemesError] = useState(null)
  const [showForm, setShowForm] = useState(false) // 内联新建表单开关
  const [form, setForm] = useState({ scheme_name: '', room_type: '', description: '' }) // 表单数据
  const [submitting, setSubmitting] = useState(false)

  /* 加载项目列表 */
  const loadProjects = useCallback(async () => {
    setLoadingProjects(true)
    setProjectsError(null)
    const r = await listProjects()
    setLoadingProjects(false)
    if (r.isSuccess) {
      setProjects(r.data || [])
    } else {
      setProjectsError(r.error || '项目列表加载失败')
    }
  }, [])

  useEffect(() => {
    loadProjects()
  }, [loadProjects])

  /* 按项目加载智能家居方案 */
  const loadSchemes = useCallback(async (id) => {
    if (!id) {
      setSchemes([])
      return
    }
    setLoadingSchemes(true)
    setSchemesError(null)
    const r = await getSmartHomeSchemes(id)
    setLoadingSchemes(false)
    if (r.isSuccess) {
      setSchemes(r.data || [])
    } else {
      setSchemesError(r.error || '方案列表加载失败')
    }
  }, [])

  useEffect(() => {
    loadSchemes(projectId)
  }, [projectId, loadSchemes])

  /* 新建方案 */
  const submitScheme = async (e) => {
    e.preventDefault()
    if (!form.scheme_name.trim()) {
      toast('请填写方案名称', 'error')
      return
    }
    if (!form.room_type.trim()) {
      toast('请填写房间类型', 'error')
      return
    }
    setSubmitting(true)
    const r = await createSmartHomeScheme(projectId, {
      scheme_name: form.scheme_name.trim(),
      room_type: form.room_type.trim(),
      description: form.description.trim(),
    })
    setSubmitting(false)
    if (r.isSuccess) {
      toast('方案创建成功', 'success')
      setShowForm(false)
      setForm({ scheme_name: '', room_type: '', description: '' })
      loadSchemes(projectId) // 成功后刷新列表
    } else {
      toast(r.error || '创建失败，请重试', 'error')
    }
  }

  /* 统计：方案总数 / 启用中 / 草稿 */
  const total = schemes.length
  const activeCount = schemes.filter((s) => s.status === 'active').length
  const draftCount = schemes.filter((s) => s.status === 'draft').length

  /* 数据视图 */
  let body
  if (loadingProjects) {
    body = <Spinner label="项目列表加载中…" />
  } else if (projectsError) {
    body = <ErrorBox message={projectsError} onRetry={loadProjects} />
  } else if (!projectId) {
    body = <Empty message="请先选择项目" />
  } else if (loadingSchemes) {
    body = <Spinner label="方案列表加载中…" />
  } else if (schemesError) {
    body = <ErrorBox message={schemesError} onRetry={() => loadSchemes(projectId)} />
  } else if (schemes.length === 0) {
    body = <Empty message="该项目暂无智能家居方案" />
  } else {
    body = (
      <div className="table-wrap">
        <table className="table">
        <thead>
          <tr>
            <th>方案名</th>
            <th>房间类型</th>
            <th>设备数</th>
            <th>状态</th>
            <th>描述</th>
          </tr>
        </thead>
        <tbody>
          {schemes.map((s, i) => {
            const st = STATUS_MAP[s.status] || { tone: undefined, label: s.status || '—' }
            return (
              <tr key={s.id || i}>
                <td>{s.scheme_name || s.room_name || '—'}</td>
                <td>{ROOM_META[s.room_type] || s.room_type || '—'}</td>
                <td className="num">{s.device_count ?? '—'}</td>
                <td>
                  <Badge tone={st.tone}>{st.label}</Badge>
                </td>
                <td className="dim">{s.description || s.notes || '—'}</td>
              </tr>
            )
          })}
        </tbody>
        </table>
      </div>
    )
  }

  return (
    <div>
      <div className="page-head">
        <h2>智能家居</h2>
        <div className="desc">管理全屋智能方案与设备配置</div>
      </div>

      <div className="toolbar">
        <select
          className="select"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          <option value="">选择项目…</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>

        {projectId && (
          <button className="btn btn--primary" onClick={() => setShowForm(!showForm)}>
            {showForm ? <X size={15} /> : <Plus size={15} />}
            {showForm ? '取消' : '新建方案'}
          </button>
        )}
      </div>

      {/* 内联新建表单 */}
      {showForm && projectId && (
        <Card
          title="新建方案"
          sub={projectId}
          icon={<Home size={16} className="ico" />}
          style={{ marginBottom: 16 }}
        >
          <form onSubmit={submitScheme} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="field">
              <label>方案名称</label>
              <input
                className="input"
                value={form.scheme_name}
                onChange={(e) => setForm({ ...form, scheme_name: e.target.value })}
                placeholder="如：客厅全屋智能方案"
                maxLength={100}
              />
            </div>
            <div className="field">
              <label>房间类型</label>
              <input
                className="input"
                value={form.room_type}
                onChange={(e) => setForm({ ...form, room_type: e.target.value })}
                placeholder="如：living_room / 卧室 / 厨房"
                maxLength={50}
              />
            </div>
            <div className="field">
              <label>方案描述</label>
              <textarea
                className="textarea"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="简述方案亮点与设备规划（可选）"
                maxLength={500}
              />
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button className="btn btn--primary" type="submit" disabled={submitting}>
                {submitting ? '提交中…' : '提交'}
              </button>
              <button className="btn btn--ghost" type="button" onClick={() => setShowForm(false)}>
                取消
              </button>
            </div>
          </form>
        </Card>
      )}

      {/* 统计行：仅选中项目后展示 */}
      {projectId && (
        <div className="stat-grid">
          <Stat label="方案总数" value={total} />
          <Stat label="启用中" value={activeCount} tone="green" />
          <Stat label="草稿" value={draftCount} tone="amber" />
        </div>
      )}

      {body}
    </div>
  )
}
