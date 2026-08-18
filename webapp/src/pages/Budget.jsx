import React, { useEffect, useState, useCallback } from 'react'
import { Wallet } from 'lucide-react'
import { Card, Badge, Stat, Spinner, Empty, ErrorBox } from '../components/ui'
import { listProjects, getBudgetByProject } from '../lib/api'

// 预算明细行状态 → 徽章映射（未知状态兜底为无 tone 灰色徽章）
const LINE_STATUS = {
  over_budget: { tone: 'red', label: '超支' },
  on_budget: { tone: 'green', label: '正常' },
  under_budget: { tone: 'sky', label: '节省' },
  pending: { tone: 'amber', label: '待定' },
  completed: { tone: 'green', label: '已完成' },
}

// 防御性金额格式化（null/undefined/空串/非法值兜底为 —）
function fmtMoney(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  return Number.isFinite(n) ? n.toLocaleString('zh-CN') : '—'
}

export default function BudgetPage() {
  const [projects, setProjects] = useState([])
  const [projectsLoading, setProjectsLoading] = useState(true)
  const [projectsError, setProjectsError] = useState(null)
  const [projectId, setProjectId] = useState('')
  const [budget, setBudget] = useState(null)
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

  // 加载选中项目的预算
  const loadBudget = useCallback(async (id) => {
    setLoading(true)
    setError(null)
    const r = await getBudgetByProject(id)
    if (r.isSuccess) {
      setBudget(r.data || null)
    } else {
      setError(r.error || '加载预算数据失败')
    }
    setLoading(false)
  }, [])

  // 项目切换时重新加载预算
  useEffect(() => {
    if (projectId) {
      loadBudget(projectId)
    } else {
      setBudget(null)
    }
  }, [projectId, loadBudget])

  // 统计：预估总额 / 实际总额 / 执行率（实际 ÷ 预估）
  const estimated = budget?.total_estimated
  const actual = budget?.total_actual
  const currency = budget?.currency || 'CNY'
  const rate = Number(estimated) > 0 ? `${Math.round((Number(actual) / Number(estimated)) * 100)}%` : '—'
  const lines = Array.isArray(budget?.lines) ? budget.lines : []

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>预算管理</h2>
          <div className="desc">按项目查看预算执行情况</div>
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
        <Spinner label="加载预算数据…" />
      ) : error ? (
        <ErrorBox message={error} onRetry={() => loadBudget(projectId)} />
      ) : (
        <>
          {/* 预算统计行 */}
          <div className="stat-grid">
            <Stat label="预估总额" value={fmtMoney(estimated)} hint={currency} />
            <Stat label="实际总额" value={fmtMoney(actual)} hint={currency} tone="sky" />
            <Stat label="执行率" value={rate} hint="实际 / 预估" tone="amber" />
          </div>

          {/* 预算明细表 */}
          <Card title="预算明细" sub={`${lines.length} 项`} icon={<Wallet size={15} className="ico" />}>
            {lines.length === 0 ? (
              <Empty message="暂无预算明细" />
            ) : (
              <div className="table-wrap">
                <table className="table">
                <thead>
                  <tr>
                    <th>项目</th>
                    <th>预估金额</th>
                    <th>实际金额</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((l, i) => {
                    const meta = LINE_STATUS[l.status] || {}
                    return (
                      <tr key={l.id ?? l.name ?? i}>
                        <td>{l.name || '—'}</td>
                        <td>{fmtMoney(l.estimated_amount)}</td>
                        <td>{fmtMoney(l.actual_amount)}</td>
                        <td>
                          {meta.tone ? (
                            <Badge tone={meta.tone}>{meta.label}</Badge>
                          ) : (
                            <Badge>{l.status || '—'}</Badge>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
