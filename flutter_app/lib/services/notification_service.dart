/// 索克家居 · 推送通知服务
///
/// 功能：
/// - 初始化本地通知插件（flutter_local_notifications）
/// - 请求通知权限（iOS/Android，HarmonyOS 优雅降级）
/// - 注册设备 Token 到后端
/// - 处理接收到的推送消息并路由到对应页面
library;

import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:permission_handler/permission_handler.dart';

import 'api.dart';

/// 推送通知服务（本地通知 + 远程推送注册）
///
/// 设计原则：
/// - 所有原生插件调用均包裹 try-catch，失败仅 debugPrint，不抛异常
/// - 未知平台（如 HarmonyOS/ohos）跳过原生初始化，保持应用可用
/// - 单例模式，全局共享一个 [FlutterLocalNotificationsPlugin] 实例
class NotificationService {
  static final NotificationService _instance = NotificationService._();
  factory NotificationService() => _instance;
  NotificationService._();

  static const String _kDefaultChannelId = 'ihome_default';
  static const String _kDefaultChannelName = '索克家居通知';
  static const String _kDefaultChannelDescription =
      '索克家居 App 任务、审批、结算等业务通知';

  final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();

  bool _initialized = false;
  String? _deviceToken;

  /// 当前平台是否启用了原生通知（仅 Android/iOS）
  bool _nativeSupported = false;

  bool get isInitialized => _initialized;
  String? get deviceToken => _deviceToken;

  /// 初始化通知服务
  ///
  /// 失败不抛异常，仅记录日志，确保不影响应用启动。
  Future<void> initialize() async {
    if (_initialized) return;

    // 平台检查：仅 Android/iOS 启用原生通知，HarmonyOS/ohos 等未知平台跳过
    if (!Platform.isAndroid && !Platform.isIOS) {
      debugPrint('[NotificationService] 当前平台不支持原生通知插件，跳过初始化 '
          '(platform=${Platform.operatingSystem})');
      _nativeSupported = false;
      // 仍然标记为已初始化，避免重复尝试
      _initialized = true;
      return;
    }

    _nativeSupported = true;

    try {
      await _initLocalNotifications();
    } catch (e, st) {
      debugPrint('[NotificationService] 本地通知插件初始化失败: $e\n$st');
    }

    try {
      await _requestPermission();
    } catch (e, st) {
      debugPrint('[NotificationService] 通知权限请求失败: $e\n$st');
    }

    try {
      await _getDeviceToken();
    } catch (e, st) {
      debugPrint('[NotificationService] 设备 Token 获取失败: $e\n$st');
    }

    _initialized = true;
  }

  /// 初始化 flutter_local_notifications 插件
  Future<void> _initLocalNotifications() async {
    // Android: 配置默认 channel（Importance.high 保证横幅通知）
    const AndroidInitializationSettings androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');

    // iOS: 配置默认权限（alert/badge/sound）
    const DarwinInitializationSettings iosSettings =
        DarwinInitializationSettings(
      requestAlertPermission: false, // 权限统一在 _requestPermission 中请求
      requestBadgePermission: false,
      requestSoundPermission: false,
      // 前台展示通知
      requestCriticalPermission: false,
    );

    const InitializationSettings settings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    final ok = await _localNotifications.initialize(
      settings: settings,
      onDidReceiveNotificationResponse: _onDidReceiveNotificationResponse,
    );
    debugPrint('[NotificationService] 插件初始化结果: $ok');

    // 创建默认 channel（Android 8.0+ 必需）
    if (Platform.isAndroid) {
      await _localNotifications
          .resolvePlatformSpecificImplementation<
              AndroidFlutterLocalNotificationsPlugin>()
          ?.createNotificationChannel(const AndroidNotificationChannel(
        _kDefaultChannelId,
        _kDefaultChannelName,
        description: _kDefaultChannelDescription,
        importance: Importance.high,
      ));
    }
  }

  /// 接收通知点击回调
  void _onDidReceiveNotificationResponse(NotificationResponse response) {
    debugPrint('[NotificationService] 通知点击: '
        'id=${response.id}, payload=${response.payload}');
    // TODO: 根据 payload 路由到对应页面
  }

