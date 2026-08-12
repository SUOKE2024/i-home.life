import React, { useEffect, useState } from 'react'
import { Smartphone, Camera, Ruler, ShieldCheck, ArrowRight } from 'lucide-react'
import { Spinner, ErrorBox } from '../components/ui'
import { arDeviceCapability } from '../lib/api'

const METHOD_META = {
  lidar: { label: 'LiDAR 激光扫描', desc: 'iPhone Pro / iPad Pro 专属，厘米级精度，3 分钟/100㎡', accuracy: '约 1.0 cm' },
  visual_slam: { label: '视觉 SLAM', desc: 'ARKit / ARCore / AR Engine，无需 LiDAR，5 分钟/100㎡', accuracy: '约 3.0 cm' },
  photogrammetry: { label: '照片建模', desc: '多角度拍照重建，8 分钟/100㎡', accuracy: '约 5.0 cm' },
  manual: { label: '手动测量', desc: '钢尺 / 激光测距仪，10 分钟/100㎡', accuracy: '参考级' },
}

export default function ARScanPage() {
  const [loading, setLoading] = useState(true)
  const [cap, setCap] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    ;(async () => {
      setLoading(true)
      setError(null)
      // Web 端探测：摄像头 + IMU 可用性（尽力而为，失败静默）
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
      if (!r.isSuccess) {
        setError(r.error || '设备能力检测失败')
      } else {
        setCap(r.data)
      }
      setLoading(false)
    })()
  }, [])

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>AR 量房</h2>
          <div className="desc">AI 空间测量 · 设备能力检测 → 降级链引导</div>
        </div>
      </div>

      {loading && <Spinner label="正在检测设备能力…" />}
      {!loading && error && <ErrorBox message={error} />}
      {!loading && cap && (
        <div className="bento">
          <div className="b-col" style={{ gridColumn: 'span 2' }}>
            <div className="card">
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>推荐扫描方式</div>
              <div className="mono" style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 12 }}>
                设备能力检测结果 · 诚实标注
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                {(() => {
                  const m = METHOD_META[cap.recommended_method] || METHOD_META.manual
                  return (
                    <div
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '10px 14px', borderRadius: 10,
                        background: 'var(--accent-dim)', border: '1px solid var(--accent)',
                      }}
                    >
                      <Ruler size={18} className="ico" />
                      <div>
                        <b>{m.label}</b>
                        <div style={{ fontSize: 11.5, color: 'var(--text-sub)' }}>{m.desc}</div>
                      </div>
                      <span className="badge" style={{ background: 'var(--accent-dim)', color: 'var(--accent-text)' }}>
                        {m.accuracy}
                      </span>
                    </div>
                  )
                })()}
              </div>

              <div style={{ fontSize: 14, fontWeight: 700, margin: '16px 0 8px' }}>降级链</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                {(cap.fallback_chain || []).map((method, i) => (
                  <React.Fragment key={method}>
                    <span
                      className="badge"
                      style={{
                        background: i === 0 ? 'var(--accent-dim)' : 'var(--border)',
                        color: i === 0 ? 'var(--accent-text)' : 'var(--text-sub)',
                        padding: '6px 10px',
                      }}
                    >
                      {METHOD_META[method]?.label || method}
                    </span>
                    {i < (cap.fallback_chain || []).length - 1 && <ArrowRight size={14} className="dim" />}
                  </React.Fragment>
                ))}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-dim)', marginTop: 8 }}>
                可用方法：{(cap.available_methods || []).map((m) => METHOD_META[m]?.label || m).join(' · ')}
              </div>
            </div>
          </div>

          <div className="b-col">
            <div className="card">
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Web 端说明</div>
              <div style={{ fontSize: 12.5, color: 'var(--text-sub)', lineHeight: 1.7 }}>
                浏览器无法调用 LiDAR / ARKit / ARCore 原生能力，Web 端可用的测量方式：
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5 }}>
                  <Camera size={15} className="ico" /> 照片建模（逐房间多角度拍摄）
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5 }}>
                  <Ruler size={15} className="ico" /> 手动测量（钢尺 / 激光测距仪录入）
                </div>
              </div>
            </div>
          </div>

          <div className="b-col">
            <div className="card">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Smartphone size={16} className="ico" />
                <b style={{ fontSize: 13.5 }}>推荐使用 App 获得完整体验</b>
              </div>
              <p style={{ fontSize: 12.5, color: 'var(--text-sub)', lineHeight: 1.7, margin: '8px 0' }}>
                移动端 App（iOS / Android / HarmonyOS）支持 LiDAR 级 AR 扫描，自动生成户型并校验精度。
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                <ShieldCheck size={15} className="ico" style={{ color: 'var(--green)' }} />
                <span>精度校验：RMS &lt; 2cm 为优秀（LiDAR），2~5cm 合格（视觉 SLAM）</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
