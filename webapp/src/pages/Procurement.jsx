import React, { useEffect, useState, useCallback } from 'react'
import { Plus, X, ShoppingCart } from 'lucide-react'
import { Card, Badge, Stat, Spinner, Empty, ErrorBox } from '../components/ui'
import { useApp } from '../lib/store'
import { listProjects, getProcurementOrders, createProcurementOrder } from '../lib/api'

/* 金额格式化：¥1,234.56 */
function fmtMoney(v) {
  const n = Number(v ?? 0)
  return `¥${n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

/* 采购单状态 → Badge 映射 */
const STATUS_MAP = {
  pending: { tone: 'amber', label: '待审批' },
  approved: { tone: 'sky', label: '已批准' },
  delivered: { tone: 'violet', label: '已交付' },
  completed: { tone: 'green', label: '已完成' },
}

/* 日期格式化：YYYY-MM-DD */
function fmtDate(v) {
  if (!v) return '—'
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('zh-CN')
}

export default function ProcurementPage() {
  const { toast } = useApp()
  const [projects, setProjects] = useState([]) // 项目列表
  const [projectId, setProjectId] = useState('') // 当前选中的项目
  const [orders, setOrders] = useState([]) // 采购单列表
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [loadingOrders, setLoadingOrders] = useState(false)
  const [projectsError, setProjectsError] = useState(null)
  const [ordersError, setOrdersError] = useState(null)
  const [showForm, setShowForm] = useState(false) // 内联新建表单开关
  const [form, setForm] = useState({ supplier_name: '', total_amount: '' }) // 表单数据
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

  /* 按项目加载采购单 */
  const loadOrders = useCallback(async (id) => {
    if (!id) {
      setOrders([])
      return
    }
    setLoadingOrders(true)
    setOrdersError(null)
    const r = await getProcurementOrders(id)
    setLoadingOrders(false)
    if (r.isSuccess) {
      setOrders(r.data || [])
    } else {
      setOrdersError(r.error || '采购单加载失败')
    }
  }, [])

  useEffect(() => {
    loadOrders(projectId)
  }, [projectId, loadOrders])

  /* 新建采购单 */
  const submitOrder = async (e) => {
    e.preventDefault()
    if (!form.supplier_name.trim()) {
      toast('请填写供应商名称', 'error')
      return
    }
    if (!form.total_amount || Number(form.total_amount) < 0) {
      toast('请填写正确的采购金额', 'error')
      return
    }
    setSubmitting(true)
    const r = await createProcurementOrder(projectId, {
      supplier_name: form.supplier_name.trim(),
      total_amount: Number(form.total_amount),
    })
    setSubmitting(false)
    if (r.isSuccess) {
      toast('采购单创建成功', 'success')
      setShowForm(false)
      setForm({ supplier_name: '', total_amount: '' })
      loadOrders(projectId) // 成功后刷新列表
    } else {
      toast(r.error || '创建失败，请重试', 'error')
    }
  }

  /* 统计：订单总数 / 待审批 / 已交付 / 已完成 */
  const total = orders.length
  const pendingCount = orders.filter((o) => o.status === 'pending').length
  const deliveredCount = orders.filter((o) => o.status === 'delivered').length
  const completedCount = orders.filter((o) => o.status === 'completed').length

  /* 数据视图 */
  let body
  if (loadingProjects) {
    body = <Spinner label="项目列表加载中…" />
  } else if (projectsError) {
    body = <ErrorBox message={projectsError} onRetry={loadProjects} />
  } else if (!projectId) {
    body = <Empty message="请先选择项目" />
  } else if (loadingOrders) {
    body = <Spinner label="采购单加载中…" />
  } else if (ordersError) {
    body = <ErrorBox message={ordersError} onRetry={() => loadOrders(projectId)} />
  } else if (orders.length === 0) {
    body = <Empty message="该项目暂无采购单" />
  } else {
    body = (
      <div className="table-wrap">
        <table className="table">
        <thead>
          <tr>
            <th>订单号</th>
            <th>供应商</th>
            <th>金额</th>
            <th>创建时间</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o, i) => {
            const st = STATUS_MAP[o.status] || { tone: undefined, label: o.status || '—' }
            return (
              <tr key={o.id || i}>
                <td className="mono">{o.order_no || o.id || '—'}</td>
                <td>{o.supplier_name || o.supplier_id || '—'}</td>
                <td className="num">{fmtMoney(o.total_amount)}</td>
                <td className="dim">{fmtDate(o.created_at)}</td>
                <td>
                  <Badge tone={st.tone}>{st.label}</Badge>
                </td>
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
        <h2>采购管理</h2>
        <div className="desc">管理项目采购订单与审批状态</div>
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
            {showForm ? '取消' : '新建采购单'}
          </button>
        )}
      </div>

      {/* 内联新建表单 */}
      {showForm && projectId && (
        <Card
          title="新建采购单"
          sub={projectId}
          icon={<ShoppingCart size={16} className="ico" />}
          style={{ marginBottom: 16 }}
        >
          <form onSubmit={submitOrder} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="field">
              <label>供应商名称</label>
              <input
                className="input"
                value={form.supplier_name}
                onChange={(e) => setForm({ ...form, supplier_name: e.target.value })}
                placeholder="如：昆明某某建材有限公司"
                maxLength={100}
              />
            </div>
            <div className="field">
              <label>采购金额（元）</label>
              <input
                className="input"
                type="number"
                min="0"
                step="0.01"
                value={form.total_amount}
                onChange={(e) => setForm({ ...form, total_amount: e.target.value })}
                placeholder="0.00"
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
          <Stat label="订单总数" value={total} />
          <Stat label="待审批" value={pendingCount} tone="amber" />
          <Stat label="已交付" value={deliveredCount} tone="violet" />
          <Stat label="已完成" value={completedCount} tone="green" />
        </div>
      )}

      {body}
    </div>
  )
}
