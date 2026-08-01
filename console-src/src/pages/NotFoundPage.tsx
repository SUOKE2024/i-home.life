/**
 * NotFoundPage — 真 404 页（取代此前 path="*" 静默回退到 Workbench 的反直觉行为）
 *
 * 2026 UX 基线：未知路由给出明确反馈 + 可操作出口，而非"看起来成功了但其实是别的页面"。
 * 视觉对齐 EmptyState 的居中卡片语言，提供「返回工作台」「查看项目」两个主出口。
 */

import { useNavigate } from 'react-router-dom';
import { SuokeLayout } from '../components/layout';

export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <SuokeLayout>
      <div
        className="wb-notfound"
        role="alert"
        data-testid="wb-notfound"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          flex: 1,
          minHeight: 0,
          padding: 'var(--spacing-xl)',
          textAlign: 'center',
        }}
      >
        <div
          className="wb-notfound__code"
          aria-hidden="true"
          style={{
            fontSize: '72px',
            fontWeight: 800,
            lineHeight: 1,
            background: 'linear-gradient(135deg, var(--accent), var(--accent-bright))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            marginBottom: 'var(--spacing-lg)',
          }}
        >
          404
        </div>
        <h1
          className="wb-notfound__title"
          style={{ fontSize: '20px', fontWeight: 700, marginBottom: 'var(--spacing-sm)' }}
        >
          页面走丢了
        </h1>
        <p
          className="wb-notfound__desc"
          style={{
            color: 'var(--text-secondary)',
            fontSize: 'var(--font-size-md)',
            maxWidth: '420px',
            marginBottom: 'var(--spacing-xl)',
          }}
        >
          您访问的页面不存在或已被移动。请返回工作台继续，或前往项目列表。
        </p>
        <div
          className="wb-notfound__actions"
          style={{ display: 'flex', gap: 'var(--spacing-md)', flexWrap: 'wrap', justifyContent: 'center' }}
        >
          <button
            type="button"
            className="wb-notfound__btn wb-notfound__btn--primary"
            onClick={() => navigate('/')}
            style={{
              padding: '12px 24px',
              borderRadius: 'var(--radius-input)',
              border: '1px solid var(--accent)',
              background: 'var(--accent)',
              color: 'var(--bg-deep)',
              fontWeight: 600,
              fontSize: 'var(--font-size-md)',
              cursor: 'pointer',
            }}
          >
            返回工作台
          </button>
          <button
            type="button"
            className="wb-notfound__btn"
            onClick={() => navigate('/projects')}
            style={{
              padding: '12px 24px',
              borderRadius: 'var(--radius-input)',
              border: '1px solid var(--border-active)',
              background: 'transparent',
              color: 'var(--text-primary)',
              fontWeight: 600,
              fontSize: 'var(--font-size-md)',
              cursor: 'pointer',
            }}
          >
            查看项目
          </button>
        </div>
      </div>
    </SuokeLayout>
  );
}
