import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getDeviceOverlay, deviceCommand, sceneExecute } from '../lib/api'
import useProjectSocket from './useProjectSocket'

/**
 * useDeviceOverlay — P0 设备热点联动 hook
 *
 * - 加载项目 3D 设备图层（设备锚点 + 关联场景 + 最近传感器快照）
 * - 实时推送：WS 订阅 smart.device.state / scene.triggered（StateSyncHook）
 * - 降级纪律：WS 不可用时退化为 30s 轮询，恢复推送后自动停止轮询
 * - sendCommand / triggerScene：命令下发时设备热点进入「触发中闪烁」，返回 action_status 诚实标注
 * - 场景触发后相关设备「联动高亮」+ sceneFlash（最近执行结果，供 SceneTriggerOverlay 展示）
 */
const FLASH_MS = 2500 // 激活/高亮动画时长
const POLL_MS = 30_000 // 轮询兜底间隔（WS 降级）

export default function useDeviceOverlay(projectId) {
  const [devices, setDevices] = useState([])
  const [latestSensor, setLatestSensor] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeIds, setActiveIds] = useState([]) // 触发中闪烁 / 联动高亮设备
  const [sceneFlash, setSceneFlash] = useState(null) // 最近场景执行结果
  const timerRef = useRef(null)
  const flashTimersRef = useRef([])

  const refresh = useCallback(async () => {
    if (!projectId) {
      setDevices([])
      setLatestSensor(null)
      return
    }
    setLoading(true)
    setError(null)
    const r = await getDeviceOverlay(projectId)
    if (!r.isSuccess) {
      setError(r.error || '加载设备图层失败')
      // 失败不清空旧数据（降级：保留上次状态）
    } else {
      const data = r.data || {}
      // 后端返回 snake_case，转换为前端组件契约字段（deviceId/sceneIds/room_name）
      setDevices(Array.isArray(data.devices)
        ? data.devices.map((d) => ({
            deviceId: d.device_id,
            name: d.name,
            type: d.type,
            room_name: d.room_name,
            status: d.status,
            yaw: d.yaw,
            pitch: d.pitch,
            state: d.state || null,
            sceneIds: d.scene_ids || [],
          }))
        : [])
      setLatestSensor(data.latest_sensor || null)
    }
    setLoading(false)
  }, [projectId])

  /** 设备热点进入激活动画（触发中闪烁 / 场景联动高亮），FLASH_MS 后自动恢复 */
  const flashDevices = useCallback((ids) => {
    const list = (ids || []).filter(Boolean)
    if (list.length === 0) return
    setActiveIds((prev) => [...new Set([...prev, ...list])])
    const t = setTimeout(() => {
      setActiveIds((prev) => prev.filter((id) => !list.includes(id)))
    }, FLASH_MS)
    flashTimersRef.current.push(t)
  }, [])

  /** 记录场景执行结果（SceneTriggerOverlay 浮层），FLASH_MS 后自动关闭 */
  const showSceneFlash = useCallback(({ sceneId, sceneName, actions }) => {
    const list = actions || []
    const status = list.length > 0 && list.every((a) => a.action_status === 'success')
      ? 'success'
      : list.some((a) => a.action_status === 'failed')
        ? 'failed'
        : 'pending'
    setSceneFlash({ sceneId, sceneName, status, actions: list })
    const t = setTimeout(() => setSceneFlash(null), FLASH_MS + 500)
    flashTimersRef.current.push(t)
  }, [])

  // ── WS 推送（StateSyncHook）：事件处理 + 连接状态 ──
  const handlersRef = useRef({})
  handlersRef.current = {
    'smart.device.state': (data) => {
      const { device_id: deviceId, action_status: status, state } = data || {}
      if (deviceId && state) {
        // 真机状态推送：仅更新该设备实时状态（保留激活动画期间的其他字段）
        setDevices((prev) => prev.map((d) => (d.deviceId === deviceId ? { ...d, state } : d)))
      }
      // 命令执行中 → 热点闪烁；状态稳定后由 FLASH_MS 自动恢复
      if (deviceId && status) flashDevices([deviceId])
    },
    'scene.triggered': (data) => {
      const actions = data?.result?.actions || []
      flashDevices(actions.map((a) => a.device_id).filter(Boolean))
      showSceneFlash({
        sceneId: data?.scene_id,
        sceneName: data?.scene_name || data?.scene_id,
        actions,
      })
    },
  }
  const wsConnected = useProjectSocket(projectId, handlersRef)

  // 轮询兜底：WS 未连接时 30s 轮询，推送恢复后自动停止
  useEffect(() => {
    refresh()
    if (wsConnected) return undefined
    timerRef.current = setInterval(refresh, POLL_MS)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [refresh, wsConnected])

  useEffect(() => () => {
    flashTimersRef.current.forEach(clearTimeout)
  }, [])

  /** 发送设备命令（返回 action_status: pending/success/failed） */
  const sendCommand = useCallback(async (device, action, params = {}) => {
    flashDevices([device.deviceId])
    const r = await deviceCommand(device.deviceId, {
      action, params, source: 'vr_overlay',
    })
    if (r.isSuccess) {
      await refresh() // 刷新状态（若桥接返回成功，状态色更新）
    }
    return r
  }, [refresh, flashDevices])

  /** 触发关联场景（一键场景）：相关设备联动高亮 + 记录执行结果 */
  const triggerScene = useCallback(async (sceneId) => {
    const r = await sceneExecute(sceneId, 'vr_overlay')
    if (r.isSuccess) {
      await refresh()
      const actions = r.data?.actions || []
      flashDevices(actions.map((a) => a.device_id).filter(Boolean))
      showSceneFlash({
        sceneId,
        sceneName: r.data?.scene_name || sceneId,
        actions,
      })
    }
    return r
  }, [refresh, flashDevices, showSceneFlash])

  // devices 附加激活标志（驱动 3D 热点闪烁/高亮动画）
  const devicesWithActivating = useMemo(
    () => devices.map((d) => ({ ...d, activating: activeIds.includes(d.deviceId) })),
    [devices, activeIds],
  )

  return {
    devices: devicesWithActivating,
    latestSensor, loading, error, refresh,
    sendCommand, triggerScene, sceneFlash,
    wsConnected,
  }
}
