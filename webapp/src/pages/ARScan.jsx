import React, { useEffect, useState, useCallback } from 'react'
import {
  Smartphone, Ruler, ShieldCheck, Play, ScanLine, Plus, Layers, Crosshair, Home,
} from 'lucide-react'
import { Spinner, ErrorBox, Empty } from '../components/ui'
import {
  arDeviceCapability, listProjects, createARScanSession, listARSessions,
  startARScan, processARScan, getARScanAccuracy, addARMeasurementPoint, applyARScanSession,
} from '../lib/api'

const METHOD_META = {
  lidar: { label: 'LiDAR 激光扫描', desc: 'iPhone Pro / iPad Pro 专属，厘米级精度' },
  visual_slam: { label: '视觉 SLAM', desc: 'ARKit / ARCore / AR Engine' },
  photogrammetry: { label: '照片建模', desc: '多角度拍照重建房间结构' },
  manual: { label: '手动测量', desc: '钢尺 / 激光测距仪录入' },
}

const STATUS_META = {
  created: ['已创建', 'sky'],
  scanning: ['扫描中', 'amber'],
  uploaded: ['已上传', 'sky'],
  processing: ['处理中', 'amber'],
  completed: ['已完成', 'green'],
  failed: ['失败', 'red'],
}

const ACCURACY_META = {
  high: ['优秀', 'green'],
  medium: ['合格', 'amber'],
  low: ['偏低', 'red'],
  unknown: ['待校准', 'gray'],
}

