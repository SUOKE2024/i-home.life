import 'package:flutter/material.dart';
import '../theme/suoke_theme.dart';

/// 统一空态组件（2026 UX 规范：图标 + 标题 + 引导文案 + 可选 CTA）
///
/// 替代各页面手写的「纯文字/空白」空态，保证全 App 空态一致且可访问。
/// 使用规范（对齐 Web 端 Empty 组件）：
/// - 标题：一句话说明当前状态（如「暂无服务者」）
/// - 描述：引导下一步或说明数据从何而来
/// - action：首屏空态提供创建/刷新 CTA，筛选空态提供清除筛选
class EmptyStateWidget extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? description;
  final String? actionLabel;
  final VoidCallback? onAction;
  final double iconSize;

  const EmptyStateWidget({
    super.key,
    this.icon = Icons.inbox_outlined,
    required this.title,
    this.description,
    this.actionLabel,
    this.onAction,
    this.iconSize = 48,
  });

  @override
  Widget build(BuildContext context) {
    final titleStyle = Theme.of(context).textTheme.titleMedium?.copyWith(
          color: SuokeDesignTokens.text(context),
          fontWeight: FontWeight.w600,
        );
    return Semantics(
      container: true,
      label: '空状态：$title',
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: iconSize, color: SuokeDesignTokens.textMuted),
              const SizedBox(height: 16),
              Text(title, textAlign: TextAlign.center, style: titleStyle),
              if (description != null) ...[
                const SizedBox(height: 8),
                Text(
                  description!,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: SuokeDesignTokens.textSub(context),
                      ),
                ),
              ],
              if (actionLabel != null && onAction != null) ...[
                const SizedBox(height: 20),
                Semantics(
                  label: actionLabel,
                  button: true,
                  child: OutlinedButton.icon(
                    onPressed: onAction,
                    icon: const Icon(Icons.add, size: 18),
                    label: Text(actionLabel!),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: SuokeDesignTokens.accent,
                      side: const BorderSide(color: SuokeDesignTokens.accent),
                      minimumSize: const Size(120, 44),
                      padding:
                          const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
