/**
 * PlaceholderPage — 27 个 Flutter 独有页的 Web 占位
 *
 * 批次 4/5 逐步替换为真实页面实现。
 * 当前提供：图标 + 标题 + "即将上线"提示 + 返回工作台入口。
 */

import { useNavigate } from 'react-router-dom';
import SuokeButton from '../components/SuokeButton';

export interface PlaceholderPageProps {
  /** 页面标题 */
  title: string;
  /** emoji 图标 */
  emoji?: string;
  /** 关联 agent key（取 emoji + color） */
  agent?: string;
  /** 批次编号（提示何时实现） */
  batch?: string;
}

export default function PlaceholderPage({
  title,
  emoji,
  agent,
  batch = '批次 4/5',
}: PlaceholderPageProps) {
  const navigate = useNavigate();
  const icon = emoji ?? (agent ? '·' : '🚧');

  return (
    <div className="wb-placeholder-page" data-testid="wb-placeholder-page">
      <div className="wb-placeholder-page__icon">{icon}</div>
      <div className="wb-placeholder-page__title">{title}</div>
      <div className="wb-placeholder-page__desc">
        此页面将在 {batch} 实现。当前可通过工作台与对应 Agent 对话使用相关功能。
      </div>
      <div className="wb-placeholder-page__badge">{batch} 即将上线</div>
      <div style={{ marginTop: 16 }}>
        <SuokeButton variant="outline" size="sm" onClick={() => navigate('/')} testId="wb-placeholder-back">
          ← 返回工作台
        </SuokeButton>
      </div>
    </div>
  );
}
