import { useEffect, useRef, useState } from 'react'
import { getToken } from '../lib/api'

/**
 * useProjectSocket — 项目级 WebSocket 订阅（P0 StateSyncHook 落地）
 *
 * - 连接 /ws/{project_id}?token=（PASETO 认证，Nginx/Vite 均已反代 Upgrade）
 * - 服务端事件格式：{"event": "smart.device.state" | "scene.triggered" | ..., "data": {...}}
 * - 心跳保活：收到服务端 ping 自动回 pong（服务端 RECEIVE_TIMEOUT 后探测，不回会被断开）
 * - 断线自动重连（指数退避，最多 5 次后放弃，由调用方降级轮询）
 * - handlers 以 ref 传入，事件处理函数变化不重建连接
 */
const MAX_RETRY = 5
const RETRY_BASE_MS = 2000

export default function useProjectSocket(projectId, handlersRef) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const retryRef = useRef(0)
  const timerRef = useRef(null)

  useEffect(() => {
    if (!projectId) {
      setConnected(false)
      return undefined
    }
    let closed = false

    const connect = () => {
      if (closed) return
      const token = getToken()
      if (!token) {
        setConnected(false)
        return
      }
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(
        `${proto}://${window.location.host}/ws/${projectId}?token=${encodeURIComponent(token)}`,
      )
      wsRef.current = ws
      ws.onopen = () => {
        retryRef.current = 0
        setConnected(true)
      }
      ws.onmessage = (ev) => {
        let msg
        try {
          msg = JSON.parse(ev.data)
        } catch {
          return
        }
        const { event, data } = msg || {}
        if (event === 'ping') {
          // 服务端心跳探测 → 回 pong 保活
          ws.send(JSON.stringify({ event: 'pong', data: {} }))
          return
        }
        if (event === 'pong') return
        handlersRef.current?.[event]?.(data || {})
      }
      ws.onclose = () => {
        if (closed) return
        setConnected(false)
        if (retryRef.current < MAX_RETRY) {
          const delay = RETRY_BASE_MS * Math.min(2 ** retryRef.current, 16)
          retryRef.current += 1
          timerRef.current = setTimeout(connect, delay)
        }
      }
      ws.onerror = () => {
        try {
          ws.close()
        } catch {
          /* noop */
        }
      }
    }

    connect()
    return () => {
      closed = true
      clearTimeout(timerRef.current)
      try {
        wsRef.current?.close()
      } catch {
        /* noop */
      }
      setConnected(false)
    }
  }, [projectId])

  return connected
}
