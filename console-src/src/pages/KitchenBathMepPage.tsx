/**
 * KitchenBathMepPage — F18 厨卫水电（对齐 flutter_app/lib/pages/kitchen_bath_mep_page.dart）
 *
 * 结构：Scaffold > AppBar(厨卫水电) > [项目选择器] > 方案列表（选中展开详情）
 * API（app/api/kitchen_bath_mep.py）：
 *   GET /api/mep-kb/plans/project/{projectId}（方案列表）
 *   GET /api/mep-kb/plans/{planId}/points（点位）
 *   GET /api/mep-kb/plans/{planId}/circuits（厨房回路）
 *   GET /api/mep-kb/plans/{planId}/equipotential（等电位校验 GB 50096）
 *   GET /api/mep-kb/plans/{planId}/gas（燃气管道规划）
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  KitchenBathMEPPlan,
  MEPCircuitResult,
  MEPEquipotentialResult,
  MEPGasResult,
  MEPPoint,
  Project,
} from '../types/domain';

const ROOM_TYPE_CN: Record<string, string> = {
  kitchen: '厨房',
  bathroom: '卫生间',
  laundry: '洗衣房',
  balcony: '阳台',
};

const POINT_TYPE_CN: Record<string, string> = {
  water_inlet: '给水',
  drain: '排水',
};

export default function KitchenBathMepPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [selectedPlanId, setSelectedPlanId] = useState<string>('');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 方案列表
  const { data: plans, loading, error, reload } = useAsync<KitchenBathMEPPlan[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.listKitchenBathMepPlans<KitchenBathMEPPlan[]>(selectedProjectId);
      if (r.status === 404) return [];
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载方案失败');
      return r.data;
    },
    [selectedProjectId],
  );

  // 默认选中第一个方案
  useEffect(() => {
    if (!selectedPlanId && plans && plans.length > 0) {
      setSelectedPlanId(plans[0].id);
    }
  }, [plans, selectedPlanId]);

  const selectedPlan = plans?.find((p) => p.id === selectedPlanId) ?? null;

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-mepkb-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🔧 厨卫水电</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 项目选择器 */}
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-mepkb-project-select"
            >
              <option value="">选择项目…</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-mepkb-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-mepkb-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载厨卫水电方案中…</div>
            </div>
          )}

          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-mepkb-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {selectedProjectId && !loading && !error && (plans?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-mepkb-empty">
              <div className="wb-state__icon">🔧</div>
              <div>暂无厨卫水电方案</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>
                可通过工作台与水电 Agent 对话生成方案
              </div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (plans?.length ?? 0) > 0 && (
            <div data-testid="wb-mepkb-content">
              {/* 方案选择 */}
              <div className="wb-section-label">方案（{plans!.length}）</div>
              <div className="wb-task-filter">
                {plans!.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className={`wb-task-filter__chip ${selectedPlanId === p.id ? 'wb-task-filter__chip--active' : ''}`}
                    onClick={() => setSelectedPlanId(p.id)}
                    data-testid={`wb-mepkb-plan-chip--${p.id}`}
                  >
                    {ROOM_TYPE_CN[p.room_type] ?? p.room_type} · {p.room_name}
                  </button>
                ))}
              </div>

              {selectedPlan && <PlanDetail plan={selectedPlan} />}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}

