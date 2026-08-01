/**
 * ProjectsPage — 对齐 flutter_app/lib/pages/projects_page.dart
 *
 * 结构：Scaffold > AppBar(标题+新建) > ListView[项目卡片] | 创建表单
 * API：GET /api/projects（列表）、POST /api/projects（创建）
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { SuokeCard } from '../components';
import { SuokeInput, SuokeButton } from '../components';
import { apiClient } from '../services/api-client';
import { useAsync } from '../hooks/useAsync';
import type { Project, ProjectCreateInput, ProjectType } from '../types/domain';

const PROJECT_TYPE_LABELS: Record<string, string> = {
  full_renovation: '整装',
  hard_decoration: '硬装',
  soft_furnishing: '软装',
  curtain: '窗帘定制',
  kitchen: '厨房改造',
  bathroom: '卫浴改造',
  electrical: '电路改造',
  carpentry: '木工制作',
  painting: '油漆涂刷',
  plumbing: '水管改造',
  masonry: '泥瓦铺贴',
  installation: '设备安装',
};

const STATUS_LABELS: Record<string, string> = {
  planning: '规划中',
  design: '设计中',
  construction: '施工中',
  inspection: '验收中',
  settlement: '结算中',
  completed: '已完工',
  archived: '已归档',
};

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('zh-CN');
  } catch {
    return '';
  }
}

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<ProjectCreateInput>({
    name: '',
    address: '',
    total_area: undefined,
    project_type: 'full_renovation',
  });

  const { data: projects, loading, error, reload } = useAsync<Project[]>(
    async () => {
      const r = await apiClient.listProjects<Project[]>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [],
  );

  // Bento 概览统计（2026 趋势：模块化非对称卡片，离散数值单元）
  const counts = projects?.reduce(
    (acc, p) => {
      acc.total += 1;
      acc[p.status] = (acc[p.status] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );
  const showBento = !loading && !error && projects && projects.length > 0;

  async function handleCreate() {
    if (!form.name.trim()) return;
    setCreating(true);
    const r = await apiClient.createProject<Project>({
      ...form,
      name: form.name.trim(),
      source: 'manual',
    });
    setCreating(false);
    if (r.isSuccess) {
      setShowCreate(false);
      setForm({ name: '', address: '', total_area: undefined, project_type: 'full_renovation' });
      reload();
    } else {
      alert(`创建失败：${r.error ?? '未知错误'}`);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-projects-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">项目列表</div>
          <SuokeButton
            size="sm"
            onClick={() => setShowCreate((v) => !v)}
            testId="wb-projects-toggle-create"
          >
            {showCreate ? '取消' : '＋ 新建'}
          </SuokeButton>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {showBento && counts && (
            <section className="wb-bento" aria-label="项目概览" data-testid="wb-projects-bento">
              <div className="wb-bento__cell wb-bento__cell--hero">
                <div>
                  <div className="wb-bento__label">项目总数</div>
                  <div className="wb-bento__value wb-bento__value--accent">{counts.total ?? 0}</div>
                </div>
                <div className="wb-bento__hint">
                  {STATUS_LABELS.construction && `施工中 ${counts.construction ?? 0}`}
                </div>
              </div>
              <div className="wb-bento__stats">
                <div className="wb-bento__cell">
                  <div className="wb-bento__label">设计中</div>
                  <div className="wb-bento__value">{counts.design ?? 0}</div>
                </div>
                <div className="wb-bento__cell">
                  <div className="wb-bento__label">施工中</div>
                  <div className="wb-bento__value">{counts.construction ?? 0}</div>
                </div>
                <div className="wb-bento__cell">
                  <div className="wb-bento__label">已完工</div>
                  <div className="wb-bento__value">{counts.completed ?? 0}</div>
                </div>
              </div>
            </section>
          )}

          {showCreate && (
            <div className="wb-create-form" data-testid="wb-create-form">
              <div className="wb-create-form__title">创建新项目</div>
              <div style={{ marginBottom: 10 }}>
                <SuokeInput
                  placeholder="项目名称（如：三居室整装）"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  data-testid="wb-create-name"
                />
              </div>
              <div style={{ marginBottom: 10 }}>
                <SuokeInput
                  placeholder="地址（可选）"
                  value={form.address ?? ''}
                  onChange={(e) => setForm({ ...form, address: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
                <SuokeInput
                  type="number"
                  placeholder="面积㎡（可选）"
                  value={form.total_area ?? ''}
                  onChange={(e) =>
                    setForm({ ...form, total_area: e.target.value ? Number(e.target.value) : undefined })
                  }
                  style={{ flex: 1 }}
                />
                <select
                  value={form.project_type}
                  onChange={(e) => setForm({ ...form, project_type: e.target.value as ProjectType })}
                  style={{
                    flex: 1,
                    height: 40,
                    padding: '0 12px',
                    background: 'var(--input-bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-input)',
                    color: 'var(--text-primary)',
                    fontSize: 'var(--font-size-md)',
                    fontFamily: 'inherit',
                  }}
                >
                  {Object.entries(PROJECT_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </div>
              <div className="wb-create-form__actions">
                <SuokeButton onClick={handleCreate} disabled={creating || !form.name.trim()} testId="wb-create-submit">
                  {creating ? '创建中…' : '创建项目'}
                </SuokeButton>
              </div>
            </div>
          )}

          {loading && (
            <div className="wb-state" data-testid="wb-projects-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载项目中…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-projects-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <SuokeButton variant="outline" size="sm" onClick={reload}>
                重试
              </SuokeButton>
            </div>
          )}

          {!loading && !error && projects && projects.length === 0 && (
            <div className="wb-state" data-testid="wb-projects-empty">
              <div className="wb-state__icon">📋</div>
              <div>暂无项目</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>点击右上角"新建"创建第一个项目</div>
            </div>
          )}

          {!loading && !error && projects && projects.length > 0 && (
            <div data-testid="wb-projects-list">
              {projects.map((p) => (
                <SuokeCard
                  key={p.id}
                  interactive
                  testId={`wb-project-card--${p.id}`}
                  style={{ marginBottom: 12 }}
                >
                  <div className="wb-project-card__title">{p.name}</div>
                  <div className="wb-project-card__meta">
                    <span className="wb-project-card__meta-item">
                      📐 {PROJECT_TYPE_LABELS[p.project_type] ?? p.project_type}
                    </span>
                    {p.total_area != null && (
                      <span className="wb-project-card__meta-item">📏 {p.total_area}㎡</span>
                    )}
                    <span className="wb-project-card__meta-item">
                      🔖 {STATUS_LABELS[p.status] ?? p.status}
                    </span>
                    <span className="wb-project-card__meta-item">📅 {formatDate(p.created_at)}</span>
                  </div>
                  {p.address && (
                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-muted)', marginTop: 6 }}>
                      📍 {p.address}
                    </div>
                  )}
                </SuokeCard>
              ))}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
