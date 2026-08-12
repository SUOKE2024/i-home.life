import React, { useEffect, useState, useCallback } from 'react'
import { X, Package, BadgeCheck, Store, Clock, HardHat } from 'lucide-react'
import { Spinner, Empty, ErrorBox } from '../components/ui'
import PanoramaViewer from '../components/PanoramaViewer'
import { listProjects, getVRPanoramas, getVRPanorama, getMaterial, getMaterialCert, addBomItem, listSuppliers, listCrews, matchCrews, getCrewPortfolio } from '../lib/api'

const STATUS_LABELS = {
  queued: ['排队中', 'amber'], rendering: ['渲染中', 'sky'],
  completed: ['已完成', 'green'], failed: ['失败', 'red'],
  pending: ['待渲染', 'amber'],
}

/**
 * ShowroomPage — 供应链智能展厅（M4，2026-08-12）
 *
 * 设计 4.2：把「供应商/材料库」变成可漫游的 3D 展厅
 * - 材料展厅 = 项目 VRPanorama（复用 PanoramaViewer 漫游），展品即热点（material_id）
 * - 供应商实景展厅 = 供应商 showroom_panorama_id（车间/样品间 360°）→ 线上验厂漫游
 * - 服务商作品集展厅 = 工程队 showcase_panorama_id（已交付项目 VRPanorama 实景）→ 漫游后发起接单
 * - 认证状态诚实标注：is_verified ? 已认证徽标 : pending 水印（平台授予，非自报）
 * - 点击展品 → Material 详情（价格/品牌/规格 + 环保认证 MaterialEcoCert）→ 加入 BOM
 */
