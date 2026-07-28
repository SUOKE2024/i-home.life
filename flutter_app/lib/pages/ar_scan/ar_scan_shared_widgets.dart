/// AR 扫描页面 — 跨步骤复用的共享 Widget 组件
///
/// 从 ar_scan_page.dart 提取，减少单文件体积并提高可维护性。
library;

import 'package:flutter/material.dart';
import '../../theme/suoke_theme.dart';

// ── 颜色常量 ──
const arSuccess = SuokeDesignTokens.success;
const arWarning = SuokeDesignTokens.warning;
const arDanger = SuokeDesignTokens.danger;

// ── 房间类型预设 ──
class RoomPreset {
  final String name;
  final IconData icon;
  final double defaultArea;
  final double defaultHeight;
  final String description;
  const RoomPreset({
    required this.name,
    required this.icon,
    this.defaultArea = 20.0,
    this.defaultHeight = 2.8,
    this.description = '',
  });
}

const roomPresets = [
  RoomPreset(name: '客厅', icon: Icons.weekend, defaultArea: 30.0, description: '家庭活动中心'),
  RoomPreset(name: '主卧', icon: Icons.king_bed, defaultArea: 18.0, description: '含衣柜/卫生间'),
  RoomPreset(name: '次卧', icon: Icons.bed, defaultArea: 12.0),
  RoomPreset(name: '厨房', icon: Icons.countertops, defaultArea: 8.0, defaultHeight: 2.4, description: 'L型/U型/一字型'),
  RoomPreset(name: '卫生间', icon: Icons.bathtub, defaultArea: 5.0, defaultHeight: 2.4, description: '干湿分离'),
  RoomPreset(name: '书房', icon: Icons.menu_book, defaultArea: 10.0),
  RoomPreset(name: '阳台', icon: Icons.wb_sunny, defaultArea: 6.0, description: '封闭/开放'),
  RoomPreset(name: '走廊/玄关', icon: Icons.meeting_room, defaultArea: 4.0),
  RoomPreset(name: '餐厅', icon: Icons.table_restaurant, defaultArea: 12.0),
  RoomPreset(name: '储物间', icon: Icons.inventory_2, defaultArea: 4.0, defaultHeight: 2.4),
];

// ── 枚举 ──
enum ScanStep { deviceCheck, roomSetup, scanGuide, review, results, doorWindow, mep }
enum ScanState { idle, detecting, ready, scanning, uploading, processing, completed, failed }
enum TrackingQuality { searching, limited, normal, lost }
enum EnvCondition { normal, lowLight, lowTexture, fastMotion }

// ── 扫描方法工具函数 ──
IconData methodIcon(String method) => switch (method) {
  'lidar' => Icons.bluetooth_searching,
  'visual_slam' => Icons.camera,
  'photogrammetry' => Icons.collections,
  'manual' => Icons.straighten,
  _ => Icons.view_in_ar,
};

String methodLabel(String method) => switch (method) {
  'lidar' => 'LiDAR 激光雷达',
  'visual_slam' => '视觉 SLAM',
  'photogrammetry' => '摄影测量',
  'manual' => '手动测量',
  _ => '未知方法',
};

// ── 共享卡片装饰 ──
BoxDecoration cardDecoration(BuildContext context) => BoxDecoration(
  color: const Color(0xFF1A1D23),
  borderRadius: BorderRadius.circular(16),
  border: Border.all(color: SuokeDesignTokens.borderClr(context).withValues(alpha: 0.3)),
);

// ── 共享 Widget ──

/// 步骤标题区
class SectionHeader extends StatelessWidget {
  final String title;
  final IconData icon;
  const SectionHeader(this.title, this.icon, {super.key});

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Icon(icon, color: SuokeDesignTokens.accent, size: 20),
      const SizedBox(width: 8),
      Text(title, style: TextStyle(color: SuokeDesignTokens.text(context), fontWeight: FontWeight.bold, fontSize: 18)),
    ]);
  }
}

/// 传感器状态徽章
class SensorBadge extends StatelessWidget {
  final String name;
  final bool available;
  final IconData icon;
  final Color? successColor;
  const SensorBadge({
    super.key,
    required this.name,
    required this.available,
    required this.icon,
    this.successColor,
  });

  @override
  Widget build(BuildContext context) {
    final color = available ? (successColor ?? arSuccess) : arDanger;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: color),
        const SizedBox(width: 6),
        Text(name, style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 12)),
        const SizedBox(width: 4),
        Container(
          width: 6, height: 6,
          decoration: BoxDecoration(shape: BoxShape.circle, color: color),
        ),
      ],
    );
  }
}

/// 信息标签芯片
class InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  const InfoChip({super.key, required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.bg(context),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: SuokeDesignTokens.accent),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 11)),
          const SizedBox(width: 4),
          Text(value, style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 11, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}

