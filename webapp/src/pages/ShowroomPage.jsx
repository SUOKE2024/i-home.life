import React, { useEffect, useState, useCallback } from 'react'
import { X, Package, BadgeCheck } from 'lucide-react'
import { Spinner, Empty, ErrorBox } from '../components/ui'
import PanoramaViewer from '../components/PanoramaViewer'
import { listProjects, getVRPanoramas, getMaterial, getMaterialCert, addBomItem } from '../lib/api'

const STATUS_LABELS = {
  queued: ['排队中', 'amber'], rendering: ['渲染中', 'sky'],
  completed: ['已完成', 'green'], failed: ['失败', 'red'],
  pending: ['待渲染', 'amber'],
}

/**
 * ShowroomPage — 供应链智能展厅（M4 最小原型，2026-08-12）
 *
 * 设计 4.2：把「供应商/材料库」变成可漫游的 3D 展厅
 * - 展厅 = 项目 VRPanorama（复用 PanoramaViewer 漫游），展品即热点（material_id）
 * - 点击展品 → Material 详情（价格/品牌/规格 + 环保认证 MaterialEcoCert）
 * - 一键加入 BOM（复用 POST /api/materials/bom 链路）
 * 数据诚实：Supplier.is_verified 字段模型不存在，不伪造认证状态（待模型落地后补）
 */
export default function ShowroomPage() {
  const [projects, setProjects] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [panoramas, setPanoramas] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [viewing, setViewing] = useState(null) // { pano, initialView }
  const [exhibit, setExhibit] = useState(null) // 展品面板数据

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
      const r = await listProjects()
      const list = r.isSuccess && Array.isArray(r.data) ? r.data : []
      setProjects(list)
      const target = list[0]?.id || ''
      setSelectedId(target)
      load(target)
    })()
  }, [load])

  const switchProject = (id) => {
    setSelectedId(id)
    setViewing(null)
    setExhibit(null)
    load(id)
  }

  const openViewer = (pano) => {
    let initialView = null
    if (pano.initial_view && typeof pano.initial_view === 'object') {
      initialView = {
        heading: pano.initial_view.heading ?? 0,
        pitch: pano.initial_view.pitch ?? 0,
        fov: pano.initial_view.fov ?? 75,
      }
    }
    setViewing({ pano, initialView })
    setExhibit(null)
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
          <div className="desc">材料展厅 3D 漫游 · 展品即热点 · 一键加入采购清单</div>
        </div>
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
      </div>

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

      {viewing && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 60, display: 'flex', flexDirection: 'column',
          background: '#0a0c10',
        }}
        >
          <div style={{ display: 'flex', alignItems: 'center', padding: '10px 16px', color: '#fff' }}>
            <b style={{ flex: 1 }}>{viewing.pano.room_name} · 材料展厅</b>
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
    </div>
  )
}
