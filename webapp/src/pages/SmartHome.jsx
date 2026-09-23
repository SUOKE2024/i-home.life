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

/* 房间类型 → 中文文案。
   取值必须逐字等于后端 CheckConstraint chk_smart_home_scheme_room_type
   （app/models/smart_home.py：living_room/bedroom/kitchen/bathroom/entrance/study），
   表单下拉直接由本表生成，多一个键即写出库约束错误（曾含 balcony/dining_room 且缺 entrance）。 */
const ROOM_META = {
  living_room: '客厅',
  bedroom: '卧室',
  kitchen: '厨房',
  bathroom: '卫生间',
  entrance: '玄关',
  study: '书房',
}

/* 新建方案表单（后端方案按房间组织：room_name 必填，room_type 默认 living_room） */
const EMPTY_FORM = { room_name: '', room_type: 'living_room', notes: '' }

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
  const [form, setForm] = useState(EMPTY_FORM) // 表单数据（room_name/room_type/notes）
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

  /* 新建方案（POST /api/smart-home/schemes：project_id + room_name 必填） */
  const submitScheme = async (e) => {
    e.preventDefault()
    if (!form.room_name.trim()) {
      toast('请填写房间名称', 'error')
      return
    }
    setSubmitting(true)
    const r = await createSmartHomeScheme(projectId, {
      room_name: form.room_name.trim(),
      room_type: form.room_type,
      notes: form.notes.trim() || undefined,
    })
    setSubmitting(false)
    if (r.isSuccess) {
      toast(`已创建「${r.data?.room_name || form.room_name.trim()}」智能方案`, 'success')
      setShowForm(false)
      setForm(EMPTY_FORM)
      loadSchemes(projectId) // 成功后刷新列表
    } else {
      toast(`方案创建失败：${r.error || '请重试'}`, 'error')
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
            <th>房间名称</th>
            <th>房间类型</th>
            <th>设备数</th>
            <th>状态</th>
            <th>备注</th>
          </tr>
        </thead>
        <tbody>
          {schemes.map((s, i) => {
            const st = STATUS_MAP[s.status] || { tone: undefined, label: s.status || '—' }
            return (
              <tr key={s.id || i} data-testid={`smart-home-scheme-row--${s.id || i}`}>
                <td>{s.room_name || '—'}</td>
                <td>{ROOM_META[s.room_type] || s.room_type || '—'}</td>
                <td className="num">{s.device_count ?? '—'}</td>
                <td>
                  <Badge tone={st.tone}>{st.label}</Badge>
                </td>
                <td className="dim">{s.notes || '—'}</td>
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
          aria-label="选择项目"
          data-testid="smart-home-project-select"
        >
          <option value="">选择项目…</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>

        {projectId && (
          <button
            className="btn btn--primary"
            onClick={() => setShowForm(!showForm)}
            data-testid="smart-home-toggle-form"
          >
            {showForm ? <X size={15} /> : <Plus size={15} />}
            {showForm ? '取消' : '新建方案'}
          </button>
        )}
      </div>

      {/* 内联新建表单 */}
      {showForm && projectId && (
        <Card
          title="新建方案"
          sub="方案按房间组织，一个房间一份方案"
          icon={<Home size={16} className="ico" />}
          style={{ marginBottom: 16 }}
        >
          <form onSubmit={submitScheme} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="field">
              <label htmlFor="sh-room-name">房间名称 *</label>
              <input
                id="sh-room-name"
                className="input"
                value={form.room_name}
                onChange={(e) => setForm({ ...form, room_name: e.target.value })}
                placeholder="如：客厅 / 主卧"
                maxLength={100}
                data-testid="smart-home-room-name"
              />
            </div>
            <div className="field">
              <label htmlFor="sh-room-type">房间类型</label>
              <select
                id="sh-room-type"
                className="select"
                value={form.room_type}
                onChange={(e) => setForm({ ...form, room_type: e.target.value })}
                data-testid="smart-home-room-type"
              >
                {Object.entries(ROOM_META).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="sh-notes">备注（可选）</label>
              <textarea
                id="sh-notes"
                className="textarea"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="简述设备规划（可选）"
                maxLength={500}
                data-testid="smart-home-notes"
              />
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                className="btn btn--primary"
                type="submit"
                disabled={submitting}
                data-testid="smart-home-scheme-submit"
              >
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
