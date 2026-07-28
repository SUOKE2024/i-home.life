/**
 * ChatHeader — 对齐 ai_chat_page.dart:843-908 _buildChatHeader
 *
 * 布局：Row[返回?(可选) + 标题块(Expanded) + 语音任务按钮 + 头像]
 * 样式：半透明 cardBgSemi + 底部 border；标题 fontSizeLg w700，副标题 fontSizeXs accent
 */

export interface ChatHeaderProps {
  title: string;
  subtitle?: string;
  avatarSrc?: string;
  onAvatarClick?: () => void;
  onVoiceTasksClick?: () => void;
  onBack?: () => void;
  onTitleClick?: () => void;
}

export default function ChatHeader({
  title,
  subtitle,
  avatarSrc,
  onAvatarClick,
  onVoiceTasksClick,
  onBack,
  onTitleClick,
}: ChatHeaderProps) {
  return (
    <header className="wb-header" data-testid="wb-header">
      {onBack && (
        <button
          className="wb-header__icon-btn"
          onClick={onBack}
          aria-label="返回"
          type="button"
        >
          ‹
        </button>
      )}
      <div
        className="wb-header__title-block"
        onClick={onTitleClick}
        role={onTitleClick ? 'button' : undefined}
      >
        <div className="wb-header__title">
          <span>{title}</span>
          {onTitleClick && <span style={{ fontSize: 16, color: 'var(--accent)' }}>＋</span>}
        </div>
        {subtitle && <div className="wb-header__subtitle">{subtitle}</div>}
      </div>
      <button
        className="wb-header__icon-btn"
        onClick={onVoiceTasksClick}
        aria-label="语音任务"
        title="语音任务"
        type="button"
        data-testid="wb-header-voice-tasks"
      >
        ⊞
      </button>
      <button
        className="wb-header__avatar"
        onClick={onAvatarClick}
        aria-label="用户头像"
        type="button"
        data-testid="wb-header-avatar"
      >
        {avatarSrc ? (
          <img src={avatarSrc} alt="头像" />
        ) : (
          <span style={{ fontSize: 16 }}>👤</span>
        )}
      </button>
    </header>
  );
}