/** 方案详情：点位 + 回路 + 等电位 + 燃气 */
function PlanDetail({ plan }: { plan: KitchenBathMEPPlan }) {
  const { data: points, loading: pointsLoading, error: pointsError } = useAsync<
    MEPPoint[] | null
  >(
    async () => {
      const r = await apiClient.getKitchenBathMepPoints<MEPPoint[]>(plan.id);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载点位失败');
      return r.data;
    },
    [plan.id],
  );

  const { data: circuits, error: circuitsError } = useAsync<MEPCircuitResult | null>(
    async () => {
      const r = await apiClient.getKitchenCircuits<MEPCircuitResult>(plan.id);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载回路失败');
      return r.data;
    },
    [plan.id],
  );

  const { data: equipotential, error: epError } = useAsync<MEPEquipotentialResult | null>(
    async () => {
      const r = await apiClient.getEquipotentialCheck<MEPEquipotentialResult>(plan.id);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载等电位校验失败');
      return r.data;
    },
    [plan.id],
  );

  const { data: gas, error: gasError } = useAsync<MEPGasResult | null>(
    async () => {
      const r = await apiClient.getGasPlan<MEPGasResult>(plan.id);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载燃气规划失败');
      return r.data;
    },
    [plan.id],
  );

  return (
    <div data-testid="wb-mepkb-plan-detail">
      {/* 方案概览 */}
      <div className="wb-smart-card">
        <div className="wb-smart-card__head">
          <div className="wb-smart-card__room">
            {ROOM_TYPE_CN[plan.room_type] ?? plan.room_type} · {plan.room_name}
          </div>
          <span
            className={`wb-status-chip ${
              plan.equipotential_bonding ? 'wb-status-chip--success' : 'wb-status-chip--warning'
            }`}
          >
            等电位 {plan.equipotential_bonding ? '已设置' : '未设置'}
          </span>
        </div>
        <div className="wb-smart-card__meta">
          {plan.water_heater_type && (
            <span>热水器：{plan.water_heater_type === 'gas' ? '燃气' : plan.water_heater_type}</span>
          )}
          {plan.water_heater_capacity_l && <span>容量 {plan.water_heater_capacity_l}L</span>}
          <span>状态：{({ draft: '草稿', completed: '已完成' } as Record<string, string>)[plan.status] ?? plan.status}</span>
          {plan.notes && <span>备注：{plan.notes}</span>}
        </div>
      </div>

      {/* 点位规划 */}
      <div className="wb-section-label">点位规划</div>
      {pointsLoading && (
        <div className="wb-state" style={{ padding: '24px' }}>
          <div className="wb-state__icon">⏳</div>
          <div>加载点位中…</div>
        </div>
      )}
      {pointsError && !pointsLoading && (
        <div className="wb-state wb-state--error" style={{ padding: '24px' }}>
          <div>{pointsError}</div>
        </div>
      )}
      {!pointsLoading && !pointsError && (points?.length ?? 0) === 0 && (
        <div className="wb-state" style={{ padding: '24px' }}>
          <div>暂无点位，可先创建方案后再规划</div>
        </div>
      )}
      {!pointsLoading && !pointsError && (points?.length ?? 0) > 0 && (
        <div data-testid="wb-mepkb-points">
          {points!.map((pt, i) => (
            <div className="wb-budget-item" key={pt.id} data-testid={`wb-mepkb-point--${i}`}>
              <div>
                <div className="wb-budget-item__name">{pt.device ?? pt.point_type}</div>
                <div className="wb-budget-item__cat">
                  {POINT_TYPE_CN[pt.point_type] ?? pt.point_type}
                  {pt.spec ? ` · ${pt.spec}` : ''}
                  {pt.voltage ? ` · ${pt.voltage}` : ''}
                  {pt.power_w != null ? ` · ${pt.power_w}W` : ''}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="wb-budget-item__cat">
                  x={pt.position_x} y={pt.position_y} z={pt.position_z}
                </div>
                {pt.notes && <div className="wb-budget-item__spent">{pt.notes}</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 厨房回路 */}
      <div className="wb-section-label">厨房回路设计</div>
      {circuitsError && (
        <div className="wb-state wb-state--error" style={{ padding: '24px' }}>
          <div>{circuitsError}</div>
        </div>
      )}
      {!circuitsError && circuits && (
        <div data-testid="wb-mepkb-circuits">
          <div className="wb-vent-box">
            <div className="wb-vent-box__head">
              <div className="wb-vent-box__title">回路方案</div>
              <span className="wb-status-chip wb-status-chip--accent">
                {circuits.total_circuits} 路 · 主开推荐 {circuits.main_breaker_recommended}
              </span>
            </div>
            {circuits.circuits.map((c, i) => (
              <div className="wb-vent-box__row" key={i}>
                <span>
                  {c.circuit_no} · {c.type} · {c.device}
                </span>
                <span>
                  {c.power_w}W · {c.wire} · {c.breaker}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 等电位校验 */}
      <div className="wb-section-label">等电位校验（GB 50096）</div>
      {epError && (
        <div className="wb-state wb-state--error" style={{ padding: '24px' }}>
          <div>{epError}</div>
        </div>
      )}
      {!epError && equipotential && (
        <div data-testid="wb-mepkb-equipotential">
          <div
            className={`wb-settlement-alert ${equipotential.compliant ? 'wb-settlement-alert--review' : ''}`}
            style={{
              ...(equipotential.compliant
                ? {
                    background: 'rgba(74, 158, 110, 0.12)',
                    borderColor: 'var(--success)',
                    color: 'var(--success)',
                  }
                : {}),
            }}
          >
            {equipotential.compliant ? '✅ 等电位校验通过' : '⚠ 等电位校验未通过'}
          </div>
          {equipotential.checks.map((c, i) => (
            <div className="wb-vent-box__row" key={i} style={{ padding: '6px 0' }}>
              <span>
                {c.passed ? '✅' : '❌'} {c.item}（{c.value}）
              </span>
              <span style={{ color: 'var(--text-muted)' }}>{c.standard}</span>
            </div>
          ))}
        </div>
      )}

      {/* 燃气规划 */}
      <div className="wb-section-label">燃气管道规划</div>
      {gasError && (
        <div className="wb-state wb-state--error" style={{ padding: '24px' }}>
          <div>{gasError}</div>
        </div>
      )}
      {!gasError && gas && (
        <div data-testid="wb-mepkb-gas">
          {!gas.needed && gas.reason && (
            <div className="wb-state" style={{ padding: '24px' }}>
              <div>{gas.reason}</div>
            </div>
          )}
          {gas.needed && (
            <div className="wb-vent-box">
              <div className="wb-vent-box__head">
                <div className="wb-vent-box__title">燃气预留接口</div>
                <span className="wb-status-chip wb-status-chip--warning">需规划</span>
              </div>
              {gas.outlets.map((o, i) => (
                <div key={i}>
                  <div className="wb-vent-box__row">
                    <span>🔥 {o.device}</span>
                    <span>
                      {o.pipe_spec} · {o.valve}
                    </span>
                  </div>
                  <div className="wb-vent-box__hint">
                    {o.note}（位置 x={o.position.x} y={o.position.y} z={o.position.z}）
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