/// 摘要芯片（扫描参数展示）
class SummaryChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  const SummaryChip({super.key, required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.bg(context), borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: SuokeDesignTokens.accent),
          const SizedBox(width: 4),
          Text('$label: ', style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 10)),
          Text(value, style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 10, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}

/// 操作指引步骤
class GuideStep extends StatelessWidget {
  final int num;
  final String title;
  final String desc;
  const GuideStep({super.key, required this.num, required this.title, required this.desc});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 24, height: 24,
            decoration: BoxDecoration(
              color: SuokeDesignTokens.accent.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(
              child: Text('$num', style: const TextStyle(color: SuokeDesignTokens.accent, fontWeight: FontWeight.bold, fontSize: 12)),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: TextStyle(color: SuokeDesignTokens.text(context), fontWeight: FontWeight.w500, fontSize: 13)),
                const SizedBox(height: 2),
                Text(desc, style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 11, height: 1.3)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// 追踪质量指示器
class TrackingIndicator extends StatelessWidget {
  final TrackingQuality quality;
  final EnvCondition env;
  const TrackingIndicator({super.key, required this.quality, required this.env});

  Color get _color => switch (quality) {
    TrackingQuality.normal => arSuccess,
    TrackingQuality.limited => arWarning,
    TrackingQuality.lost => arDanger,
    TrackingQuality.searching => SuokeDesignTokens.accent,
  };

  String get _label => switch (quality) {
    TrackingQuality.normal => '追踪正常',
    TrackingQuality.limited => '追踪受限',
    TrackingQuality.lost => '追踪丢失',
    TrackingQuality.searching => '搜索中...',
  };

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          width: 8, height: 8,
          decoration: BoxDecoration(shape: BoxShape.circle, color: _color),
        ),
        const SizedBox(width: 6),
        Text(_label, style: TextStyle(color: _color, fontSize: 12, fontWeight: FontWeight.w500)),
        if (env != EnvCondition.normal) ...[
          const SizedBox(width: 8),
          Icon(_envIcon, size: 14, color: arWarning),
          const SizedBox(width: 2),
          Text(_envLabel, style: const TextStyle(color: arWarning, fontSize: 10)),
        ],
      ],
    );
  }

  IconData get _envIcon => switch (env) {
    EnvCondition.lowLight => Icons.brightness_low,
    EnvCondition.lowTexture => Icons.texture,
    EnvCondition.fastMotion => Icons.speed,
    EnvCondition.normal => Icons.check,
  };

  String get _envLabel => switch (env) {
    EnvCondition.lowLight => '光线不足',
    EnvCondition.lowTexture => '纹理不足',
    EnvCondition.fastMotion => '移动过快',
    EnvCondition.normal => '',
  };
}

// ── 自定义 Painter ──

/// 网格背景 Painter
class GridPainter extends CustomPainter {
  final double opacity;
  const GridPainter({this.opacity = 0.05});

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
  bool shouldRepaint(covariant GridPainter old) => old.opacity != opacity;
}

/// AR 追踪十字准线 Painter
class ReticlePainter extends CustomPainter {
  final Color color;
  final double pulse;
  final TrackingQuality quality;

  const ReticlePainter({required this.color, required this.pulse, required this.quality});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final armLength = 20.0 + pulse * 4;
    const gap = 8.0;
    const armThickness = 2.0;

    final paint = Paint()
      ..color = color
      ..strokeWidth = armThickness
      ..style = PaintingStyle.stroke;

    // 上
    canvas.drawLine(Offset(center.dx, center.dy - gap), Offset(center.dx, center.dy - gap - armLength), paint);
    // 下
    canvas.drawLine(Offset(center.dx, center.dy + gap), Offset(center.dx, center.dy + gap + armLength), paint);
    // 左
    canvas.drawLine(Offset(center.dx - gap, center.dy), Offset(center.dx - gap - armLength, center.dy), paint);
    // 右
    canvas.drawLine(Offset(center.dx + gap, center.dy), Offset(center.dx + gap + armLength, center.dy), paint);

    // 外圈脉冲
    if (quality == TrackingQuality.searching) {
      final ringPaint = Paint()
        ..color = color.withValues(alpha: 0.3)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5;
      canvas.drawCircle(center, 30 + pulse * 15, ringPaint);
    }
  }

  @override
  bool shouldRepaint(covariant ReticlePainter old) =>
      old.color != color || old.pulse != pulse || old.quality != quality;
}

// ── 复核条目 ──
class ReviewItem {
  final String id;
  final String label;
  final String value;
  final String confidence;
  final String? hint;

  const ReviewItem({
    required this.id,
    required this.label,
    required this.value,
    required this.confidence,
    this.hint,
  });

  Color get confidenceColor => switch (confidence) {
    'high' => arSuccess,
    'medium' => arWarning,
    'low' => arDanger,
    _ => arSuccess,
  };

  String get confidenceLabel => switch (confidence) {
    'high' => '高置信',
    'medium' => '中置信',
    'low' => '低置信',
    _ => confidence.toUpperCase(),
  };
}
