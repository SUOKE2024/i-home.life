import { useState } from 'react'
import { X } from 'lucide-react'

/**
 * DeviceCommandPanel — 3D 漫游中的设备控制面板（P0 设备热点联动）
 *
 * - 设备信息 + 动作按钮（按 DEVICE_ACTION_WHITELIST 渲染，仅渲染该类型支持的动作）
 * - 关联场景一键触发
 * - action_status 诚实标注：pending(桥接未接真机)/success/failed
 */
const ACTIONS_BY_TYPE = {
  light: [['turn_on', '开灯'], ['turn_off', '关灯'], ['set_brightness', '调光']],
  switch: [['turn_on', '开'], ['turn_off', '关']],
  socket: [['turn_on', '通电'], ['turn_off', '断电']],
  curtain: [['open', '开帘'], ['close', '关帘']],
  speaker: [['play', '播放'], ['pause', '暂停']],
  thermostat: [['set_temperature', '调温'], ['turn_on', '开'], ['turn_off', '关']],
  air_purifier: [['turn_on', '开'], ['turn_off', '关']],
  robot_vacuum: [['start', '开始'], ['return_dock', '回充']],
  camera: [['start_record', '录像'], ['stop_record', '停止']],
  lock: [['lock', '上锁'], ['unlock', '开锁']],
}

// 设备实时状态值 → 可读文案（state 来自聚合层，真机执行成功才非空）
const STATE_LABELS = {
  power: (v) => (v ? '开' : '关'),
  brightness: (v) => `亮度 ${v}%`,
  position: (v) => `开合 ${v}%`,
  volume: (v) => `音量 ${v}`,
  temperature: (v) => `温度 ${v}°C`,
}
const formatState = (s) =>
  Object.entries(s || {})
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => (STATE_LABELS[k] ? STATE_LABELS[k](v) : `${k}: ${v}`))
    .join(' · ')

export default function DeviceCommandPanel({
  device, sensor, onClose, onCommand, onScene,
}) {
  const [busy, setBusy] = useState(null)
  const [result, setResult] = useState(null)

  if (!device) return null

  const actions = ACTIONS_BY_TYPE[device.type] || []
  const online = device.status === 'online' || device.status === 'installed'

  const run = async (key, fn) => {
    setBusy(key)
    setResult(null)
    const r = await fn()
    if (r && r.isSuccess) {
      const d = r.data || {}
      // 场景执行响应无顶层 action_status（在 actions[] 内）→ 按动作状态推导；
      // 设备命令响应有顶层 action_status → 直接取用
      let status = d.action_status
      if (Array.isArray(d.actions) && d.actions.length > 0) {
        const list = d.actions
        status = list.every((a) => a.action_status === 'success')
          ? 'success'
          : list.some((a) => a.action_status === 'failed')
            ? 'failed'
            : 'pending'
      }
      setResult({ status: status || 'ok', note: d.note || null })
    } else {
      setResult({ status: 'failed', note: r?.error || '执行失败' })
    }
    setBusy(null)
  }

  return (
    <div
      style={{
        position: 'absolute', right: 16, top: 16, width: 260, zIndex: 30,
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 12, padding: 14, boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <strong style={{ fontSize: 15 }}>{device.name}</strong>
          <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
            {device.type} · {device.room_name || '-'} ·{' '}
            <span style={{ color: online ? 'var(--success)' : 'var(--text-dim)' }}>
              {online ? '在线' : '离线'}
            </span>
          </div>
          {device.state && Object.keys(device.state).length > 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>
              状态：{formatState(device.state)}
            </div>
          )}
        </div>
        <button
          className="ghost"
          style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}
          onClick={onClose}
          aria-label="关闭"
        >
          <X size={18} />
        </button>
      </div>

      {sensor && (
        <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 8 }}>
          环境：{sensor.temperature != null ? `${sensor.temperature}°C` : '-'} /
          湿度 {sensor.humidity != null ? `${sensor.humidity}%` : '-'}
        </div>
      )}

      {actions.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
          {actions.map(([key, label]) => (
            <button
              key={key}
              className="btn"
              disabled={busy === key}
              onClick={() => run(key, () => onCommand(device, key))}
              style={{ fontSize: 13, padding: '6px 10px' }}
            >
              {busy === key ? '执行中…' : label}
            </button>
          ))}
        </div>
      )}

      {device.sceneIds && device.sceneIds.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 6 }}>一键场景</div>
          {device.sceneIds.map((sid) => (
            <button
              key={sid}
              className="btn btn-primary"
              style={{ width: '100%', marginBottom: 6, fontSize: 13 }}
              disabled={busy === `scene:${sid}`}
              onClick={() => run(`scene:${sid}`, () => onScene(sid))}
            >
              {busy === `scene:${sid}` ? '触发中…' : '触发场景'}
            </button>
          ))}
        </div>
      )}

      {result && (
        <div
          style={{
            marginTop: 10, fontSize: 12, padding: '6px 8px', borderRadius: 6,
            background: result.status === 'failed'
              ? 'rgba(220, 60, 60, 0.12)'
              : result.status === 'success'
                ? 'rgba(34, 197, 94, 0.12)'
                : 'rgba(250, 200, 60, 0.12)',
            color: result.status === 'failed'
              ? 'var(--danger, #dc3c3c)'
              : result.status === 'success'
                ? 'var(--success, #22c55e)'
                : 'var(--text-dim)',
          }}
        >
          {result.status === 'pending'
            ? '已记录触发意图（生态桥接未接真机，待接入后执行）'
            : result.status === 'success'
              ? '执行成功'
              : `执行失败：${result.note || '未知错误'}`}
        </div>
      )}
    </div>
  )
}
