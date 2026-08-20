import React, { useEffect, useRef, useState } from 'react'
import { Send, Square, Bot, ScanLine, Mic } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { streamChat, listProjects, processVoice } from '../lib/api'
import useVoiceInput from '../hooks/useVoiceInput'

/* 后端 /api/agents/chat/stream 的 agent_type → 身份（中文名 + 身份色 token，对齐 DESIGN.md Agent 身份色） */
const AGENT_META = {
  // 总管家（master 金）
  orchestrator: { label: '总管家', color: 'var(--agent-master)' },
  general: { label: '总管家', color: 'var(--agent-master)' },
  // 设计类（design 蓝）
  designer: { label: '设计顾问', color: 'var(--agent-design)' },
  kitchen: { label: '厨房设计', color: 'var(--agent-design)' },
  bathroom: { label: '卫浴设计', color: 'var(--agent-design)' },
  lighting: { label: '灯光设计', color: 'var(--agent-design)' },
  smart_home: { label: '智能家居', color: 'var(--agent-design)' },
  scene_automation: { label: '场景自动化', color: 'var(--agent-design)' },
  custom_furniture: { label: '定制家具', color: 'var(--agent-design)' },
  soft_furnishing: { label: '软装搭配', color: 'var(--agent-design)' },
  hard_decoration: { label: '硬装设计', color: 'var(--agent-design)' },
  structural: { label: '结构设计', color: 'var(--agent-design)' },
  furniture: { label: '家具选型', color: 'var(--agent-design)' },
  door_window: { label: '门窗方案', color: 'var(--agent-design)' },
  floorplans: { label: '户型图', color: 'var(--agent-design)' },
  vr_panorama: { label: '全景漫游', color: 'var(--agent-design)' },
  sketch_to_3d: { label: '草图转 3D', color: 'var(--agent-design)' },
  cad_import: { label: 'CAD 导入', color: 'var(--agent-design)' },
  ar_measurement: { label: 'AR 量房', color: 'var(--agent-design)' },
  ai_render: { label: 'AI 效果图', color: 'var(--agent-design)' },
  // 预算（budget 绿）
  budget: { label: '预算顾问', color: 'var(--agent-budget)' },
  // 采购（procurement 橙）
  procurement: { label: '采购助手', color: 'var(--agent-procurement)' },
  // 施工（construction 红）
  construction: { label: '施工管家', color: 'var(--agent-construction)' },
  tasks: { label: '任务管理', color: 'var(--agent-construction)' },
  crews: { label: '施工班组', color: 'var(--agent-construction)' },
  takeoff: { label: '工程量算量', color: 'var(--agent-construction)' },
  mep: { label: '水电方案', color: 'var(--agent-construction)' },
  appliance: { label: '家电选型', color: 'var(--agent-construction)' },
  // 质检（quality 青）
  qa_inspector: { label: '质检专员', color: 'var(--agent-quality)' },
  points: { label: '验收要点', color: 'var(--agent-quality)' },
  // 结算（settlement 紫）
  settlement: { label: '结算顾问', color: 'var(--agent-settlement)' },
  change_orders: { label: '变更单', color: 'var(--agent-settlement)' },
  // 支持/运营（support 蓝灰）
  content_publisher: { label: '内容发布', color: 'var(--agent-support)' },
  files: { label: '文件管理', color: 'var(--agent-support)' },
  products: { label: '产品助手', color: 'var(--agent-support)' },
  identity: { label: '实名认证', color: 'var(--agent-support)' },
  notifications: { label: '通知助手', color: 'var(--agent-support)' },
  ifc_export: { label: 'IFC 导出', color: 'var(--agent-support)' },
  voice: { label: '语音助手', color: 'var(--agent-support)' },
  marketing: { label: '营销顾问', color: 'var(--agent-support)' },
  competitor_research: { label: '竞品分析', color: 'var(--agent-support)' },
  growth: { label: '增长顾问', color: 'var(--agent-support)' },
  finance_recon: { label: '财务对账', color: 'var(--agent-support)' },
}
const resolveAgent = (type) => (type && AGENT_META[type]) || null