export default function ShowroomPage() {
  const [tab, setTab] = useState('material') // material / supplier / crew
  const [projects, setProjects] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [panoramas, setPanoramas] = useState([])
  const [suppliers, setSuppliers] = useState([])
  const [crews, setCrews] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [viewing, setViewing] = useState(null) // { pano, initialView, title }
  const [exhibit, setExhibit] = useState(null) // 展品面板数据
  const [crewMatch, setCrewMatch] = useState(null) // 接单匹配结果面板
  const [portfolio, setPortfolio] = useState(null) // 施工进度/质检时间线面板

  const load = useCallback(async (projectId) => {
    if (!projectId) {
      setPanoramas([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    const r = await getVRPanoramas(projectId)
    if (!r.isSuccess) {
      setError(r.error || '加载展厅全景失败')
    } else {
      setPanoramas(Array.isArray(r.data) ? r.data : [])
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    ;(async () => {
      const [pr, su, cr] = await Promise.all([listProjects(), listSuppliers(), listCrews()])
      const list = pr.isSuccess && Array.isArray(pr.data) ? pr.data : []
      setProjects(list)
      setSuppliers(su.isSuccess && Array.isArray(su.data) ? su.data : [])
      setCrews(cr.isSuccess && Array.isArray(cr.data) ? cr.data : [])
      const target = list[0]?.id || ''
      setSelectedId(target)
      load(target)
    })()
  }, [load])

  const switchProject = (id) => {
    setSelectedId(id)
    setViewing(null)
    setExhibit(null)
    setCrewMatch(null)
    load(id)
  }

  const switchTab = (t) => {
    setTab(t)
    setViewing(null)
    setExhibit(null)
    setCrewMatch(null)
  }

  const openViewer = (pano, title) => {
    let initialView = null
    if (pano.initial_view && typeof pano.initial_view === 'object') {
      initialView = {
        heading: pano.initial_view.heading ?? 0,
        pitch: pano.initial_view.pitch ?? 0,
        fov: pano.initial_view.fov ?? 75,
      }
    }
    setViewing({ pano, initialView, title: title || pano.room_name })
    setExhibit(null)
  }

  /** 供应商在线验厂：showroom_panorama_id → 全景详情 → 漫游 */
  const openSupplierShowroom = async (s) => {
    if (!s.showroom_panorama_id) return
    const r = await getVRPanorama(s.showroom_panorama_id)
    if (!r.isSuccess || !r.data) {
      alert(`${s.name}：实景展厅全景加载失败（${r.error || '不存在'}）`)
      return
    }
    openViewer(r.data, `${s.name} · 实景展厅`)
  }

  /** 服务商作品集漫游：showcase_panorama_id → 全景详情 → 漫游 */
  const openCrewShowcase = async (c) => {
    if (!c.showcase_panorama_id) return
    const r = await getVRPanorama(c.showcase_panorama_id)
    if (!r.isSuccess || !r.data) {
      alert(`${c.name}：作品集全景加载失败（${r.error || '不存在'}）`)
      return
    }
    openViewer(r.data, `${c.name} · 作品集`)
  }

  /** 发起接单：对当前项目跑工程队匹配（复用 /api/crews/match 链路） */
  const initiateMatch = async (c) => {
    if (!selectedId) {
      alert('请先选择项目')
      return
    }
    setCrewMatch({ loading: true, crew: c })
    const r = await matchCrews({ project_id: selectedId, top_n: 20 })
    if (!r.isSuccess) {
      setCrewMatch({ loading: false, crew: c, error: r.error || '匹配失败' })
      return
    }
    const list = Array.isArray(r.data) ? r.data : []
    const mine = list.find((m) => m.crew_id === c.id)
    setCrewMatch({
      loading: false,
      crew: c,
      mine: mine || null,
      top: list.slice(0, 3),
      total: list.length,
    })
  }

  /** 装修过程透明：拉取工程队作品集（施工进度 + 质检时间线，设计 4.3） */
  const openPortfolio = async (c) => {
    setPortfolio({ loading: true, crew: c })
    const r = await getCrewPortfolio(c.id)
    if (!r.isSuccess) {
      setPortfolio({ loading: false, crew: c, error: r.error || '作品集加载失败' })
      return
    }
    setPortfolio({ loading: false, crew: c, data: r.data })
  }

  const VERDICT_LABEL = {
    excellent: ['优秀', 'green'], pass: ['通过', 'green'], conditional_pass: ['有条件通过', 'amber'],
    fail: ['不合格', 'red'], pending: ['待评估', 'amber'],
  }

  /** 点击展品热点 → 加载材料详情 + 环保认证 */
  const onHotspotClick = async (hs) => {
    if (!hs.material_id) {
      if (hs.url) window.open(hs.url, '_blank', 'noopener')
      else alert(`${hs.label}：展品未关联材料`)
      return
    }
    setExhibit({ loading: true, material: null, cert: null, materialId: hs.material_id, action: null })
    const [m, c] = await Promise.all([getMaterial(hs.material_id), getMaterialCert(hs.material_id)])
    setExhibit({
      loading: false,
      material: m.isSuccess ? m.data : null,
      cert: c.isSuccess && c.data ? c.data : null,
      materialId: hs.material_id,
      action: null,
      error: !m.isSuccess ? (m.error || '材料不存在') : null,
    })
  }

  /** 一键加入 BOM（复用 procurement/BOMItem 链路） */
  const addToBom = async () => {
    if (!exhibit?.material) return
    setExhibit((e) => ({ ...e, action: { busy: true } }))
    const r = await addBomItem({
      project_id: selectedId,
      material_id: exhibit.material.id,
      quantity: 1,
    })
    setExhibit((e) => ({
      ...e,
      action: r.isSuccess
        ? { ok: true, msg: '已加入 BOM（采购清单）' }
        : { ok: false, msg: r.error || '加入 BOM 失败' },
    }))
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>智能展厅</h2>
          <div className="desc">材料展厅 3D 漫游 · 供应商实景展厅 · 服务商作品集 · 展品即热点</div>
        </div>
        {tab === 'material' ? (
          <select
            className="select"
            value={selectedId}
            onChange={(e) => switchProject(e.target.value)}
            style={{ width: 240 }}
          >
            {projects.map((pr) => (
              <option key={pr.id} value={pr.id}>{pr.name || pr.id}</option>
            ))}
          </select>
        ) : tab === 'supplier' ? (
          <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
            共 {suppliers.length} 家供应商 · 认证状态平台授予
          </span>
        ) : (
          <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
            共 {crews.length} 支工程队 · 作品集平台授予 · 审核通过可被匹配
          </span>
        )}
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
        <button
          className={tab === 'material' ? 'btn btn-primary' : 'btn'}
          style={{ fontSize: 13 }}
          onClick={() => switchTab('material')}
        >
          <Package size={15} style={{ verticalAlign: -2, marginRight: 4 }} />材料展厅
        </button>
        <button
          className={tab === 'supplier' ? 'btn btn-primary' : 'btn'}
          style={{ fontSize: 13 }}
          onClick={() => switchTab('supplier')}
        >
          <Store size={15} style={{ verticalAlign: -2, marginRight: 4 }} />供应商实景展厅
        </button>
        <button
          className={tab === 'crew' ? 'btn btn-primary' : 'btn'}
          style={{ fontSize: 13 }}
          onClick={() => switchTab('crew')}
        >
          <HardHat size={15} style={{ verticalAlign: -2, marginRight: 4 }} />服务商作品集
        </button>
      </div>

      {tab === 'crew' ? (
        <>
          {crews.length === 0 && <Empty message="暂无服务商名录，可联系平台入驻" />}
          {crews.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
              {crews.map((c) => {
                const approved = c.review_status === 'approved'
                return (
                  <div key={c.id} className="card" style={{ overflow: 'hidden', padding: 0 }}>
                    <div style={{
                      height: 88, background: approved ? 'rgba(34, 197, 94, 0.08)' : 'var(--border)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: approved ? 'var(--success, #22c55e)' : 'var(--text-dim)',
                      position: 'relative',
                    }}
                    >
                      <HardHat size={34} />
                      {!approved && (
                        <span style={{
                          position: 'absolute', top: 8, right: 8, fontSize: 10, padding: '2px 6px',
                          borderRadius: 4, background: 'rgba(251, 191, 36, 0.15)',
                          color: '#b45309', letterSpacing: 1,
                        }}
                        >
                          REVIEWING
                        </span>
                      )}
                    </div>
                    <div style={{ padding: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
                        {c.name}
                        {approved && <BadgeCheck size={15} color="var(--success, #22c55e)" />}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                        资质 {c.qualification || '-'} 级 · 评分 {Number(c.rating || 0).toFixed(1)} · 案例 {c.completed_projects || 0} 个 · ¥{c.daily_rate || 0}/天
                      </div>
                      {Array.isArray(c.specialties) && c.specialties.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
                          {c.specialties.map((sp) => (
                            <span key={sp} className="badge badge--sky">{sp}</span>
                          ))}
                        </div>
                      )}
                      {!approved && (
                        <div style={{ fontSize: 12, marginTop: 6, color: '#b45309' }}>
                          <Clock size={12} style={{ verticalAlign: -2 }} /> 入驻审核中，通过后方可接单
                        </div>
                      )}
                      {c.showcase_panorama_id ? (
                        <button
                          className="btn btn-primary"
                          style={{ width: '100%', marginTop: 8, fontSize: 13 }}
                          onClick={() => openCrewShowcase(c)}
                        >
                          进入作品集漫游
                        </button>
                      ) : (
                        <div style={{
                          width: '100%', marginTop: 8, padding: '7px 0', textAlign: 'center',
                          fontSize: 12, color: 'var(--text-dim)', border: '1px dashed var(--border)',
                          borderRadius: 6,
                        }}
                        >
                          暂无作品集全景（待上传已交付项目实景）
                        </div>
                      )}
                      <button
                        className="btn"
                        style={{ width: '100%', marginTop: 6, fontSize: 13 }}
                        disabled={!approved}
                        onClick={() => initiateMatch(c)}
                      >
                        {approved ? '发起接单' : '审核中不可接单'}
                      </button>
                      <button
                        className="ghost"
                        style={{ width: '100%', marginTop: 4, fontSize: 12, border: 'none', background: 'transparent', cursor: 'pointer' }}
                        onClick={() => openPortfolio(c)}
                      >
                        装修过程透明 · 施工进度/质检时间线
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      ) : tab === 'supplier' ? (
        <>
          {suppliers.length === 0 && <Empty message="暂无供应商名录，可联系平台入驻" />}
          {suppliers.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
              {suppliers.map((s) => (
                <div key={s.id} className="card" style={{ overflow: 'hidden', padding: 0 }}>
                  <div style={{
                    height: 96, background: s.is_verified ? 'rgba(34, 197, 94, 0.08)' : 'var(--border)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: s.is_verified ? 'var(--success, #22c55e)' : 'var(--text-dim)',
                    position: 'relative',
                  }}
                  >
                    <Store size={36} />
                    {!s.is_verified && (
                      <span style={{
                        position: 'absolute', top: 8, right: 8, fontSize: 10, padding: '2px 6px',
                        borderRadius: 4, background: 'rgba(251, 191, 36, 0.15)',
                        color: '#b45309', letterSpacing: 1,
                      }}
                      >
                        PENDING
                      </span>
                    )}
                  </div>
                  <div style={{ padding: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
                      {s.name}
                      {s.is_verified && <BadgeCheck size={15} color="var(--success, #22c55e)" />}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                      {s.category || '-'} · 评分 {Number(s.rating || 0).toFixed(1)}
                    </div>
                    <div style={{ fontSize: 12, marginTop: 6 }}>
                      {s.is_verified ? (
                        <span style={{ color: 'var(--success, #22c55e)' }}>✓ 已认证</span>
                      ) : (
                        <span style={{ color: '#b45309' }}>
                          <Clock size={12} style={{ verticalAlign: -2 }} /> 认证审核中
                        </span>
                      )}
                    </div>
                    {s.showroom_panorama_id ? (
                      <button
                        className="btn btn-primary"
                        style={{ width: '100%', marginTop: 8, fontSize: 13 }}
                        onClick={() => openSupplierShowroom(s)}
                      >
                        在线验厂 · 进入实景展厅
                      </button>
                    ) : (
                      <div style={{
                        width: '100%', marginTop: 8, padding: '7px 0', textAlign: 'center',
                        fontSize: 12, color: 'var(--text-dim)', border: '1px dashed var(--border)',
                        borderRadius: 6,
                      }}
                      >
                        暂无实景展厅（待上传车间/样品间全景）
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <>
          {loading && <Spinner label="正在加载展厅…" />}
          {!loading && error && <ErrorBox message={error} onRetry={() => load(selectedId)} />}
          {!loading && !error && panoramas.length === 0 && (
            <Empty message="暂无展厅全景，可让 AI 管家协助生成" />
          )}
          {!loading && !error && panoramas.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
              {panoramas.map((p) => {
                const st = STATUS_LABELS[p.status] || ['未知', 'sky']
                const rendered = !!p.image_url
                return (
                  <div key={p.id} className="card" style={{ overflow: 'hidden', padding: 0 }}>
                    <div style={{
                      height: 150, background: 'var(--border)', display: 'flex',
                      alignItems: 'center', justifyContent: 'center', color: 'var(--text-dim)',
                    }}
                    >
                      {p.thumbnail_url ? (
                        <img src={p.thumbnail_url} alt={p.room_name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      ) : (
                        <Package size={40} />
                      )}
                    </div>
                    <div style={{ padding: 10 }}>
                      <div style={{ fontWeight: 600 }}>{p.room_name}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                        <span className={`badge badge--${st[1]}`}>{st[0]}</span>
                        {' '}· 展品热点 {p.hotspots?.filter((h) => h.material_id).length || 0} 个
                      </div>
                      {rendered && (
                        <button
                          className="btn btn-primary"
                          style={{ width: '100%', marginTop: 8, fontSize: 13 }}
                          onClick={() => openViewer(p)}
                        >
                          进入展厅
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      {viewing && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 60, display: 'flex', flexDirection: 'column',
          background: '#0a0c10',
        }}
        >
          <div style={{ display: 'flex', alignItems: 'center', padding: '10px 16px', color: '#fff' }}>
            <b style={{ flex: 1 }}>{viewing.title}</b>
            <button
              className="icon-btn"
              style={{ color: '#fff', background: 'rgba(255,255,255,0.12)' }}
              onClick={() => setViewing(null)}
              title="关闭"
            >
              <X size={18} />
            </button>
          </div>
          <div style={{ flex: 1, position: 'relative' }}>
            <PanoramaViewer
              imageUrl={viewing.pano.image_url}
              hotspots={viewing.pano.hotspots || []}
              initialView={viewing.initialView}
              onHotspotClick={onHotspotClick}
            />
            {exhibit && (
              <div style={{
                position: 'absolute', right: 16, top: 16, width: 280, zIndex: 30,
                background: 'var(--card)', border: '1px solid var(--border)',
                borderRadius: 12, padding: 14, boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
              }}
              >
                {exhibit.loading ? (
                  <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>展品加载中…</div>
                ) : exhibit.error || !exhibit.material ? (
                  <div style={{ fontSize: 13, color: 'var(--danger, #dc3c3c)' }}>{exhibit.error || '展品不存在'}</div>
                ) : (
                  <>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <strong style={{ fontSize: 15 }}>{exhibit.material.name}</strong>
                      <button
                        className="ghost"
                        style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}
                        onClick={() => setExhibit(null)}
                        aria-label="关闭"
                      >
                        <X size={18} />
                      </button>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                      {exhibit.material.brand || '无品牌'} · {exhibit.material.spec || '-'}
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 700, marginTop: 8 }}>
                      ¥{Number(exhibit.material.unit_price || 0).toFixed(2)}
                      <span style={{ fontSize: 12, color: 'var(--text-dim)', fontWeight: 400 }}> / {exhibit.material.unit}</span>
                    </div>
                    {exhibit.material.description && (
                      <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 6 }}>
                        {exhibit.material.description}
                      </div>
                    )}
                    {exhibit.cert ? (
                      <div style={{ fontSize: 12, marginTop: 8, display: 'flex', gap: 6, alignItems: 'center', color: 'var(--success, #22c55e)' }}>
                        <BadgeCheck size={15} /> 环保认证 · {exhibit.cert.cert_name || '已认证'}
                      </div>
                    ) : (
                      <div style={{ fontSize: 12, marginTop: 8, color: 'var(--text-dim)' }}>
                        暂无环保认证记录（诚实标注，无数据不伪造）
                      </div>
                    )}
                    <button
                      className="btn btn-primary"
                      style={{ width: '100%', marginTop: 10 }}
                      disabled={exhibit.action?.busy}
                      onClick={addToBom}
                    >
                      {exhibit.action?.busy ? '加入中…' : '加入 BOM'}
                    </button>
                    {exhibit.action && !exhibit.action.busy && (
                      <div
                        style={{
                          marginTop: 8, fontSize: 12, padding: '6px 8px', borderRadius: 6,
                          background: exhibit.action.ok ? 'rgba(34, 197, 94, 0.12)' : 'rgba(220, 60, 60, 0.12)',
                          color: exhibit.action.ok ? 'var(--success, #22c55e)' : 'var(--danger, #dc3c3c)',
                        }}
                      >
                        {exhibit.action.msg}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
            <div style={{
              position: 'absolute', bottom: 14, left: '50%', transform: 'translateX(-50%)',
              color: 'rgba(255,255,255,0.75)', fontSize: 12,
            }}
            >
              拖拽环视 · 滚轮缩放 · 点击展品热点查看详情
            </div>
          </div>
        </div>
      )}

      {crewMatch && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 55, display: 'flex', alignItems: 'center',
          justifyContent: 'center', background: 'rgba(10,12,16,0.55)',
        }}
        >
          <div style={{
            width: 420, maxWidth: '92vw', background: 'var(--card)',
            border: '1px solid var(--border)', borderRadius: 12, padding: 16,
            boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
          }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <strong>{crewMatch.crew.name} · 发起接单</strong>
              <button
                className="ghost"
                style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}
                onClick={() => setCrewMatch(null)}
                aria-label="关闭"
              >
                <X size={18} />
              </button>
            </div>
            {crewMatch.loading ? (
              <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 12 }}>
                正在匹配当前项目工程队…
              </div>
            ) : crewMatch.error ? (
              <div style={{ fontSize: 13, color: 'var(--danger, #dc3c3c)', marginTop: 12 }}>{crewMatch.error}</div>
            ) : (
              <>
                {crewMatch.mine ? (
                  <div style={{
                    marginTop: 12, padding: 10, borderRadius: 8,
                    background: 'rgba(34, 197, 94, 0.08)', border: '1px solid rgba(34, 197, 94, 0.25)',
                  }}
                  >
                    <div style={{ fontSize: 14, fontWeight: 600 }}>
                      匹配评分 {Number(crewMatch.mine.match_score || 0).toFixed(0)} / 100
                    </div>
                    {crewMatch.mine.recommendation && (
                      <div style={{ fontSize: 12, marginTop: 4, color: 'var(--text-dim)' }}>
                        {crewMatch.mine.recommendation}
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ fontSize: 13, marginTop: 12, color: 'var(--text-dim)' }}>
                    该工程队未进入本项目的匹配结果（可能不符地域/专长条件）
                  </div>
                )}
                {crewMatch.top && crewMatch.top.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 6 }}>
                      当前项目推荐工程队 Top {crewMatch.top.length}（共 {crewMatch.total} 支）
                    </div>
                    {crewMatch.top.map((m) => (
                      <div
                        key={m.id}
                        style={{
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          padding: '6px 8px', marginBottom: 4, borderRadius: 6,
                          background: 'var(--bg, #f6f7f9)',
                        }}
                      >
                        <span style={{ fontSize: 13 }}>
                          {m.crew?.name || m.crew_id}
                          {m.crew?.qualification ? `（资质 ${m.crew.qualification}）` : ''}
                        </span>
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--success, #22c55e)' }}>
                          {Number(m.match_score || 0).toFixed(0)} 分
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {portfolio && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 56, display: 'flex', alignItems: 'center',
          justifyContent: 'center', background: 'rgba(10,12,16,0.55)',
        }}
        >
          <div style={{
            width: 520, maxWidth: '94vw', maxHeight: '86vh', overflowY: 'auto',
            background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, padding: 16,
            boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
          }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <strong>{portfolio.crew.name} · 装修过程透明</strong>
              <button
                className="ghost"
                style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}
                onClick={() => setPortfolio(null)}
                aria-label="关闭"
              >
                <X size={18} />
              </button>
            </div>
            {portfolio.loading ? (
              <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 12 }}>
                正在加载施工进度与质检记录…
              </div>
            ) : portfolio.error ? (
              <div style={{ fontSize: 13, color: 'var(--danger, #dc3c3c)', marginTop: 12 }}>{portfolio.error}</div>
            ) : (
              <>
                {!portfolio.data.projects || portfolio.data.projects.length === 0 ? (
                  <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 12 }}>
                    暂无已雇佣项目的施工记录（诚实标注，无数据不伪造）
                  </div>
                ) : (
                  portfolio.data.projects.map((p) => (
                    <div key={p.project_id} style={{ marginTop: 12, padding: 10, borderRadius: 8, background: 'var(--bg, #f6f7f9)' }}>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{p.name}</div>
                      {p.task_phases && p.task_phases.length > 0 ? (
                        <div style={{ marginTop: 8 }}>
                          {p.task_phases.map((ph) => {
                            const done = ph.total > 0 ? Math.round((ph.completed / ph.total) * 100) : 0
                            return (
                              <div key={ph.phase} style={{ marginBottom: 6 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 }}>
                                  <span>{ph.phase_label} · {ph.completed}/{ph.total} 项</span>
                                  <span style={{ color: 'var(--text-dim)' }}>
                                    {ph.in_progress > 0 ? `${ph.in_progress} 进行中 · ` : ''}{done}%
                                  </span>
                                </div>
                                <div style={{ height: 6, borderRadius: 3, background: 'var(--border)' }}>
                                  <div style={{
                                    width: `${done}%`, height: 6, borderRadius: 3,
                                    background: done === 100 ? 'var(--success, #22c55e)' : 'var(--primary, #2563eb)',
                                  }}
                                  />
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      ) : (
                        <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 6 }}>暂无施工任务记录</div>
                      )}
                      {p.assessments && p.assessments.length > 0 && (
                        <div style={{ marginTop: 8 }}>
                          <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 4 }}>质检时间线</div>
                          {p.assessments.map((a, i) => {
                            const v = VERDICT_LABEL[a.verdict] || ['未知', 'sky']
                            return (
                              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, marginBottom: 3 }}>
                                <span className={`badge badge--${v[1]}`}>{v[0]}</span>
                                <span>{a.phase_label} · 得分 {Number(a.score || 0).toFixed(1)}</span>
                              </div>
                            )
                          })}
                        </div>
                      )}
                      {(!p.assessments || p.assessments.length === 0) && p.task_phases && p.task_phases.length > 0 && (
                        <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 6 }}>暂无质检评估记录</div>
                      )}
                    </div>
                  ))
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
