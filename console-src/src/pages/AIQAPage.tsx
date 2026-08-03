/**
 * AIQAPage — AI 装修问答 / 案例搜索（F47, v1.5.0）
 *
 * 结构：Scaffold > AppBar(AI 装修问答) > 搜索框 + 答案区（含引用来源）+ FAQ 话题列表
 * API（对齐 app/api/ai_qa.py）：
 *   POST /api/ai-qa/search  知识库问答搜索（带引用来源，未命中诚实降级）
 *   GET  /api/ai-qa/faq     FAQ 话题列表（知识库 faq 域前 20 条）
 *
 * match_type: knowledge_base / no_match（未命中不编造内容）
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { AIQAFaq, AIQAResult } from '../types/domain';

export default function AIQAPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AIQAResult | null>(null);

  const { data: faq, loading: faqLoading, error: faqError, reload: reloadFaq } = useAsync<AIQAFaq | null>(
    async () => {
      const r = await apiClient.getAIQAFaq<AIQAFaq>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载 FAQ 失败');
      return r.data;
    },
    [],
  );

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) {
      setError('请输入搜索问题');
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const r = await apiClient.searchAIQA<AIQAResult>(q);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '搜索失败');
      setResult(r.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setResult(null);
    } finally {
      setSearching(false);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-ai-qa-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🤖 AI 装修问答</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 搜索框 */}
          <div className="wb-create-form" data-testid="wb-ai-qa-search">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">🤖</div>
              <div>
                <div className="wb-create-form__title">知识库问答搜索</div>
                <div className="wb-create-form__subtitle">答案来自内置装修知识库（含 GB 标准引用），未命中时不编造内容</div>
              </div>
            </div>
            <form onSubmit={handleSearch}>
              <div className="wb-create-form__body">
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-ai-qa-query">搜索问题</label>
                  <input
                    id="wb-ai-qa-query"
                    className="wb-input"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="如：卫生间防水规范要求？"
                    data-testid="wb-ai-qa-query-input"
                  />
                </div>
                {error && (
                  <div className="wb-create-form__error" data-testid="wb-ai-qa-error">
                    ⚠ {error}
                  </div>
                )}
                <div className="wb-create-form__actions">
                  <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={searching} data-testid="wb-ai-qa-submit" style={{ width: '100%' }}>
                    {searching ? '搜索中…' : '🔍 搜索'}
                  </button>
                </div>
              </div>
            </form>
          </div>

          {/* 答案区 */}
          {result && (
            <div data-testid="wb-ai-qa-result">
              <div className="wb-smart-card">
                <div className="wb-smart-card__head">
                  <div className="wb-smart-card__room">答案</div>
                  <span className={`wb-status-chip ${result.match_type === 'knowledge_base' ? 'wb-status-chip--success' : 'wb-status-chip--warning'}`}>
                    {result.match_type === 'knowledge_base' ? '知识库命中' : '未命中'}
                  </span>
                </div>
                <div style={{ whiteSpace: 'pre-wrap', fontSize: 'var(--font-size-sm)', lineHeight: 1.7 }} data-testid="wb-ai-qa-answer">
                  {result.answer}
                </div>
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 8 }} data-testid="wb-ai-qa-honest-note">
                  {result.honest_note}
                </div>
              </div>

              {/* 引用来源列表 */}
              {result.sources.length > 0 && (
                <div className="wb-section-label" style={{ marginTop: 16 }}>引用来源（{result.sources.length}）</div>
              )}
              {result.sources.map((src, i) => (
                <div key={i} className="wb-smart-card" data-testid={`wb-ai-qa-source--${i}`}>
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">{src.title}</div>
                    <span className="wb-status-chip wb-status-chip--muted">{src.domain}</span>
                  </div>
                  <div className="wb-smart-card__meta">
                    <span>📖 {src.citation || '无出处编号'}</span>
                  </div>
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 6 }}>{src.snippet}…</div>
                </div>
              ))}
            </div>
          )}

          {/* FAQ 区 */}
          <div className="wb-section-label" style={{ marginTop: 20 }}>常见问题（FAQ · {faq?.total ?? 0}）</div>
          {faqLoading && (
            <div className="wb-state" data-testid="wb-ai-qa-faq-loading">
              <div className="wb-state__icon">⏳</div><div>加载 FAQ 中…</div>
            </div>
          )}
          {faqError && !faqLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-ai-qa-faq-error">
              <div className="wb-state__icon">⚠</div><div>{faqError}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadFaq()} type="button">重试</button>
            </div>
          )}
          {!faqLoading && !faqError && (faq?.topics.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-ai-qa-faq-empty">
              <div className="wb-state__icon">📚</div><div>暂无 FAQ 话题</div>
            </div>
          )}
          {(faq?.topics ?? []).map((topic, i) => (
            <div key={topic.id || i} className="wb-smart-card" data-testid={`wb-ai-qa-faq--${i}`}>
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{topic.name}</div>
                {topic.citation && <span className="wb-status-chip wb-status-chip--muted">{topic.citation}</span>}
              </div>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 6 }}>{topic.content}</div>
            </div>
          ))}
        </div>
      </div>
    </SuokeLayout>
  );
}
