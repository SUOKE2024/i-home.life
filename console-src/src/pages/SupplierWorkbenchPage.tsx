import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../services/api-client';
import { useUser } from '../context/UserContext';
import { SuokeLayout } from '../components/layout';
import type { SseEvent } from '../types/chat';

/**
 * SupplierWorkbenchPage — 供应商工作台（v1.15.4）
 *
 * 供应链/服务商生态的「可管理、可运营 + AI 协助」入口：
 * - 看板：我的产品 / 交付单 / 生效权限码（真实 API，失败诚实显示 —）
 * - 模块：产品/物料/采购交付/资金托管/预算/设置（复用既有页面）
 * - AI 助手：streamChat 路由 ProcurementAgent，预设提示词（寻源/文案/履约/简报）
 *
 * 设计：B 端深色工程台 token（surface1 卡片 / 12px 圆角 / stat-value 等宽数字）。
 */

interface ChatMsg {
  role: 'user' | 'assistant';
  content: string;
}

const PRESET_PROMPTS = [
  { label: '寻源匹配', text: '帮我分析最近的采购寻源需求，并推荐匹配的产品方向' },
  { label: '产品文案', text: '为我的主推产品生成一段 50-150 字的专业卖点文案' },
  { label: '履约答疑', text: '交付单状态流转有哪些环节？签收后如何发起结算？' },
  { label: '经营简报', text: '汇总我的在途订单、待结算金额，并给出履约建议' },
];

const MODULES = [
  { title: '产品管理', desc: '上架 / 编辑我的产品', path: '/products', icon: '📦' },
  { title: '物料管理', desc: '物料维护与报价', path: '/materials', icon: '🧱' },
  { title: '采购与交付', desc: '寻源 / 采购 / 交付链路', path: '/procurement', icon: '🚚' },
  { title: '资金托管', desc: '托管状态与结算', path: '/escrow', icon: '🛡️' },
  { title: '预算', desc: '项目预算查看', path: '/budget', icon: '💰' },
  { title: '设置', desc: '账户与实名认证', path: '/settings', icon: '⚙️' },
];

const cardStyle: React.CSSProperties = {
  background: 'var(--surface1)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  padding: 18,
};

export default function SupplierWorkbenchPage() {
  const { user } = useUser();
  const [stats, setStats] = useState<{ products: number | null; deliveries: number | null; permissions: number | null }>({
    products: null,
    deliveries: null,
    permissions: null,
  });
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  // ── 看板数据（真实 API；失败诚实显示 —，不伪造） ──
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [mine, deliveries, perms] = await Promise.all([
        apiClient.request<unknown[]>('/api/products/mine'),
        apiClient.request<unknown[]>('/api/b2b/delivery'),
        apiClient.request<{ permissions?: string[] }>('/api/auth/me/permissions'),
      ]);
      if (cancelled) return;
      setStats({
        products: mine.isSuccess && mine.data ? mine.data.length : null,
        deliveries: deliveries.isSuccess && deliveries.data ? deliveries.data.length : null,
        permissions: perms.isSuccess && perms.data?.permissions ? perms.data.permissions.length : null,
      });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── AI 助手：streamChat 流式回复（ProcurementAgent） ──
  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: trimmed }, { role: 'assistant', content: '' }]);
    let full = '';
    try {
      const stream = apiClient.streamChat(trimmed, { agentType: 'procurement' });
      for await (const event of stream as AsyncIterable<SseEvent>) {
        if (event.type === 'token' && event.content) {
          full += event.content;
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = { role: 'assistant', content: full };
            return next;
          });
        }
        if (event.type === 'error') {
          if (!full) full = 'AI 助手暂不可用，请稍后重试（诚实降级，未生成占位回复）';
        }
        if (event.type === 'done' && !full) {
          full = '（本次无文本回复）';
        }
      }
    } catch {
      if (!full) full = 'AI 助手请求失败，请稍后重试';
    }
    if (full) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { role: 'assistant', content: full };
        return next;
      });
    }
    setBusy(false);
  };

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages]);

  const stat = (value: number | null) => (
    <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 22, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
      {value === null ? '—' : value}
    </span>
  );

  return (
    <SuokeLayout>
      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 1100, margin: '0 auto' }}>
      <header>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>供应商工作台</h1>
        <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>
          {user ? `${user.name ?? user.phone ?? ''} · 角色 supplier${user.sub_role ? ` · ${user.sub_role}` : ''}` : ''} ·
          供应链/服务商生态 · AI 协助经营
        </div>
      </header>

      {/* 看板（真实数据） */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
        <div style={cardStyle}>
          <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>我的产品</div>
          {stat(stats.products)}
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>GET /api/products/mine</div>
        </div>
        <div style={cardStyle}>
          <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>交付单</div>
          {stat(stats.deliveries)}
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>GET /api/b2b/delivery</div>
        </div>
        <div style={cardStyle}>
          <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>生效权限码</div>
          {stat(stats.permissions)}
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>GET /auth/me/permissions</div>
        </div>
      </div>

      {/* 模块入口 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
        {MODULES.map((m) => (
          <Link key={m.path} to={m.path} style={{ ...cardStyle, textDecoration: 'none', color: 'var(--text-primary)', display: 'block' }}>
            <div style={{ fontSize: 20 }}>{m.icon}</div>
            <div style={{ fontWeight: 600, fontSize: 13, marginTop: 8 }}>{m.title}</div>
            <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>{m.desc}</div>
          </Link>
        ))}
      </div>

      {/* AI 助手（可运营） */}
      <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>AI 经营助手 <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>· ProcurementAgent</span></div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {PRESET_PROMPTS.map((p) => (
            <button
              key={p.label}
              type="button"
              className="wb-btn"
              style={{ height: 32, fontSize: 12 }}
              disabled={busy}
              onClick={() => send(p.text)}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div
          ref={listRef}
          aria-live="polite"
          style={{ maxHeight: 280, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}
        >
          {messages.length === 0 && (
            <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>选择上方预设提问，或输入你的经营问题（寻源/文案/履约/对账）。</div>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '78%',
                background: m.role === 'user' ? 'var(--bubble-user, var(--surface2))' : 'var(--surface2)',
                borderRadius: 12,
                padding: '8px 12px',
                fontSize: 13,
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
              }}
            >
              {m.content || (busy && i === messages.length - 1 ? '思考中…' : '')}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            placeholder="问 AI 助手：例如『本月哪些交付单临近签收？』"
            aria-label="AI 助手输入框"
            style={{
              flex: 1,
              background: 'var(--input-bg, var(--surface2))',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-input)',
              color: 'var(--text-primary)',
              padding: '10px 12px',
              fontSize: 13,
              fontFamily: 'inherit',
            }}
          />
          <button type="button" className="wb-btn" style={{ height: 40 }} disabled={busy} onClick={() => send(input)}>
            发送
          </button>
        </div>
      </div>
      </div>
    </SuokeLayout>
  );
}
