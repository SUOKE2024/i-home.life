// ar_scan_components — AR 扫描页独立辅助组件（v1.2.9 G7 可维护性拆分）
//
// 从 ar_scan_page.dart 抽出的零/低耦合辅助类：
//   - ArGridPainter：扫描网格背景 Painter
//   - ArCoachingTip：首次引导提示组件
//   - ArReviewItem：复核项数据模型
//
// 主文件通过 typedef 别名引用（_GridPainter/_CoachingTip/_ReviewItem），
// 保持主文件零改动，降低拆分回归风险。
//
// 注：_ReticlePainter 因依赖 _TrackingQuality enum（29 处引用）高耦合，
//     暂保留在主文件；核心 _ARScanPageState（3353 行）拆分需先补 widget 测试。

import 'package:flutter/material.dart';

import '../../theme/suoke_theme.dart';

/// AR 扫描网格背景 Painter
class ArGridPainter extends CustomPainter {
  final double opacity;
  const ArGridPainter({this.opacity = 0.05});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: opacity)
      ..strokeWidth = 0.5;

    const gridSize = 20.0;
    for (double x = 0; x < size.width; x += gridSize) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y < size.height; y += gridSize) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant ArGridPainter old) => old.opacity != opacity;
}

/// 首次引导提示组件
class ArCoachingTip extends StatelessWidget {
  final IconData icon;
  final String text;
  const ArCoachingTip({super.key, required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 14, color: SuokeDesignTokens.accent),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text,
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context),
                    fontSize: 12,
                    height: 1.3)),
          ),
        ],
      ),
    );
  }
}

/// 复核项数据模型
class ArReviewItem {
  final String id;
  final String label;
  final String value;
  final String confidence; // 'high', 'medium', 'low'
  final String? hint;

  const ArReviewItem({
    required this.id,
    required this.label,
    required this.value,
    required this.confidence,
    this.hint,
  });

  Color get confidenceColor => switch (confidence) {
        'high' => SuokeDesignTokens.success,
        'medium' => SuokeDesignTokens.warning,
        'low' => SuokeDesignTokens.danger,
        _ => SuokeDesignTokens.success,
      };

  String get confidenceLabel => switch (confidence) {
        'high' => '高置信',
        'medium' => '中置信',
        'low' => '低置信',
        _ => confidence.toUpperCase(),
      };
}
