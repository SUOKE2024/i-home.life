/**
 * SurveysPage — 量房 / AR 空间扫描
 *
 * 结构：Scaffold > AppBar(量房/AR扫描) > [项目选择器] + 设备能力检测 + 创建量房
 *   + 量房列表（详情/编辑/应用/删除）+ AR 会话（创建/列表/开始/应用/删除）
 * API（对齐 app/api/surveys.py，前缀 /api/surveys）：
 *   GET  /api/surveys/device-check                 设备能力检测（LiDAR/摄像头/语音）
 *   POST /api/surveys                              创建量房记录
 *   GET  /api/surveys/project/{projectId}          项目量房列表
 *   GET  /api/surveys/{surveyId}                   量房详情
 *   PUT  /api/surveys/{surveyId}                   更新量房
 *   DELETE /api/surveys/{surveyId}                 删除量房
 *   POST /api/surveys/{surveyId}/apply             应用量房生成户型
 *   GET  /api/surveys/ar/sessions/project/{projectId}  AR 会话列表
 *   POST /api/surveys/ar/sessions                  创建 AR 扫描会话
 *   POST /api/surveys/ar/sessions/{id}/start       开始扫描
 *   POST /api/surveys/ar/sessions/{id}/apply       应用扫描结果到量房
 *   DELETE /api/surveys/ar/sessions/{id}           删除会话
 *
 * 诚实降级：isSuccess=false 展示后端真实 error；AR 仅做会话级集成，不做端内 AR 交互。
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  ARScanSession,
  ARScanSessionListItem,
  Project,
  RoomMeasureItem,
  SurveyDetail,
  SurveyDeviceCheck,
  SurveyItem,
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

const METHOD_LABELS: Record<string, string> = {
  manual: '手动测量',
  lidar: 'LiDAR 扫描',
  visual: '视觉辅助',
  photo: '拍照建模',
  voice_guided: '语音引导',
};

const ROOM_TYPE_OPTIONS = ['living_room', 'bedroom', 'kitchen', 'bathroom', 'study', 'balcony'];

const AR_STATUS_TONE: Record<string, string> = {
  completed: 'wb-status-chip--success',
  failed: 'wb-status-chip--danger',
  scanning: 'wb-status-chip--info',
  processing: 'wb-status-chip--info',
  uploaded: 'wb-status-chip--warning',
  created: 'wb-status-chip--muted',
};

interface RoomRow {
  name: string;
  room_type: string;
  width: string;
  length: string;
  height: string;
}

const EMPTY_ROOM: RoomRow = { name: '', room_type: 'bedroom', width: '', length: '', height: '' };

export default function SurveysPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');

  // 设备能力检测（按钮触发）
  const [deviceCheck, setDeviceCheck] = useState<SurveyDeviceCheck | null>(null);
  const [deviceLoading, setDeviceLoading] = useState(false);
  const [deviceError, setDeviceError] = useState<string | null>(null);

  // 创建量房
  const [surveyForm, setSurveyForm] = useState({
    name: '现场测量',
    surveyor: '',
    method: 'manual',
    scene_type: 'indoor',
    wall_height: '2.8',
    rooms: [{ ...EMPTY_ROOM }] as RoomRow[],
  });
  const [createError, setCreateError] = useState<string | null>(null);
  const [createMsg, setCreateMsg] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  // 量房详情 / 编辑
  const [selectedSurveyId, setSelectedSurveyId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: '', surveyor: '', method: 'manual', scene_type: 'indoor', wall_height: '2.8', notes: '' });
  const [editError, setEditError] = useState<string | null>(null);
  const [editMsg, setEditMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  // AR 会话
  const [arForm, setArForm] = useState({ name: 'AR 扫描', platform: 'ios', requested_method: 'lidar', wall_height: '2.8', floor_count: '1' });
  const [arError, setArError] = useState<string | null>(null);
  const [arMsg, setArMsg] = useState<string | null>(null);
  const [arCreating, setArCreating] = useState(false);

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    const pid = selectedProjectId || projects?.[0]?.id || '';
    setSelectedProjectId(pid);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projects]);

  const { data: surveys, loading: surveysLoading, error: surveysError, reload: reloadSurveys } =
    useAsync<SurveyItem[] | null>(async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.listSurveys<SurveyItem[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载量房列表失败');
      return r.data;
    }, [selectedProjectId]);

  const { data: surveyDetail, loading: detailLoading, error: detailError } =
    useAsync<SurveyDetail | null>(async () => {
      if (!selectedSurveyId) return null;
      const r = await apiClient.getSurvey<SurveyDetail>(selectedSurveyId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载量房详情失败');
      return r.data;
    }, [selectedSurveyId]);

  const { data: arSessions, loading: arLoading, error: arErrorList, reload: reloadAr } =
    useAsync<ARScanSessionListItem[] | null>(async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.listARScanSessions<ARScanSessionListItem[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载 AR 会话失败');
      return r.data;
    }, [selectedProjectId]);

  async function handleDeviceCheck() {
    setDeviceLoading(true);
    setDeviceError(null);
    try {
      const r = await apiClient.getSurveyDeviceCheck<SurveyDeviceCheck>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '设备能力检测失败');
      setDeviceCheck(r.data);
    } catch (err) {
      setDeviceError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeviceLoading(false);
    }
  }

  function updateRoom(index: number, key: keyof RoomRow, value: string) {
    setSurveyForm((f) => ({
      ...f,
      rooms: f.rooms.map((room, i) => (i === index ? { ...room, [key]: value } : room)),
    }));
  }

  function addRoom() {
    setSurveyForm((f) => ({ ...f, rooms: [...f.rooms, { ...EMPTY_ROOM }] }));
  }

  function removeRoom(index: number) {
    setSurveyForm((f) => ({ ...f, rooms: f.rooms.filter((_, i) => i !== index) }));
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    setCreateMsg(null);
    setCreating(true);
    try {
      if (!selectedProjectId) throw new Error('请先选择项目');
      const rooms: RoomMeasureItem[] = surveyForm.rooms.map((room) => ({
        name: room.name.trim(),
        room_type: room.room_type,
        width: parseFloat(room.width) || 0,
        length: parseFloat(room.length) || 0,
        height: room.height.trim() ? parseFloat(room.height) || null : null,
        area: null,
        notes: null,
      }));
      if (rooms.length === 0 || rooms.some((r) => !r.name)) throw new Error('请填写至少一个房间名称');
      if (rooms.some((r) => r.width <= 0 || r.length <= 0)) throw new Error('房间宽/长必须大于 0');
      const r = await apiClient.createSurvey<SurveyDetail>({
        project_id: selectedProjectId,
        name: surveyForm.name.trim() || '现场测量',
        surveyor: surveyForm.surveyor.trim() || null,
        method: surveyForm.method,
        scene_type: surveyForm.scene_type,
        wall_height: parseFloat(surveyForm.wall_height) || 2.8,
        rooms,
      });
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '创建量房失败');
      setCreateMsg(`量房「${r.data.name}」已创建，总面积 ${r.data.total_area}㎡`);
      reloadSurveys();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  }

  function startEdit(survey: SurveyItem) {
    setEditingId(survey.id);
    setEditForm({
      name: survey.name,
      surveyor: survey.surveyor ?? '',
      method: survey.method,
      scene_type: survey.scene_type,
      wall_height: String(survey.wall_height ?? 2.8),
      notes: '',
    });
    setEditError(null);
    setEditMsg(null);
  }

  async function handleSaveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editingId) return;
    setEditError(null);
    setEditMsg(null);
    setSaving(true);
    try {
      const r = await apiClient.updateSurvey<SurveyDetail>(editingId, {
        name: editForm.name.trim() || undefined,
        surveyor: editForm.surveyor.trim() || null,
        method: editForm.method,
        scene_type: editForm.scene_type,
        wall_height: parseFloat(editForm.wall_height) || undefined,
        notes: editForm.notes.trim() || null,
      });
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '更新量房失败');
      setEditMsg('量房已更新');
      setEditingId(null);
      reloadSurveys();
      if (selectedSurveyId === editingId) setSelectedSurveyId(editingId);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(surveyId: string) {
    setActionError(null);
    setActionMsg(null);
    try {
      const r = await apiClient.deleteSurvey(surveyId);
      if (!r.isSuccess) throw new Error(r.error ?? '删除失败');
      if (selectedSurveyId === surveyId) setSelectedSurveyId(null);
      reloadSurveys();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleApply(surveyId: string) {
    setActionError(null);
    setActionMsg(null);
    try {
      const r = await apiClient.applySurvey(surveyId);
      if (!r.isSuccess) throw new Error(r.error ?? '应用量房失败');
      setActionMsg('量房数据已应用到项目（已生成户型）');
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleCreateAr(e: React.FormEvent) {
    e.preventDefault();
    setArError(null);
    setArMsg(null);
    setArCreating(true);
    try {
      if (!selectedProjectId) throw new Error('请先选择项目');
      const r = await apiClient.createARScanSession<ARScanSession>({
        project_id: selectedProjectId,
        name: arForm.name.trim() || 'AR 扫描',
        platform: arForm.platform,
        requested_method: arForm.requested_method,
        wall_height: parseFloat(arForm.wall_height) || 2.8,
        floor_count: parseInt(arForm.floor_count, 10) || 1,
      });
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '创建 AR 会话失败');
      setArMsg(`AR 扫描会话已创建（${r.data.scan_method}）`);
      reloadAr();
    } catch (err) {
      setArError(err instanceof Error ? err.message : String(err));
    } finally {
      setArCreating(false);
    }
  }

  async function handleArAction(session: ARScanSessionListItem, action: 'start' | 'apply' | 'delete') {
    setArError(null);
    setArMsg(null);
    try {
      if (action === 'start') {
        const r = await apiClient.startARScan<ARScanSession>(session.id);
        if (!r.isSuccess || !r.data) throw new Error(r.error ?? '开始扫描失败');
        setArMsg(`会话「${session.name}」已开始扫描`);
      } else if (action === 'apply') {
        const r = await apiClient.applyARScanSession(session.id);
        if (!r.isSuccess) throw new Error(r.error ?? '应用扫描结果失败');
        setArMsg('扫描结果已应用到量房');
      } else {
        const r = await apiClient.deleteARScanSession(session.id);
        if (!r.isSuccess) throw new Error(r.error ?? '删除会话失败');
        setArMsg('会话已删除');
      }
      reloadAr();
    } catch (err) {
      setArError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-surveys-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">📏 量房 / AR 扫描</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 项目选择器 */}
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-surveys-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {/* 设备能力检测 */}
          <div className="wb-create-form" data-testid="wb-surveys-device-check">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">📡</div>
              <div>
                <div className="wb-create-form__title">设备能力检测</div>
                <div className="wb-create-form__subtitle">查看 LiDAR / 摄像头 / 语音 / 传感器可用硬件能力与推荐工作流</div>
              </div>
            </div>
            <div className="wb-create-form__body">
              {deviceError && (
                <div className="wb-create-form__error" data-testid="wb-surveys-device-error">⚠ {deviceError}</div>
              )}
              <div className="wb-create-form__actions">
                <button className="wb-theme-option wb-theme-option--active" type="button" onClick={handleDeviceCheck} disabled={deviceLoading} data-testid="wb-surveys-device-btn">
                  {deviceLoading ? '检测中…' : '📡 检测设备能力'}
                </button>
              </div>
              {deviceCheck && (
                <div data-testid="wb-surveys-device-result" style={{ marginTop: 10 }}>
                  {Object.entries(deviceCheck.available_sensors ?? {}).map(([name, info]) => (
                    <div key={name} className="wb-smart-card" data-testid={`wb-surveys-device-sensor--${name}`}>
                      <div className="wb-smart-card__head">
                        <div className="wb-smart-card__room">{name}</div>
                        <span className="wb-status-chip wb-status-chip--info">{(info as Record<string, unknown>)?.api as string}</span>
                      </div>
                      <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}>
                        {JSON.stringify(info)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 创建量房 */}
          <div className="wb-create-form" style={{ marginTop: 16 }} data-testid="wb-surveys-create">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">📏</div>
              <div>
                <div className="wb-create-form__title">创建量房记录</div>
                <div className="wb-create-form__subtitle">手动录入房间尺寸（method: manual / lidar / visual / photo / voice_guided）</div>
              </div>
            </div>
            <form onSubmit={handleCreate}>
              <div className="wb-create-form__body">
                <div className="wb-create-form__row">
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-surveys-create-name">名称</label>
                    <input id="wb-surveys-create-name" className="wb-input" value={surveyForm.name} onChange={(e) => setSurveyForm((f) => ({ ...f, name: e.target.value }))} data-testid="wb-surveys-create-name" />
                  </div>
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-surveys-create-surveyor">测量人</label>
                    <input id="wb-surveys-create-surveyor" className="wb-input" value={surveyForm.surveyor} onChange={(e) => setSurveyForm((f) => ({ ...f, surveyor: e.target.value }))} data-testid="wb-surveys-create-surveyor" />
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-surveys-create-method">测量方式</label>
                    <select id="wb-surveys-create-method" className="wb-input" value={surveyForm.method} onChange={(e) => setSurveyForm((f) => ({ ...f, method: e.target.value }))} data-testid="wb-surveys-create-method">
                      {Object.entries(METHOD_LABELS).map(([value, label]) => (<option key={value} value={value}>{label}</option>))}
                    </select>
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-surveys-create-scene">场景</label>
                    <select id="wb-surveys-create-scene" className="wb-input" value={surveyForm.scene_type} onChange={(e) => setSurveyForm((f) => ({ ...f, scene_type: e.target.value }))} data-testid="wb-surveys-create-scene">
                      <option value="indoor">室内</option>
                      <option value="outdoor">室外</option>
                      <option value="balcony">阳台</option>
                    </select>
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-surveys-create-height">层高（m）</label>
                    <input id="wb-surveys-create-height" className="wb-input wb-input--num" type="number" min={2} max={5} step={0.1} value={surveyForm.wall_height} onChange={(e) => setSurveyForm((f) => ({ ...f, wall_height: e.target.value }))} data-testid="wb-surveys-create-height" />
                  </div>
                </div>

                <div className="wb-create-form__label" style={{ marginTop: 4 }}>房间列表（{surveyForm.rooms.length}）</div>
                {surveyForm.rooms.map((room, index) => (
                  <div key={index} className="wb-create-form__row" style={{ marginTop: 8 }}>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label">房间名 <span className="wb-create-form__required">*</span></label>
                      <input className="wb-input" value={room.name} onChange={(e) => updateRoom(index, 'name', e.target.value)} placeholder="如：主卧" data-testid={`wb-surveys-room-name--${index}`} />
                    </div>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label">类型</label>
                      <select className="wb-input" value={room.room_type} onChange={(e) => updateRoom(index, 'room_type', e.target.value)} data-testid={`wb-surveys-room-type--${index}`}>
                        {ROOM_TYPE_OPTIONS.map((t) => (<option key={t} value={t}>{t}</option>))}
                      </select>
                    </div>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label">宽（m）<span className="wb-create-form__required">*</span></label>
                      <input className="wb-input wb-input--num" type="number" min={0.1} step={0.1} value={room.width} onChange={(e) => updateRoom(index, 'width', e.target.value)} data-testid={`wb-surveys-room-width--${index}`} />
                    </div>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label">长（m）<span className="wb-create-form__required">*</span></label>
                      <input className="wb-input wb-input--num" type="number" min={0.1} step={0.1} value={room.length} onChange={(e) => updateRoom(index, 'length', e.target.value)} data-testid={`wb-surveys-room-length--${index}`} />
                    </div>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label">层高（m）</label>
                      <input className="wb-input wb-input--num" type="number" min={2} max={5} step={0.1} value={room.height} onChange={(e) => updateRoom(index, 'height', e.target.value)} data-testid={`wb-surveys-room-height--${index}`} />
                    </div>
                    <div className="wb-create-form__field" style={{ justifyContent: 'flex-end' }}>
                      <button type="button" className="wb-theme-option" onClick={() => removeRoom(index)} disabled={surveyForm.rooms.length <= 1} data-testid={`wb-surveys-room-remove--${index}`}>移除</button>
                    </div>
                  </div>
                ))}
                <div style={{ marginTop: 8 }}>
                  <button type="button" className="wb-theme-option" onClick={addRoom} data-testid="wb-surveys-room-add">＋ 添加房间</button>
                </div>

                {createError && (
                  <div className="wb-create-form__error" data-testid="wb-surveys-create-error">⚠ {createError}</div>
                )}
                {createMsg && (
                  <div className="wb-smart-card" data-testid="wb-surveys-create-msg">✅ {createMsg}</div>
                )}
                <div className="wb-create-form__actions">
                  <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={creating} data-testid="wb-surveys-create-submit">
                    {creating ? '提交中…' : '📏 创建量房'}
                  </button>
                </div>
              </div>
            </form>
          </div>

          {/* 量房列表 */}
          <div className="wb-section-label" style={{ marginTop: 16 }}>项目量房（{surveys?.length ?? 0}）</div>
          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-surveys-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && surveysLoading && (
            <div className="wb-state" data-testid="wb-surveys-loading">
              <div className="wb-state__icon">⏳</div><div>加载量房列表…</div>
            </div>
          )}
          {selectedProjectId && surveysError && !surveysLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-surveys-error">
              <div className="wb-state__icon">⚠</div><div>{surveysError}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadSurveys()} type="button">重试</button>
            </div>
          )}
          {selectedProjectId && !surveysLoading && !surveysError && (surveys?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-surveys-empty">
              <div className="wb-state__icon">📭</div><div>该项目暂无量房记录</div>
            </div>
          )}
          {actionError && (
            <div className="wb-create-form__error" data-testid="wb-surveys-action-error">⚠ {actionError}</div>
          )}
          {actionMsg && (
            <div className="wb-smart-card" data-testid="wb-surveys-action-msg">✅ {actionMsg}</div>
          )}
          {(surveys ?? []).map((survey, i) => (
            <div key={survey.id} className="wb-smart-card" data-testid={`wb-surveys-item--${i}`}>
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{survey.name}</div>
                <span className="wb-status-chip wb-status-chip--muted">{METHOD_LABELS[survey.method] ?? survey.method} · {survey.status}</span>
              </div>
              <div className="wb-smart-card__meta">
                <span>总面积 {survey.total_area}㎡</span>
                <span>层高 {survey.wall_height}m</span>
                <span>{fmtTime(survey.created_at)}</span>
              </div>
              <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" className="wb-theme-option" onClick={() => { setSelectedSurveyId(survey.id); setActionError(null); setActionMsg(null); }} data-testid={`wb-surveys-detail--${i}`}>详情</button>
                <button type="button" className="wb-theme-option" onClick={() => startEdit(survey)} data-testid={`wb-surveys-edit--${i}`}>编辑</button>
                <button type="button" className="wb-theme-option wb-theme-option--active" onClick={() => handleApply(survey.id)} data-testid={`wb-surveys-apply--${i}`}>应用</button>
                <button type="button" className="wb-theme-option" onClick={() => handleDelete(survey.id)} data-testid={`wb-surveys-delete--${i}`}>删除</button>
              </div>
            </div>
          ))}

          {/* 量房详情 */}
          {selectedSurveyId && detailLoading && (
            <div className="wb-state" data-testid="wb-surveys-detail-loading">
              <div className="wb-state__icon">⏳</div><div>加载量房详情…</div>
            </div>
          )}
          {selectedSurveyId && detailError && !detailLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-surveys-detail-error">
              <div className="wb-state__icon">⚠</div><div>{detailError}</div>
            </div>
          )}
          {surveyDetail && !detailLoading && !detailError && (
            <div className="wb-smart-card" data-testid="wb-surveys-detail">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">量房详情：{surveyDetail.name}</div>
                <span className="wb-status-chip wb-status-chip--muted">{surveyDetail.rooms.length} 个房间</span>
              </div>
              {surveyDetail.rooms.map((room, ri) => (
                <div key={ri} className="wb-smart-card__meta" data-testid={`wb-surveys-detail-room--${ri}`}>
                  <span>{room.name}（{room.room_type}）</span>
                  <span>{room.width}m × {room.length}m{room.height ? ` × ${room.height}m` : ''}</span>
                </div>
              ))}
              {surveyDetail.notes && (
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}>备注：{surveyDetail.notes}</div>
              )}
            </div>
          )}

          {/* 编辑量房 */}
          {editingId && (
            <div className="wb-create-form" style={{ marginTop: 16 }} data-testid="wb-surveys-edit">
              <div className="wb-create-form__head">
                <div className="wb-create-form__badge">✏️</div>
                <div>
                  <div className="wb-create-form__title">编辑量房</div>
                  <div className="wb-create-form__subtitle">更新基本信息（房间尺寸请在详情中确认后整体重建）</div>
                </div>
              </div>
              <form onSubmit={handleSaveEdit}>
                <div className="wb-create-form__body">
                  <div className="wb-create-form__row">
                    <div className="wb-create-form__field wb-create-form__field--grow">
                      <label className="wb-create-form__label" htmlFor="wb-surveys-edit-name">名称</label>
                      <input id="wb-surveys-edit-name" className="wb-input" value={editForm.name} onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))} data-testid="wb-surveys-edit-name" />
                    </div>
                    <div className="wb-create-form__field wb-create-form__field--grow">
                      <label className="wb-create-form__label" htmlFor="wb-surveys-edit-surveyor">测量人</label>
                      <input id="wb-surveys-edit-surveyor" className="wb-input" value={editForm.surveyor} onChange={(e) => setEditForm((f) => ({ ...f, surveyor: e.target.value }))} data-testid="wb-surveys-edit-surveyor" />
                    </div>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label" htmlFor="wb-surveys-edit-method">测量方式</label>
                      <select id="wb-surveys-edit-method" className="wb-input" value={editForm.method} onChange={(e) => setEditForm((f) => ({ ...f, method: e.target.value }))} data-testid="wb-surveys-edit-method">
                        {Object.entries(METHOD_LABELS).map(([value, label]) => (<option key={value} value={value}>{label}</option>))}
                      </select>
                    </div>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label" htmlFor="wb-surveys-edit-height">层高（m）</label>
                      <input id="wb-surveys-edit-height" className="wb-input wb-input--num" type="number" min={2} max={5} step={0.1} value={editForm.wall_height} onChange={(e) => setEditForm((f) => ({ ...f, wall_height: e.target.value }))} data-testid="wb-surveys-edit-height" />
                    </div>
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-surveys-edit-notes">备注</label>
                    <input id="wb-surveys-edit-notes" className="wb-input" value={editForm.notes} onChange={(e) => setEditForm((f) => ({ ...f, notes: e.target.value }))} data-testid="wb-surveys-edit-notes" />
                  </div>
                  {editError && (
                    <div className="wb-create-form__error" data-testid="wb-surveys-edit-error">⚠ {editError}</div>
                  )}
                  {editMsg && (
                    <div className="wb-smart-card" data-testid="wb-surveys-edit-msg">✅ {editMsg}</div>
                  )}
                  <div className="wb-create-form__actions" style={{ display: 'flex', gap: 8 }}>
                    <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={saving} data-testid="wb-surveys-edit-submit">
                      {saving ? '保存中…' : '💾 保存'}
                    </button>
                    <button className="wb-theme-option" type="button" onClick={() => setEditingId(null)} data-testid="wb-surveys-edit-cancel">取消</button>
                  </div>
                </div>
              </form>
            </div>
          )}

          {/* AR 会话 */}
          <div className="wb-section-label" style={{ marginTop: 16 }}>AR 扫描会话（{arSessions?.length ?? 0}）</div>
          <div className="wb-create-form" style={{ marginTop: 8 }} data-testid="wb-surveys-ar-create">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">📱</div>
              <div>
                <div className="wb-create-form__title">创建 AR 扫描会话</div>
                <div className="wb-create-form__subtitle">简单集成：创建会话后可开始扫描，完成后应用结果到量房（端内 AR 交互不在本页）</div>
              </div>
            </div>
            <form onSubmit={handleCreateAr}>
              <div className="wb-create-form__body">
                <div className="wb-create-form__row">
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-surveys-ar-name">会话名称</label>
                    <input id="wb-surveys-ar-name" className="wb-input" value={arForm.name} onChange={(e) => setArForm((f) => ({ ...f, name: e.target.value }))} data-testid="wb-surveys-ar-name" />
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-surveys-ar-platform">平台</label>
                    <select id="wb-surveys-ar-platform" className="wb-input" value={arForm.platform} onChange={(e) => setArForm((f) => ({ ...f, platform: e.target.value }))} data-testid="wb-surveys-ar-platform">
                      <option value="ios">iOS</option>
                      <option value="android">Android</option>
                      <option value="harmonyos">HarmonyOS</option>
                      <option value="web">Web</option>
                    </select>
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-surveys-ar-method">扫描方式</label>
                    <select id="wb-surveys-ar-method" className="wb-input" value={arForm.requested_method} onChange={(e) => setArForm((f) => ({ ...f, requested_method: e.target.value }))} data-testid="wb-surveys-ar-method">
                      <option value="lidar">LiDAR</option>
                      <option value="visual_slam">视觉 SLAM</option>
                      <option value="photogrammetry">拍照建模</option>
                      <option value="manual">手动</option>
                    </select>
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-surveys-ar-height">层高（m）</label>
                    <input id="wb-surveys-ar-height" className="wb-input wb-input--num" type="number" min={2} max={5} step={0.1} value={arForm.wall_height} onChange={(e) => setArForm((f) => ({ ...f, wall_height: e.target.value }))} data-testid="wb-surveys-ar-height" />
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-surveys-ar-floors">楼层数</label>
                    <input id="wb-surveys-ar-floors" className="wb-input wb-input--num" type="number" min={1} max={10} value={arForm.floor_count} onChange={(e) => setArForm((f) => ({ ...f, floor_count: e.target.value }))} data-testid="wb-surveys-ar-floors" />
                  </div>
                </div>
                {arError && (
                  <div className="wb-create-form__error" data-testid="wb-surveys-ar-error">⚠ {arError}</div>
                )}
                {arMsg && (
                  <div className="wb-smart-card" data-testid="wb-surveys-ar-msg">✅ {arMsg}</div>
                )}
                <div className="wb-create-form__actions">
                  <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={arCreating} data-testid="wb-surveys-ar-create-submit">
                    {arCreating ? '创建中…' : '📱 创建会话'}
                  </button>
                </div>
              </div>
            </form>
          </div>

          {selectedProjectId && arLoading && (
            <div className="wb-state" data-testid="wb-surveys-ar-loading">
              <div className="wb-state__icon">⏳</div><div>加载 AR 会话…</div>
            </div>
          )}
          {selectedProjectId && arErrorList && !arLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-surveys-ar-error-list">
              <div className="wb-state__icon">⚠</div><div>{arErrorList}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadAr()} type="button">重试</button>
            </div>
          )}
          {selectedProjectId && !arLoading && !arErrorList && (arSessions?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-surveys-ar-empty">
              <div className="wb-state__icon">📱</div><div>该项目暂无 AR 扫描会话</div>
            </div>
          )}
          {(arSessions ?? []).map((session, i) => (
            <div key={session.id} className="wb-smart-card" data-testid={`wb-surveys-ar-session--${i}`}>
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{session.name}</div>
                <span className={`wb-status-chip ${AR_STATUS_TONE[session.status] ?? 'wb-status-chip--muted'}`}>{session.status}</span>
              </div>
              <div className="wb-smart-card__meta">
                <span>{session.scan_method} · {session.platform}</span>
                <span>房间 {session.room_count}</span>
                <span>面积 {session.total_area}㎡</span>
                {session.accuracy_level && <span>精度 {session.accuracy_level}</span>}
                <span>{fmtTime(session.created_at)}</span>
              </div>
              <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {(session.status === 'created' || session.status === 'failed') && (
                  <button type="button" className="wb-theme-option wb-theme-option--active" onClick={() => handleArAction(session, 'start')} data-testid={`wb-surveys-ar-start--${i}`}>开始扫描</button>
                )}
                {session.status === 'completed' && (
                  <button type="button" className="wb-theme-option wb-theme-option--active" onClick={() => handleArAction(session, 'apply')} data-testid={`wb-surveys-ar-apply--${i}`}>应用到量房</button>
                )}
                <button type="button" className="wb-theme-option" onClick={() => handleArAction(session, 'delete')} data-testid={`wb-surveys-ar-delete--${i}`}>删除</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </SuokeLayout>
  );
}
