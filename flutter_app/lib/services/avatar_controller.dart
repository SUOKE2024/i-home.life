import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 用户头像控制器（2026 暖境身份体系）
///
/// 规则（优先级从高到低）：
/// 1. 用户从相册上传的自定义头像（`customPath`）——跨启动保持；
/// 2. 用户从手绘宫格挑选的头像（`chosenIndex`）——跨启动保持；
/// 3. 未做任何选择：应用每次启动随机载入一张手绘头像（本次启动内保持一致）。
///
/// 手绘头像资产位于
/// `assets/images/avatars/hand-drawn-profiles/1..110.webp`（共 110 张）。
class AvatarController extends ChangeNotifier {
  static const _kCustomPath = 'user_avatar_custom_path';
  static const _kChosenIndex = 'user_avatar_chosen_index';

  /// 手绘头像资产总数
  static const int assetCount = 110;

  String? _customPath;
  int? _chosenIndex;
  int _launchRandom = 1;
  bool _loaded = false;

  String? get customPath => _customPath;

  /// 用户从手绘宫格固定的头像序号（未选择为 null）
  int? get chosenIndex => _chosenIndex;

  /// 手绘资产路径：优先用户选择，否则为本次启动随机头像
  String get assetPath =>
      'assets/images/avatars/hand-drawn-profiles/'
      '${_chosenIndex ?? _launchRandom}.webp';

  bool get isLoaded => _loaded;

  /// 应用启动时调用：加载持久化选择；未选择则本次启动随机载入。
  Future<void> initialize() async {
    if (_loaded) return;
    // 应用启动随机：每次启动重新掷一次（用户未固定选择时生效）
    _launchRandom = Random().nextInt(assetCount) + 1;
    try {
      final prefs = await SharedPreferences.getInstance();
      _customPath = prefs.getString(_kCustomPath);
      _chosenIndex = prefs.getInt(_kChosenIndex);
      if (_chosenIndex != null &&
          (_chosenIndex! < 1 || _chosenIndex! > assetCount)) {
        _chosenIndex = null;
      }
    } catch (_) {
      // SharedPreferences 不可用：仅本次会话随机，不影响使用
    }
    _loaded = true;
    notifyListeners();
  }

  /// 从相册自定义头像（优先级最高）
  Future<void> setCustomPath(String path) async {
    _customPath = path;
    _chosenIndex = null;
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kCustomPath, path);
      await prefs.remove(_kChosenIndex);
    } catch (_) {}
  }

  /// 从手绘宫格固定选择一张头像
  Future<void> setChosenIndex(int index) async {
    if (index < 1 || index > assetCount) return;
    _chosenIndex = index;
    _customPath = null;
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt(_kChosenIndex, index);
      await prefs.remove(_kCustomPath);
    } catch (_) {}
  }

  /// 恢复随机：清空自定义与固定选择，本次会话随机
  Future<void> randomize() async {
    _customPath = null;
    _chosenIndex = null;
    _launchRandom = Random().nextInt(assetCount) + 1;
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_kCustomPath);
      await prefs.remove(_kChosenIndex);
    } catch (_) {}
  }
}
