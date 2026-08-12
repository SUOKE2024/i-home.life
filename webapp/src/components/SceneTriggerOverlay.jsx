import React from 'react'

/**
 * SceneTriggerOverlay — 3D 漫游中的场景联动高亮浮层（P0 设备热点联动）
 *
 * - 场景触发后展示最近执行结果（sceneName + action_status 诚实标注）
 * - status: pending(生态桥未接真机，待执行) / success / failed
 * - 相关设备热点的「联动高亮」由 useDeviceOverlay.activating + PanoramaViewer 动画承担
 */
const STATUS_LABELS = {
  pending: ['场景触发，待设备执行（生态桥未接真机）', 'amber'],
  success: ['场景执行成功', 'green'],
  failed: ['场景执行失败', 'red'],
}

export default function SceneTriggerOverlay({ flash }) {
  if (!flash) return null
  const [label, tone] = STATUS_LABELS[flash.status] || STATUS_LABELS.pending
  const colors = {
    amber: 'rgba(250, 200, 60, 0.14)', green: 'rgba(34, 197, 94, 0.14)', red: 'rgba(220, 60, 60, 0.14)',
    text: { amber: 'var(--text-dim)', green: 'var(--success, #22c55e)', red: 'var(--danger, #dc3c3c)' }[tone],
  }
  const ok = flash.actions.filter((a) => a.action_status === 'success').length
  return (
    <div
      style={{
        position: 'absolute', left: 16, bottom: 44, zIndex: 30, maxWidth: 320,
        background: 'rgba(20, 24, 32, 0.85)', border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: 10, padding: '8px 12px', fontSize: 12, color: '#fff',
        backdropFilter: 'blur(4px)',
      }}
    >
      <div style={{ fontWeight: 600 }}>⚡ {flash.sceneName}</div>
      <div style={{ color: colors.text, marginTop: 3 }}>{label}</div>
      {flash.actions.length > 0 && (
        <div style={{ opacity: 0.75, marginTop: 3 }}>
          {flash.actions.length} 个动作 · {ok}/{flash.actions.length} 成功
        </div>
      )}
    </div>
  )
}
