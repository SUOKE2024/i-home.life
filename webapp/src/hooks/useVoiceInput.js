import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * useVoiceInput — Web 麦克风语音输入
 *
 * getUserMedia 申请麦克风权限 + Web Speech API 浏览器端转写，
 * 转写结果经 onTranscript 回调交回调用方（由调用方复用后端语音端点）。
 * 转写走浏览器内置能力，后端仅负责意图分类 + 回复（诚实分工，不伪造流式识别）。
 */
export default function useVoiceInput({ onTranscript, onError } = {}) {
  const [listening, setListening] = useState(false)
  const [supported] = useState(
    () => !!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window),
  )
  const recRef = useRef(null)
  const streamRef = useRef(null)

  const stop = useCallback(() => {
    if (recRef.current) {
      try { recRef.current.stop() } catch { /* noop */ }
      recRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    setListening(false)
  }, [])

  const start = useCallback(async () => {
    if (!supported) {
      onError?.('当前浏览器不支持语音识别（需 Chrome/Edge）')
      return
    }
    // 1. 显式调用 getUserMedia 申请麦克风权限（先拿到流，避免识别器启动竞态）
    try {
      streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      onError?.('麦克风权限被拒绝或不可用')
      return
    }

    // 2. 浏览器端语音转写
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec = new SR()
    rec.lang = 'zh-CN'
    rec.continuous = false
    rec.interimResults = false
    rec.onresult = (ev) => {
      const text = Array.from(ev.results || [])
        .map((r) => r[0]?.transcript || '')
        .join('')
        .trim()
      if (text) onTranscript?.(text)
    }
    rec.onerror = (ev) => {
      onError?.(`语音识别失败：${ev.error || '未知错误'}`)
    }
    rec.onend = () => stop()
    recRef.current = rec

    try {
      rec.start()
      setListening(true)
    } catch {
      stop()
      onError?.('语音识别启动失败')
    }
  }, [supported, onTranscript, onError, stop])

  useEffect(() => () => stop(), [stop])

  return { listening, supported, start, stop }
}
