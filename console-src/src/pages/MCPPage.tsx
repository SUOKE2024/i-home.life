/**
 * MCPPage — MCP Server 管理（v1.3.0 对齐 MCP 2026-07-28 规范）
 *
 * 结构：Scaffold > AppBar(MCP Server) > manifest 元信息 > 工具列表 > 工具调用演示 > MRTR 待响应请求
 * API（对齐 app/api/mcp.py + app/mcp/server.py）：
 *   GET  /api/mcp/manifest    服务器元信息（公开，向后兼容端点）
 *   GET  /api/mcp/tools       工具列表（需 PASETO 认证，MCP 协议格式）
 *   POST /api/mcp/tools/call  调用工具（含 project_id 时校验项目归属，越权 403）
 *   GET  /api/mcp/mrtr        MRTR 待响应请求列表（flag mcp_mrtr_enabled 关闭返回 503）
 *
 * 工具调用失败属业务错误：isError=True 上报，页面按真实结果展示。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  MCPManifest,
  MCPMrtrListResponse,
  MCPToolCallResult,
  MCPToolsResponse,
} from '../types/domain';

/** 404/503 多为灰度 flag 未启用，追加诚实提示（保留后端真实 error 文案） */
function flagGuardMessage(status: number, error?: string): string {
  if (status === 404 || status === 503) {
    return `功能未启用（灰度 flag 默认关闭）：${error ?? `HTTP ${status}`}`;
  }
  return error ?? `HTTP ${status}`;
}

