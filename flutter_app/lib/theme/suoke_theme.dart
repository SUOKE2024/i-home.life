import 'package:flutter/material.dart';

/// 索克家居统一设计令牌 v2 (2026 upgrade)
///
/// 对齐 Web 端 workbench.css 的暗色主题设计，
/// 新增 surface hierarchy、fluid typography 指引、WCAG 触摸目标。
class SuokeDesignTokens {
  SuokeDesignTokens._();

  // ── Surface hierarchy (2026 pattern: 4 levels) ──

  /// Canvas base (deepest)
  static const Color bgDeep = Color(0xFF08080F);
  /// Surface 0 — equivalent to bgDeep
  static const Color surface0 = bgDeep;
  /// Surface 1 — cards, panels
  static const Color surface1 = Color(0xFF12121D);
  /// Surface 2 — hover, elevated panels, headers
  static const Color surface2 = Color(0xFF1A1A2A);
  /// Surface 3 — modal, dialog, popover
  static const Color surface3 = Color(0xFF222238);

  /// 卡片背景色（半透明，模拟 Web 的 rgba(18,18,29,0.95)）
  static const Color cardBg = surface1;
  static Color cardBgSemi = surface1.withValues(alpha: 0.95);

  /// 卡片悬浮色
  static const Color cardBgHover = surface2;

  /// 边框色
  static const Color border = Color(0xFF1E1E32);

  /// 激活边框色
  static const Color borderActive = Color(0xFF2A2A45);

  /// 主文字
  static const Color textPrimary = Color(0xFFE8E6E1);

  /// 次文字（已升级对比度，适配 WCAG 2.2）
  static const Color textSecondary = Color(0xFF8A8894);

  /// 弱文字/占位（升级对比度：was 0xFF5A5866, now 0xFF6B6978 for WCAG AA）
  static const Color textMuted = Color(0xFF6B6978);

  /// 品牌金色
  static const Color accent = Color(0xFFC9973B);

  /// 亮金色
  static const Color accentBright = Color(0xFFE0AA4A);

  /// 金色发光
  static Color accentGlow = const Color(0xFFC9973B).withValues(alpha: 0.15);

  /// 成功色
  static const Color success = Color(0xFF4A9E6E);

  /// 警告色
  static const Color warning = Color(0xFFC97A3B);

  /// 危险色
  static const Color danger = Color(0xFFC94A4A);

  /// 信息色
  static const Color info = Color(0xFF5A7EC9);

  /// 紫色
  static const Color purple = Color(0xFF9B6AC9);

  /// 青色
  static const Color teal = Color(0xFF4AC9A3);

  /// 用户气泡色
  static const Color bubbleUser = Color(0xFF2A2218);

  /// Agent 气泡色
  static const Color bubbleAgent = Color(0xFF1A1A2A);

  /// 输入底色
  static const Color inputBg = Color(0xFF0D0D18);

  // ── 圆角 ──

  static const double radiusSm = 10.0;
  static const double radius = 12.0;
  static const double radiusMd = 14.0;
  static const double radiusLg = 16.0;
  static const double radiusXl = 24.0;
  static const double radiusPill = 20.0;
  static const double radiusInput = 8.0;

  // ── 间距 ──

  static const double spacingXs = 4.0;
  static const double spacingSm = 8.0;
  static const double spacingMd = 12.0;
  static const double spacingLg = 16.0;
  static const double spacingXl = 24.0;

  // ── WCAG 2.2 触摸目标 ──

  /// 最小触摸尺寸 48×48 (WCAG 2.2 SC 2.5.8)
  static const double touchTargetMin = 48.0;
  /// 推荐触摸尺寸 44×44 (WCAG 2.2 AA minimum)
  static const double touchTargetAa = 44.0;

  // ── 字体大小 ──

  static const double fontSizeXs = 10.0;
  static const double fontSizeSm = 12.0;
  static const double fontSizeMd = 13.0;
  static const double fontSizeLg = 16.0;

  // ── Agent 颜色（与 Web 端 agent 颜色保持一致） ──

  static const Color agentMaster = Color(0xFFC9973B);
  static const Color agentDesign = Color(0xFF5A7EC9);
  static const Color agentBudget = Color(0xFF4A9E6E);
  static const Color agentProcurement = Color(0xFFC97A3B);
  static const Color agentConstruction = Color(0xFFC94A4A);
  static const Color agentQuality = Color(0xFF4AC9A3);
  static const Color agentSettlement = Color(0xFF9B6AC9);
  static const Color agentSupport = Color(0xFF6A9BC9);

  /// 根据 agent key 获取颜色
  static Color agentColor(String key) {
    return switch (key) {
      'master' => agentMaster,
      'design' => agentDesign,
      'budget' => agentBudget,
      'procurement' => agentProcurement,
      'construction' => agentConstruction,
      'quality' => agentQuality,
      'settlement' => agentSettlement,
      'support' => agentSupport,
      _ => agentMaster,
    };
  }

  // ── 浅色主题令牌 ──