export default function AiPage() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [projects, setProjects] = useState([])
  const [projectId, setProjectId] = useState('')
  const [card, setCard] = useState(null)   // 当前回复的富卡片（ar_scan_trigger 等）
  const [steps, setSteps] = useState([])   // 后端 thinking_step 进度轨迹（意图分析/Agent 调度）
  const agentRef = useRef(null)            // 当前回复派发的 agent_type（来自 thinking_step/meta）
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
    setSteps([])
    agentRef.current = null
    setMessages((m) => [...m, { role: 'user', content: text }])
    setBusy(true)

    const ctrl = new AbortController()
    abortRef.current = ctrl
    let acc = ''

    try {
      await streamChat(
        { message: text, projectId: projectId || null },
        (evt) => {
          if (evt.event === 'thinking_step') {
            // 后端思考步骤（分析意图 → 调度 Agent），让等待有可见进度
            const content = evt.data?.content || ''
            const agentType = evt.data?.agent_type
            if (agentType) agentRef.current = agentType
            if (content) setSteps((s) => [...s, { content, agentType }])
          } else if (evt.event === 'meta') {
            // 富卡片：ar_scan_trigger 等 message_type + card_payload；agent_type 标记回复身份
            if (evt.data?.agent_type) agentRef.current = evt.data.agent_type
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
                  return [...m.slice(0, -1), { ...last, content: last.content + chunk }]
                }
                return [...m, { role: 'assistant', content: chunk, raw: true, agent: agentRef.current }]
              })
            }
          } else if (evt.event === 'done') {
            const finalText = evt.data?.text ?? evt.data?.content ?? evt.data?.reply
            if (finalText && finalText !== acc) {
              setMessages((m) => [...m, { role: 'assistant', content: finalText, agent: agentRef.current }])
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

  // 麦克风语音：getUserMedia 浏览器端转写 → 复用后端语音端点
  const handleVoiceTranscript = async (text) => {
    setError(null)
    setCard(null)
    setMessages((m) => [...m, { role: 'user', content: text }])
    setBusy(true)
    const r = await processVoice(text, projectId || null)
    setBusy(false)
    if (r.isSuccess && r.data) {
      setMessages((m) => [...m, { role: 'assistant', content: r.data.reply || '（无回复）' }])
    } else {
      setError(r.error || '语音处理失败')
    }
  }

  const { listening, supported: voiceSupported, start: startVoice, stop: stopVoice } = useVoiceInput({
    onTranscript: handleVoiceTranscript,
    onError: (msg) => setError(msg),
  })

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

        {messages.map((msg, i) => {
          const agent = msg.role === 'assistant' ? resolveAgent(msg.agent) : null
          return (
            <div key={i} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <div style={{ maxWidth: '78%' }}>
                {agent && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '0 2px 5px' }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: agent.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 11.5, color: 'var(--text-sub)', letterSpacing: 0.3 }}>{agent.label}</span>
                  </div>
                )}
                <div
                  style={{
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
            </div>
          )
        })}

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
            <div style={{ padding: '10px 14px', borderRadius: 12, background: 'var(--bg-elev)', border: '1px solid var(--border)' }}>
              {steps.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                  {steps.map((s, i) => {
                    const agent = resolveAgent(s.agentType)
                    const active = i === steps.length - 1
                    return (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span
                          style={{
                            width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                            background: active ? (agent?.color || 'var(--accent)') : 'var(--border-strong)',
                          }}
                        />
                        <span style={{ fontSize: 12.5, color: active ? 'var(--text)' : 'var(--text-sub)', lineHeight: 1.5 }}>
                          {s.content}
                        </span>
                      </div>
                    )
                  })}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                    <Bot size={13} className="amber-text" style={{ flexShrink: 0 }} />
                    <span style={{ fontSize: 12.5, color: 'var(--text-sub)' }}>正在生成回复…</span>
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Bot size={15} className="amber-text" />
                  <span style={{ fontSize: 13, color: 'var(--text-sub)' }}>AI 思考中…</span>
                </div>
              )}
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
        <button
          className="btn"
          onClick={listening ? stopVoice : startVoice}
          disabled={!voiceSupported || busy}
          title={voiceSupported ? '语音输入' : '当前浏览器不支持语音识别'}
        >
          <Mic size={15} /> {listening ? '聆听中…' : '语音'}
        </button>
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
