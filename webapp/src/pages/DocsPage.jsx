import React, { useMemo } from 'react'
import guideMd from '../../../assets/guide/user-guide.md?raw'
import privacyMd from '../../../assets/legal/privacy-policy.md?raw'
import termsMd from '../../../assets/legal/terms-of-service.md?raw'
import agentMemoryMd from '../../../assets/legal/agent-memory-privacy-notice.md?raw'

/* ── 公开文档页（/guide /legal/privacy /legal/terms /legal/agent-memory-privacy）
 * 内容唯一来源：assets/guide + assets/legal 的 markdown 文件（?raw 构建期注入）。
 * 渲染器仅支持文档实际使用的 markdown 子集（标题/段落/列表/表格/引用/链接/加粗/行内代码），
 * 先转义 HTML 再结构化，防注入。
 */
const DOCS = {
  guide: { title: '用户使用指南', md: guideMd },
  privacy: { title: '隐私政策', md: privacyMd },
  terms: { title: '服务条款', md: termsMd },
  'agent-memory': { title: 'Agent 自进化功能隐私声明', md: agentMemoryMd },
}

// 相对 .md 链接 → SPA 路由（assets 中文件间互链可点击）
const DOC_ROUTES = {
  'user-guide.md': '/guide',
  'privacy-policy.md': '/legal/privacy',
  'terms-of-service.md': '/legal/terms',
  'agent-memory-privacy-notice.md': '/legal/agent-memory-privacy',
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function slugify(text) {
  return text.replace(/^\d+[.、]\s*/, '').replace(/[（()）]/g, '').replace(/\s+/g, '')
}

function inline(text) {
  let s = escapeHtml(text)
  // 行内代码优先（其后不再做链接/加粗解析）
  s = s.replace(/`([^`]+)`/g, (_m, c) => `<code>${c}</code>`)
  // 邮箱 autolink：<a@b.c>
  s = s.replace(/&lt;([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})&gt;/g, (_m, email) => `<a href="mailto:${email}">${email}</a>`)
  // 链接 [text](url)
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, text, url) => {
    if (url.startsWith('http')) {
      return `<a href="${url}" target="_blank" rel="noopener noreferrer">${text}</a>`
    }
    if (url.startsWith('#') || url.startsWith('mailto:')) {
      return `<a href="${url}">${text}</a>`
    }
    const href = DOC_ROUTES[url.split('/').pop()] || url
    return `<a href="${href}">${text}</a>`
  })
  // 加粗 **x**
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  return s
}

function renderMarkdown(md) {
  const lines = md.split('\n')
  const out = []
  let i = 0

  const flushList = (list) => {
    if (!list) return
    const tag = list.type === 'ol' ? 'ol' : 'ul'
    out.push(`<${tag}>${list.items.map((it) => `<li>${inline(it)}</li>`).join('')}</${tag}>`)
  }

  const flushQuote = (quote) => {
    if (quote.length) {
      out.push(`<blockquote>${inline(quote.join(' '))}</blockquote>`)
      quote.length = 0
    }
  }

  let list = null
  let quote = []

  while (i < lines.length) {
    const line = lines[i]

    // 围栏代码块（文档中未使用，防御性支持）
    if (line.startsWith('```')) {
      flushList(list); list = null
      flushQuote(quote)
      const buf = []
      i += 1
      while (i < lines.length && !lines[i].startsWith('```')) {
        buf.push(escapeHtml(lines[i]))
        i += 1
      }
      i += 1 // 跳过闭合
      out.push(`<pre><code>${buf.join('\n')}</code></pre>`)
      continue
    }

    // 表格：当前行含 | 且下一行为分隔行
    if (line.includes('|') && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes('-')) {
      flushList(list); list = null
      flushQuote(quote)
      const header = line.split('|').slice(1, -1).map((c) => c.trim())
      i += 2
      const rows = []
      while (i < lines.length && lines[i].includes('|') && lines[i].trim() !== '') {
        rows.push(lines[i].split('|').slice(1, -1).map((c) => c.trim()))
        i += 1
      }
      out.push(
        '<div class="docs-table-wrap"><table><thead><tr>' +
        header.map((h) => `<th>${inline(h)}</th>`).join('') +
        '</tr></thead><tbody>' +
        rows.map((r) => '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('') +
        '</tbody></table></div>',
      )
      continue
    }

    // 引用
    if (line.startsWith('> ')) {
      flushList(list); list = null
      quote.push(line.slice(2))
      i += 1
      continue
    }

    // 标题
    const h = line.match(/^(#{1,4})\s+(.*)$/)
    if (h) {
      flushList(list); list = null
      flushQuote(quote)
      const level = h[1].length
      const text = h[2]
      out.push(`<h${level} id="${slugify(text)}">${inline(text)}</h${level}>`)
      i += 1
      continue
    }

    // 水平线
    if (/^---+$/.test(line.trim())) {
      flushList(list); list = null
      flushQuote(quote)
      out.push('<hr />')
      i += 1
      continue
    }

    // 列表
    const ul = line.match(/^[-*]\s+(.*)$/)
    const ol = line.match(/^\d+[.)]\s+(.*)$/)
    if (ul || ol) {
      flushQuote(quote)
      const item = (ul ? ul[1] : ol[1])
      const type = ol ? 'ol' : 'ul'
      if (!list || list.type !== type) {
        flushList(list)
        list = { type, items: [item] }
      } else {
        list.items.push(item)
      }
      i += 1
      continue
    }

    // 空行 → 刷新列表/引用
    if (line.trim() === '') {
      flushList(list); list = null
      flushQuote(quote)
      i += 1
      continue
    }

    // 普通段落
    flushList(list); list = null
    flushQuote(quote)
    const para = []
    while (i < lines.length && lines[i].trim() !== '' && !lines[i].startsWith('#') && !lines[i].startsWith('```') && !lines[i].startsWith('- ') && !lines[i].startsWith('* ') && !/^\d+[.)]\s+/.test(lines[i])) {
      para.push(lines[i])
      i += 1
    }
    out.push(`<p>${inline(para.join(' '))}</p>`)
  }
  flushList(list)
  flushQuote(quote)
  return out.join('\n')
}

export default function DocsPage({ doc }) {
  const entry = DOCS[doc] || DOCS.guide
  const html = useMemo(() => renderMarkdown(entry.md), [entry])
  return (
    <main className="docs-page">
      <article className="docs-card" dangerouslySetInnerHTML={{ __html: html }} />
    </main>
  )
}
