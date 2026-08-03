/**
 * VoiceTaskPanel — 对齐 workbench.html:401-430 浮动面板
 *
 * 固定右下角（right:16 bottom:76，340px 宽），含 header + launch input + note + task list。
 * 调用 api-client.orchestrateVoice / listVoiceTasks。
 */

import { useEffect, useState } from 'react';
import { apiClient } from '../../services/api-client';

export interface VoiceTaskPanelProps {
  open: boolean;
  onClose: () => void;
  projectId?: string | null;
}

interface VoiceTask {
  task_id?: string;
  id?: string;
  command?: string;
  cmd?: string;
  status?: string;
  agent?: string;
  text?: string;
}

const STATUS_COLOR: Record<string, string> = {
  running: 'var(--info)',
  pending: 'var(--text-secondary)',
  done: 'var(--success)',
  completed: 'var(--success)',
  failed: 'var(--danger)',
  cancelled: 'var(--text-muted)',
};

const STATUS_LABEL: Record<string, string> = {
  running: '进行中',
  pending: '待处理',
  done: '已完成',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

export default function VoiceTaskPanel({ open, onClose, projectId }: VoiceTaskPanelProps) {
  const [input, setInput] = useState('');
  const [note, setNote] = useState<string | null>(null);
  const [tasks, setTasks] = useState<VoiceTask[]>([]);
  const [launching, setLaunching] = useState(false);

  // 打开时加载任务列表
  useEffect(() => {
    if (!open) return;
    refreshTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  async function refreshTasks() {
    const result = await apiClient.listVoiceTasks();
    if (result.isSuccess && Array.isArray(result.data)) {
      setTasks(result.data as VoiceTask[]);
    }
  }

  async function launch() {
    const text = input.trim();
    if (!text || launching) return;
    setLaunching(true);
    setInput('');
    const result = await apiClient.orchestrateVoice(text, projectId);
    if (result.isSuccess) {
      setNote(`已启动：${text}`);
      refreshTasks();
    } else {
      setNote(`启动失败：${result.error ?? '未知错误'}`);
    }
    setLaunching(false);
  }

  if (!open) return null;

  return (
    <div className="wb-vtp" role="dialog" aria-label="语音任务面板" data-testid="wb-vtp">
      <div className="wb-vtp__header">
        <span>🎯 语音任务</span>
        <button className="wb-vtp__close" onClick={onClose} aria-label="关闭任务面板" type="button">
          ×
        </button>
      </div>
      <div className="wb-vtp__launch">
        <input
          className="wb-vtp__input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') launch();
          }}
          placeholder="试试：帮我设计客厅，同时做份预算"
          aria-label="语音任务指令"
          enterKeyHint="send"
          disabled={launching}
        />
        <button className="wb-vtp__send" onClick={launch} disabled={launching} type="button">
          启动
        </button>
      </div>
      {note && <div className="wb-vtp__note">{note}</div>}
      <ul className="wb-vtp__list">
        {tasks.length === 0 ? (
          <li className="wb-vtp__empty">暂无语音任务</li>
        ) : (
          tasks.map((t, i) => {
            const status = t.status ?? 'pending';
            const cmd = t.command ?? t.cmd ?? t.text ?? '';
            return (
              <li className="wb-vtp__item" key={t.task_id ?? t.id ?? i}>
                <div className="wb-vtp__item-head">
                  <span
                    className="wb-vtp__badge"
                    style={{ background: STATUS_COLOR[status] ?? 'var(--text-secondary)' }}
                  >
                    {STATUS_LABEL[status] ?? status}
                  </span>
                  {t.agent && <span style={{ color: 'var(--text-secondary)' }}>{t.agent}</span>}
                </div>
                <div className="wb-vtp__cmd">{cmd}</div>
              </li>
            );
          })
        )}
      </ul>
    </div>
  );
}
