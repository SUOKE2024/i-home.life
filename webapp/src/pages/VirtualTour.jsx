import React, { useEffect, useState, useCallback } from 'react'
import { X, Rotate3D } from 'lucide-react'
import { Spinner, Empty, ErrorBox } from '../components/ui'
import PanoramaViewer from '../components/PanoramaViewer'
import GaussianViewer from '../components/GaussianViewer'
import DeviceCommandPanel from '../components/DeviceCommandPanel'
import SceneTriggerOverlay from '../components/SceneTriggerOverlay'
import useDeviceOverlay from '../hooks/useDeviceOverlay'
import { listProjects, getVRPanoramas, uploadSplatPanorama, restagePanorama } from '../lib/api'

const STATUS_LABELS = {
  queued: ['排队中', 'amber'],
  rendering: ['渲染中', 'sky'],
  completed: ['已完成', 'green'],
  failed: ['失败', 'red'],
  // 兼容历史数据
  pending: ['待渲染', 'amber'],
}

export default function VirtualTourPage() {
  const [projects, setProjects] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [panoramas, setPanoramas] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [viewing, setViewing] = useState(null)
  const [selectedDevice, setSelectedDevice] = useState(null)
  // 3DGS 实景上传（P0：外部工具采集 .spz/.ply 登记，2026-09-12）
  const [showUpload, setShowUpload] = useState(false)
  const [uploadRoom, setUploadRoom] = useState('')
  const [uploadFile, setUploadFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  // P2 AI 换装（virtual staging）：效果图与实景双视图对比
  const [restageStyle, setRestageStyle] = useState('modern')
  const [restaging, setRestaging] = useState(false)
  const [restageResult, setRestageResult] = useState(null)
  const [restageError, setRestageError] = useState(null)

  // P0 设备热点联动：当前项目设备图层（加载 + 30s 轮询 + 命令/场景触发）
  const { devices, latestSensor, sendCommand, triggerScene, sceneFlash } = useDeviceOverlay(selectedId)

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
      setError(r.error || '加载全景图失败')
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
    load(id)
  }

  const doUpload = async () => {
    if (!selectedId || !uploadFile || uploading) return
    setUploading(true)
    setUploadError(null)
    // 未填房间名时用文件名兜底（去扩展名）
    const room = uploadRoom.trim() || uploadFile.name.replace(/\.[^.]+$/, '')
    const r = await uploadSplatPanorama(selectedId, room, uploadFile)
    setUploading(false)
    if (!r.isSuccess) {
      setUploadError(r.error || '上传失败')
      return
    }
    setShowUpload(false)
    setUploadRoom('')
    setUploadFile(null)
    load(selectedId)
  }

  const doRestage = async () => {
    if (!viewing || restaging) return
    setRestaging(true)
    setRestageError(null)
    setRestageResult(null)
    const r = await restagePanorama(viewing.pano.id, restageStyle, '')
    setRestaging(false)
    if (!r.isSuccess) {
      setRestageError(r.error || '换装失败')
      return
    }
    setRestageResult(r.data)
  }

  const closeViewer = () => {
    setViewing(null)
    setRestageResult(null)
    setRestageError(null)
  }

  const openViewer = (pano) => {
    // 后端列表项 initial_view 为解析后的 dict {heading, pitch, fov}
    let initialView = null
    if (pano.initial_view && typeof pano.initial_view === 'object') {
      initialView = {
        heading: pano.initial_view.heading ?? 0,
        pitch: pano.initial_view.pitch ?? 0,
        fov: pano.initial_view.fov ?? 75,
      }
    }
    setViewing({ pano, initialView })
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>VR 全景</h2>
          <div className="desc">全景看房 · 拖拽环视 / 滚轮缩放 / 点击热点跳转（AI 效果图为 2D 平面预览）</div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button
            className="btn"
            disabled={!selectedId}
            onClick={() => { setShowUpload((v) => !v); setUploadError(null) }}
          >
            上传 3DGS 场景
          </button>
          <select
            className="select"
            value={selectedId}
            onChange={(e) => switchProject(e.target.value)}
            style={{ width: 240 }}
          >
            {projects.map((pr) => (
              <option key={pr.id} value={pr.id}>
                {pr.name || pr.id}
              </option>
            ))}
          </select>
        </div>
      </div>

      {showUpload && (
        <div className="card" style={{ marginBottom: 14, padding: '12px 14px' }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              className="input"
              style={{ width: 180 }}
              placeholder="房间名（默认取文件名）"
              value={uploadRoom}
              onChange={(e) => setUploadRoom(e.target.value)}
            />
            <input
              type="file"
              accept=".spz,.ply,.glb"
              onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
            />
            <button className="btn primary" disabled={!uploadFile || uploading} onClick={doUpload}>
              {uploading ? '上传中…' : '确认上传'}
            </button>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 8 }}>
            支持 .spz / .ply / .glb（≤64MB，推荐 SPZ 压缩格式）。由外部工具采集重建后导出
            （如 LCC Scan / Polycam / LCC2 glTF），平台负责托管与 3D 漫游渲染，不做 2D→3D 重建。
          </div>
          {uploadError && (
            <div style={{ fontSize: 12, color: 'var(--red)', marginTop: 6 }}>{uploadError}</div>
          )}
        </div>
      )}

      {loading && <Spinner label="正在加载全景图…" />}
      {!loading && error && <ErrorBox message={error} onRetry={() => load(selectedId)} />}
      {!loading && !error && panoramas.length === 0 && (
        <Empty message="暂无全景图，可让 AI 管家协助生成" />
      )}
      {!loading && !error && panoramas.length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 14,
          }}
        >
          {panoramas.map((p) => {
            const st = STATUS_LABELS[p.status] || ['未知', 'sky']
            const isGaussian = p.panorama_type === 'gaussian'
            // 3DGS 实景（splat_url）与贴图全景（image_url）均为可渲染成品
            const rendered = !!(p.image_url || p.splat_url)
            return (
              <div
                key={p.id}
                className="card"
                style={{ overflow: 'hidden', padding: 0 }}
              >
                <div
                  style={{
                    height: 150,
                    background: 'var(--border)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--text-dim)',
                  }}
                >
                  {p.thumbnail_url ? (
                    <img
                      src={p.thumbnail_url}
                      alt={p.room_name}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      onError={(e) => { e.currentTarget.style.display = 'none' }}
                    />
                  ) : rendered ? (
                    <img
                      src={p.image_url}
                      alt={p.room_name}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      onError={(e) => { e.currentTarget.style.display = 'none' }}
                    />
                  ) : (
                    <Rotate3D size={40} strokeWidth={1.2} />
                  )}
                </div>
                <div style={{ padding: '12px 14px 14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <b style={{ flex: 1, fontSize: 14 }}>{p.room_name || '未命名'}</b>
                    <span className="badge" style={{ background: `var(--${st[1]}-dim)`, color: `var(--${st[1]})`, fontSize: 11 }}>
                      {st[0]}
                    </span>
                  </div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>
                    {p.content_source === 'effect' ? (
                      <span style={{ color: 'var(--accent-text)' }}>AI 效果图 · 2D 平面预览（非 360° 实景）</span>
                    ) : (
                      <>
                        {isGaussian
                          ? '高斯泼溅 3DGS · 实景漫游'
                          : `${p.panorama_type === 'equirectangular' ? '球面全景' : p.panorama_type || '-'} · ${p.resolution} · ${p.hotspots?.length ?? 0} 热点`}
                      </>
                    )}
                  </div>
                  <div style={{ marginTop: 10 }}>
                    <button
                      className="btn"
                      style={{ width: '100%' }}
                      disabled={!rendered}
                      onClick={() => openViewer(p)}
                    >
                      {rendered
                        ? p.content_source === 'effect'
                          ? '效果图预览'
                          : isGaussian
                            ? '进入 3D 漫游'
                            : '进入 360° 全景'
                        : '等待渲染'}
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {viewing && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 100,
            background: 'rgba(10,10,12,0.92)',
            display: 'flex', flexDirection: 'column',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', padding: '10px 16px', color: '#fff' }}>
            <b style={{ flex: 1 }}>
              {viewing.pano.room_name} · {viewing.pano.content_source === 'effect'
                ? '效果图预览'
                : viewing.pano.panorama_type === 'gaussian'
                  ? '3D 实景漫游'
                  : '360° 全景'}
            </b>
            {viewing.pano.content_source !== 'effect' && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginRight: 8 }}>
                <select
                  className="select"
                  value={restageStyle}
                  onChange={(e) => setRestageStyle(e.target.value)}
                  style={{ width: 110, color: '#fff', background: 'rgba(255,255,255,0.12)', borderColor: 'transparent' }}
                >
                  {['modern', 'nordic', 'japanese', 'luxury', 'chinese', 'industrial'].map((s) => (
                    <option key={s} value={s} style={{ color: '#000' }}>{s}</option>
                  ))}
                </select>
                <button
                  className="icon-btn"
                  style={{ color: '#fff', background: 'rgba(255,255,255,0.12)', width: 'auto', padding: '0 12px' }}
                  onClick={doRestage}
                  disabled={restaging}
                  title="AI 换装（生成效果图与实景对比）"
                >
                  {restaging ? '生成中…' : 'AI 换装'}
                </button>
              </div>
            )}
            <button
              className="icon-btn"
              style={{ color: '#fff', background: 'rgba(255,255,255,0.12)' }}
              onClick={closeViewer}
              title="关闭"
            >
              <X size={18} />
            </button>
          </div>
          <div style={{ flex: 1, position: 'relative' }}>
            {viewing.pano.content_source === 'effect' ? (
              // 设计 4.1：AI 效果图为 2D 平面图（非等距柱状），平面预览 + 诚实标注，不伪造 360° 沉浸感
              <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <img
                  src={viewing.pano.image_url}
                  alt={viewing.pano.room_name}
                  style={{ maxWidth: '94%', maxHeight: '92%', objectFit: 'contain', borderRadius: 8 }}
                />
                <div style={{
                  position: 'absolute', top: 14, left: '50%', transform: 'translateX(-50%)',
                  background: 'var(--accent)', color: 'var(--on-accent)',
                  fontSize: 12, padding: '4px 12px', borderRadius: 999, fontWeight: 600,
                }}
                >
                  效果图预览 · AI 生成非实景（2D→3D 漫游待 GPU 内容管线）
                </div>
              </div>
            ) : viewing.pano.splat_url && !viewing.gsFailed ? (
              // M3：3DGS 漫游（Spark），失败/无 WebGL2 → 降级贴图全景
              <GaussianViewer
                splatUrl={viewing.pano.splat_url}
                devices={devices}
                hotspots={viewing.pano.hotspots || []}
                initialView={viewing.initialView}
                onDeviceClick={(d) => setSelectedDevice(d)}
                onHotspotClick={(hs) => {
                  const target =
                    (hs.target_panorama_id && panoramas.find((x) => x.id === hs.target_panorama_id)) || null
                  if (target && (target.splat_url || target.image_url)) openViewer(target)
                  else alert(`${hs.label}：${hs.target_panorama_id ? '目标场景未渲染' : '暂无可跳转目标'}`)
                }}
                onFallback={() => setViewing((v) => (v ? { ...v, gsFailed: true } : v))}
              />
            ) : (
              <div data-pv-status="active" style={{ width: '100%', height: '100%' }}>
                <PanoramaViewer
                imageUrl={viewing.pano.image_url}
                hotspots={viewing.pano.hotspots || []}
                devices={devices}
                initialView={viewing.initialView}
                onHotspotClick={(hs) => {
                  const target =
                    (hs.target_panorama_id && panoramas.find((x) => x.id === hs.target_panorama_id)) || null
                  if (target && target.image_url) openViewer(target)
                  else if (hs.url) window.open(hs.url, '_blank', 'noopener')
                  else alert(`${hs.label}：${hs.target_panorama_id ? '目标全景未渲染' : hs.type === 'info' ? '信息热点' : '暂无可跳转目标'}`)
                }}
                onDeviceClick={(d) => setSelectedDevice(d)}
              />
              </div>
            )}
            {selectedDevice && (
              <DeviceCommandPanel
                device={selectedDevice}
                sensor={latestSensor}
                onClose={() => setSelectedDevice(null)}
                onCommand={(device, action) => sendCommand(device, action)}
                onScene={(sceneId) => triggerScene(sceneId)}
              />
            )}
            <SceneTriggerOverlay flash={sceneFlash} />
            {restaging && (
              <div style={{ position: 'absolute', top: 14, right: 14, background: 'rgba(10,12,16,0.8)', color: '#fff', fontSize: 12, padding: '6px 12px', borderRadius: 8 }}>
                AI 换装生成中…
              </div>
            )}
            {restageError && (
              <div style={{ position: 'absolute', top: 14, right: 14, background: 'rgba(200,60,60,0.9)', color: '#fff', fontSize: 12, padding: '6px 12px', borderRadius: 8 }}>
                {restageError}
              </div>
            )}
            {restageResult && restageResult.image_url && (
              <div style={{
                position: 'absolute', top: 14, right: 14, width: 260,
                background: 'rgba(10,12,16,0.92)', borderRadius: 10, overflow: 'hidden',
                border: '1px solid rgba(255,255,255,0.15)',
              }}
              >
                <div style={{ padding: '8px 10px', fontSize: 12, color: '#fff', fontWeight: 600, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>AI 换装效果 · {restageStyle}</span>
                  <button
                    className="icon-btn"
                    style={{ color: '#fff', background: 'transparent' }}
                    onClick={() => setRestageResult(null)}
                    title="关闭对比"
                  >
                    <X size={14} />
                  </button>
                </div>
                <img
                  src={restageResult.image_url}
                  alt={`${viewing.pano.room_name} AI 换装效果图`}
                  style={{ width: '100%', height: 160, objectFit: 'cover', display: 'block' }}
                  onError={(e) => { e.currentTarget.style.display = 'none' }}
                />
                <div style={{ padding: '6px 10px', fontSize: 11, color: 'var(--text-dim)' }}>
                  {restageResult.reconstruction_available === false
                    ? '效果图预览 · AI 生成非实景（不做 2D→3D）'
                    : 'AI 换装效果图（实景结构保留）'}
                </div>
              </div>
            )}
            {viewing.pano.content_source === 'effect' ? (
              <div style={{ position: 'absolute', bottom: 14, left: '50%', transform: 'translateX(-50%)', color: 'rgba(255,255,255,0.75)', fontSize: 12 }}>
                静态效果图预览 · 无 360° 交互（实景 360° 漫游查看 actual 全景）
              </div>
            ) : (
              <div style={{ position: 'absolute', bottom: 14, left: '50%', transform: 'translateX(-50%)', color: 'rgba(255,255,255,0.75)', fontSize: 12 }}>
                拖拽环视 · 滚轮缩放 · 点击 ★ 热点跳转 · 点击 💡 设备控制
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