  /// 请求通知权限
  ///
  /// - Android 13+: POST_NOTIFICATIONS（用 permission_handler）
  /// - iOS: alert/badge/sound（用 flutter_local_notifications）
  Future<bool> _requestPermission() async {
    bool granted = false;

    if (Platform.isAndroid) {
      // Android 13+ 需要运行时请求 POST_NOTIFICATIONS
      try {
        final status = await Permission.notification.status;
        if (status.isGranted) {
          granted = true;
        } else if (status.isDenied || status.isRestricted) {
          final result = await Permission.notification.request();
          granted = result.isGranted;
        }
      } catch (e) {
        debugPrint('[NotificationService] Android 通知权限请求异常: $e');
        // 低版本 Android 不需要运行时权限，默认允许
        granted = true;
      }
    } else if (Platform.isIOS) {
      try {
        final result = await _localNotifications
            .resolvePlatformSpecificImplementation<
                IOSFlutterLocalNotificationsPlugin>()
            ?.requestPermissions(
              alert: true,
              badge: true,
              sound: true,
            );
        granted = result ?? false;
      } catch (e) {
        debugPrint('[NotificationService] iOS 通知权限请求异常: $e');
        granted = false;
      }
    }

    debugPrint('[NotificationService] 通知权限授予: $granted');
    return granted;
  }

  /// 获取设备推送 Token
  ///
  /// TODO: 实际环境通过平台通道获取 FCM/HMS/PushKit token
  /// 当前使用平台标识作为占位 token，确保后端可记录设备
  Future<void> _getDeviceToken() async {
    final platform = Platform.isIOS ? 'ios' : 'android';
    _deviceToken = '${platform}_device_${DateTime.now().millisecondsSinceEpoch}';
    debugPrint('[NotificationService] 设备 Token: $_deviceToken');
  }

  /// 注册设备 Token 到后端
  ///
  /// 保留原方法签名，实际发送通过 ApiClient 调用后端接口
  Future<void> registerDeviceToken(String userId) async {
    if (_deviceToken == null) {
      debugPrint('[NotificationService] 设备 Token 为空，跳过注册');
      return;
    }

    try {
      final api = ApiClient();
      final platform = Platform.isIOS ? 'ios' : 'android';
      final result = await api.post('/notifications/register-device', {
        'user_id': userId,
        'device_token': _deviceToken,
        'platform': platform,
      });
      if (result.isSuccess) {
        debugPrint('[NotificationService] 设备 Token 注册成功: '
            '$_deviceToken for user $userId');
      } else {
        debugPrint('[NotificationService] 设备 Token 注册失败: ${result.error}');
      }
    } catch (e) {
      debugPrint('[NotificationService] 设备 Token 注册异常: $e');
    }
  }

  /// 处理接收到的推送消息
  ///
  /// 保留原方法签名，由远程推送回调（FCM/HMS）触发
  void handleNotification(Map<String, dynamic> data) {
    final type = data['type'] as String? ?? '';
    final projectId = data['project_id'] as String?;
    debugPrint('[NotificationService] 收到推送: type=$type, project_id=$projectId');

    // 自动展示本地通知（前台收到推送时）
    final title = data['title'] as String? ?? '索克家居';
    final body = data['body'] as String? ?? data['message'] as String? ?? '';
    if (title.isNotEmpty && body.isNotEmpty) {
      showLocalNotification(
        title: title,
        body: body,
        payload: data.toString(),
      );
    }

    // 根据 type 路由到不同页面：
    // - task.completed → 施工进度
    // - inspection.ready → 质检报告
    // - budget.approved → 预算详情
    // - settlement.confirmed → 结算确认
  }

  /// 显示本地通知
  ///
  /// 真正调用 flutter_local_notifications.show()
  /// 未知平台或未初始化时仅 debugPrint，不抛异常
  Future<void> showLocalNotification({
    required String title,
    required String body,
    String? payload,
  }) async {
    if (!_nativeSupported) {
      debugPrint('[NotificationService] 当前平台不支持原生通知，跳过显示: $title - $body');
      return;
    }

    try {
      const AndroidNotificationDetails androidDetails =
          AndroidNotificationDetails(
        _kDefaultChannelId,
        _kDefaultChannelName,
        channelDescription: _kDefaultChannelDescription,
        importance: Importance.high,
        priority: Priority.high,
      );

      const DarwinNotificationDetails iosDetails = DarwinNotificationDetails(
        presentAlert: true,
        presentBadge: true,
        presentSound: true,
      );

      const NotificationDetails details = NotificationDetails(
        android: androidDetails,
        iOS: iosDetails,
      );

      // id=0 使用单一通知槽位，后续可扩展为按业务类型分配 id
      await _localNotifications.show(
        id: 0,
        title: title,
        body: body,
        notificationDetails: details,
        payload: payload,
      );
      debugPrint('[NotificationService] 本地通知已显示: $title - $body');
    } catch (e, st) {
      debugPrint('[NotificationService] 显示本地通知失败: $e\n$st');
    }
  }
}
