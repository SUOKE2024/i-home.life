/**
 * PointsPage — 积分商城
 *
 * 结构：Scaffold > AppBar(积分商城) > 账户概览 + 流水 + 规则 + 商城商品（兑换）+ 兑换记录 + 排行榜
 * API（对齐 app/api/points.py，前缀 /api/points）：
 *   GET  /api/points/account        当前用户积分账户
 *   GET  /api/points/transactions   积分流水
 *   GET  /api/points/rules          积分规则
 *   GET  /api/points/mall           商城商品
 *   POST /api/points/redeem         积分兑换商品（body: { item_id }）
 *   GET  /api/points/redemptions    兑换记录
 *   GET  /api/points/ranking        年度积分排行榜
 *
 * 诚实降级：isSuccess=false 时展示后端真实 error；兑换失败（余额不足/库存不足等）原样展示。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  PointsAccount,
  PointsMallItem,
  PointsRankingEntry,
  PointsRedemption,
  PointsRule,
  PointsTransaction,
} from '../types/domain';

function fmtTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const ROLE_LABELS: Record<string, string> = {
  homeowner: '业主',
  designer: '设计师',
  contractor: '施工方',
  supplier: '供应商',
};

export default function PointsPage() {
  const navigate = useNavigate();
  const [redeemError, setRedeemError] = useState<string | null>(null);
  const [redeemMsg, setRedeemMsg] = useState<string | null>(null);
  const [redeemingId, setRedeemingId] = useState<string | null>(null);

  const { data: account, loading: accountLoading, error: accountError, reload: reloadAccount } =
    useAsync<PointsAccount | null>(async () => {
      const r = await apiClient.getPointsAccount<PointsAccount>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载积分账户失败');
      return r.data;
    }, []);

  const { data: transactions, loading: txnLoading, error: txnError, reload: reloadTxns } =
    useAsync<PointsTransaction[] | null>(async () => {
      const r = await apiClient.getPointsTransactions<PointsTransaction[]>(0, 20);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载积分流水失败');
      return r.data;
    }, []);

  const { data: rules, loading: rulesLoading, error: rulesError, reload: reloadRules } =
    useAsync<PointsRule[] | null>(async () => {
      const r = await apiClient.getPointsRules<PointsRule[]>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载积分规则失败');
      return r.data;
    }, []);

  const { data: mall, loading: mallLoading, error: mallError, reload: reloadMall } =
    useAsync<PointsMallItem[] | null>(async () => {
      const r = await apiClient.getPointsMall<PointsMallItem[]>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载积分商城失败');
      return r.data;
    }, []);

  const { data: redemptions, loading: rdLoading, error: rdError, reload: reloadRd } =
    useAsync<PointsRedemption[] | null>(async () => {
      const r = await apiClient.getPointsRedemptions<PointsRedemption[]>(0, 20);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载兑换记录失败');
      return r.data;
    }, []);

  const { data: ranking, loading: rankLoading, error: rankError, reload: reloadRank } =
    useAsync<PointsRankingEntry[] | null>(async () => {
      const r = await apiClient.getPointsRanking<PointsRankingEntry[]>({ category: 'overall', limit: 50 });
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载排行榜失败');
      return r.data;
    }, []);

  async function handleRedeem(item: PointsMallItem) {
    setRedeemError(null);
    setRedeemMsg(null);
    setRedeemingId(item.id);
    try {
      const r = await apiClient.redeemPoints<PointsRedemption>(item.id);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '兑换失败');
      setRedeemMsg(`兑换成功：「${r.data.item_name}」扣减 ${r.data.points_spent} 积分`);
      reloadAccount();
      reloadRd();
    } catch (err) {
      setRedeemError(err instanceof Error ? err.message : String(err));
    } finally {
      setRedeemingId(null);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-points-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🏅 积分商城</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 账户概览 */}
          <div className="wb-section-label">我的积分账户</div>
          {accountLoading && (
            <div className="wb-state" data-testid="wb-points-account-loading">
              <div className="wb-state__icon">⏳</div><div>加载积分账户…</div>
            </div>
          )}
          {accountError && !accountLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-points-account-error">
              <div className="wb-state__icon">⚠</div><div>{accountError}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadAccount()} type="button">重试</button>
            </div>
          )}
          {account && !accountLoading && !accountError && (
            <div className="wb-smart-card" data-testid="wb-points-account">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">当前可用</div>
                <span className="wb-status-chip wb-status-chip--accent">Lv.{account.level}</span>
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--accent-bright)', marginTop: 4 }} data-testid="wb-points-balance">
                {account.balance} <span style={{ fontSize: 14, fontWeight: 400 }}>积分</span>
              </div>
              <div className="wb-smart-card__meta">
                <span>累计获得 {account.total_earned}</span>
                <span>累计消耗 {account.total_spent}</span>
                <span>本年获得 {account.year_earned}</span>
                <span>本年消耗 {account.year_spent}</span>
              </div>
            </div>
          )}

          {/* 商城商品 */}
          <div className="wb-section-label" style={{ marginTop: 16 }}>积分商城（{mall?.length ?? 0}）</div>
          {mallLoading && (
            <div className="wb-state" data-testid="wb-points-mall-loading">
              <div className="wb-state__icon">⏳</div><div>加载商城商品…</div>
            </div>
          )}
          {mallError && !mallLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-points-mall-error">
              <div className="wb-state__icon">⚠</div><div>{mallError}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadMall()} type="button">重试</button>
            </div>
          )}
          {!mallLoading && !mallError && (mall?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-points-mall-empty">
              <div className="wb-state__icon">🛍</div><div>商城暂无上架商品</div>
            </div>
          )}
          {redeemError && (
            <div className="wb-create-form__error" data-testid="wb-points-redeem-error">⚠ {redeemError}</div>
          )}
          {redeemMsg && (
            <div className="wb-smart-card" data-testid="wb-points-redeem-msg" style={{ borderColor: 'rgba(74, 158, 110, 0.5)' }}>
              ✅ {redeemMsg}
            </div>
          )}
          {(mall ?? []).map((item, i) => (
            <div key={item.id} className="wb-smart-card" data-testid={`wb-points-mall--${i}`}>
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{item.name}</div>
                <span className="wb-status-chip wb-status-chip--muted">{item.category}</span>
              </div>
              {item.description && (
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}>{item.description}</div>
              )}
              <div className="wb-smart-card__meta">
                <span>💎 {item.points_required} 积分</span>
                <span>库存 {item.stock}</span>
                <span>有效期 {item.validity_days} 天</span>
              </div>
              <div style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className="wb-theme-option wb-theme-option--active"
                  disabled={redeemingId === item.id || item.stock <= 0}
                  onClick={() => handleRedeem(item)}
                  data-testid={`wb-points-redeem--${i}`}
                >
                  {redeemingId === item.id ? '兑换中…' : item.stock <= 0 ? '已兑罄' : '🎁 兑换'}
                </button>
              </div>
            </div>
          ))}

          {/* 兑换记录 */}
          <div className="wb-section-label" style={{ marginTop: 16 }}>兑换记录（{redemptions?.length ?? 0}）</div>
          {rdLoading && (
            <div className="wb-state" data-testid="wb-points-rd-loading">
              <div className="wb-state__icon">⏳</div><div>加载兑换记录…</div>
            </div>
          )}
          {rdError && !rdLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-points-rd-error">
              <div className="wb-state__icon">⚠</div><div>{rdError}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadRd()} type="button">重试</button>
            </div>
          )}
          {!rdLoading && !rdError && (redemptions?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-points-rd-empty">
              <div className="wb-state__icon">📭</div><div>暂无兑换记录</div>
            </div>
          )}
          {(redemptions ?? []).map((rd, i) => (
            <div key={rd.id} className="wb-smart-card" data-testid={`wb-points-rd--${i}`}>
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{rd.item_name}</div>
                <span className={`wb-status-chip ${rd.status === 'completed' ? 'wb-status-chip--success' : 'wb-status-chip--info'}`}>{rd.status}</span>
              </div>
              <div className="wb-smart-card__meta">
                <span>-{rd.points_spent} 积分</span>
                <span>{fmtTime(rd.created_at)}</span>
                {rd.discount_code && <span>🎟 {rd.discount_code}</span>}
              </div>
            </div>
          ))}

          {/* 流水 */}
          <div className="wb-section-label" style={{ marginTop: 16 }}>积分流水（{transactions?.length ?? 0}）</div>
          {txnLoading && (
            <div className="wb-state" data-testid="wb-points-txn-loading">
              <div className="wb-state__icon">⏳</div><div>加载积分流水…</div>
            </div>
          )}
          {txnError && !txnLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-points-txn-error">
              <div className="wb-state__icon">⚠</div><div>{txnError}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadTxns()} type="button">重试</button>
            </div>
          )}
          {!txnLoading && !txnError && (transactions?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-points-txn-empty">
              <div className="wb-state__icon">📄</div><div>暂无积分流水</div>
            </div>
          )}
          {(transactions ?? []).map((t, i) => (
            <div key={t.id} className="wb-smart-card" data-testid={`wb-points-txn--${i}`}>
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{t.description || t.source}</div>
                <span className={`wb-status-chip ${t.amount >= 0 ? 'wb-status-chip--success' : 'wb-status-chip--warning'}`}>
                  {t.amount >= 0 ? `+${t.amount}` : t.amount}
                </span>
              </div>
              <div className="wb-smart-card__meta">
                <span>{t.transaction_type} · {t.source}</span>
                <span>{fmtTime(t.created_at)}</span>
                <span>余额 {t.balance_after}</span>
              </div>
            </div>
          ))}

          {/* 规则 */}
          <div className="wb-section-label" style={{ marginTop: 16 }}>积分规则（{rules?.length ?? 0}）</div>
          {rulesLoading && (
            <div className="wb-state" data-testid="wb-points-rules-loading">
              <div className="wb-state__icon">⏳</div><div>加载积分规则…</div>
            </div>
          )}
          {rulesError && !rulesLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-points-rules-error">
              <div className="wb-state__icon">⚠</div><div>{rulesError}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadRules()} type="button">重试</button>
            </div>
          )}
          {!rulesLoading && !rulesError && (rules?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-points-rules-empty">
              <div className="wb-state__icon">📜</div><div>暂无积分规则</div>
            </div>
          )}
          {(rules ?? []).map((rule, i) => (
            <div key={rule.id} className="wb-smart-card" data-testid={`wb-points-rule--${i}`}>
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{rule.action}</div>
                <span className="wb-status-chip wb-status-chip--accent">+{rule.points}</span>
              </div>
              <div className="wb-smart-card__meta">
                <span>{ROLE_LABELS[rule.role] ?? rule.role}</span>
                {rule.limit_daily != null && <span>每日上限 {rule.limit_daily}</span>}
                {rule.limit_weekly != null && <span>每周上限 {rule.limit_weekly}</span>}
              </div>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}>{rule.description}</div>
            </div>
          ))}

          {/* 排行榜 */}
          <div className="wb-section-label" style={{ marginTop: 16 }}>年度积分排行榜（{ranking?.length ?? 0}）</div>
          {rankLoading && (
            <div className="wb-state" data-testid="wb-points-rank-loading">
              <div className="wb-state__icon">⏳</div><div>加载排行榜…</div>
            </div>
          )}
          {rankError && !rankLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-points-rank-error">
              <div className="wb-state__icon">⚠</div><div>{rankError}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadRank()} type="button">重试</button>
            </div>
          )}
          {!rankLoading && !rankError && (ranking?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-points-rank-empty">
              <div className="wb-state__icon">🏆</div><div>排行榜暂无数据</div>
            </div>
          )}
          {(ranking ?? []).map((entry, i) => (
            <div key={entry.user_id} className="wb-smart-card" data-testid={`wb-points-rank--${i}`}>
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">
                  <span style={{ color: i < 3 ? 'var(--warning)' : 'var(--text-muted)' }}>#{entry.rank}</span>
                  {' '}{entry.user_name ?? entry.user_id.slice(0, 8)}
                </div>
                <span className="wb-status-chip wb-status-chip--accent">{entry.year_earned} 分</span>
              </div>
              <div className="wb-smart-card__meta">
                <span>{ROLE_LABELS[entry.role] ?? entry.role}</span>
                {entry.level && <span>Lv.{entry.level}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </SuokeLayout>
  );
}
