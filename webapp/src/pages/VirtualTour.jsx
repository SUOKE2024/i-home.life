import React, { useEffect, useState, useCallback } from 'react'
import { X, Rotate3D } from 'lucide-react'
import { Spinner, Empty, ErrorBox } from '../components/ui'
import PanoramaViewer from '../components/PanoramaViewer'
import DeviceCommandPanel from '../components/DeviceCommandPanel'
import SceneTriggerOverlay from '../components/SceneTriggerOverlay'
import useDeviceOverlay from '../hooks/useDeviceOverlay'
import { listProjects, getVRPanoramas } from '../lib/api'

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
          <div className="desc">360° 全景看房 · 拖拽环视 / 滚轮缩放 / 点击热点跳转</div>
        </div>
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
            const rendered = !!p.image_url
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
                    {p.panorama_type === 'equirectangular' ? '球面全景' : p.panorama_type || '-'} · {p.resolution} · {p.hotspots?.length ?? 0} 热点
                  </div>
                  <div style={{ marginTop: 10 }}>
                    <button
                      className="btn"
                      style={{ width: '100%' }}
                      disabled={!rendered}
                      onClick={() => openViewer(p)}
                    >
                      {rendered ? '进入 360° 全景' : '等待渲染'}
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
            <b style={{ flex: 1 }}>{viewing.pano.room_name} · 360° 全景</b>
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
            <div style={{ position: 'absolute', bottom: 14, left: '50%', transform: 'translateX(-50%)', color: 'rgba(255,255,255,0.75)', fontSize: 12 }}>
              拖拽环视 · 滚轮缩放 · 点击 ★ 热点跳转 · 点击 💡 设备控制
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