  static const Color lightBg = Color(0xFFF8F7F4);
  static const Color lightCard = Color(0xFFFFFFFF);
  static const Color lightBorder = Color(0xFFE8E5DE);
  static const Color lightTextPrimary = Color(0xFF1A1814);
  static const Color lightTextSecondary = Color(0xFF6B6760);
  static const Color lightTextMuted = Color(0xFF9E9A94);
}

/// 暗色 + 普通主题工厂
class SuokeTheme {
  SuokeTheme._();

  /// 暗色主题（主力，对齐 Web 端 workbench）
  static ThemeData dark() {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: SuokeDesignTokens.bgDeep,
      colorScheme: const ColorScheme.dark(
        primary: SuokeDesignTokens.accent,
        surface: SuokeDesignTokens.cardBg,
        onPrimary: SuokeDesignTokens.bgDeep,
        onSurface: SuokeDesignTokens.textPrimary,
        error: SuokeDesignTokens.danger,
      ),

      // ── AppBar 半透明，对齐 Web chat-header ──
      appBarTheme: AppBarTheme(
        backgroundColor: SuokeDesignTokens.cardBgSemi,
        foregroundColor: SuokeDesignTokens.textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        titleTextStyle: const TextStyle(
          color: SuokeDesignTokens.textPrimary,
          fontSize: SuokeDesignTokens.fontSizeLg,
          fontWeight: FontWeight.w700,
        ),
        surfaceTintColor: Colors.transparent,
      ),

      // ── 卡片：半透明 + 边框 ──
      cardTheme: CardThemeData(
        color: SuokeDesignTokens.cardBgSemi,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radius),
          side: const BorderSide(color: SuokeDesignTokens.border, width: 1),
        ),
        margin: const EdgeInsets.symmetric(horizontal: 0, vertical: 4),
      ),

      // ── 输入框 ──
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: SuokeDesignTokens.inputBg,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: SuokeDesignTokens.spacingMd,
          vertical: SuokeDesignTokens.spacingMd,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
          borderSide: const BorderSide(color: SuokeDesignTokens.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
          borderSide: const BorderSide(color: SuokeDesignTokens.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
          borderSide: const BorderSide(color: SuokeDesignTokens.accent),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
          borderSide: const BorderSide(color: SuokeDesignTokens.danger),
        ),
        labelStyle: const TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: SuokeDesignTokens.fontSizeSm),
        hintStyle: const TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: SuokeDesignTokens.fontSizeMd),
      ),

      // ── 主要按钮（品牌金色） ──
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: SuokeDesignTokens.accent,
          foregroundColor: SuokeDesignTokens.bgDeep,
          elevation: 0,
          surfaceTintColor: Colors.transparent,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          textStyle: const TextStyle(
            fontSize: SuokeDesignTokens.fontSizeMd,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),

      // ── 次要按钮（边框） ──
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: SuokeDesignTokens.textPrimary,
          side: const BorderSide(color: SuokeDesignTokens.borderActive),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          textStyle: const TextStyle(fontSize: SuokeDesignTokens.fontSizeSm),
        ),
      ),

      // ── 文本按钮 ──
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: SuokeDesignTokens.accent,
        ),
      ),

      // ── BottomNavigationBar ──
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: SuokeDesignTokens.cardBgSemi,
        indicatorColor: SuokeDesignTokens.accentGlow,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        height: 64,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(
              color: SuokeDesignTokens.accent,
              fontSize: SuokeDesignTokens.fontSizeXs,
              fontWeight: FontWeight.w600,
            );
          }
          return const TextStyle(
            color: SuokeDesignTokens.textSecondary,
            fontSize: SuokeDesignTokens.fontSizeXs,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(color: SuokeDesignTokens.accent, size: 22);
          }
          return const IconThemeData(color: SuokeDesignTokens.textSecondary, size: 22);
        }),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),

      // ── Dialog ──
      dialogTheme: DialogThemeData(
        backgroundColor: SuokeDesignTokens.cardBg,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusLg),
          side: const BorderSide(color: SuokeDesignTokens.border),
        ),
      ),

      // ── SnackBar ──
      snackBarTheme: SnackBarThemeData(
        backgroundColor: SuokeDesignTokens.cardBg,
        contentTextStyle: const TextStyle(color: SuokeDesignTokens.textPrimary),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
          side: const BorderSide(color: SuokeDesignTokens.border),
        ),
        behavior: SnackBarBehavior.floating,
      ),

      // ── Divider ──
      dividerTheme: const DividerThemeData(
        color: SuokeDesignTokens.border,
        thickness: 1,
        space: 0,
      ),

      // ── Chip ──
      chipTheme: ChipThemeData(
        backgroundColor: SuokeDesignTokens.bgDeep,
        selectedColor: SuokeDesignTokens.accentGlow,
        side: const BorderSide(color: SuokeDesignTokens.border),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusPill),
        ),
        labelStyle: const TextStyle(fontSize: SuokeDesignTokens.fontSizeSm, color: SuokeDesignTokens.textPrimary),
        secondaryLabelStyle: const TextStyle(fontSize: SuokeDesignTokens.fontSizeSm, color: SuokeDesignTokens.accent),
        padding: const EdgeInsets.symmetric(horizontal: SuokeDesignTokens.spacingSm),
      ),

      // ── Progress Indicator ──
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: SuokeDesignTokens.accent,
        linearTrackColor: SuokeDesignTokens.border,
      ),

      // ── 全局文字主题 ──
      textTheme: const TextTheme(
        titleLarge: TextStyle(
          color: SuokeDesignTokens.textPrimary,
          fontSize: 18,
          fontWeight: FontWeight.w700,
        ),
        titleMedium: TextStyle(
          color: SuokeDesignTokens.textPrimary,
          fontSize: SuokeDesignTokens.fontSizeLg,
          fontWeight: FontWeight.w600,
        ),
        bodyLarge: TextStyle(
          color: SuokeDesignTokens.textPrimary,
          fontSize: SuokeDesignTokens.fontSizeMd,
        ),
        bodyMedium: TextStyle(
          color: SuokeDesignTokens.textSecondary,
          fontSize: SuokeDesignTokens.fontSizeSm,
        ),
        bodySmall: TextStyle(
          color: SuokeDesignTokens.textMuted,
          fontSize: SuokeDesignTokens.fontSizeXs,
        ),
        labelLarge: TextStyle(
          color: SuokeDesignTokens.textPrimary,
          fontSize: SuokeDesignTokens.fontSizeMd,
          fontWeight: FontWeight.w600,
        ),
        labelMedium: TextStyle(
          color: SuokeDesignTokens.textSecondary,
          fontSize: SuokeDesignTokens.fontSizeSm,
        ),
        labelSmall: TextStyle(
          color: SuokeDesignTokens.textMuted,
          fontSize: SuokeDesignTokens.fontSizeXs,
        ),
      ),
    );
  }

  /// 浅色/普通主题
  static ThemeData light() {
    return ThemeData(
      brightness: Brightness.light,
      scaffoldBackgroundColor: SuokeDesignTokens.lightBg,
      colorScheme: const ColorScheme.light(
        primary: SuokeDesignTokens.accent,
        surface: SuokeDesignTokens.lightCard,
        onPrimary: Colors.white,
        onSurface: SuokeDesignTokens.lightTextPrimary,
        error: SuokeDesignTokens.danger,
      ),

      appBarTheme: AppBarTheme(
        backgroundColor: SuokeDesignTokens.lightCard.withValues(alpha: 0.92),
        foregroundColor: SuokeDesignTokens.lightTextPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: const TextStyle(
          color: SuokeDesignTokens.lightTextPrimary,
          fontSize: SuokeDesignTokens.fontSizeLg,
          fontWeight: FontWeight.w700,
        ),
      ),

      cardTheme: CardThemeData(
        color: SuokeDesignTokens.lightCard,
        elevation: 1,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radius),
          side: const BorderSide(color: SuokeDesignTokens.lightBorder, width: 1),
        ),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: SuokeDesignTokens.lightBg,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
          borderSide: const BorderSide(color: SuokeDesignTokens.lightBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
          borderSide: const BorderSide(color: SuokeDesignTokens.lightBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
          borderSide: const BorderSide(color: SuokeDesignTokens.accent),
        ),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: SuokeDesignTokens.accent,
          foregroundColor: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: SuokeDesignTokens.lightTextPrimary,
          side: const BorderSide(color: SuokeDesignTokens.lightBorder),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
          ),
        ),
      ),

      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: SuokeDesignTokens.lightCard.withValues(alpha: 0.92),
        indicatorColor: SuokeDesignTokens.accent.withValues(alpha: 0.12),
        surfaceTintColor: Colors.transparent,
        height: 64,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),

      dialogTheme: DialogThemeData(
        backgroundColor: SuokeDesignTokens.lightCard,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusLg),
          side: const BorderSide(color: SuokeDesignTokens.lightBorder),
        ),
      ),

      textTheme: const TextTheme(
        titleLarge: TextStyle(
          color: SuokeDesignTokens.lightTextPrimary,
          fontSize: 18,
          fontWeight: FontWeight.w700,
        ),
        titleMedium: TextStyle(
          color: SuokeDesignTokens.lightTextPrimary,
          fontSize: SuokeDesignTokens.fontSizeLg,
          fontWeight: FontWeight.w600,
        ),
        bodyLarge: TextStyle(
          color: SuokeDesignTokens.lightTextPrimary,
          fontSize: SuokeDesignTokens.fontSizeMd,
        ),
        bodyMedium: TextStyle(
          color: SuokeDesignTokens.lightTextSecondary,
          fontSize: SuokeDesignTokens.fontSizeSm,
        ),
        bodySmall: TextStyle(
          color: SuokeDesignTokens.lightTextMuted,
          fontSize: SuokeDesignTokens.fontSizeXs,
        ),
      ),
    );
  }
}
