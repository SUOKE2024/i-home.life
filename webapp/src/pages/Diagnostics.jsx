import React, { useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, Server, Route, Gauge,
  Wrench, CircleCheck, CircleX, Eye, RefreshCw,
} from 'lucide-react'
import { Card, Stat, Badge, Spinner, Empty, ErrorBox } from '../components/ui'
import {
  getDiagnosticsOverview, getDiagnosticsEndpoints, getDiagnosticsMetrics,
  getDiagnosticsTraces, getDiagnosticsTraceDetail, getDiagnosticsAlerts,
  acknowledgeDiagnosticsAlert, resolveDiagnosticsAlert, getDiagnosticsRecommendations,
  dismissDiagnosticsRecommendation, getDiagnosticsRum,
} from '../lib/api'

const TABS = [
  { key: 'overview', label: '概览', icon: Gauge },
  { key: 'endpoints', label: '端点', icon: Server },
  { key: 'traces', label: '链路追踪', icon: Route },
  { key: 'alerts', label: '告警', icon: AlertTriangle },
  { key: 'reco', label: '优化建议', icon: Wrench },
  { key: 'rum', label: 'RUM 体验', icon: Activity },
]

const SEV_TONE = { info: 'sky', warning: 'amber', critical: 'red' }
const ALERT_STATUS = { open: ['未处理', 'red'], ack: ['已确认', 'amber'], resolved: ['已解决', 'green'] }

function fmtMs(v) {
  if (v === null || v === undefined) return '—'
  return v >= 1000 ? `${(v / 1000).toFixed(2)}s` : `${Math.round(v)}ms`
}
function fmtPct(v) {
  if (v === null || v === undefined) return '—'
  return `${(v * 100).toFixed(1)}%`
}
function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}

