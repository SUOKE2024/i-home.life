import { useCallback, useState } from 'react'
import { uploadSensorSnapshot } from '../lib/api'

/**
 * useGeolocation — Web 定位 + 上传后端传感器快照
 *
 * navigator.geolocation.getCurrentPosition 获取真实坐标，
 * 复用后端 /api/sensors/snapshot 落库（platform=web）。
 * 仅上传真实 GPS 读数，不伪造环境量（temperature/humidity/light_lux 恒缺省）。
 */
export default function useGeolocation() {
  const [locating, setLocating] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const locate = useCallback(async () => {
    if (!('geolocation' in navigator)) {
      setError('当前浏览器不支持定位')
      return
    }
    setLocating(true)
    setError(null)
    setResult(null)

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude, accuracy, altitude } = pos.coords
        const r = await uploadSensorSnapshot({
          gps: {
            latitude,
            longitude,
            accuracy,
            altitude: altitude ?? null,
            available: true,
          },
          timestamp: new Date().toISOString(),
          platform: 'web',
        })
        setLocating(false)
        if (r.isSuccess) {
          setResult({ latitude, longitude, accuracy, sensors_count: r.data?.sensors_count ?? 1 })
        } else {
          setError(r.error || '定位上报失败')
        }
      },
      (err) => {
        setLocating(false)
        setError(`定位失败：${err.message || '未知错误'}`)
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    )
  }, [])

  return { locating, result, error, locate }
}
