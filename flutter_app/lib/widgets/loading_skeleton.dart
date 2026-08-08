import 'package:flutter/material.dart';
import '../theme/suoke_theme.dart';

class LoadingSkeleton extends StatefulWidget {
  final int itemCount;
  final double itemHeight;

  const LoadingSkeleton({
    super.key,
    this.itemCount = 4,
    this.itemHeight = 120,
  });

  @override
  State<LoadingSkeleton> createState() => _LoadingSkeletonState();
}

class _LoadingSkeletonState extends State<LoadingSkeleton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
    _animation = Tween<double>(begin: 0.3, end: 0.7).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // 无障碍：系统开启「减少动态效果」(prefers-reduced-motion) 时停止呼吸动画，
    // 退化为静态骨架；恢复后自动续播。对齐 2026 WCAG 2.2 对动效的约束。
    final reduceMotion = MediaQuery.disableAnimationsOf(context);
    if (reduceMotion) {
      _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat(reverse: true);
    }
    final surfaceColor = Theme.of(context).colorScheme.surface;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    // 浅色主题下用 surface variant 作为骨架底色
    final baseColor = isDark ? SuokeDesignTokens.cardBg : surfaceColor;
    // 浅色主题下稍微变暗，暗色主题下稍微变亮
    final shimmerEnd = isDark
        ? baseColor.withValues(alpha: 0.7)
        : baseColor.withValues(alpha: 0.3);

    return Semantics(
      label: '加载中',
      child: RepaintBoundary(
        child: AnimatedBuilder(
          animation: _animation,
          builder: (context, _) {
            final t = _animation.value;
            final color = Color.lerp(baseColor, shimmerEnd, t)!;
            return ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: widget.itemCount,
              itemBuilder: (context, index) {
                // 不同索引的骨架条有不同宽度，模拟真实内容层次
                final isFirst = index == 0;
                final widthFactor = isFirst ? 0.7 : (0.5 + (index % 3) * 0.1);
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: FractionallySizedBox(
                    widthFactor: widthFactor,
                    child: Container(
                      height: widget.itemHeight,
                      decoration: BoxDecoration(
                        color: color,
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