export default function DiagnosticsPage() {
  const [tab, setTab] = useState('overview')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [overview, setOverview] = useState(null)
  const [endpoints, setEndpoints] = useState([])
  const [metrics, setMetrics] = useState([])
  const [traces, setTraces] = useState([])
  const [alerts, setAlerts] = useState([])
  const [recos, setRecos] = useState([])
  const [rum, setRum] = useState(null)
  const [traceDetail, setTraceDetail] = useState(null)
  const [tFilter, setTFilter] = useState({ endpoint: '', errorOnly: false })
  const [endpointSel, setEndpointSel] = useState('')
  const [hours, setHours] = useState(24)

  const load = async () => {
    setLoading(true)
    setError(null)
    const [ov, ep, tr, al, re, rm] = await Promise.all([
      getDiagnosticsOverview(), getDiagnosticsEndpoints(), getDiagnosticsTraces({ limit: 30 }),
      getDiagnosticsAlerts(''), getDiagnosticsRecommendations(''), getDiagnosticsRum(hours),
    ])
    // 任一接口非成功即视为诊断未启用/无权限
    if (!ov.isSuccess || ov.status === 503 || ov.status === 403) {
      setError(ov.error || '诊断功能不可用')
      setLoading(false)
      return
    }
    setOverview(ov.data || {})
    setEndpoints(ep.isSuccess ? (ep.data?.endpoints || []) : [])
    setTraces(tr.isSuccess ? (tr.data?.traces || []) : [])
    setAlerts(al.isSuccess ? (al.data?.alerts || []) : [])
    setRecos(re.isSuccess ? (re.data?.recommendations || []) : [])
    setRum(rm.isSuccess ? rm.data : null)
    setLoading(false)
  }

  const loadMetrics = async (endpoint) => {
    const m = await getDiagnosticsMetrics(hours, 'endpoint', endpoint)
    setMetrics(m.isSuccess ? (m.data?.series || []) : [])
    setEndpointSel(endpoint)
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    if (tab === 'endpoints') loadMetrics(endpointSel)
    if (tab === 'traces') refreshTraces()
    if (tab === 'alerts') refreshAlerts()
    if (tab === 'reco') refreshRecos()
    if (tab === 'rum') refreshRum()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])

  const refreshTraces = async () => {
    const tr = await getDiagnosticsTraces({ limit: 30, ...tFilter })
    setTraces(tr.isSuccess ? (tr.data?.traces || []) : [])
    setTraceDetail(null)
  }
  const refreshAlerts = async () => {
    const al = await getDiagnosticsAlerts('')
    setAlerts(al.isSuccess ? (al.data?.alerts || []) : [])
  }
  const refreshRecos = async () => {
    const re = await getDiagnosticsRecommendations('')
    setRecos(re.isSuccess ? (re.data?.recommendations || []) : [])
  }
  const refreshRum = async () => {
    const rm = await getDiagnosticsRum(hours)
    setRum(rm.isSuccess ? rm.data : null)
  }

  const openTrace = async (traceId) => {
    const d = await getDiagnosticsTraceDetail(traceId)
    setTraceDetail(d.isSuccess ? d.data : null)
  }

  const ackAlert = async (id) => { await acknowledgeDiagnosticsAlert(id); refreshAlerts() }
  const resolveAlert = async (id) => { await resolveDiagnosticsAlert(id); refreshAlerts() }
  const dismissReco = async (id) => { await dismissDiagnosticsRecommendation(id); refreshRecos() }

  const p95Series = useMemo(() => {
    return metrics.slice(-30).map((m) => ({ t: m.window_end, v: m.p95_ms }))
  }, [metrics])

  if (loading) return <Spinner label="正在加载诊断数据…" />
  if (error) {
    return (
      <div>
        <div className="page-head">
          <div>
            <h2>全链路诊断</h2>
            <div className="desc">性能指标 · 全链路追踪 · 异常告警 · 优化建议</div>
          </div>
        </div>
        <ErrorBox
          message={`${error}（需管理端权限且 diagnostics_enabled=true）`}
          onRetry={load}
        />
      </div>
    )
  }

  const ov = overview || {}

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>全链路诊断</h2>
          <div className="desc">MELT 可观测性 · 性能指标采集 → 全链路追踪 → 异常告警 → 优化建议</div>
        </div>
        <button className="btn btn--ghost" onClick={load} title="刷新">
          <RefreshCw size={14} /> 刷新
        </button>
      </div>

      {/* 状态徽标 */}
      <div className="diag-status">
        <Badge tone={ov.diagnostics_enabled ? 'green' : 'amber'}>
          诊断{ov.diagnostics_enabled ? '已启用' : '未启用'}
        </Badge>
        <Badge tone={ov.rum_enabled ? 'green' : 'amber'}>RUM {ov.rum_enabled ? '采集' : '未开启'}</Badge>
        {ov.latest_snapshot?.window_end && (
          <span className="mono dim">最近快照 {fmtTime(ov.latest_snapshot.window_end)}</span>
        )}
      </div>

      {/* Tabs */}
      <div className="diag-tabs">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            className={`diag-tab${tab === key ? ' diag-tab--active' : ''}`}
            onClick={() => setTab(key)}
          >
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      {tab === 'overview' && <OverviewTab ov={ov} traces={traces} alerts={alerts} onOpenTrace={openTrace} onOpenAlerts={() => setTab('alerts')} />}
      {tab === 'endpoints' && (
        <EndpointsTab
          endpoints={endpoints}
          endpointSel={endpointSel}
          onSelect={(ep) => loadMetrics(ep)}
          metrics={metrics}
          p95Series={p95Series}
          hours={hours}
          onHours={setHours}
        />
      )}
      {tab === 'traces' && (
        <TracesTab
          traces={traces}
          filter={tFilter}
          setFilter={setTFilter}
          onRefresh={refreshTraces}
          detail={traceDetail}
          onOpenTrace={openTrace}
        />
      )}
      {tab === 'alerts' && <AlertsTab alerts={alerts} onAck={ackAlert} onResolve={resolveAlert} />}
      {tab === 'reco' && <RecosTab recos={recos} onDismiss={dismissReco} />}
      {tab === 'rum' && <RumTab rum={rum} hours={hours} onHours={setHours} onRefresh={refreshRum} />}
    </div>
  )
}

