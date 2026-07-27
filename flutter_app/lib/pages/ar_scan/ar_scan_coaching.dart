/// AR 扫描 — 首次使用引导覆盖层
///
/// 新用户首次打开 AR 扫描页面时展示操作指引卡片，
/// 覆盖在扫描视图上方，提供可视化交互提示。
library;

import 'package:flutter/material.dart';
import '../../theme/suoke_theme.dart';
import 'ar_scan_shared_widgets.dart';

/// 首次使用引导覆盖层
///
/// 在半透明遮罩上展示分步操作指引，包含图片示意和文字说明。
/// 用户点击"开始使用"或背景区域关闭。
class CoachingOverlay extends StatefulWidget {
  final String scanMethod;
  final VoidCallback onDismiss;

  const CoachingOverlay({
    super.key,
    required this.scanMethod,
    required this.onDismiss,
  });

  @override
  State<CoachingOverlay> createState() => _CoachingOverlayState();
}

class _CoachingOverlayState extends State<CoachingOverlay> {
  int _currentTip = 0;

  static const _tips = [
    _TipData(
      title: '站在房间角落',
      icon: Icons.person_pin_circle,
      body: '选一个房间角落作为起点，\n背靠墙壁站稳。',
    ),
    _TipData(
      title: '缓慢移动手机',
      icon: Icons.slow_motion_video,
      body: '保持手机与地面平行，\n缓慢沿墙壁移动。',
    ),
    _TipData(
      title: '覆盖全部墙面',
      icon: Icons.view_in_ar,
      body: '绕房间走一圈，\n确保手机能扫描到所有墙面。',
    ),
    _TipData(
      title: '充足光线',
      icon: Icons.lightbulb_outline,
      body: '确保房间光线充足，\n避免逆光和强烈阴影。',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final tip = _tips[_currentTip];
    final isLast = _currentTip == _tips.length - 1;

    return GestureDetector(
      onTap: widget.onDismiss,
      child: Container(
        color: Colors.black.withValues(alpha: 0.75),
        child: Center(
          child: GestureDetector(
            onTap: () {}, // 阻止点击穿透
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 32),
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: const Color(0xFF1A1D23),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: SuokeDesignTokens.accent.withValues(alpha: 0.3)),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // 步骤指示器
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(_tips.length, (i) =>
                      AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        margin: const EdgeInsets.symmetric(horizontal: 3),
                        width: i == _currentTip ? 20.0 : 6.0,
                        height: 6,
                        decoration: BoxDecoration(
                          color: i == _currentTip ? SuokeDesignTokens.accent : SuokeDesignTokens.textSub(context).withValues(alpha: 0.3),
                          borderRadius: BorderRadius.circular(3),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // 图标
                  Container(
                    width: 72, height: 72,
                    decoration: BoxDecoration(
                      color: SuokeDesignTokens.accent.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(36),
                    ),
                    child: Icon(tip.icon, color: SuokeDesignTokens.accent, size: 36),
                  ),
                  const SizedBox(height: 16),

                  // 标题
                  Text(tip.title,
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 18),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),

                  // 正文
                  Text(tip.body,
                    style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 14, height: 1.5),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 24),

                  // 操作按钮
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      TextButton(
                        onPressed: widget.onDismiss,
                        child: Text('跳过', style: TextStyle(color: SuokeDesignTokens.textSub(context))),
                      ),
                      ElevatedButton(
                        onPressed: isLast ? widget.onDismiss : () {
                          setState(() => _currentTip++);
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: SuokeDesignTokens.accent,
                          foregroundColor: Colors.black,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        child: Text(isLast ? '开始使用' : '下一步'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _TipData {
  final String title;
  final IconData icon;
  final String body;
  const _TipData({required this.title, required this.icon, required this.body});
}

/// 主动环境提示横幅
///
/// 当扫描环境出现问题时（光线不足/纹理不足/移动过快），
/// 在扫描视图顶部弹出 coaching 横幅提示。
class EnvCoachingBanner extends StatelessWidget {
  final EnvCondition condition;
  final VoidCallback? onDismiss;

  const EnvCoachingBanner({
    super.key,
    required this.condition,
    this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    final (icon, title, hint) = switch (condition) {
      EnvCondition.lowLight => (Icons.brightness_low, '光线不足', '请打开室内灯光或移动到明亮区域'),
      EnvCondition.lowTexture => (Icons.texture, '纹理不足', '请对准有纹理的墙面或家具表面'),
      EnvCondition.fastMotion => (Icons.speed, '移动过快', '请放慢手机移动速度，保持平稳'),
      _ => (Icons.check, '', ''),
    };

    if (condition == EnvCondition.normal) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: arWarning.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: arWarning.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(icon, color: arWarning, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: TextStyle(color: arWarning, fontWeight: FontWeight.w600, fontSize: 13)),
                const SizedBox(height: 2),
                Text(hint, style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 11)),
              ],
            ),
          ),
          if (onDismiss != null)
            GestureDetector(
              onTap: onDismiss,
              child: Icon(Icons.close, size: 16, color: SuokeDesignTokens.textSub(context)),
            ),
        ],
      ),
    );
  }
}
