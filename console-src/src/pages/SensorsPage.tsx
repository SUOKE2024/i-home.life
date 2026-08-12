/**
 * SensorsPage — 传感器能力（v1.13.x 前端缺口补齐 B2）
 *
 * 结构：Scaffold > AppBar(传感器) > 能力声明 + 数据流向说明
 * API（对齐 app/api/sensor_snapshot.py，前缀 /api/sensors）：
 *   GET /api/sensors/capabilities   能力声明
 *
 * 诚实标注：/api/sensors/snapshot 为移动端写通道（Flutter SensorService 实时上报），
 * 非管理查询类 API；本页仅展示能力声明与数据流向，不做伪造展示。
 */

import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { SensorCapabilities } from '../types/domain';

const SENSOR_LABELS: Record<string, string> = {
  accelerometer: '加速度计',
  gyroscope: '陀螺仪',
  magnetometer: '磁力计（罗盘）',
  gps: 'GPS 定位',
};

export default function SensorsPage() {
  const navigate = useNavigate();

  const { data: caps, loading, error, reload } = useAsync<SensorCapabilities | null>(async () => {
    const r = await apiClient.getSensorCapabilities<SensorCapabilities>();
    return r.isSuccess && r.data ? r.data : null;
  }, []);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-sensors-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">📡 传感器</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {loading && (
            <div className="wb-state"><div className="wb-state__icon">⏳</div><div>加载传感器能力中…</div></div>
          )}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-sensors-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-btn wb-btn--sm" onClick={() => reload()} type="button">重试</button>
            </div>
          )}
          {!loading && !error && caps && (
            <div data-testid="wb-sensors-content">
              {/* 能力声明 */}
              <div className="wb-card" data-testid="wb-sensors-capabilities">
                <div className="wb-card__title">支持的后端传感器</div>
                <div className="wb-actions">
                  {(caps.supported_sensors ?? []).map((s) => (
                    <span key={s} className="wb-status-chip wb-status-chip--info">
                      {SENSOR_LABELS[s] ?? s}
                    </span>
                  ))}
                </div>
                <div className="wb-list-row__sub" style={{ marginTop: 10 }}>
                  采样率：{caps.sampling_rate_hz} Hz · 自动场景触发：
                  {caps.auto_trigger_enabled ? ' 已启用' : ' 未启用'}
                </div>
              </div>

              {/* 数据流向说明 */}
              <div className="wb-card" data-testid="wb-sensors-flow">
                <div className="wb-card__title">数据流向</div>
                <div style={{ fontSize: 13, lineHeight: 1.7 }}>
                  <div>1. 移动端 SensorService 实时采集设备读数</div>
                  <div>2. POST {caps.upload_endpoint} 上传快照（真实落库 sensor_snapshots）</div>
                  <div>3. 仅真实可用的 GPS/环境数据参与场景自动化 sensor 触发匹配</div>
                  <div style={{ marginTop: 8, color: 'var(--text-muted)', fontSize: 12 }}>
                    诚实标注：手机传感器无法提供温度/湿度/光照/占用率等环境量，
                    不构造假数据；环境量需接入生态桥接设备后由真实传感器上报。
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
