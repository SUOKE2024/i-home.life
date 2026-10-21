/**
 * SupplierApplyPage — 供应商自助入驻申请（v1.19.x）
 *
 * 背景：此前供应商主体只能由后端 API/种子创建，console 无入驻入口。
 * 本页调用 `POST /api/procurement/suppliers` 提交入驻档案；认证状态
 * `is_verified` 恒为 false，须由平台管理员审核授予，页面不得宣称已认证。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { apiClient } from '../services/api-client';

interface SupplierCreated {
  id: string;
  name: string;
  category: string;
  is_verified: boolean;
  created_at: string;
}

const CATEGORIES = [
  '主材',
  '辅材',
  '家具',
  '家电',
  '软装',
  '门窗',
  '卫浴',
  '灯具',
  '智能家居',
  '其他',
];

export default function SupplierApplyPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: '',
    contact_name: '',
    phone: '',
    address: '',
    category: '主材',
  });
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<SupplierCreated | null>(null);
  const [error, setError] = useState('');

  const update = (key: keyof typeof form, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  async function submit() {
    if (!form.name.trim() || !form.category.trim()) {
      setError('请填写供应商名称与品类');
      return;
    }
    setSubmitting(true);
    setError('');
    const result = await apiClient.request<SupplierCreated>('/api/procurement/suppliers', {
      method: 'POST',
      body: JSON.stringify({
        name: form.name.trim(),
        contact_name: form.contact_name.trim() || null,
        phone: form.phone.trim() || null,
        address: form.address.trim() || null,
        category: form.category.trim(),
      }),
    });
    setSubmitting(false);
    if (!result.isSuccess || !result.data) {
      setError(result.error ?? `提交失败（HTTP ${result.status}）`);
      return;
    }
    setCreated(result.data);
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-supplier-apply-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">供应商入驻申请</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {created ? (
            <div className="wb-card" data-testid="wb-supplier-apply-success">
              <div className="wb-card__title">申请已提交</div>
              <p className="wb-muted">
                供应商「{created.name}」档案已创建，编号 {created.id}。
              </p>
              <p className="wb-muted">
                当前认证状态：<strong>{created.is_verified ? '已认证' : '待平台审核'}</strong>。
                未认证期间暂不支持发布产品与接单；认证通过并由管理员分配供应商角色后，
                供应商工作台才可用。
              </p>
              <div className="wb-actions">
                <button
                  className="wb-btn wb-btn--primary"
                  type="button"
                  onClick={() => navigate('/')}
                >
                  返回工作台
                </button>
                <button
                  className="wb-btn"
                  type="button"
                  onClick={() => {
                    setCreated(null);
                    setForm({ name: '', contact_name: '', phone: '', address: '', category: '主材' });
                  }}
                >
                  再提交一个
                </button>
              </div>
            </div>
          ) : (
            <div className="wb-card">
              <div className="wb-card__title">入驻资料</div>
              <p className="wb-muted">
                提交后由平台审核资质；认证状态以审核结果为准，页面不承诺自动通过。
              </p>

              <label className="wb-field">
                <span>供应商名称 *</span>
                <input
                  value={form.name}
                  onChange={(e) => update('name', e.target.value)}
                  placeholder="如：昆明某某建材有限公司"
                  data-testid="wb-supplier-name"
                />
              </label>
              <label className="wb-field">
                <span>品类 *</span>
                <select
                  value={form.category}
                  onChange={(e) => update('category', e.target.value)}
                  data-testid="wb-supplier-category"
                >
                  {CATEGORIES.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label className="wb-field">
                <span>联系人</span>
                <input
                  value={form.contact_name}
                  onChange={(e) => update('contact_name', e.target.value)}
                  placeholder="联系人姓名"
                />
              </label>
              <label className="wb-field">
                <span>联系电话</span>
                <input
                  value={form.phone}
                  onChange={(e) => update('phone', e.target.value)}
                  placeholder="手机号"
                />
              </label>
              <label className="wb-field">
                <span>地址</span>
                <input
                  value={form.address}
                  onChange={(e) => update('address', e.target.value)}
                  placeholder="经营地址"
                />
              </label>

              {error && (
                <p className="wb-error" data-testid="wb-supplier-apply-error">{error}</p>
              )}

              <div className="wb-actions">
                <button
                  className="wb-btn wb-btn--primary"
                  type="button"
                  disabled={submitting}
                  onClick={submit}
                  data-testid="wb-supplier-apply-submit"
                >
                  {submitting ? '提交中…' : '提交入驻申请'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
