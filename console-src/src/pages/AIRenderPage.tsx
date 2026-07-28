/**
 * AIRenderPage — AI 渲染
 *
 * 结构：Scaffold > AppBar(AI 渲染) > 能力展示（渲染类型卡片 + 风格 chips + 重布置模式说明）
 * API：GET /api/ai-render/capabilities
 *      （对齐 app/api/ai_render.py:151 get_capabilities 返回）
 *
 * 后端字段（app/api/ai_render.py:get_capabilities 返回 dict）：
 *   styles: string[]          推荐风格列表（style 字段允许自由文本，列表仅供参考）
 *   restage_modes: string[]   照片重布置模式（必须取自列表：inpainting / full_regen）
 *   render_types: string[]    渲染类型（2d / 3d / restage）
 *   note: string              说明
 *
 * 注意：实际渲染为 POST 端点（/2d /3d /restage），本页仅展示能力。
 *      ai_render_enabled flag 控制后端是否启用（前端展示不受 flag 影响）。
 */

import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { AIRenderCapabilities } from '../types/domain';

const STYLE_LABELS: Record<string, string> = {
  modern: '现代',
  nordic: '北欧',
  japanese: '日式',
  luxury: '轻奢',
  chinese: '中式',
  industrial: '工业风',
  coastal: '海滨',
};

const RENDER_TYPE_INFO: Record<
  string,
  { label: string; emoji: string; endpoint: string; desc: string }
> = {
  '2d': {
    label: '2D 效果图',
    emoji: '🖼',
    endpoint: 'POST /api/ai-render/2d',
    desc: '根据布局 JSON + 风格生成 SD prompt + 自然语言描述 + 占位图',
  },
  '3d': {
    label: '3D 场景',
    emoji: '🌐',
    endpoint: 'POST /api/ai-render/3d',
    desc: '户型 + 风格 → SpatialGen 多视角 prompt + 高斯重建参数',
  },
  restage: {
    label: '照片重布置',
    emoji: '📸',
    endpoint: 'POST /api/ai-render/restage',
    desc: '上传照片 + 模式 → 重布置结果（inpainting 局部重绘 / full_regen 完全重生）',
  },
};

const RESTAGE_MODE_INFO: Record<string, string> = {
  inpainting: '局部重绘 — 保留主体结构，替换家具/装饰',
  full_regen: '完全重生 — 基于照片整体重新生成',
};

export default function AIRenderPage() {
  const navigate = useNavigate();

  const { data: caps, loading, error, reload } = useAsync<AIRenderCapabilities | null>(
    async () => {
      const r = await apiClient.getAIRenderCapabilities<AIRenderCapabilities>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [],
  );

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-airender-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🎨 AI 渲染</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {loading && (
            <div className="wb-state" data-testid="wb-airender-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载 AI 渲染能力…</div>
            </div>
          )}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-airender-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {caps && !loading && !error && (
            <div data-testid="wb-airender-content">
              {/* 渲染类型 */}
              <div className="wb-section-label">渲染类型（{caps.render_types.length}）</div>
              {caps.render_types.map((rt, i) => {
                const info = RENDER_TYPE_INFO[rt];
                return (
                  <div
                    key={rt}
                    className="wb-project-card"
                    data-testid={`wb-airender-type--${i}`}
                  >
                    <div className="wb-project-card__title">
                      {info?.emoji ?? '🎨'} {info?.label ?? rt}
                    </div>
                    <div style={{ fontSize: 'var(--font-size-sm)', marginTop: 4 }}>
                      {info?.desc ?? rt}
                    </div>
                    <div
                      style={{
                        fontSize: 'var(--font-size-xs)',
                        color: 'var(--text-muted)',
                        marginTop: 8,
                        fontFamily: 'monospace',
                      }}
                    >
                      {info?.endpoint ?? rt}
                    </div>
                  </div>
                );
              })}

              {/* 推荐风格 */}
              <div className="wb-section-label" style={{ marginTop: 16 }}>
                推荐风格（{caps.styles.length}）
              </div>
              <div
                className="wb-task-filter"
                role="list"
                aria-label="推荐风格"
                data-testid="wb-airender-styles"
              >
                {caps.styles.map((s, i) => (
                  <span
                    key={s}
                    className="wb-task-filter__chip wb-task-filter__chip--active"
                    data-testid={`wb-airender-style--${i}`}
                  >
                    {STYLE_LABELS[s] ?? s}
                  </span>
                ))}
              </div>
              <div
                style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--text-muted)',
                  marginTop: 8,
                }}
              >
                💡 {caps.note}
              </div>

              {/* 重布置模式 */}
              {caps.restage_modes.length > 0 && (
                <>
                  <div className="wb-section-label" style={{ marginTop: 16 }}>
                    照片重布置模式（{caps.restage_modes.length}）
                  </div>
                  {caps.restage_modes.map((m, i) => (
                    <div
                      key={m}
                      className="wb-project-card"
                      data-testid={`wb-airender-restage--${i}`}
                    >
                      <div className="wb-project-card__title">{m}</div>
                      <div style={{ fontSize: 'var(--font-size-sm)', marginTop: 4 }}>
                        {RESTAGE_MODE_INFO[m] ?? m}
                      </div>
                    </div>
                  ))}
                </>
              )}

              {/* 引导 */}
              <div
                className="wb-project-card"
                style={{ marginTop: 16, background: 'var(--surface2)' }}
                data-testid="wb-airender-guide"
              >
                <div className="wb-project-card__title">💬 通过工作台发起渲染</div>
                <div style={{ fontSize: 'var(--font-size-sm)', marginTop: 4, color: 'var(--text-muted)' }}>
                  AI 渲染需通过工作台与 AI 渲染 Agent 对话发起，支持上传户型/照片 + 选择风格与模式。
                </div>
                <button
                  type="button"
                  className="wb-theme-option wb-theme-option--active"
                  style={{ marginTop: 8 }}
                  onClick={() => navigate('/')}
                  data-testid="wb-airender-goto-workbench"
                >
                  前往工作台
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