export default function ARScanPage() {
  const [projects, setProjects] = useState([])
  const [projectId, setProjectId] = useState('')
  const [cap, setCap] = useState(null)
  const [capLoading, setCapLoading] = useState(true)
  const [sessions, setSessions] = useState([])
  const [sessionsLoading, setSessionsLoading] = useState(false)

  // 当前量房会话 + 处理结果 + 精度报告
  const [active, setActive] = useState(null)          // ScanSession
  const [result, setResult] = useState(null)          // process 返回
  const [accuracy, setAccuracy] = useState(null)      // 精度报告
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // 手动测量校准点表单
  const [ptLabel, setPtLabel] = useState('主卧对角线')
  const [ptAr, setPtAr] = useState('')
  const [ptRef, setPtRef] = useState('')

  const loadSessions = useCallback(async (pid) => {
    if (!pid) { setSessions([]); return }
    setSessionsLoading(true)
    const r = await listARSessions(pid)
    setSessions(r.isSuccess ? (r.data || []) : [])
    setSessionsLoading(false)
  }, [])

  // 初始化：项目列表 + 设备能力检测
  useEffect(() => {
    ;(async () => {
      setCapLoading(true)
      const pr = await listProjects()
      const list = pr.isSuccess && Array.isArray(pr.data) ? pr.data : []
      setProjects(list)
      const target = list[0]?.id || ''
      setProjectId(target)
      if (target) loadSessions(target)

      // Web 端能力探测：摄像头 + IMU（尽力而为）
      let cameraOk = false
      let gyroOk = false
      try {
        const devices = await navigator.mediaDevices?.enumerateDevices?.()
        cameraOk = !!devices?.some((d) => d.kind === 'videoinput')
      } catch { /* 忽略 */ }
      gyroOk = !!('DeviceOrientationEvent' in window) || !!('DeviceMotionEvent' in window)
      const r = await arDeviceCapability({
        platform: 'web',
        supports_photogrammetry: true,
        has_gyroscope: gyroOk,
        has_accelerometer: gyroOk,
        camera_resolution: cameraOk ? 'auto' : 'none',
      })
      setCap(r.isSuccess ? r.data : null)
      if (!r.isSuccess) setError(r.error || '设备能力检测失败，无法继续量房')
      setCapLoading(false)
    })()
  }, [loadSessions])

  const switchProject = (id) => {
    setProjectId(id)
    setActive(null)
    setResult(null)
    setAccuracy(null)
    loadSessions(id)
  }

  const refreshAccuracy = async (sessionId) => {
    const r = await getARScanAccuracy(sessionId)
    if (r.isSuccess) setAccuracy(r.data)
  }

  // 步骤 1：新建量房会话
  const createSession = async () => {
    if (!projectId || busy) return
    setBusy(true)
    setError(null)
    const r = await createARScanSession({
      project_id: projectId,
      name: 'AR 量房 · 全屋扫描',
      platform: 'web',
      requested_method: cap?.recommended_method || 'manual',
      device_capability: {
        platform: 'web',
        supports_photogrammetry: true,
        has_gyroscope: cap?.available_methods?.includes('visual_slam') || false,
      },
      wall_height: 2.8,
    })
    if (!r.isSuccess) {
      setError(r.error || '创建扫描会话失败')
    } else {
      setActive(r.data)
      setResult(null)
      setAccuracy(null)
      loadSessions(projectId)
    }
    setBusy(false)
  }

  // 步骤 2：开始扫描 → 处理扫描（照片建模走 mock 解析，诚实标注）
  const runScan = async (sessionId) => {
    if (busy) return
    setBusy(true)
    setError(null)
    const s = await startARScan(sessionId)
    if (!s.isSuccess) {
      setError(s.error || '开始扫描失败')
      setBusy(false)
      return
    }
    const p = await processARScan(sessionId, {
      model_format: 'glb',
      scan_points_count: 50000,
      scan_duration_sec: 120,
    })
    if (!p.isSuccess) {
      setError(p.error || '处理扫描失败')
      setBusy(false)
      return
    }
    setResult(p.data)
    setActive((prev) => (prev ? { ...prev, ...p.data } : prev))
    await refreshAccuracy(sessionId)
    loadSessions(projectId)
    setBusy(false)
  }

  // 步骤 3：添加校准点（手动测量）
  const addPoint = async () => {
    if (!active || busy) return
    const arV = parseFloat(ptAr)
    const refV = parseFloat(ptRef)
    if (!ptLabel.trim() || Number.isNaN(arV) || Number.isNaN(refV)) {
      setError('请填写校准点名称、AR 测量值与参考值')
      return
    }
    setBusy(true)
    setError(null)
    const r = await addARMeasurementPoint({
      session_id: active.id,
      label: ptLabel.trim(),
      room_name: ptLabel.trim(),
      point_type: 'distance',
      ar_value: arV,
      reference_value: refV,
      unit: 'm',
    })
    if (!r.isSuccess) {
      setError(r.error || '添加校准点失败')
    } else {
      setPtAr('')
      setPtRef('')
      await refreshAccuracy(active.id)
    }
    setBusy(false)
  }

  // 步骤 4：应用生成户型（Survey）
  const applySurvey = async (sessionId) => {
    if (busy) return
    setBusy(true)
    setError(null)
    const r = await applyARScanSession(sessionId)
    if (!r.isSuccess) {
      setError(r.error || '应用生成户型失败')
    } else {
      setActive((prev) => (prev ? { ...prev, survey_id: r.data?.survey_id } : prev))
      loadSessions(projectId)
    }
    setBusy(false)
  }

  const selectSession = (s) => {
    setActive(s)
    setResult(null)
    setAccuracy(null)
    if (s.status === 'completed') refreshAccuracy(s.id)
  }

  const m = METHOD_META[cap?.recommended_method] || METHOD_META.manual

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>AR 量房</h2>
          <div className="desc">沉浸式空间测量 · 能力检测 → 扫描建模 → 精度校准 → 生成户型</div>
        </div>
        <select className="select" value={projectId} onChange={(e) => switchProject(e.target.value)} style={{ width: 220 }}>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>{p.name || p.id}</option>
          ))}
        </select>
      </div>

      {capLoading && <Spinner label="正在检测设备能力…" />}
      {!capLoading && error && <ErrorBox message={error} onRetry={() => setError(null)} />}

      {!capLoading && cap && (
        <>
          {/* 能力 + 新建量房 */}
          <div className="bento">
            <div className="b-col" style={{ gridColumn: 'span 2' }}>
              <div className="card">
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  <div
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10, flex: 1,
                      padding: '10px 14px', borderRadius: 10,
                      background: 'var(--accent-dim)', border: '1px solid var(--accent)',
                    }}
                  >
                    <Ruler size={18} className="ico" />
                    <div>
                      <b>{m.label}</b>
                      <div style={{ fontSize: 11.5, color: 'var(--text-sub)' }}>{m.desc}</div>
                    </div>
                  </div>
                  <button className="btn btn--primary" onClick={createSession} disabled={busy || !projectId}>
                    <Plus size={15} /> 新建量房
                  </button>
                </div>

                <div style={{ fontSize: 12.5, color: 'var(--text-sub)', marginTop: 12 }}>
                  可用方法：{(cap.available_methods || []).map((x) => METHOD_META[x]?.label || x).join(' · ')}
                  <span style={{ marginLeft: 10 }}>
                    降级链：{(cap.fallback_chain || []).map((x) => METHOD_META[x]?.label || x).join(' → ')}
                  </span>
                </div>
              </div>
            </div>

            <div className="b-col">
              <div className="card">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Smartphone size={16} className="ico" />
                  <b style={{ fontSize: 13.5 }}>App 获得完整 LiDAR 体验</b>
                </div>
                <p style={{ fontSize: 12.5, color: 'var(--text-sub)', lineHeight: 1.7, margin: '8px 0' }}>
                  Web 端支持照片建模与手动测量；移动端 App（iOS/Android/鸿蒙）支持 LiDAR 级 AR 扫描。
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                  <ShieldCheck size={15} className="ico" style={{ color: 'var(--green)' }} />
                  <span>精度校验：RMS &lt; 2cm 优秀 · 2~5cm 合格</span>
                </div>
              </div>
            </div>
          </div>

          {/* 当前会话工作台 */}
          {active && (
            <div className="card" style={{ marginTop: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <ScanLine size={18} className="ico" />
                <b style={{ flex: 1 }}>量房会话 · {active.name || active.id}</b>
                {(() => {
                  const st = STATUS_META[active.status] || ['未知', 'gray']
                  return <span className="badge" style={{ background: `var(--${st[1]}-dim)`, color: `var(--${st[1]})` }}>{st[0]}</span>
                })()}
              </div>

              {/* 步骤引导 */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, margin: '14px 0' }}>
                <button className="btn" onClick={() => runScan(active.id)} disabled={busy || active.status === 'completed'}>
                  <Play size={15} /> {active.status === 'completed' ? '已处理' : '开始扫描并处理'}
                </button>
                {active.status === 'completed' && (
                  <button className="btn" onClick={() => applySurvey(active.id)} disabled={busy || active.survey_id}>
                    <Home size={15} /> {active.survey_id ? '已生成户型' : '生成户型'}
                  </button>
                )}
              </div>

              {busy && <Spinner label="扫描处理中…" />}

              {/* 处理结果 */}
              {result && (
                <div className="bento" style={{ marginTop: 4 }}>
                  <div className="b-col">
                    <div className="card">
                      <div style={{ fontSize: 12.5, color: 'var(--text-dim)' }}>解析房间</div>
                      <div style={{ fontSize: 26, fontWeight: 800, margin: '4px 0' }}>{result.room_count}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-sub)' }}>房间 · 总面积 {result.total_area} ㎡</div>
                    </div>
                  </div>
                  <div className="b-col">
                    <div className="card">
                      <div style={{ fontSize: 12.5, color: 'var(--text-dim)' }}>墙面特征</div>
                      <div style={{ fontSize: 26, fontWeight: 800, margin: '4px 0' }}>{result.wall_features_added}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-sub)' }}>
                        门窗 {result.parsed_model?.door_count ?? 0} · 窗 {result.parsed_model?.window_count ?? 0}
                      </div>
                    </div>
                  </div>
                  <div className="b-col">
                    <div className="card">
                      <div style={{ fontSize: 12.5, color: 'var(--text-dim)' }}>点云下采样</div>
                      <div style={{ fontSize: 26, fontWeight: 800, margin: '4px 0' }}>{result.point_cloud?.downsampled_points ?? 0}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-sub)' }}>体素 2cm · {result.point_cloud?.normals_method ?? '-'}</div>
                    </div>
                  </div>
                </div>
              )}
              {result && Array.isArray(result.parse_warnings) && result.parse_warnings.length > 0 && (
                <div style={{ fontSize: 12, color: '#b45309', marginTop: 8 }}>
                  解析说明：{result.parse_warnings.join('；')}
                </div>
              )}

              {/* 精度报告 + 手动校准 */}
              {active.status === 'completed' && (
                <div className="bento" style={{ marginTop: 4 }}>
                  <div className="b-col" style={{ gridColumn: 'span 2' }}>
                    <div className="card">
                      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>手动测量校准</div>
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <input className="input" style={{ flex: 1, minWidth: 140 }} placeholder="校准点（如 主卧对角线）"
                          value={ptLabel} onChange={(e) => setPtLabel(e.target.value)} />
                        <input className="input" style={{ width: 120 }} placeholder="AR 值 (m)"
                          value={ptAr} onChange={(e) => setPtAr(e.target.value)} inputMode="decimal" />
                        <input className="input" style={{ width: 120 }} placeholder="参考值 (m)"
                          value={ptRef} onChange={(e) => setPtRef(e.target.value)} inputMode="decimal" />
                        <button className="btn" onClick={addPoint} disabled={busy}>
                          <Crosshair size={15} /> 添加校准点
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="b-col">
                    <div className="card">
                      <div style={{ fontSize: 12.5, color: 'var(--text-dim)' }}>RMS 误差</div>
                      <div style={{ fontSize: 26, fontWeight: 800, margin: '4px 0' }}>
                        {accuracy ? `${accuracy.rms_error_cm} cm` : '—'}
                      </div>
                      {(() => {
                        const a = ACCURACY_META[accuracy?.accuracy_level] || ['待校准', 'gray']
                        return <span className="badge" style={{ background: `var(--${a[1]}-dim)`, color: `var(--${a[1]})` }}>{a[0]}</span>
                      })()}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 会话列表 */}
          <div className="card" style={{ marginTop: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <Layers size={16} className="ico" />
              <b style={{ fontSize: 13.5 }}>量房记录</b>
            </div>
            {sessionsLoading ? (
              <Spinner label="加载量房记录…" />
            ) : sessions.length === 0 ? (
              <Empty message="暂无量房记录，点击「新建量房」开始" />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {sessions.map((s) => {
                  const st = STATUS_META[s.status] || ['未知', 'gray']
                  return (
                    <button
                      key={s.id}
                      className="btn"
                      style={{ justifyContent: 'flex-start', width: '100%', textAlign: 'left' }}
                      onClick={() => selectSession(s)}
                    >
                      <ScanLine size={15} className="dim" />
                      <span style={{ flex: 1, fontSize: 13 }}>{s.name || s.id}</span>
                      <span className="mono dim" style={{ fontSize: 11 }}>{s.total_area || 0}㎡ · {s.room_count || 0} 房间</span>
                      <span className="badge" style={{ background: `var(--${st[1]}-dim)`, color: `var(--${st[1]})` }}>{st[0]}</span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
