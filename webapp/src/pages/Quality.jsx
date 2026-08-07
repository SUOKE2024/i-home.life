import React, { useEffect, useState, useCallback } from 'react'
import { ShieldCheck, ClipboardCheck } from 'lucide-react'
import { Card, Badge, Stat, Spinner, Empty, ErrorBox } from '../components/ui'
import { listProjects, getQualityIssues, getQualityChecklist } from '../lib/api'

// 严重度 → 徽章颜色/文案映射
const SEVERITY_META = {
  high: { tone: 'red', label: '严重' },
  medium: { tone: 'amber', label: '中等' },
  low: { tone: 'sky', label: '轻微' },
}

// 问题状态 → 徽章颜色/文案映射
const STATUS_META = {
  open: { tone: 'red', label: '待处理' },
  processing: { tone: 'amber', label: '处理中' },
  resolved: { tone: 'green', label: '已解决' },
}

// 防御性日期格式化（非法值兜底为 —）
function fmtDate(v) {
  if (!v) return '—'
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('zh-CN')
}

export default function QualityPage() {
  const [projects, setProjects] = useState([])
  const [projectsLoading, setProjectsLoading] = useState(true)
  const [projectsError, setProjectsError] = useState(null)
  const [projectId, setProjectId] = useState('')
  const [issues, setIssues] = useState([])
  const [checklist, setChecklist] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

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

  // 并行加载质量问题 + 防水验收清单
  const loadData = useCallback(async (id) => {
    setLoading(true)
    setError(null)
    const [r1, r2] = await Promise.all([getQualityIssues(id), getQualityChecklist('waterproof')])
    if (r1.isSuccess) {
      setIssues(Array.isArray(r1.data) ? r1.data : [])
    } else {
      setError(r1.error || '加载质量问题失败')
    }
    // 验收清单属辅助展示，失败时兜底为空
    setChecklist(r2.isSuccess && Array.isArray(r2.data) ? r2.data : [])
    setLoading(false)
  }, [])

  // 项目切换时重新加载数据
  useEffect(() => {
    if (projectId) {
      loadData(projectId)
    } else {
      setIssues([])
      setChecklist([])
    }
  }, [projectId, loadData])

  // 统计：问题总数 / 待处理 / 处理中 / 已解决
  const total = issues.length
  const open = issues.filter((i) => i.status === 'open').length
  const processing = issues.filter((i) => i.status === 'processing').length
  const resolved = issues.filter((i) => i.status === 'resolved').length

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>质检验收</h2>
          <div className="desc">按项目跟踪质量问题与防水验收清单</div>
        </div>
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

      {/* 四态：未选项目 / 加载中 / 错误 / 数据 */}
      {!projectId ? (
        <Empty message="请先选择项目" />
      ) : loading ? (
        <Spinner label="加载质检验收数据…" />
      ) : error ? (
        <ErrorBox message={error} onRetry={() => loadData(projectId)} />
      ) : (
        <>
          {/* 统计行 */}
          <div className="stat-grid">
            <Stat label="问题总数" value={total} />
            <Stat label="待处理" value={open} tone="red" />
            <Stat label="处理中" value={processing} tone="amber" />
            <Stat label="已解决" value={resolved} tone="green" />
          </div>

          {/* 质量问题表格 */}
          <Card title="质量问题" sub={`${total} 项`} icon={<ShieldCheck size={15} className="ico" />}>
            {issues.length === 0 ? (
              <Empty message="暂无质量问题" />
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>问题描述</th>
                    <th>所属阶段</th>
                    <th>严重度</th>
                    <th>状态</th>
                    <th>创建时间</th>
                  </tr>
                </thead>
                <tbody>
                  {issues.map((i) => {
                    const sMeta = SEVERITY_META[i.severity] || {}
                    const stMeta = STATUS_META[i.status] || {}
                    return (
                      <tr key={i.id ?? i.issue}>
                        <td>
                          {i.issue || '—'}
                          {/* description 为补充说明，防御性展示 */}
                          {i.description && (
                            <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                              {i.description}
                            </div>
                          )}
                        </td>
                        <td>{i.phase || '—'}</td>
                        <td>
                          {sMeta.tone ? <Badge tone={sMeta.tone}>{sMeta.label}</Badge> : <Badge>{i.severity || '—'}</Badge>}
                        </td>
                        <td>
                          {stMeta.tone ? <Badge tone={stMeta.tone}>{stMeta.label}</Badge> : <Badge>{i.status || '—'}</Badge>}
                        </td>
                        <td>{fmtDate(i.created_at)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </Card>

          {/* 防水验收清单（示例阶段） */}
          <Card
            title="防水验收清单（示例阶段）"
            sub="waterproof"
            icon={<ClipboardCheck size={15} className="ico" />}
            style={{ marginTop: 16 }}
          >
            {checklist.length === 0 ? (
              <Empty message="暂无验收清单数据" />
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>检查项</th>
                    <th>说明</th>
                  </tr>
                </thead>
                <tbody>
                  {checklist.map((c, idx) => (
                    <tr key={c.id ?? c.item ?? idx}>
                      <td>{c.item ?? c.name ?? c.title ?? '—'}</td>
                      <td>{c.description ?? c.detail ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
