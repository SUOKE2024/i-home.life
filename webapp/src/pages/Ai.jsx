import React, { useEffect, useRef, useState } from 'react'
import { Send, Square, Bot, ScanLine } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { streamChat, listProjects } from '../lib/api'

export default function AiPage() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [projects, setProjects] = useState([])
  const [projectId, setProjectId] = useState('')
  const [card, setCard] = useState(null)   // 当前回复的富卡片（ar_scan_trigger 等）
  const abortRef = useRef(null)
  const listRef = useRef(null)

  useEffect(() => {
    let on = true
    listProjects().then((r) => {
      if (on && r.isSuccess) setProjects(r.data || [])
    })
    return () => { on = false }
  }, [])

  const scrollToBottom = () => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }
  useEffect(scrollToBottom, [messages, busy])

  const send = async () => {
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    setError(null)
    setCard(null)
    setMessages((m) => [...m, { role: 'user', content: text }])
    setBusy(true)

    const ctrl = new AbortController()
    abortRef.current = ctrl
    let acc = ''

    try {
      await streamChat(
        { message: text, projectId: projectId || null },
        (evt) => {
          if (evt.event === 'meta') {
            // 富卡片：ar_scan_trigger 等 message_type + card_payload
            if (evt.data?.card_payload) {
              setCard({ type: evt.data.message_type || 'text', payload: evt.data.card_payload })
            }
          } else if (evt.event === 'token' || evt.event === 'message') {
            const chunk = evt.data?.text ?? evt.data?.content ?? (typeof evt.data === 'string' ? evt.data : '')
            if (chunk) {
              acc += chunk
              setMessages((m) => {
                const last = m[m.length - 1]
                if (last && last.role === 'assistant' && last.raw === true) {
                  return [...m.slice(0, -1), { role: 'assistant', content: last.content + chunk }]
                }
                return [...m, { role: 'assistant', content: chunk, raw: true }]
              })
            }
          } else if (evt.event === 'done') {
            const finalText = evt.data?.text ?? evt.data?.content ?? evt.data?.reply
            if (finalText && finalText !== acc) {
              setMessages((m) => [...m, { role: 'assistant', content: finalText }])
            }
          } else if (evt.event === 'error') {
            setError(evt.data?.message || evt.data?.detail || 'AI 响应出错')
          }
        },
        ctrl.signal,
      )
    } catch (e) {
      if (e.name !== 'AbortError') {
        setError(e.message || 'AI 服务暂不可用')
      }
    } finally {
      setBusy(false)
      abortRef.current = null
    }
  }

  const stop = () => {
    if (abortRef.current) abortRef.current.abort()
    setBusy(false)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - var(--topbar-h) - 96px)', minHeight: 420 }}>
      <div className="page-head">
        <div>
          <h2>AI 管家</h2>
          <div className="desc">自然语言调度 22 个专业智能体 · 设计/预算/采购/施工/质检/结算全链路</div>
        </div>
        <select className="select" value={projectId} onChange={(e) => setProjectId(e.target.value)} style={{ width: 200 }}>
          <option value="">全项目（不限定）</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>{p.name || p.id}</option>
          ))}
        </select>
      </div>

      {/* 消息区 */}
      <div
        ref={listRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          padding: '4px 2px',
        }}
      >
        {messages.length === 0 && !busy && (
          <div className="empty" style={{ flex: 1 }}>
            <Bot size={40} className="amber-text" />
            <div style={{ maxWidth: 420, lineHeight: 1.7 }}>
              <p>你好，我是索克家居 AI 管家。可以这样问我：</p>
              <p className="dim" style={{ fontSize: 12 }}>
                「帮我制定 100㎡ 三居室的装修预算」<br />
                「生成施工计划并按周排期」<br />
                「检查防水验收清单」<br />
                「对比两家装修公司的结算方案」
              </p>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
            <div
              style={{
                maxWidth: '78%',
                padding: '10px 14px',
                borderRadius: 12,
                fontSize: 13.5,
                lineHeight: 1.65,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                background: msg.role === 'user' ? 'var(--accent-dim)' : 'var(--bg-elev)',
                border: msg.role === 'user' ? 'none' : '1px solid var(--border)',
                color: msg.role === 'user' ? 'var(--accent-text)' : 'var(--text)',
              }}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {card && card.type === 'ar_scan_trigger' && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div
              style={{
                maxWidth: '78%', padding: 12, borderRadius: 12,
                background: 'var(--accent-dim)', border: '1px solid var(--accent)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <ScanLine size={16} className="ico" />
                <b style={{ fontSize: 13.5 }}>{card.payload.title || 'AR 空间测量'}</b>
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--text-sub)', lineHeight: 1.6 }}>
                {card.payload.prompt}
              </div>
              {(card.payload.supported_features?.length > 0) && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, margin: '8px 0' }}>
                  {card.payload.supported_features.map((f) => (
                    <span key={f} className="badge" style={{ background: 'var(--border)', color: 'var(--text-sub)', fontSize: 11 }}>
                      {f}
                    </span>
                  ))}
                </div>
              )}
              <button
                className="btn btn--primary"
                style={{ marginTop: 8, width: '100%' }}
                onClick={() => navigate('/ar-scan')}
              >
                <ScanLine size={15} /> 开始 AR 量房
              </button>
            </div>
          </div>
        )}

        {busy && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 12, background: 'var(--bg-elev)', border: '1px solid var(--border)' }}>
              <Bot size={15} className="amber-text" />
              <span style={{ fontSize: 13, color: 'var(--text-sub)' }}>AI 思考中…</span>
            </div>
          </div>
        )}

        {error && (
          <div style={{ padding: '10px 14px', borderRadius: 12, background: 'var(--red-dim)', color: 'var(--red)', fontSize: 13 }}>
            {error}
          </div>
        )}
      </div>

      {/* 输入区 */}
      <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
        <textarea
          className="textarea"
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send()
            }
          }}
          placeholder="输入问题，Enter 发送（Shift+Enter 换行）"
          style={{ flex: 1, minHeight: 48 }}
        />
        {busy ? (
          <button className="btn" onClick={stop} title="停止生成">
            <Square size={15} /> 停止
          </button>
        ) : (
          <button className="btn btn--primary" onClick={send} disabled={!input.trim()}>
            <Send size={15} /> 发送
          </button>
        )}
      </div>
    </div>
  )
}
