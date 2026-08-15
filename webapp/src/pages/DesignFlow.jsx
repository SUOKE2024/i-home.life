import React, { useEffect, useState, useCallback } from 'react'
import { Sparkles, Shuffle, UserCheck, Play, RefreshCw, CheckCircle2, Wand2, FileText } from 'lucide-react'
import { Card, Spinner, Empty, ErrorBox } from '../components/ui'
import { useApp } from '../lib/store'
import {
  listProjects, getFloorplans, getVRPanoramas,
  createDesignFlow, matchDesignFlowSuppliers, selectDesignFlowSupplier,
  generateDesignFlowDrawings, getDesignFlowDrawings,
  renderDesignFlow, adjustDesignFlow, confirmDesignFlow,
  getDesignFlowFeasibility, suggestDesignFlow,
} from '../lib/api'

// 风格（值对齐后端 SUPPORTED_STYLES，标签为中文展示）
const STYLES = [
  { value: 'modern', label: '现代简约' },
  { value: 'nordic', label: '北欧奶油' },
  { value: 'japanese', label: '日式原木' },
  { value: 'luxury', label: '轻奢' },
  { value: 'chinese', label: '新中式' },
  { value: 'industrial', label: '工业风' },
  { value: 'coastal', label: '海岸风' },
]

const TIER_LABELS = { economy: '经济', standard: '标准', premium: '高端' }

const STAGE_LABELS = {
  init: '待匹配供应商',
  supplier_matched: '已匹配供应商',
  drawings_generated: '图纸已生成',
  rendered: '已渲染',
  confirmed: '已确认',
  feasibility_done: '可行性分析完成',
  cancelled: '已取消',
}

const STEPS = ['创建会话', '匹配供应商', '设计图纸', '渲染效果图', '确认', '可行性分析']
const STAGE_STEP = {
  init: 0,
  supplier_matched: 1,
  drawings_generated: 2,
  rendered: 3,
  confirmed: 4,
  feasibility_done: 5,
}

const SIGNAL_META = {
  go: ['可推进', 'green'],
  go_with_conditions: ['有条件推进', 'amber'],
  no_go: ['不建议推进', 'red'],
}