/* ═══════════ 概览 ═══════════ */
function OverviewTab({ ov, traces, alerts, onOpenTrace, onOpenAlerts }) {
  const t = ov.traffic || {}
  const openAlerts = alerts.filter((a) => a.status === 'open')
  return (
    <>
      <div className="stat-grid">
        <Card>
          <Stat label="活跃告警" value={ov.alerts?.total ?? 0} hint={`未处理 ${ov.alerts?.open ?? 0} · 已确认 ${ov.alerts?.ack ?? 0}`} tone={ov.alerts?.open > 0 ? 'red' : 'green'} />
        </Card>
        <Card>
          <Stat label="24h 请求" value={t.requests_24h ?? 0} hint={`近 1h ${t.requests_last_hour ?? 0} 次`} tone="sky" />
        </Card>
        <Card>
          <Stat label="24h 错误率" value={fmtPct(t.error_rate)} hint={`错误 ${t.errors_24h ?? 0} 次`} tone={t.error_rate > 0.05 ? 'red' : 'green'} />
        </Card>
        <Card>
          <Stat label="LLM 调用链路" value={ov.llm?.traces_with_llm_24h ?? 0} hint="含 LLM 调用的 24h trace" />
        </Card>
        <Card>
          <Stat label="RUM LCP" value={fmtMs(ov.rum?.lcp_avg_ms)} hint="近 1h 平均首屏" />
        </Card>
        <Card>
          <Stat label="采样端点" value={ov.latest_snapshot?.endpoint_count ?? 0} hint={`avg ${fmtMs(ov.latest_snapshot?.avg_ms)} · p95 ${fmtMs(ov.latest_snapshot?.p95_ms)}`} />
        </Card>
      </div>

      <div className="grid-2">
        {/* 最近告警 */}
        <Card
          title="最近告警"
          icon={<AlertTriangle size={16} className="ico" />}
          actions={<button className="btn btn--ghost" style={{ padding: '4px 10px', fontSize: 12 }} onClick={onOpenAlerts}>全部</button>}
        >
          {openAlerts.length === 0 ? (
            <Empty icon="✅" message="当前无未处理告警" description="系统运行平稳" />
          ) : (
            <div className="diag-list">
              {openAlerts.slice(0, 5).map((a) => (
                <div key={a.id} className="diag-list-item">
                  <Badge tone={SEV_TONE[a.severity] || 'amber'}>{a.severity}</Badge>
                  <span className="grow diag-list-title">{a.title}</span>
                  <span className="mono dim">{fmtTime(a.detected_at)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* 最近链路 */}
        <Card title="最近链路" icon={<Route size={16} className="ico" />} sub={`${traces.length} 条`}>
          {traces.length === 0 ? (
            <Empty icon="🧭" message="暂无链路数据" description="诊断开启并采样后出现" />
          ) : (
            <div className="diag-list">
              {traces.slice(0, 6).map((tr) => (
                <button key={tr.trace_id} className="diag-list-item diag-list-item--btn" onClick={() => onOpenTrace(tr.trace_id)}>
                  <span className={`diag-dot${tr.has_error ? ' diag-dot--err' : ''}`} />
                  <span className="grow diag-list-title">
                    {tr.method} {tr.endpoint}
                    {tr.agent_names ? <Badge tone="violet">{tr.agent_names.split(',')[0]}</Badge> : null}
                  </span>
                  <span className={`mono ${tr.duration_ms > 2000 ? 'red-text' : 'dim'}`}>{fmtMs(tr.duration_ms)}</span>
                  <span className="mono dim">{fmtTime(tr.started_at)}</span>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>
    </>
  )
}

/* ═══════════ 端点 ═══════════ */
function EndpointsTab({ endpoints, endpointSel, onSelect, metrics, p95Series, hours, onHours }) {
  const maxP95 = Math.max(1, ...p95Series.map((p) => p.v))
  return (
    <>
      <div className="grid-2" style={{ alignItems: 'start' }}>
        <Card title="端点性能" icon={<Server size={16} className="ico" />} sub={`${endpoints.length} 个端点 · 按 p95 降序`}>
          {endpoints.length === 0 ? (
            <Empty icon="🛰" message="暂无端点数据" description="流量经采样快照后出现" />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>端点</th>
                    <th>请求</th>
                    <th>错误率</th>
                    <th>avg</th>
                    <th>p50</th>
                    <th>p95</th>
                    <th>p99</th>
                    <th>max</th>
                  </tr>
                </thead>
                <tbody>
                  {endpoints.map((ep) => (
                    <tr
                      key={ep.endpoint}
                      onClick={() => onSelect(ep.endpoint)}
                      className={endpointSel === ep.endpoint ? 'diag-row-active' : ''}
                    >
                      <td className="mono" style={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ep.endpoint}</td>
                      <td>{ep.count}</td>
                      <td>
                        <Badge tone={ep.error_rate > 0.05 ? 'red' : 'green'}>{fmtPct(ep.error_rate)}</Badge>
                      </td>
                      <td className="mono">{fmtMs(ep.avg_ms)}</td>
                      <td className="mono">{fmtMs(ep.p50_ms)}</td>
                      <td className={`mono ${ep.p95_ms > 2000 ? 'red-text' : ''}`}>{fmtMs(ep.p95_ms)}</td>
                      <td className="mono">{fmtMs(ep.p99_ms)}</td>
                      <td className="mono dim">{fmtMs(ep.max_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card
          title={`p95 趋势 ${endpointSel ? `· ${endpointSel}` : ''}`}
          icon={<Activity size={16} className="ico" />}
          actions={
            <select className="input input--sm" value={hours} onChange={(e) => onHours(Number(e.target.value))}>
              <option value={6}>6h</option>
              <option value={24}>24h</option>
              <option value={72}>3d</option>
              <option value={168}>7d</option>
            </select>
          }
        >
          {p95Series.length === 0 ? (
            <Empty icon="📈" message="暂无趋势数据" description="选择端点后展示 p95 延迟走势" />
          ) : (
            <div className="diag-bars">
              {p95Series.map((p, i) => (
                <div key={i} className="diag-bar-col" title={`${fmtTime(p.t)} · p95 ${fmtMs(p.v)}`}>
                  <div
                    className={`diag-bar${p.v > 2000 ? ' diag-bar--hot' : ''}`}
                    style={{ height: `${Math.max(6, (p.v / maxP95) * 100)}%` }}
                  />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* 指标快照表 */}
      <Card title="指标快照" icon={<Gauge size={16} className="ico" />} sub={`近 ${hours}h · ${metrics.length} 个窗口`}>
        {metrics.length === 0 ? (
          <Empty icon="🗄" message="暂无指标快照" description="采样任务滚动落库后展示" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>窗口结束</th><th>端点</th><th>请求</th><th>错误</th><th>avg</th><th>p50</th><th>p95</th><th>p99</th><th>max</th>
                </tr>
              </thead>
              <tbody>
                {metrics.slice(-20).reverse().map((m) => (
                  <tr key={m.id}>
                    <td className="mono dim">{fmtTime(m.window_end)}</td>
                    <td className="mono">{m.metric_key}</td>
                    <td>{m.count}</td>
                    <td>{m.error_count}</td>
                    <td className="mono">{fmtMs(m.avg_ms)}</td>
                    <td className="mono">{fmtMs(m.p50_ms)}</td>
                    <td className="mono">{fmtMs(m.p95_ms)}</td>
                    <td className="mono">{fmtMs(m.p99_ms)}</td>
                    <td className="mono dim">{fmtMs(m.max_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}

/* ═══════════ 链路追踪 ═══════════ */
function TracesTab({ traces, filter, setFilter, onRefresh, detail, onOpenTrace }) {
  return (
    <div className="grid-2" style={{ alignItems: 'start' }}>
      <Card
        title="全链路追踪"
        icon={<Route size={16} className="ico" />}
        sub={`${traces.length} 条 · 采样 10%`}
        actions={<button className="btn btn--ghost" style={{ padding: '4px 10px', fontSize: 12 }} onClick={onRefresh}>刷新</button>}
      >
        <div className="diag-filters">
          <input
            className="input input--sm"
            placeholder="按端点过滤…"
            value={filter.endpoint}
            onChange={(e) => setFilter({ ...filter, endpoint: e.target.value })}
            onKeyDown={(e) => e.key === 'Enter' && onRefresh()}
          />
          <label className="diag-check">
            <input type="checkbox" checked={filter.errorOnly} onChange={(e) => setFilter({ ...filter, errorOnly: e.target.checked })} />
            仅错误
          </label>
        </div>
        {traces.length === 0 ? (
          <Empty icon="🧭" message="暂无链路" description="请求经采样后出现（可放宽过滤条件）" />
        ) : (
          <div className="diag-list">
            {traces.map((tr) => (
              <button key={tr.trace_id} className="diag-list-item diag-list-item--btn" onClick={() => onOpenTrace(tr.trace_id)}>
                <span className={`diag-dot${tr.has_error ? ' diag-dot--err' : ''}`} />
                <span className="grow diag-list-title">
                  {tr.method} {tr.endpoint}
                  {tr.agent_names ? <Badge tone="violet">{tr.agent_names.split(',')[0]}</Badge> : null}
                </span>
                {tr.llm_call_count > 0 && <Badge tone="sky">LLM×{tr.llm_call_count}</Badge>}
                {tr.db_query_count > 0 && <Badge tone="amber">DB×{tr.db_query_count}</Badge>}
                <span className={`mono ${tr.duration_ms > 2000 ? 'red-text' : 'dim'}`}>{fmtMs(tr.duration_ms)}</span>
              </button>
            ))}
          </div>
        )}
      </Card>

      <Card title="链路详情" icon={<Eye size={16} className="ico" />}>
        {!detail ? (
          <Empty icon="🔍" message="点击左侧链路查看详情" description="HTTP → DB / LLM / Agent 子 span 瀑布" />
        ) : (
          <div>
            <div className="diag-detail-head">
              <div>
                <b className="mono">{detail.method} {detail.endpoint}</b>
                <div className="sub">
                  <Badge tone={detail.has_error ? 'red' : 'green'}>{detail.status_code}</Badge>{' '}
                  <span className="mono">#{detail.trace_id}</span>
                </div>
              </div>
              <div className="diag-detail-stats">
                <span>总耗时 <b>{fmtMs(detail.duration_ms)}</b></span>
                <span>DB <b>{detail.db_query_count} 次 / {fmtMs(detail.db_query_ms)}</b></span>
                <span>LLM <b>{detail.llm_call_count} 次 / {fmtMs(detail.llm_ms)}</b></span>
                <span>fallback <b>{detail.llm_fallback_count}</b></span>
              </div>
            </div>
            <div className="diag-span-list">
              <div className="diag-span diag-span--http">
                <span className="diag-span-kind">HTTP</span>
                <span className="grow mono">{detail.method} {detail.endpoint}</span>
                <span className="mono">{fmtMs(detail.duration_ms)}</span>
              </div>
              {(detail.spans || []).map((sp, i) => (
                <div key={i} className={`diag-span diag-span--${sp.span_type}`}>
                  <span className="diag-span-kind">{sp.span_type === 'llm' ? 'LLM' : 'DB'}</span>
                  <span className="grow mono" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {sp.span_type === 'llm'
                      ? `${sp.agent} → ${sp.provider}${sp.fallback ? ' (fallback)' : ''} [${sp.status}]`
                      : sp.sql}
                  </span>
                  <span className="mono">{fmtMs(sp.latency_ms ?? sp.duration_ms)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

/* ═══════════ 告警 ═══════════ */
function AlertsTab({ alerts, onAck, onResolve }) {
  return (
    <Card title="异常告警" icon={<AlertTriangle size={16} className="ico" />} sub={`${alerts.length} 条`}>
      {alerts.length === 0 ? (
        <Empty icon="✅" message="暂无告警记录" description="异常检测引擎每 60s 巡检一次" />
      ) : (
        <div className="diag-list">
          {alerts.map((a) => (
            <div key={a.id} className="diag-alert">
              <div className="diag-alert-head">
                <Badge tone={SEV_TONE[a.severity] || 'amber'}>{a.severity}</Badge>
                <span className="grow diag-list-title">{a.title}</span>
                <Badge tone={(ALERT_STATUS[a.status] || ['', ''])[1]}>
                  {(ALERT_STATUS[a.status] || ['未知'])[0]}
                </Badge>
                <span className="mono dim">{fmtTime(a.detected_at)}</span>
              </div>
              {a.description && <div className="diag-alert-desc">{a.description}</div>}
              {a.status !== 'resolved' && (
                <div className="diag-alert-actions">
                  {a.status === 'open' && (
                    <button className="btn btn--ghost" style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => onAck(a.id)}>
                      <Eye size={13} /> 确认
                    </button>
                  )}
                  <button className="btn btn--ghost" style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => onResolve(a.id)}>
                    <CircleCheck size={13} /> 解决
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

/* ═══════════ 优化建议 ═══════════ */
function RecosTab({ recos, onDismiss }) {
  return (
    <Card title="优化建议" icon={<Wrench size={16} className="ico" />} sub={`${recos.length} 条 · 规则引擎生成`}>
      {recos.length === 0 ? (
        <Empty icon="🧰" message="暂无优化建议" description="慢端点 / N+1 / 缓存命中率 / LLM 路由等规则持续分析" />
      ) : (
        <div className="diag-list">
          {recos.map((r) => (
            <div key={r.id} className="diag-alert">
              <div className="diag-alert-head">
                <Badge tone={SEV_TONE[r.severity] || 'sky'}>{r.category}</Badge>
                <span className="grow diag-list-title">{r.title}</span>
                <Badge tone={r.status === 'open' ? 'amber' : 'green'}>{r.status === 'open' ? '待处理' : '已忽略'}</Badge>
                <span className="mono dim">{fmtTime(r.created_at)}</span>
              </div>
              {r.description && <div className="diag-alert-desc">{r.description}</div>}
              {r.status === 'open' && (
                <div className="diag-alert-actions">
                  <button className="btn btn--ghost" style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => onDismiss(r.id)}>
                    <CircleX size={13} /> 忽略
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

/* ═══════════ RUM ═══════════ */
function RumTab({ rum, hours, onHours, onRefresh }) {
  const stats = rum?.stats || {}
  const labels = {
    lcp: ['LCP 首屏', 'ms', 2500],
    cls: ['CLS 布局偏移', '', 0.1],
    inp: ['INP 交互延迟', 'ms', 200],
    fcp: ['FCP 首次内容', 'ms', 1800],
    ttfb: ['TTFB 响应', 'ms', 800],
  }
  return (
    <Card
      title="RUM 前端体验（Core Web Vitals）"
      icon={<Activity size={16} className="ico" />}
      sub={rum?.rum_enabled ? '采集开启' : '采集未开启（diagnostics_rum_enabled=false）'}
      actions={
        <>
          <select className="input input--sm" value={hours} onChange={(e) => onHours(Number(e.target.value))}>
            <option value={6}>6h</option>
            <option value={24}>24h</option>
            <option value={72}>3d</option>
          </select>
          <button className="btn btn--ghost" style={{ padding: '4px 10px', fontSize: 12 }} onClick={onRefresh}>刷新</button>
        </>
      }
    >
      {!rum?.rum_enabled || Object.keys(stats).length === 0 ? (
        <Empty icon="📱" message="暂无 RUM 数据" description="webapp 已埋点，开启后端 diagnostics_rum_enabled 后落库" />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>指标</th>
                <th>含义</th>
                <th>样本</th>
                <th>均值</th>
                <th>评估</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(labels).map(([key, [name, unit, threshold]]) => {
                const s = stats[key]
                if (!s) return null
                const poor = key === 'lcp' && s.poor_count > 0
                return (
                  <tr key={key}>
                    <td className="mono">{key.toUpperCase()}</td>
                    <td>{name}</td>
                    <td>{s.count}</td>
                    <td className="mono">{unit === 'ms' ? fmtMs(s.avg) : s.avg.toFixed(3)}</td>
                    <td>
                      <Badge tone={poor ? 'red' : s.avg < threshold ? 'green' : 'amber'}>
                        {poor ? `${s.poor_count} poor` : s.avg < threshold ? '良好' : '需关注'}
                      </Badge>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