export default function MCPPage() {
  const navigate = useNavigate();

  // 工具调用演示
  const [callToolName, setCallToolName] = useState('');
  const [callArgsJson, setCallArgsJson] = useState('{}');
  const [calling, setCalling] = useState(false);
  const [callResult, setCallResult] = useState<MCPToolCallResult | null>(null);
  const [opError, setOpError] = useState<string | null>(null);

  const {
    data: manifest,
    loading: manifestLoading,
    error: manifestError,
    reload: reloadManifest,
  } = useAsync<MCPManifest | null>(async () => {
    const r = await apiClient.getMCPManifest<MCPManifest>();
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, []);

  const {
    data: toolsResp,
    loading: toolsLoading,
    error: toolsError,
    reload: reloadTools,
  } = useAsync<MCPToolsResponse | null>(async () => {
    const r = await apiClient.listMCPTools<MCPToolsResponse>();
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, []);

  const {
    data: mrtr,
    loading: mrtrLoading,
    error: mrtrError,
    reload: reloadMrtr,
  } = useAsync<MCPMrtrListResponse | null>(async () => {
    const r = await apiClient.listMCPMrtr<MCPMrtrListResponse>();
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, []);

  const tools = toolsResp?.tools ?? [];
  const requests = mrtr?.requests ?? [];

  async function handleCallTool() {
    let args: Record<string, unknown>;
    try {
      args = JSON.parse(callArgsJson || '{}');
    } catch {
      setOpError('arguments 必须是合法 JSON 对象');
      return;
    }
    setCalling(true);
    setOpError(null);
    setCallResult(null);
    try {
      const r = await apiClient.callMCPTool<MCPToolCallResult>(callToolName, args);
      if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
      setCallResult(r.data);
    } catch (err) {
      setOpError(err instanceof Error ? err.message : String(err));
    } finally {
      setCalling(false);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-mcp-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🔌 MCP Server</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {opError && (
            <div
              className="wb-create-form__error"
              style={{ marginBottom: 12 }}
              data-testid="wb-mcp-op-error"
            >
              ⚠ {opError}
            </div>
          )}

          {/* manifest */}
          <div className="wb-section-label">服务器元信息</div>
          {manifestLoading && (
            <div className="wb-state" data-testid="wb-mcp-manifest-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载 manifest…</div>
            </div>
          )}
          {manifestError && !manifestLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-mcp-manifest-error">
              <div className="wb-state__icon">⚠</div>
              <div>{manifestError}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reloadManifest}
                type="button"
              >
                重试
              </button>
            </div>
          )}
          {manifest && !manifestLoading && (
            <div className="wb-smart-card" data-testid="wb-mcp-manifest">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{manifest.name}</div>
                <span className="wb-status-chip wb-status-chip--muted">
                  v{manifest.version}
                </span>
                <span className="wb-status-chip wb-status-chip--info">
                  {manifest.protocol_version}
                </span>
              </div>
              <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                <span>🧰 工具数 {manifest.tools_count}</span>
              </div>
              {manifest.deprecated && (
                <div
                  style={{
                    fontSize: 'var(--font-size-xs)',
                    color: 'var(--warning)',
                    marginTop: 4,
                  }}
                >
                  ⚠ {manifest.deprecated}
                </div>
              )}
              <pre
                style={{
                  fontSize: 'var(--font-size-xs)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                  margin: '8px 0 0',
                }}
              >
                {JSON.stringify(manifest.capabilities, null, 2)}
              </pre>
            </div>
          )}

          {/* 工具列表 */}
          <div className="wb-section-label" style={{ marginTop: 20 }}>
            工具列表（{tools.length}）
          </div>
          {toolsLoading && (
            <div className="wb-state" data-testid="wb-mcp-tools-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载工具列表…</div>
            </div>
          )}
          {toolsError && !toolsLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-mcp-tools-error">
              <div className="wb-state__icon">⚠</div>
              <div>{toolsError}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reloadTools}
                type="button"
              >
                重试
              </button>
            </div>
          )}
          {!toolsLoading && !toolsError && tools.length === 0 && (
            <div className="wb-state" data-testid="wb-mcp-tools-empty">
              <div className="wb-state__icon">🧰</div>
              <div>暂无可用工具</div>
            </div>
          )}
          {!toolsLoading && !toolsError && tools.length > 0 && (
            <div data-testid="wb-mcp-tools-content">
              {tools.map((tool, i) => (
                <div key={tool.name} className="wb-smart-card" data-testid={`wb-mcp-tool--${i}`}>
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">{tool.name}</div>
                    <span className="wb-status-chip wb-status-chip--muted">
                      {tool.annotations?.category ?? '-'}
                    </span>
                  </div>
                  <div style={{ fontSize: 'var(--font-size-xs)', marginTop: 4 }}>
                    {tool.description || '-'}
                  </div>
                  <div
                    style={{
                      fontSize: 'var(--font-size-xs)',
                      color: 'var(--text-muted)',
                      marginTop: 6,
                    }}
                  >
                    参数（{Object.keys(tool.inputSchema?.properties ?? {}).length}）：{' '}
                    {Object.keys(tool.inputSchema?.properties ?? {}).join('、') || '-'}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* 工具调用演示 */}
          <div className="wb-create-form" style={{ marginTop: 20 }} data-testid="wb-mcp-call">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">⚡</div>
              <div>
                <div className="wb-create-form__title">工具调用演示</div>
                <div className="wb-create-form__subtitle">
                  参数含 project_id 时校验项目归属；工具执行失败以 isError=True 上报而非 HTTP 异常
                </div>
              </div>
            </div>
            <div className="wb-create-form__body">
              <div className="wb-create-form__field">
                <label className="wb-create-form__label" htmlFor="wb-mcp-call-tool">
                  工具 <span className="wb-create-form__required">*</span>
                </label>
                <select
                  id="wb-mcp-call-tool"
                  className="wb-input"
                  value={callToolName}
                  onChange={(e) => {
                    setCallToolName(e.target.value);
                    const tool = tools.find((t) => t.name === e.target.value);
                    if (tool) {
                      const props = Object.keys(tool.inputSchema?.properties ?? {});
                      if (props.length > 0) {
                        const sample: Record<string, string> = {};
                        for (const p of props) sample[p] = '';
                        setCallArgsJson(JSON.stringify(sample, null, 2));
                      } else {
                        setCallArgsJson('{}');
                      }
                    }
                  }}
                  data-testid="wb-mcp-call-tool-select"
                >
                  <option value="">选择工具…</option>
                  {tools.map((tool) => (
                    <option key={tool.name} value={tool.name}>
                      {tool.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="wb-create-form__field wb-create-form__field--area">
                <label className="wb-create-form__label" htmlFor="wb-mcp-call-args">
                  arguments（JSON）
                </label>
                <textarea
                  id="wb-mcp-call-args"
                  className="wb-input"
                  rows={6}
                  value={callArgsJson}
                  onChange={(e) => setCallArgsJson(e.target.value)}
                  data-testid="wb-mcp-call-args-input"
                />
              </div>
              <div className="wb-create-form__actions">
                <button
                  className="wb-theme-option wb-theme-option--active"
                  type="button"
                  disabled={calling || !callToolName}
                  onClick={handleCallTool}
                  data-testid="wb-mcp-call-btn"
                  style={{ width: '100%' }}
                >
                  {calling ? '调用中…' : '⚡ 调用工具'}
                </button>
              </div>
            </div>
          </div>

          {callResult && (
            <div className="wb-smart-card" style={{ marginTop: 12 }} data-testid="wb-mcp-call-result">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{callResult.tool}</div>
                <span
                  className={`wb-status-chip ${
                    callResult.isError ? 'wb-status-chip--danger' : 'wb-status-chip--success'
                  }`}
                >
                  {callResult.isError ? '失败' : '成功'}
                </span>
              </div>
              {callResult.content.map((c, i) => (
                <pre
                  key={i}
                  style={{
                    fontSize: 'var(--font-size-xs)',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                    margin: '6px 0 0',
                    maxHeight: 300,
                    overflow: 'auto',
                  }}
                >
                  {c.text}
                </pre>
              ))}
            </div>
          )}

          {/* MRTR 待响应请求 */}
          <div className="wb-section-label" style={{ marginTop: 20 }}>
            MRTR 待响应请求（{requests.length}）
          </div>
          {mrtrLoading && (
            <div className="wb-state" data-testid="wb-mcp-mrtr-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载 MRTR 请求…</div>
            </div>
          )}
          {mrtrError && !mrtrLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-mcp-mrtr-error">
              <div className="wb-state__icon">⚠</div>
              <div>{mrtrError}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reloadMrtr}
                type="button"
              >
                重试
              </button>
            </div>
          )}
          {!mrtrLoading && !mrtrError && requests.length === 0 && (
            <div className="wb-state" data-testid="wb-mcp-mrtr-empty">
              <div className="wb-state__icon">📭</div>
              <div>暂无待响应的 MRTR 请求</div>
            </div>
          )}
          {!mrtrLoading && !mrtrError && requests.length > 0 && (
            <div data-testid="wb-mcp-mrtr-content">
              {requests.map((req, i) => (
                <div key={req.id} className="wb-smart-card" data-testid={`wb-mcp-mrtr-item--${i}`}>
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">{req.id}</div>
                    <span className="wb-status-chip wb-status-chip--info">{req.method}</span>
                    <span className="wb-status-chip wb-status-chip--muted">{req.state}</span>
                  </div>
                  {req.params && (
                    <pre
                      style={{
                        fontSize: 'var(--font-size-xs)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all',
                        margin: '6px 0 0',
                        maxHeight: 140,
                        overflow: 'auto',
                      }}
                    >
                      {JSON.stringify(req.params, null, 2)}
                    </pre>
                  )}
                  <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                    <span>创建 {req.created_at}</span>
                    <span>过期 {req.expires_at}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