export default function DesignFlowPage() {
  const { toast } = useApp()

  const [projects, setProjects] = useState([])
  const [projectId, setProjectId] = useState('')
  const [floorplans, setFloorplans] = useState([])
  const [floorplanId, setFloorplanId] = useState('')

  const [style, setStyle] = useState('modern')
  const [budget, setBudget] = useState(200000)
  const [mode, setMode] = useState('random')

  const [flow, setFlow] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [panoramas, setPanoramas] = useState([])
  const [drawings, setDrawings] = useState(null)
  const [feasibility, setFeasibility] = useState(null)
  const [suggestions, setSuggestions] = useState([])

  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState(null)

  const loadProjects = useCallback(async () => {
    setLoading(true)
    setError(null)
    const r = await listProjects()
    const list = r.isSuccess && Array.isArray(r.data) ? r.data : []
    setProjects(list)
    setLoading(false)
    return list
  }, [])

  useEffect(() => {
    ;(async () => {
      const list = await loadProjects()
      const pid = list[0]?.id || ''
      setProjectId(pid)
      if (pid) {
        const fr = await getFloorplans(pid)
        const plans = fr.isSuccess && Array.isArray(fr.data) ? fr.data : []
        setFloorplans(plans)
        setFloorplanId(plans[0]?.id || '')
      }
    })()
  }, [loadProjects])

  const switchProject = async (pid) => {
    setProjectId(pid)
    setFlow(null)
    setCandidates([])
    setPanoramas([])
    setFeasibility(null)
    setSuggestions([])
    const fr = await getFloorplans(pid)
    const plans = fr.isSuccess && Array.isArray(fr.data) ? fr.data : []
    setFloorplans(plans)
    setFloorplanId(plans[0]?.id || '')
  }

  const currentFloorplan = floorplans.find((p) => p.id === floorplanId)
  const perSqm = currentFloorplan?.total_area ? Math.round(budget / currentFloorplan.total_area) : null
  const tierHint = perSqm
    ? perSqm < 1500 ? 'economy' : perSqm <= 3000 ? 'standard' : 'premium'
    : null

  const run = async (key, label, fn) => {
    setBusy(key)
    setError(null)
    try {
      await fn()
    } finally {
      setBusy('')
    }
  }

  const handleCreate = () => {
    if (!projectId || !floorplanId) {
      toast('请先选择项目和户型', 'error')
      return
    }
    run('create', '创建会话', async () => {
      const r = await createDesignFlow({
        project_id: projectId,
        floorplan_id: floorplanId,
        style,
        budget: Number(budget),
        supplier_selection_mode: mode,
      })
      if (!r.isSuccess) {
        setError(r.error || '创建会话失败')
        return
      }
      setFlow(r.data)
      setCandidates([])
      setPanoramas([])
      setDrawings(null)
      setFeasibility(null)
      setSuggestions([])
      toast('编排会话已创建', 'success')
    })
  }

  const handleMatch = () => {
    run('match', '匹配供应商', async () => {
      const r = await matchDesignFlowSuppliers(flow.id)
      if (!r.isSuccess) {
        setError(r.error || '匹配失败')
        return
      }
      setCandidates(Array.isArray(r.data) ? r.data : [])
      if (r.data?.length === 0) toast('无匹配供应商，请调整风格或预算', 'warning')
    })
  }

  const handleSelect = (supplierId) => {
    run('select', '选择供应商', async () => {
      const payload = supplierId ? { mode: 'manual', supplier_id: supplierId } : { mode: 'random' }
      const r = await selectDesignFlowSupplier(flow.id, payload)
      if (!r.isSuccess) {
        setError(r.error || '选择失败')
        return
      }
      setFlow(r.data)
      toast('供应商已选定', 'success')
    })
  }

  const handleGenerateDrawings = () => {
    run('drawings', '生成设计图纸', async () => {
      const r = await generateDesignFlowDrawings(flow.id)
      if (!r.isSuccess) {
        setError(r.error || '生成图纸失败')
        return
      }
      setFlow(r.data)
      toast('设计图纸已生成', 'success')
      const dr = await getDesignFlowDrawings(flow.id)
      if (dr.isSuccess && dr.data) setDrawings(dr.data)
    })
  }

  const handleRender = () => {
    run('render', '渲染效果图', async () => {
      const r = await renderDesignFlow(flow.id)
      if (!r.isSuccess) {
        setError(r.error || '渲染失败')
        return
      }
      setFlow(r.data)
      toast('渲染完成', 'success')
      const pr = await getVRPanoramas(flow.project_id)
      const list = pr.isSuccess && Array.isArray(pr.data) ? pr.data : []
      setPanoramas(list.filter((p) => p.content_source === 'effect'))
    })
  }

  const handleAdjust = (changes) => {
    run('adjust', '调整并重渲染', async () => {
      const r = await adjustDesignFlow(flow.id, changes)
      if (!r.isSuccess) {
        setError(r.error || '调整失败')
        return
      }
      setFlow(r.data)
      toast('已调整并重渲染', 'success')
      const pr = await getVRPanoramas(flow.project_id)
      const list = pr.isSuccess && Array.isArray(pr.data) ? pr.data : []
      setPanoramas(list.filter((p) => p.content_source === 'effect'))
    })
  }

  const handleConfirm = () => {
    run('confirm', '确认并分析', async () => {
      const r = await confirmDesignFlow(flow.id)
      if (!r.isSuccess) {
        setError(r.error || '确认失败')
        return
      }
      setFlow(r.data)
      const fr = await getDesignFlowFeasibility(flow.id)
      if (fr.isSuccess && fr.data) setFeasibility(fr.data)
      toast('可行性分析已生成', 'success')
    })
  }

  const handleSuggest = () => {
    run('suggest', '智能建议', async () => {
      const r = await suggestDesignFlow(flow.id)
      if (!r.isSuccess) {
        setError(r.error || '建议获取失败')
        return
      }
      setSuggestions(r.data?.suggestions || [])
      if (r.data?.source === 'unavailable') toast('LLM 不可用，已诚实降级（无建议）', 'warning')
    })
  }

  const step = flow ? (STAGE_STEP[flow.stage] ?? 0) : -1

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>设计流程</h2>
          <div className="desc">风格 / 预算选供应商 → VR 效果图 → 调整 → 可行性分析（全链路编排）</div>
        </div>
      </div>

      {/* ── ① 创建会话 ── */}
      <Card title="① 创建编排会话" sub="选择项目户型 + 风格预算">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
          <div className="field">
            <span className="field-label">项目</span>
            <select className="select" value={projectId} onChange={(e) => switchProject(e.target.value)}>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name || p.id}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <span className="field-label">户型</span>
            <select className="select" value={floorplanId} onChange={(e) => setFloorplanId(e.target.value)}>
              {floorplans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name || '未命名'}（{p.total_area || '-'}㎡）
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <span className="field-label">预算（元）</span>
            <input
              type="number"
              className="input"
              value={budget}
              min={10000}
              step={10000}
              onChange={(e) => setBudget(e.target.value)}
            />
          </div>
          <div className="field">
            <span className="field-label">供应商选择</span>
            <select className="select" value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="random">随机（系统推荐）</option>
              <option value="manual">自选（从候选挑）</option>
            </select>
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <span className="field-label">风格</span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 6 }}>
            {STYLES.map((s) => (
              <button
                key={s.value}
                className={style === s.value ? 'chip chip--active' : 'chip'}
                onClick={() => setStyle(s.value)}
                type="button"
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 10 }}>
          预算档位（按每平米估算）：{perSqm ? `${perSqm} 元/㎡ → ${TIER_LABELS[tierHint] || tierHint}` : '待户型面积'}
        </div>

        <div style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'center' }}>
          <button className="btn" onClick={handleCreate} disabled={!!busy || !projectId || !floorplanId}>
            <Sparkles size={15} /> 创建会话
          </button>
        </div>
      </Card>

      {/* ── 流程进度 ── */}
      {flow && (
        <>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', margin: '14px 2px' }}>
            {STEPS.map((label, i) => {
              const done = step > i
              const active = step === i
              return (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span
                    className="badge"
                    style={{
                      background: active ? 'var(--accent)' : done ? 'var(--green-dim)' : 'var(--bg-elev-2)',
                      color: active ? 'var(--on-accent, #08080F)' : done ? 'var(--green)' : 'var(--text-dim)',
                      fontSize: 11,
                    }}
                  >
                    {done ? '✓' : i + 1}
                  </span>
                  <span style={{ fontSize: 12, color: active ? 'var(--text)' : 'var(--text-dim)' }}>{label}</span>
                  {i < STEPS.length - 1 && <span className="mono" style={{ color: 'var(--text-dim)', fontSize: 10 }}>→</span>}
                </div>
              )
            })}
          </div>

          <Card title="编排会话" sub="当前状态与参数">
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <Stat label="阶段" value={STAGE_LABELS[flow.stage] || flow.stage} />
              <Stat label="风格" value={styleLabel(flow.style)} />
              <Stat label="预算" value={`¥${Number(flow.budget).toLocaleString()}`} />
              <Stat label="价格档位" value={TIER_LABELS[flow.price_tier] || flow.price_tier} />
              <Stat label="供应商" value={flow.supplier_id ? '已选定' : '待选'} hint={flow.supplier_id?.slice(0, 8)} />
            </div>
          </Card>
        </>
      )}

      {/* ── ② 匹配供应商 ── */}
      {flow && (
        <Card
          title="② 匹配供应商"
          sub="按风格 + 价格档位硬过滤"
          actions={
            <button className="btn btn--ghost" onClick={handleMatch} disabled={!!busy || flow.stage === 'init' && false}>
              <RefreshCw size={14} /> {busy === 'match' ? '匹配中…' : '匹配候选'}
            </button>
          }
        >
          {candidates.length === 0 && (
            <Empty message="尚未匹配供应商" description="点击「匹配候选」按风格/预算过滤活跃供应商" icon="🏬" />
          )}
          {candidates.length > 0 && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))', gap: 12 }}>
                {candidates.map((c) => (
                  <div key={c.supplier_id} className="card" style={{ padding: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <b style={{ flex: 1, fontSize: 14 }}>{c.name}</b>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--accent)' }}>★ {c.rating}</span>
                    </div>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 6 }}>
                      {c.category} · {TIER_LABELS[c.price_tier] || c.price_tier} · {(c.styles || []).join(' / ')}
                    </div>
                    {c.address && (
                      <div className="mono" style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 4 }}>{c.address}</div>
                    )}
                    <div className="mono" style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 4 }}>
                      {c.showroom_panorama_id
                        ? '🏬 有实景展厅（可线上验厂漫游）'
                        : '实景展厅：暂无（pending）'}
                    </div>
                    {mode === 'manual' && (
                      <button
                        className="btn btn--ghost"
                        style={{ width: '100%', marginTop: 10 }}
                        onClick={() => handleSelect(c.supplier_id)}
                        disabled={!!busy}
                      >
                        <UserCheck size={14} /> 选它
                      </button>
                    )}
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 12, display: 'flex', gap: 10 }}>
                <button className="btn" onClick={() => handleSelect(null)} disabled={!!busy}>
                  <Shuffle size={15} /> {busy === 'select' ? '选择中…' : '随机选择供应商'}
                </button>
              </div>
            </>
          )}
        </Card>
      )}

      {/* ── ③ 设计图纸 ── */}
      {flow && (flow.stage === 'supplier_matched' || flow.stage === 'drawings_generated' || flow.stage === 'rendered' || flow.stage === 'confirmed' || flow.stage === 'feasibility_done') && (
        <Card
          title="③ 设计图纸"
          sub="施工图全套 + 水电图 + 灯图（渲染前生成）"
          actions={
            flow.stage === 'supplier_matched' && (
              <button className="btn" onClick={handleGenerateDrawings} disabled={!!busy}>
                <FileText size={15} /> {busy === 'drawings' ? '生成中…' : '生成图纸'}
              </button>
            )
          }
        >
          {!drawings && flow.stage === 'supplier_matched' && (
            <Empty message="尚未生成设计图纸" description="选定供应商后点击「生成图纸」产出施工图/水电图/灯图" icon="📐" />
          )}
          {drawings && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 }}>
                {drawings.floor_plan_svg && <SvgCard title="平面布置图" svg={drawings.floor_plan_svg} />}
                {drawings.section_svg && <SvgCard title="剖面图" svg={drawings.section_svg} />}
                {drawings.mep_overlay_svg && <SvgCard title="水电平面图" svg={drawings.mep_overlay_svg} />}
              </div>
              {drawings.mep_plan?.summary && (
                <div className="card" style={{ padding: 12 }}>
                  <b style={{ fontSize: 13 }}>水电点位规划</b>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 6 }}>
                    共 {drawings.mep_plan.summary.total_points} 点位 · 开关 {drawings.mep_plan.summary.switches} / 插座 {drawings.mep_plan.summary.sockets} / 灯具 {drawings.mep_plan.summary.lights} / 网络 {drawings.mep_plan.summary.network} / 空调 {drawings.mep_plan.summary.ac}
                  </div>
                </div>
              )}
              {drawings.lighting_schemes?.length > 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
                  {drawings.lighting_schemes.map((s, i) => (
                    <div key={i} className="card" style={{ padding: 12 }}>
                      <b style={{ fontSize: 13 }}>{s.room_name}</b>
                      <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 6 }}>
                        {s.scheme_type} · {s.total_power_w}W · {s.total_lumens}lm · {s.color_temp_k}K
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {/* ── ④ 渲染效果图 ── */}
      {flow && (flow.stage === 'drawings_generated' || flow.stage === 'rendered' || flow.stage === 'confirmed' || flow.stage === 'feasibility_done') && (
        <Card
          title="④ 渲染 VR 效果图"
          sub="每房间一张 2D 效果图 + 全屋漫游组合"
          actions={
            flow.stage === 'drawings_generated' && (
              <button className="btn" onClick={handleRender} disabled={!!busy}>
                <Play size={15} /> {busy === 'render' ? '渲染中…' : '渲染'}
              </button>
            )
          }
        >
          {panoramas.length === 0 && flow.stage === 'drawings_generated' && (
            <Empty message="尚未渲染" description="生成图纸后点击「渲染」生成每房间效果图" icon="🖼" />
          )}
          {panoramas.length > 0 && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
                {panoramas.map((p) => (
                  <div key={p.id} className="card" style={{ overflow: 'hidden', padding: 0 }}>
                    <div style={{ height: 120, background: 'var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-dim)' }}>
                      {p.image_url ? (
                        <img
                          src={p.image_url}
                          alt={p.room_name}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          onError={(e) => { e.currentTarget.style.display = 'none' }}
                        />
                      ) : (
                        <Play size={28} strokeWidth={1.2} />
                      )}
                    </div>
                    <div style={{ padding: '10px 12px 12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <b style={{ flex: 1, fontSize: 13 }}>{p.room_name || '房间'}</b>
                        <span className="badge" style={{ background: 'var(--amber-dim)', color: 'var(--amber)', fontSize: 10 }}>
                          效果图
                        </span>
                      </div>
                      <div className="mono" style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 4 }}>
                        AI 生成 · 2D 平面（非 360° 实景）
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-sub)' }}>
                全屋漫游已组合（场景 ID <span className="mono">{flow.scene_id?.slice(0, 8)}…</span>），可前往
                <a href="/virtual-tour" style={{ color: 'var(--accent)', marginLeft: 4 }}>VR 全景</a> 查看。
              </div>
            </>
          )}
        </Card>
      )}

      {/* ── ⑤ 调整（含 LLM 建议）── */}
      {flow && (flow.stage === 'rendered' || flow.stage === 'confirmed' || flow.stage === 'feasibility_done') && (
        <Card
          title="⑤ 调整（可选）"
          sub="任意环节调整均触发重渲染"
          actions={
            <button className="btn btn--ghost" onClick={handleSuggest} disabled={!!busy}>
              <Wand2 size={14} /> {busy === 'suggest' ? '获取中…' : '智能建议'}
            </button>
          }
        >
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'end' }}>
            <div className="field" style={{ minWidth: 160 }}>
              <span className="field-label">换风格</span>
              <select className="select" value={style} onChange={(e) => setStyle(e.target.value)}>
                {STYLES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
            <div className="field" style={{ minWidth: 160 }}>
              <span className="field-label">调预算（元）</span>
              <input type="number" className="input" value={budget} min={10000} step={10000} onChange={(e) => setBudget(e.target.value)} />
            </div>
            <button className="btn" onClick={() => handleAdjust({ style, budget: Number(budget) })} disabled={!!busy}>
              <RefreshCw size={15} /> {busy === 'adjust' ? '调整中…' : '应用并重渲染'}
            </button>
          </div>

          {suggestions.length > 0 && (
            <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {suggestions.map((s, i) => (
                <div key={i} className="card" style={{ padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="badge" style={{ background: 'var(--violet-dim)', color: 'var(--violet)', fontSize: 10 }}>
                    {s.type || '建议'}
                  </span>
                  <span style={{ flex: 1, fontSize: 12 }}>{s.suggestion || JSON.stringify(s)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* ── ⑤ 确认 + 可行性分析 ── */}
      {flow && (flow.stage === 'rendered' || flow.stage === 'confirmed' || flow.stage === 'feasibility_done') && (
        <Card
          title="⑥ 可行性分析"
          sub="工期 / 预算 / 物料 / 风险四维度"
          actions={
            flow.stage === 'rendered' && (
              <button className="btn" onClick={handleConfirm} disabled={!!busy}>
                <CheckCircle2 size={15} /> {busy === 'confirm' ? '分析中…' : '确认并分析'}
              </button>
            )
          }
        >
          {!feasibility && flow.stage === 'rendered' && (
            <Empty message="尚未生成可行性分析" description="点击「确认并分析」生成四维度可行性报告" icon="📊" />
          )}
          {feasibility && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {(() => {
                  const meta = SIGNAL_META[feasibility.summary?.signal] || ['未知', 'sky']
                  return (
                    <span className="badge" style={{ background: `var(--${meta[1]}-dim)`, color: `var(--${meta[1]})`, fontSize: 12 }}>
                      结论：{meta[0]}
                    </span>
                  )
                })()}
                <span className="mono" style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                  status={feasibility.status} · {feasibility.summary?.note || ''}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: 12 }}>
                <FeasibilityBlock title="工期可行性" data={feasibility.duration_analysis} tone="green">
                  {feasibility.duration_analysis?.total_days != null && (
                    <div className="stat-value mono" style={{ fontSize: 18 }}>
                      {feasibility.duration_analysis.total_days} 天
                      <span className="stat-hint" style={{ fontSize: 11 }}>
                        含 {feasibility.duration_analysis.buffer_days} 天缓冲
                      </span>
                    </div>
                  )}
                </FeasibilityBlock>

                <FeasibilityBlock title="预算可行性" data={feasibility.budget_analysis} tone="amber">
                  {feasibility.budget_analysis?.user_budget != null && (
                    <div>
                      <div className="mono" style={{ fontSize: 13 }}>
                        预算 ¥{Number(feasibility.budget_analysis.user_budget).toLocaleString()}
                      </div>
                      <div className="mono" style={{ fontSize: 13, marginTop: 4 }}>
                        BOM ¥{Number(feasibility.budget_analysis.bom_total || 0).toLocaleString()}
                      </div>
                      <div className="mono" style={{ fontSize: 11, color: feasibility.budget_analysis.over_budget ? 'var(--red)' : 'var(--green)', marginTop: 4 }}>
                        {feasibility.budget_analysis.over_budget ? '超支' : '预算内'}（差 ¥{Number(feasibility.budget_analysis.gap || 0).toLocaleString()}）
                      </div>
                    </div>
                  )}
                </FeasibilityBlock>

                <FeasibilityBlock title="物料可供应性" data={feasibility.material_analysis} tone="sky">
                  {feasibility.material_analysis?.total_materials != null && (
                    <div>
                      <div className="mono" style={{ fontSize: 13 }}>
                        {feasibility.material_analysis.total_materials} 类物料
                      </div>
                      <div className="mono" style={{ fontSize: 11, color: feasibility.material_analysis.shortage_count > 0 ? 'var(--red)' : 'var(--green)', marginTop: 4 }}>
                        {feasibility.material_analysis.shortage_count > 0
                          ? `${feasibility.material_analysis.shortage_count} 项缺货`
                          : '全部可供应'}
                      </div>
                    </div>
                  )}
                </FeasibilityBlock>

                <FeasibilityBlock title="施工条件/风险" data={feasibility.risk_analysis} tone="red">
                  {feasibility.risk_analysis?.risks != null && (
                    <div>
                      <div className="mono" style={{ fontSize: 13 }}>
                        {feasibility.risk_analysis.risks.length} 项风险
                      </div>
                      <div className="mono" style={{ fontSize: 11, color: feasibility.risk_analysis.risks.length > 0 ? 'var(--red)' : 'var(--green)', marginTop: 4 }}>
                        {feasibility.risk_analysis.risks.length > 0 ? '需关注' : '暂无显著风险'}
                      </div>
                    </div>
                  )}
                </FeasibilityBlock>
              </div>
            </div>
          )}
        </Card>
      )}

      {loading && <Spinner label="正在加载项目…" />}
      {!loading && error && (
        <div style={{ marginTop: 12 }}>
          <ErrorBox message={error} onRetry={loadProjects} />
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, hint }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value" style={{ fontSize: 16 }}>{value ?? '—'}</span>
      {hint && <span className="stat-hint mono">{hint}</span>}
    </div>
  )
}

function FeasibilityBlock({ title, data, tone, children }) {
  return (
    <div className="card" style={{ padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <span style={{ width: 8, height: 8, borderRadius: 2, background: `var(--${tone})` }} />
        <b style={{ fontSize: 13 }}>{title}</b>
      </div>
      {children}
      {data?.source && (
        <div className="mono" style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 6 }}>
          source={data.source}
        </div>
      )}
    </div>
  )
}

function styleLabel(value) {
  const hit = STYLES.find((s) => s.value === value)
  return hit ? hit.label : value
}

function SvgCard({ title, svg }) {
  const src = `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
  return (
    <div className="card" style={{ padding: 10 }}>
      <b style={{ fontSize: 12 }}>{title}</b>
      <div
        style={{
          height: 180, marginTop: 8, background: 'var(--border)', borderRadius: 8,
          overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <img src={src} alt={title} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
      </div>
    </div>
  )
}
