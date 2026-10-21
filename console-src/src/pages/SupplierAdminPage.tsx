/**
 * SupplierAdminPage — 平台侧供应商认证（v1.19.x）
 *
 * 闭环：console 供应商自助入驻 → 平台管理员在此授予/撤销认证。
 * API：GET /api/procurement/suppliers；PATCH /api/procurement/suppliers/{id}/verify
 * 认证状态由平台授予，页面不提供"自动通过"。
 */

import { useCallback, useEffect, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { apiClient } from '../services/api-client';

const rowStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  padding: '8px 0',
  borderBottom: '1px solid var(--border)',
};

const nameStyle: CSSProperties = {
  fontSize: 14,
  color: 'var(--text-primary)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const metaStyle: CSSProperties = {
  fontSize: 12,
  color: 'var(--text-muted)',
};

interface Supplier {
  id: string;
  name: string;
  category: string;
  contact_name?: string | null;
  phone?: string | null;
  is_verified: boolean;
  created_at: string;
}

export default function SupplierAdminPage() {
  const navigate = useNavigate();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionId, setActionId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const result = await apiClient.request<Supplier[]>('/api/procurement/suppliers');
    setLoading(false);
    if (!result.isSuccess || !result.data) {
      setError(result.error ?? `加载失败（HTTP ${result.status}）`);
      setSuppliers([]);
      return;
    }
    setSuppliers(result.data);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggle(supplier: Supplier) {
    setActionId(supplier.id);
    setError('');
    const result = await apiClient.request<Supplier>(
      `/api/procurement/suppliers/${supplier.id}/verify`,
      {
        method: 'PATCH',
        body: JSON.stringify({ is_verified: !supplier.is_verified }),
      },
    );
    setActionId(null);
    if (!result.isSuccess) {
      setError(result.error ?? `操作失败（HTTP ${result.status}）`);
      return;
    }
    setSuppliers((prev) =>
      prev.map((item) =>
        item.id === supplier.id
          ? { ...item, is_verified: !supplier.is_verified }
          : item,
      ),
    );
  }

  const pending = suppliers.filter((item) => !item.is_verified);
  const verified = suppliers.filter((item) => item.is_verified);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-supplier-admin-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">供应商认证</div>
        </div>

        <div className="wb-page-body">
          <p className="wb-muted">
            认证由平台管理员授予。未认证供应商不可发布产品与接单；
            认证前请核对主体资质，本页不代替线下资质审查。
          </p>

          {loading && <div className="wb-state">加载中…</div>}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-supplier-admin-error">
              {error}
              <button className="wb-btn wb-btn--sm" type="button" onClick={() => void load()}>
                重试
              </button>
            </div>
          )}

          {!loading && !error && (
            <>
              <div className="wb-card">
                <div className="wb-card__title">待认证（{pending.length}）</div>
                {pending.length === 0 ? (
                  <p className="wb-muted">暂无待认证供应商</p>
                ) : (
                  <div>
                    {pending.map((item) => (
                      <div key={item.id} style={rowStyle}>
                        <div style={{ minWidth: 0 }}>
                          <p style={nameStyle}>
                            {item.name} · {item.category}
                          </p>
                          <p style={metaStyle}>
                            {item.contact_name || '未填联系人'} · {item.phone || '未填电话'}
                          </p>
                        </div>
                        <button
                          className="wb-btn wb-btn--sm wb-btn--primary"
                          type="button"
                          disabled={actionId === item.id}
                          onClick={() => void toggle(item)}
                        >
                          {actionId === item.id ? '处理中…' : '授予认证'}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="wb-card">
                <div className="wb-card__title">已认证（{verified.length}）</div>
                {verified.length === 0 ? (
                  <p className="wb-muted">暂无已认证供应商</p>
                ) : (
                  <div>
                    {verified.map((item) => (
                      <div key={item.id} style={rowStyle}>
                        <div style={{ minWidth: 0 }}>
                          <p style={nameStyle}>
                            {item.name} · {item.category}
                          </p>
                          <p style={metaStyle}>
                            {item.contact_name || '未填联系人'} · {item.phone || '未填电话'}
                          </p>
                        </div>
                        <button
                          className="wb-btn wb-btn--sm"
                          type="button"
                          disabled={actionId === item.id}
                          onClick={() => void toggle(item)}
                        >
                          {actionId === item.id ? '处理中…' : '撤销认证'}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
