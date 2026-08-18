import React, { useEffect, useState, useCallback } from 'react'
import { ListOrdered } from 'lucide-react'
import { Card, Badge, Stat, Spinner, Empty, ErrorBox } from '../components/ui'
import { listProjects, getSettlementByProject } from '../lib/api'

/* 金额格式化：¥1,234.56 */
function fmtMoney(v) {
  const n = Number(v ?? 0)
  return `¥${n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

/* 结算状态 → Badge 映射 */
const STATUS_MAP = {
  draft: { tone: 'amber', label: '草稿' },
  pending: { tone: 'sky', label: '待结算' },
  settled: { tone: 'green', label: '已结算' },
}

export default function SettlementPage() {
  const [projects, setProjects] = useState([]) // 项目列表
  const [projectId, setProjectId] = useState('') // 当前选中的项目
  const [settlement, setSettlement] = useState(null) // 结算单数据
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [loadingSettlement, setLoadingSettlement] = useState(false)
  const [projectsError, setProjectsError] = useState(null)
  const [settlementError, setSettlementError] = useState(null)

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

  /* 按项目加载结算单 */
  const loadSettlement = useCallback(async (id) => {
    if (!id) {
      setSettlement(null)
      return
    }
    setLoadingSettlement(true)
    setSettlementError(null)
    const r = await getSettlementByProject(id)
    setLoadingSettlement(false)
    if (r.isSuccess) {
      setSettlement(r.data)
    } else if (r.status === 404) {
      // 该项目尚无结算单 → 空态
      setSettlement(null)
    } else {
      setSettlementError(r.error || '结算单加载失败')
    }
  }, [])

  useEffect(() => {
    loadSettlement(projectId)
  }, [projectId, loadSettlement])

  /* 数据视图 */
  let body
  if (loadingProjects) {
    body = <Spinner label="项目列表加载中…" />
  } else if (projectsError) {
    body = <ErrorBox message={projectsError} onRetry={loadProjects} />
  } else if (!projectId) {
    body = <Empty message="请先选择项目" />
  } else if (loadingSettlement) {
    body = <Spinner label="结算单加载中…" />
  } else if (settlementError) {
    body = <ErrorBox message={settlementError} onRetry={() => loadSettlement(projectId)} />
  } else if (!settlement) {
    body = <Empty message="该项目暂无结算单" />
  } else {
    const s = settlement
    // 字段防御性访问：兼容 total_amount/settled_amount/pending_amount 与后端实际字段
    const total = s.total_amount ?? s.contract_amount ?? 0
    const settled = s.settled_amount ?? s.actual_amount ?? 0
    const pending = s.pending_amount ?? s.payable_amount ?? 0
    const st = STATUS_MAP[s.status] || { tone: undefined, label: s.status || '未知' }
    const lines = s.lines || []

    body = (
      <>
        <div className="stat-grid">
          <Stat label="结算总额" value={fmtMoney(total)} hint="含变更与扣款" tone="amber" />
          <Stat label="已结算" value={fmtMoney(settled)} tone="green" />
          <Stat label="待结算" value={fmtMoney(pending)} tone="sky" />
          <Stat label="结算状态" value={st.label} tone={st.tone} hint={s.milestone ? `里程碑：${s.milestone}` : undefined} />
        </div>

        <Card
          title="结算明细"
          sub={lines.length ? `${lines.length} 项` : undefined}
          icon={<ListOrdered size={16} className="ico" />}
        >
          {lines.length === 0 ? (
            <Empty message="暂无结算明细" />
          ) : (
            <div className="table-wrap">
              <table className="table">
              <thead>
                <tr>
                  <th>项目</th>
                  <th>金额</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line, i) => {
                  const ls = STATUS_MAP[line.status] || { tone: undefined, label: line.status || '—' }
                  return (
                    <tr key={line.id || i}>
                      <td>{line.name || '—'}</td>
                      <td className="num">{fmtMoney((line.contract_amount ?? 0) + (line.change_amount ?? 0))}</td>
                      <td>
                        <Badge tone={ls.tone}>{ls.label}</Badge>
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
    )
  }

  return (
    <div>
      <div className="page-head">
        <h2>结算管理</h2>
        <div className="desc">查看项目结算总额与明细</div>
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
      </div>

      {body}
    </div>
  )
}
