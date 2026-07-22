/// F1 AR 空间测量页面 — 专业化重设计
///
/// 4 步骤扫描引导流程：
///   Step 0: 设备能力检测仪表盘（真实传感器数据）
///   Step 1: 房间设置（选择户型、房间类型、尺寸）
///   Step 2: 扫描引导（动画化指引）
///   Step 3: 扫描结果（精度报告 + 后续操作）
///
/// 设计原则：
///   - 真实设备能力检测（SensorService + 平台 API）
///   - 户型选择器（后端 API 集成）
///   - 分步骤引导体验（PageView + 步骤指示器）
///   - 专业化 UI/UX（暗色主题 + 渐变 + 动画 + 脉冲雷达）
library;

import 'dart:async';
import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

import '../config.dart';
import '../services/api.dart';
import '../services/sensor_service.dart';

// ── AR 平台通道（iOS ARKit / Android ARCore / 鸿蒙 AR Engine）──
const _arChannel = MethodChannel('com.ihome.life/ar_scan');

// ── 设计 Token ──
const _brand = Color(0xFFC9973B);
const _bgDeep = Color(0xFF0A0A14);
const _bgCard = Color(0xFF141428);
const _textPrimary = Color(0xFFE8E6E1);
const _textSecondary = Color(0xFF8A8894);
const _textMuted = Color(0xFF5A5874);
const _border = Color(0xFF1E1E36);
const _success = Color(0xFF4CAF50);
const _warning = Color(0xFFFFA726);
const _danger = Color(0xFFEF5350);

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

const _roomPresets = [
  RoomPreset(name: '客厅', icon: Icons.weekend, defaultArea: 30.0, defaultHeight: 2.8, description: '家庭活动中心'),
  RoomPreset(name: '主卧', icon: Icons.king_bed, defaultArea: 18.0, defaultHeight: 2.8, description: '含衣柜/卫生间'),
  RoomPreset(name: '次卧', icon: Icons.bed, defaultArea: 12.0, defaultHeight: 2.8),
  RoomPreset(name: '厨房', icon: Icons.countertops, defaultArea: 8.0, defaultHeight: 2.4, description: 'L型/U型/一字型'),
  RoomPreset(name: '卫生间', icon: Icons.bathtub, defaultArea: 5.0, defaultHeight: 2.4, description: '干湿分离'),
  RoomPreset(name: '书房', icon: Icons.menu_book, defaultArea: 10.0, defaultHeight: 2.8),
  RoomPreset(name: '阳台', icon: Icons.wb_sunny, defaultArea: 6.0, defaultHeight: 2.8, description: '封闭/开放'),
  RoomPreset(name: '走廊/玄关', icon: Icons.meeting_room, defaultArea: 4.0, defaultHeight: 2.8),
  RoomPreset(name: '餐厅', icon: Icons.table_restaurant, defaultArea: 12.0, defaultHeight: 2.8),
  RoomPreset(name: '储物间', icon: Icons.inventory_2, defaultArea: 4.0, defaultHeight: 2.4),
];

// ── 扫描状态枚举 ──
enum _ScanStep { deviceCheck, roomSetup, scanGuide, review, results, doorWindow, mep }
enum _ScanState { idle, detecting, ready, scanning, uploading, processing, completed, failed }
enum _TrackingQuality { searching, limited, normal, lost } // AR 追踪质量
enum _EnvCondition { normal, lowLight, lowTexture, fastMotion } // 环境条件

class ARScanPage extends StatefulWidget {
  final String projectId;
  const ARScanPage({super.key, required this.projectId});

  @override
  State<ARScanPage> createState() => _ARScanPageState();
}

class _ARScanPageState extends State<ARScanPage> with TickerProviderStateMixin {
  final _api = ApiClient();
  final _sensor = SensorService();

  // ── 动画控制器 ──
  late final AnimationController _pulseCtrl;
  late final AnimationController _radarCtrl;
  late final AnimationController _slideCtrl;
  late final PageController _pageCtrl;

  // ── 步骤状态 ──
  _ScanStep _currentStep = _ScanStep.deviceCheck;
  _ScanState _scanState = _ScanState.idle;

  // ── 设备能力 ──
  bool _isIOS = false;
  String _deviceModel = '';
  bool _hasLidarProbed = false;
  bool _hasGyro = false;
  bool _hasAccel = false;
  bool _hasMagnet = false;
  bool _hasCamera = false;
  String _osVersion = '';
  double _screenWidth = 0;
  double _screenHeight = 0;
  double _pixelRatio = 1.0;

  // ── 扫描方法 ──
  String _scanMethod = 'lidar';
  final List<String> _availableMethods = [];
  double _estimatedAccuracyCm = 1.0;
  int _estimatedTimeMin = 5;

  // ── 房间设置 ──
  int _selectedRoomIndex = 0;
  double _roomLength = 6.0;
  double _roomWidth = 4.0;
  double _roomHeight = 2.8;
  int _floorCount = 1;

  // ── 户型 ──
  List<Map<String, dynamic>> _floorplans = [];
  String? _selectedFloorplanId;
  bool _loadingFloorplans = false;

  // ── 扫描 ──
  String? _sessionId;
  String _sessionName = '';

  // ── 结果 ──
  int _roomCount = 0;
  double _totalArea = 0.0;
  String _accuracyLevel = '';
  double? _rmsErrorCm;
  int _wallFeatures = 0;

  // ── 校准点 ──
  final List<Map<String, dynamic>> _calibrationPoints = [];
  final _labelCtrl = TextEditingController();
  final _arValueCtrl = TextEditingController();
  final _refValueCtrl = TextEditingController();

  String _errorMessage = '';
  int _detectionProgress = 0;

  // ── AR 追踪与环境状态 ──
  _TrackingQuality _trackingQuality = _TrackingQuality.searching;
  _EnvCondition _envCondition = _EnvCondition.normal;
  String _trackingHint = '';
  bool _scanCancelled = false;
  double _scanProgress = 0.0;
  int _scanPointsDetected = 0;
  int _scanWallsDetected = 0;

  // ── 单位切换 cm/m ──
  bool _useCentimeters = false;

  // ── 尺寸字段控制器（修复内存泄漏：生命周期管理）──
  late final TextEditingController _dimLengthCtrl;
  late final TextEditingController _dimWidthCtrl;
  late final TextEditingController _dimHeightCtrl;

  // ── 复核流程状态 ──
  final Set<String> _reviewConfirmedItems = {}; // 已确认的检测项 ID
  bool _reviewAllConfirmed = false;
  final _reviewNoteCtrl = TextEditingController();

  // ── 最佳实践 ──
  bool _showCoachingCard = true; // 首次引导卡片

  // ── 户型图上传 ──
  String? _floorplanImageUrl;

  // ── 门窗 ──
  List<Map<String, dynamic>> _doorWindows = [];
  bool _loadingDoorWindows = false;
  String _dwSelectedType = 'door'; // 替代 TextEditingController 做类型选择
  final _dwTypeCtrl = TextEditingController();
  final _dwWidthCtrl = TextEditingController();
  final _dwHeightCtrl = TextEditingController();
  final _dwPosCtrl = TextEditingController();

  // ── MEP 水电 ──
  List<Map<String, dynamic>> _mepPoints = [];
  String? _mepPlanId;
  bool _loadingMep = false;
  final _mepLabelCtrl = TextEditingController();
  final _mepTypeCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 2))..repeat();
    _radarCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 3))..repeat();
    _slideCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 400));
    _pageCtrl = PageController();
    // 初始化尺寸字段控制器（修复内存泄漏：late final，生命周期内复用）
    _dimLengthCtrl = TextEditingController(text: '6.0');
    _dimWidthCtrl = TextEditingController(text: '4.0');
    _dimHeightCtrl = TextEditingController(text: '2.8');
    _detectRealCapabilities();
    _loadFloorplans();
    _setupArListeners();
  }

  void _setupArListeners() {
    _arChannel.setMethodCallHandler((call) async {
      if (!mounted) return;
      switch (call.method) {
        case 'onScanProgress':
          final args = call.arguments as Map?;
          if (args != null) {
            setState(() {
              _scanProgress = (args['progress'] as num?)?.toDouble() ?? _scanProgress;
              _scanPointsDetected = args['points_count'] as int? ?? _scanPointsDetected;
              _scanWallsDetected = args['walls_detected'] as int? ?? _scanWallsDetected;
              if (_isIOS) {
                _roomCount = args['room_count'] as int? ?? 0;
                _wallFeatures = (args['door_count'] as int? ?? 0) + (args['window_count'] as int? ?? 0);
              }
            });
          }
        case 'onTrackingQuality':
          final args = call.arguments as Map?;
          if (args != null && mounted) {
            final quality = args['quality'] as String? ?? 'searching';
            final hint = args['hint'] as String? ?? '';
            setState(() {
              _trackingQuality = _parseTrackingQuality(quality);
              _trackingHint = hint;
              if (quality == 'normal') _envCondition = _EnvCondition.normal;
            });
            if (quality == 'normal' && _trackingQuality == _TrackingQuality.searching) {
              _hapticLight();
            }
          }
        case 'onEnvironmentalCondition':
          final args = call.arguments as Map?;
          if (args != null && mounted) {
            final cond = args['condition'] as String? ?? 'normal';
            final msg = args['message'] as String? ?? '';
            setState(() {
              _envCondition = _parseEnvCondition(cond);
              _trackingHint = msg;
            });
            _hapticWarning();
          }
        case 'onScanInstruction':
          final args = call.arguments as Map?;
          if (args != null) {
            final type = args['type'] as String? ?? '';
            final msg = args['instruction'] as String? ?? '';
            String hint;
            switch (type) {
              case 'move_away_from_wall':
                hint = '请远离墙壁';
                break;
              case 'turn_on_light':
                hint = '请打开灯光或增加照明';
                break;
              case 'low_texture':
                hint = '请对特征不明显的区域添加纹理标记';
                break;
              default:
                hint = msg;
            }
            if (msg.isNotEmpty) {
              setState(() => _trackingHint = hint);
              _showSnack(hint);
            }
          }
        case 'onScanError':
          final msg = call.arguments as String? ?? '扫描出错';
          setState(() {
            _errorMessage = msg;
            _scanState = _ScanState.failed;
          });
        case 'onScanCancelled':
          setState(() {
            _scanState = _ScanState.ready;
            _scanCancelled = true;
            _scanProgress = 0.0;
            _scanPointsDetected = 0;
            _scanWallsDetected = 0;
            _trackingQuality = _TrackingQuality.searching;
          });
        case 'onScanStarted':
          setState(() {
            _scanCancelled = false;
            _scanProgress = 0.0;
            _scanPointsDetected = 0;
            _scanWallsDetected = 0;
          });
        case 'onScanPaused':
        case 'onScanResumed':
          break;
      }
    });
  }

  _TrackingQuality _parseTrackingQuality(String q) => switch (q) {
    'limited' => _TrackingQuality.limited,
    'normal' => _TrackingQuality.normal,
    'lost' => _TrackingQuality.lost,
    _ => _TrackingQuality.searching,
  };

  _EnvCondition _parseEnvCondition(String c) => switch (c) {
    'low_light' => _EnvCondition.lowLight,
    'low_texture' => _EnvCondition.lowTexture,
    'fast_motion' => _EnvCondition.fastMotion,
    _ => _EnvCondition.normal,
  };

  void _hapticLight() {
    try { HapticFeedback.lightImpact(); } catch (_) {}
  }

  void _hapticWarning() {
    try { HapticFeedback.heavyImpact(); } catch (_) {}
  }

  void _hapticSuccess() {
    try { HapticFeedback.mediumImpact(); } catch (_) {}
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    _radarCtrl.dispose();
    _slideCtrl.dispose();
    _pageCtrl.dispose();
    _labelCtrl.dispose();
    _arValueCtrl.dispose();
    _refValueCtrl.dispose();
    _dwTypeCtrl.dispose();
    _dwWidthCtrl.dispose();
    _dwHeightCtrl.dispose();
    _dwPosCtrl.dispose();
    _mepLabelCtrl.dispose();
    _mepTypeCtrl.dispose();
    _dimLengthCtrl.dispose();
    _dimWidthCtrl.dispose();
    _dimHeightCtrl.dispose();
    _reviewNoteCtrl.dispose();
    _sensor.dispose();
    super.dispose();
  }

  // ═══════════════════════════════════════════════
  // 设备能力检测（真实数据）
  // ═══════════════════════════════════════════════

  Future<void> _detectRealCapabilities() async {
    setState(() => _scanState = _ScanState.detecting);

    // 平台
    _isIOS = Platform.isIOS;
    _detectionProgress = 10;

    // 操作系统版本
    try {
      _osVersion = Platform.operatingSystemVersion;
    } catch (_) {
      _osVersion = Platform.operatingSystem;
    }

    // 设备型号
    try {
      final model = await _arChannel.invokeMethod<String>('getDeviceModel');
      _deviceModel = model ?? (_isIOS ? 'iPhone' : Platform.isAndroid ? 'Android' : 'Mobile');
    } catch (_) {
      _deviceModel = _isIOS ? 'iPhone' : Platform.isAndroid ? 'Android' : 'Mobile';
    }
    _detectionProgress = 25;

    // 屏幕参数
    if (mounted) {
      final media = MediaQuery.of(context);
      _screenWidth = media.size.width;
      _screenHeight = media.size.height;
      _pixelRatio = media.devicePixelRatio;
    }
    _detectionProgress = 35;

    // LiDAR 探测（iOS 设备通过屏幕特征 + 系统版本推断）
    if (_isIOS) {
      try {
        final lidarInfo = await _arChannel.invokeMethod<Map>('detectLidar');
        _hasLidarProbed = lidarInfo?['available'] == true;
      } catch (_) {
        // 无法探测则根据已知支持 LiDAR 的设备推断
        // iPhone 12 Pro/13 Pro/14 Pro/15 Pro/16 Pro, iPad Pro 2020+
        _hasLidarProbed = false;
      }
    }
    _detectionProgress = 50;

    // 真实传感器
    try {
      await _sensor.start();
      final caps = _sensor.getCapabilities();
      _hasAccel = caps['accelerometer'] ?? false;
      _hasGyro = caps['gyroscope'] ?? false;
      _hasMagnet = caps['magnetometer'] ?? false;
    } catch (_) {
      _hasAccel = false;
      _hasGyro = false;
      _hasMagnet = false;
    }
    _detectionProgress = 70;

    // 相机可用性（移动平台默认可用）
    _hasCamera = _isIOS || Platform.isAndroid;
    _detectionProgress = 85;

    // 确定扫描方法
    if (_hasLidarProbed && _isIOS) {
      _scanMethod = 'lidar';
      _availableMethods.addAll(['lidar', 'visual_slam', 'photogrammetry', 'manual']);
      _estimatedAccuracyCm = 1.0;
      _estimatedTimeMin = 3;
    } else if (_hasGyro && _hasAccel) {
      _scanMethod = 'visual_slam';
      _availableMethods.addAll(['visual_slam', 'photogrammetry', 'manual']);
      _estimatedAccuracyCm = 3.0;
      _estimatedTimeMin = 5;
    } else if (_hasCamera) {
      _scanMethod = 'photogrammetry';
      _availableMethods.addAll(['photogrammetry', 'manual']);
      _estimatedAccuracyCm = 5.0;
      _estimatedTimeMin = 8;
    } else {
      _scanMethod = 'manual';
      _availableMethods.addAll(['manual']);
      _estimatedAccuracyCm = 5.0;
      _estimatedTimeMin = 10;
    }
    _detectionProgress = 100;

    if (mounted) {
      setState(() => _scanState = _ScanState.ready);
    }
  }

  // ═══════════════════════════════════════════════
  // 户型加载
  // ═══════════════════════════════════════════════

  Future<void> _loadFloorplans() async {
    setState(() => _loadingFloorplans = true);
    try {
      final result = await _api.getFloorplans(widget.projectId);
      if (result.isSuccess && result.data is List) {
        setState(() {
          _floorplans = (result.data as List)
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
        });
      }
    } catch (_) {
      // 户型加载失败，不影响主体流程
    }
    if (mounted) setState(() => _loadingFloorplans = false);
  }

  Future<void> _createQuickFloorplan(String name) async {
    final result = await _api.createFloorplan({
      'project_id': widget.projectId,
      'name': name,
      'room_count': 1,
      'total_area': _roomLength * _roomWidth,
    });
    if (result.isSuccess && mounted) {
      await _loadFloorplans();
      if (_floorplans.isNotEmpty) {
        setState(() => _selectedFloorplanId = _floorplans.last['id'] as String?);
      }
    }
  }

  // ═══════════════════════════════════════════════
  // 扫描生命周期
  // ═══════════════════════════════════════════════

  /// 取消当前扫描
  void _cancelScan() {
    _hapticLight();
    setState(() {
      _scanState = _ScanState.ready;
      _scanCancelled = true;
      _scanProgress = 0.0;
      _scanPointsDetected = 0;
      _scanWallsDetected = 0;
      _trackingQuality = _TrackingQuality.searching;
      _errorMessage = '';
    });
    try {
      _arChannel.invokeMethod('cancelScan');
    } catch (_) {}
  }

  Future<void> _startScan() async {
    setState(() {
      _errorMessage = '';
      _scanState = _ScanState.scanning;
      _scanCancelled = false;
      _scanProgress = 0.0;
      _scanPointsDetected = 0;
      _scanWallsDetected = 0;
    });

    // 创建扫描会话
    final presets = _roomPresets[_selectedRoomIndex];
    _sessionName = '${presets.name} ${DateTime.now().toString().substring(0, 16)}';

    final createResult = await _api.post('/surveys/ar/sessions', {
      'project_id': widget.projectId,
      'name': _sessionName,
      'platform': _isIOS ? 'ios' : Platform.isAndroid ? 'android' : 'unknown',
      'requested_method': _scanMethod,
      'device_capability': {
        'device_model': _deviceModel,
        'has_lidar': _hasLidarProbed,
        'has_gyroscope': _hasGyro,
        'has_accelerometer': _hasAccel,
        'has_magnetometer': _hasMagnet,
        'has_camera': _hasCamera,
        'screen_width': _screenWidth,
        'screen_height': _screenHeight,
        'pixel_ratio': _pixelRatio,
        'os_version': _osVersion,
      },
      'floor_count': _floorCount,
      'wall_height': _roomHeight,
      'floorplan_id': _selectedFloorplanId,
    });

    if (!createResult.isSuccess) {
      setState(() {
        _errorMessage = '创建扫描会话失败: ${createResult.error}';
        _scanState = _ScanState.failed;
      });
      return;
    }

    final session = createResult.data as Map<String, dynamic>;
    _sessionId = session['id'] as String?;
    if (_sessionId == null) return;

    // 启动扫描
    await _api.post('/surveys/ar/sessions/$_sessionId/start', {});

    // 引导原生 AR 扫描
    try {
      final scanResult = await _arChannel.invokeMethod<Map>('startScan', {
        'session_id': _sessionId,
        'method': _scanMethod,
        'room_length': _roomLength,
        'room_width': _roomWidth,
        'room_height': _roomHeight,
      });

      setState(() => _scanState = _ScanState.uploading);
      _hapticLight();
      final modelPath = scanResult?['model_path'] as String?;
      final modelFormat = scanResult?['model_format'] as String? ?? 'usdz';
      final pointsCount = scanResult?['points_count'] as int? ?? 0;
      final durationSec = scanResult?['duration_sec'] as int? ?? 0;

      // RoomPlan 自动检测的门窗 → 同步写入后端
      final doors = scanResult?['doors'] as List<dynamic>? ?? [];
      final windows = scanResult?['windows'] as List<dynamic>? ?? [];
      final totalArea = (scanResult?['total_area_sqm'] as num?)?.toDouble();

      await _uploadAndProcess(modelPath, modelFormat, pointsCount, durationSec);

      // 自动同步 RoomPlan 检测到的门窗到后端
      if (doors.isNotEmpty || windows.isNotEmpty) {
        await _syncDetectedDoorWindows(doors, windows);
      }

      // 使用真实测量面积
      if (totalArea != null && totalArea > 0 && mounted) {
        setState(() => _totalArea = totalArea);
      }
    } on MissingPluginException {
      await _fallbackPhotoScan();
    } on PlatformException catch (e) {
      if (AppConfig.debugMode) {
        await _uploadAndProcess(null, 'usdz', 50000, 120);
      } else if (e.code == 'UNSUPPORTED') {
        // RoomPlan 不可用（无 LiDAR），自动降级为拍照
        await _fallbackPhotoScan();
      } else {
        setState(() {
          _errorMessage = 'AR 扫描引擎不可用: ${e.message}';
          _scanState = _ScanState.failed;
        });
      }
    }
  }

  Future<void> _syncDetectedDoorWindows(List<dynamic> doors, List<dynamic> windows) async {
    // 将 RoomPlan 自动检测的门窗写入后端 doorWin API
    for (final d in doors) {
      if (d is! Map) continue;
      final pos = d['position'] as Map<String, dynamic>? ?? {};
      await _api.doorWinCreateSpec({
        'project_id': widget.projectId,
        'type': 'door',
        'width': ((d['width'] as num?)?.toDouble() ?? 0.9 * 100).round(),
        'height': ((d['height'] as num?)?.toDouble() ?? 2.1 * 100).round(),
        'position': '自动检测 x:${(pos['x'] as num?)?.toStringAsFixed(1) ?? "?"} z:${(pos['z'] as num?)?.toStringAsFixed(1) ?? "?"}',
        'room': _roomPresets[_selectedRoomIndex].name,
      });
    }
    for (final w in windows) {
      if (w is! Map) continue;
      final pos = w['position'] as Map<String, dynamic>? ?? {};
      await _api.doorWinCreateSpec({
        'project_id': widget.projectId,
        'type': 'window',
        'width': ((w['width'] as num?)?.toDouble() ?? 1.5 * 100).round(),
        'height': ((w['height'] as num?)?.toDouble() ?? 1.2 * 100).round(),
        'position': '自动检测 x:${(pos['x'] as num?)?.toStringAsFixed(1) ?? "?"} z:${(pos['z'] as num?)?.toStringAsFixed(1) ?? "?"}',
        'room': _roomPresets[_selectedRoomIndex].name,
      });
    }
    // 重新加载门窗列表
    _loadDoorWindows();
  }

  Future<void> _fallbackPhotoScan() async {
    final picker = ImagePicker();
    final photo = await picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 95,
      preferredCameraDevice: CameraDevice.rear,
    );
    if (photo == null) {
      setState(() {
        _scanState = _ScanState.ready;
        _errorMessage = '已取消拍照';
      });
      return;
    }
    setState(() => _scanState = _ScanState.uploading);
    await _uploadAndProcess(photo.path, 'photo', 0, 0);
  }

  Future<void> _uploadAndProcess(
    String? modelPath, String modelFormat, int pointsCount, int durationSec,
  ) async {
    String? modelUrl;
    if (modelPath != null) {
      final uploadResult = await _api.uploadFile(
        '/files/upload',
        filePath: modelPath,
        projectId: widget.projectId,
      );
      if (uploadResult.isSuccess) {
        modelUrl = uploadResult.data?['url'] as String?;
      }
    }

    setState(() => _scanState = _ScanState.processing);
    final result = await _api.post('/surveys/ar/sessions/$_sessionId/process', {
      'model_url': modelUrl,
      'model_format': modelFormat,
      'scan_points_count': pointsCount,
      'scan_duration_sec': durationSec,
    });

    if (result.isSuccess) {
      final data = result.data as Map<String, dynamic>? ?? {};
      setState(() {
        _scanState = _ScanState.completed;
        _roomCount = data['room_count'] as int? ?? 1;
        _totalArea = (data['total_area'] as num?)?.toDouble() ?? (_roomLength * _roomWidth);
        _wallFeatures = data['wall_features_added'] as int? ?? 0;
        final accuracy = data['accuracy_report'] as Map<String, dynamic>?;
        if (accuracy != null) {
          _accuracyLevel = accuracy['accuracy_level'] as String? ?? 'medium';
          _rmsErrorCm = (accuracy['rms_error_cm'] as num?)?.toDouble();
        }
      });
      _hapticSuccess();
      _goToStep(_ScanStep.review);
    } else {
      setState(() {
        _errorMessage = '处理失败: ${result.error}';
        _scanState = _ScanState.failed;
      });
    }
  }

  // ═══════════════════════════════════════════════
  // 校准点
  // ═══════════════════════════════════════════════

  Future<void> _addCalibrationPoint() async {
    if (_sessionId == null) return;
    final label = _labelCtrl.text.trim();
    final arValue = double.tryParse(_arValueCtrl.text);
    final refValue = double.tryParse(_refValueCtrl.text);
    if (label.isEmpty || arValue == null || refValue == null) {
      _showSnack('请填写完整的校准点信息');
      return;
    }
    final result = await _api.post('/surveys/ar/points', {
      'session_id': _sessionId,
      'label': label,
      'point_type': 'distance',
      'ar_value': arValue,
      'reference_value': refValue,
      'unit': 'm',
    });
    if (result.isSuccess) {
      final point = result.data as Map<String, dynamic>;
      setState(() {
        _calibrationPoints.add({
          'id': point['id'],
          'label': label, 'ar_value': arValue, 'reference_value': refValue,
          'deviation': point['deviation'],
          'deviation_percent': point['deviation_percent'],
        });
        _rmsErrorCm = (point['rms_error_cm'] as num?)?.toDouble() ?? _rmsErrorCm;
      });
      _labelCtrl.clear();
      _arValueCtrl.clear();
      _refValueCtrl.clear();
    } else {
      _showSnack('添加校准点失败: ${result.error}');
    }
  }

  Future<void> _applyToSurvey() async {
    if (_sessionId == null) return;
    final result = await _api.post('/surveys/ar/sessions/$_sessionId/apply', {});
    if (result.isSuccess) {
      _showSnack('已应用到测量记录');
    } else {
      _showSnack('应用失败: ${result.error}');
    }
  }

  void _showSnack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  void _goToStep(_ScanStep step) {
    _slideCtrl.forward(from: 0).then((_) => _slideCtrl.reset());
    setState(() => _currentStep = step);
    _pageCtrl.animateToPage(
      step.index,
      duration: const Duration(milliseconds: 400),
      curve: Curves.easeInOut,
    );
    // 进入复核步骤时重置确认状态
    if (step == _ScanStep.review) {
      _reviewConfirmedItems.clear();
      _reviewAllConfirmed = false;
    }
    // 自动加载数据
    if (step == _ScanStep.doorWindow && _doorWindows.isEmpty) {
      _loadDoorWindows();
    }
    if (step == _ScanStep.mep && _mepPlanId != null && _mepPoints.isEmpty) {
      _loadMepPoints();
    }
  }

  // ═══════════════════════════════════════════════
  // 方法标签
  // ═══════════════════════════════════════════════

  String _methodLabel(String method) => switch (method) {
    'lidar' => 'LiDAR 激光雷达',
    'visual_slam' => '视觉 SLAM',
    'photogrammetry' => '照片建模',
    'manual' => '手动测量',
    _ => method,
  };

  IconData _methodIcon(String method) => switch (method) {
    'lidar' => Icons.sensors,
    'visual_slam' => Icons.view_in_ar,
    'photogrammetry' => Icons.camera_alt,
    'manual' => Icons.straighten,
    _ => Icons.device_unknown,
  };

  String _accuracyLabel(String level) => switch (level) {
    'high' => '高精度 (±1cm)',
    'medium' => '中等精度 (±3cm)',
    'low' => '低精度 (±5cm+)',
    _ => level.toUpperCase(),
  };

  Color _accuracyColor(String level) => switch (level) {
    'high' => _success,
    'medium' => _warning,
    'low' => _danger,
    _ => _textSecondary,
  };

  // ═══════════════════════════════════════════════
  // UI
  // ═══════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgDeep,
      appBar: _buildAppBar(),
      body: Column(
        children: [
          _buildStepIndicator(),
          Expanded(
            child: PageView(
              controller: _pageCtrl,
              physics: const NeverScrollableScrollPhysics(),
              children: [
                _buildDeviceCheckStep(),
                _buildRoomSetupStep(),
                _buildScanGuideStep(),
                _buildReviewStep(),
                _buildResultsStep(),
                _buildDoorWindowStep(),
                _buildMepStep(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      backgroundColor: _bgCard,
      title: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.view_in_ar, color: _brand, size: 20),
          SizedBox(width: 8),
          Text('AR 空间测量', style: TextStyle(color: _textPrimary, fontSize: 17, fontWeight: FontWeight.w600)),
        ],
      ),
      centerTitle: true,
      leading: Semantics(
        label: '返回上一页',
        child: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, color: _textSecondary, size: 18),
          onPressed: () => Navigator.pop(context),
        ),
      ),
    );
  }

  // ── 步骤指示器 ──

  Widget _buildStepIndicator() {
    const steps = ['设备检测', '房间设置', '扫描', '复核', '结果', '门窗', '水电'];
    const icons = [Icons.sensors, Icons.home, Icons.camera_alt, Icons.fact_check, Icons.check_circle, Icons.door_sliding, Icons.electrical_services];

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      color: _bgCard,
      child: Row(
        children: List.generate(steps.length, (i) {
          final isActive = i == _currentStep.index;
          final isPast = i < _currentStep.index;
          final color = isActive ? _brand : isPast ? _success : _textMuted;

          return Expanded(
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _stepDot(i, isActive, isPast, color, icons[i]),
                if (i < steps.length - 1)
                  Expanded(
                    child: Container(
                      height: 2,
                      color: isPast ? _success.withValues(alpha: 0.3) : _border,
                    ),
                  ),
              ],
            ),
          );
        }),
      ),
    );
  }

  Widget _stepDot(int index, bool active, bool past, Color color, IconData icon) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          width: active ? 36 : 28,
          height: active ? 36 : 28,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: active ? color.withValues(alpha: 0.15) : past ? _success.withValues(alpha: 0.1) : Colors.transparent,
            border: Border.all(color: color, width: active ? 2 : 1),
          ),
          child: Icon(icon, size: active ? 16 : 12, color: color),
        ),
        if (active) ...[
          const SizedBox(height: 3),
          AnimatedBuilder(
            animation: _pulseCtrl,
            builder: (_, child) => Container(
              width: 4,
              height: 4,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: color.withValues(alpha: 0.5 + 0.5 * math.sin(_pulseCtrl.value * math.pi * 2)),
              ),
            ),
          ),
        ],
      ],
    );
  }

  // ═══════════════════════════════════════════════
  // Step 0: 设备能力检测仪表盘
  // ═══════════════════════════════════════════════

  Widget _buildDeviceCheckStep() {
    if (_scanState == _ScanState.detecting) return _buildDetectingView();
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionHeader('设备能力仪表盘', Icons.dashboard_customize),
          const SizedBox(height: 12),
          _buildDeviceInfoGrid(),
          const SizedBox(height: 16),
          _buildSensorStatusGrid(),
          const SizedBox(height: 16),
          _buildMethodRecommendation(),
          const SizedBox(height: 20),
          _buildNextStepButton('继续设置房间', () => _goToStep(_ScanStep.roomSetup)),
        ],
      ),
    );
  }

  Widget _buildDetectingView() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedBuilder(
            animation: _radarCtrl,
            builder: (_, __) {
              final angle = _radarCtrl.value * math.pi * 2;
              return Transform.rotate(
                angle: angle,
                child: Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: SweepGradient(
                      colors: [
                        _brand.withValues(alpha: 0.0),
                        _brand.withValues(alpha: 0.3),
                        _brand.withValues(alpha: 0.0),
                      ],
                    ),
                  ),
                  child: const Center(
                    child: Icon(Icons.sensors, color: _brand, size: 32),
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 24),
          const Text('正在检测设备能力...', style: TextStyle(color: _textPrimary, fontSize: 16)),
          const SizedBox(height: 12),
          Container(
            width: 200,
            height: 4,
            decoration: BoxDecoration(
              color: _border,
              borderRadius: BorderRadius.circular(2),
            ),
            child: FractionallySizedBox(
              widthFactor: _detectionProgress / 100,
              child: Container(
                decoration: BoxDecoration(
                  color: _brand,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text('$_detectionProgress%', style: const TextStyle(color: _textSecondary, fontSize: 12)),
        ],
      ),
    );
  }

  Widget _buildDeviceInfoGrid() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.phone_android, color: _brand, size: 18),
            const SizedBox(width: 8),
            const Text('设备信息', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
          ]),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 10,
            children: [
              _infoChip(Icons.devices, '平台', _isIOS ? 'iOS' : Platform.isAndroid ? 'Android' : 'Other'),
              _infoChip(Icons.model_training, '型号', _deviceModel.isEmpty ? '检测中...' : _deviceModel),
              _infoChip(Icons.screenshot_monitor, '屏幕', '${_screenWidth.toStringAsFixed(0)}x${_screenHeight.toStringAsFixed(0)}'),
              _infoChip(Icons.high_quality, '像素比', '${_pixelRatio}x'),
              _infoChip(Icons.info_outline, '系统版本', _osVersion),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSensorStatusGrid() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.sensors, color: _brand, size: 18),
            const SizedBox(width: 8),
            const Text('传感器状态', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
            const Spacer(),
            GestureDetector(
              onTap: () { setState(() => _scanState = _ScanState.detecting); _detectRealCapabilities(); },
              child: const Icon(Icons.refresh, color: _textSecondary, size: 18),
            ),
          ]),
          const SizedBox(height: 12),
          Wrap(spacing: 16, runSpacing: 12, children: [
            _sensorBadge('LiDAR', _hasLidarProbed, Icons.bluetooth_searching),
            _sensorBadge('加速度计', _hasAccel, Icons.vibration),
            _sensorBadge('陀螺仪', _hasGyro, Icons.rotate_right),
            _sensorBadge('磁力计', _hasMagnet, Icons.compass_calibration),
            _sensorBadge('相机', _hasCamera, Icons.camera_alt),
          ]),
        ],
      ),
    );
  }

  Widget _infoChip(IconData icon, String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: _bgDeep,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: _brand),
          const SizedBox(width: 6),
          Text(label, style: const TextStyle(color: _textSecondary, fontSize: 11)),
          const SizedBox(width: 4),
          Text(value, style: const TextStyle(color: _textPrimary, fontSize: 11, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  Widget _sensorBadge(String name, bool available, IconData icon) {
    final color = available ? _success : _textMuted;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: color),
        const SizedBox(width: 6),
        Text(name, style: TextStyle(color: _textPrimary, fontSize: 12)),
        const SizedBox(width: 4),
        Container(
          width: 6, height: 6,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: available ? _success : _danger,
          ),
        ),
      ],
    );
  }

  Widget _buildMethodRecommendation() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration().copyWith(
        border: Border.all(color: _brand.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.auto_fix_high, color: _brand, size: 18),
            const SizedBox(width: 8),
            const Text('智能推荐扫描方法', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
          ]),
          const SizedBox(height: 12),
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: _brand.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(_methodIcon(_scanMethod), color: _brand, size: 28),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_methodLabel(_scanMethod),
                        style: const TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 15)),
                    const SizedBox(height: 2),
                    Text(
                      '预计精度: ±${_estimatedAccuracyCm.toStringAsFixed(1)} cm · ${_estimatedTimeMin} 分钟/房间',
                      style: const TextStyle(color: _textSecondary, fontSize: 11),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (_availableMethods.length > 1) ...[
            const SizedBox(height: 12),
            const Divider(color: _border),
            const SizedBox(height: 8),
            const Text('可选方法:', style: TextStyle(color: _textSecondary, fontSize: 11)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: _availableMethods.map((m) => GestureDetector(
                onTap: () => setState(() => _scanMethod = m),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: _scanMethod == m ? _brand.withValues(alpha: 0.15) : _bgDeep,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: _scanMethod == m ? _brand : _border),
                  ),
                  child: Text(_methodLabel(m),
                      style: TextStyle(
                        color: _scanMethod == m ? _brand : _textSecondary,
                        fontSize: 12,
                      )),
                ),
              )).toList(),
            ),
          ],
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════
  // Step 1: 房间设置
  // ═══════════════════════════════════════════════

  Widget _buildRoomSetupStep() {
    final presets = _roomPresets[_selectedRoomIndex];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionHeader('房间设置', Icons.home_work),
          const SizedBox(height: 12),

          // 户型选择
          if (_floorplans.isNotEmpty) ...[
            _buildFloorplanSelector(),
            const SizedBox(height: 16),
          ],

          // 户型图上传/拍照
          _buildFloorplanUploadSection(),
          const SizedBox(height: 16),

          // 房间类型
          const Text('房间类型', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 10),
          _buildRoomTypeGrid(),
          const SizedBox(height: 16),

          // 房间尺寸
          _buildDimensionInput(presets),
          const SizedBox(height: 16),

          // 快速户型创建
          if (_floorplans.isEmpty && !_loadingFloorplans)
            _buildQuickFloorplanButton(),

          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: _outlineButton('上一步', Icons.arrow_back, () => _goToStep(_ScanStep.deviceCheck)),
              ),
              const SizedBox(width: 12),
              Expanded(flex: 2, child: _buildNextStepButton('开始扫描引导', () => _goToStep(_ScanStep.scanGuide))),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildFloorplanSelector() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(children: [
            Icon(Icons.layers, color: _brand, size: 16),
            SizedBox(width: 6),
            Text('选择户型', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
          ]),
          const SizedBox(height: 10),
          SizedBox(
            height: 70,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: _floorplans.length + 1, // +1 for "无户型"
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (_, i) {
                if (i == 0) {
                  final selected = _selectedFloorplanId == null;
                  return _floorplanChip('无户型', '独立测量', selected, () {
                    setState(() => _selectedFloorplanId = null);
                  });
                }
                final fp = _floorplans[i - 1];
                final id = fp['id'] as String?;
                final name = fp['name'] as String? ?? '户型 ${i}';
                final rooms = fp['room_count']?.toString() ?? '?';
                final selected = _selectedFloorplanId == id;
                return _floorplanChip(name, '$rooms 房间', selected, () {
                  setState(() => _selectedFloorplanId = id);
                });
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _floorplanChip(String title, String subtitle, bool selected, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 100,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: selected ? _brand.withValues(alpha: 0.12) : _bgDeep,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: selected ? _brand : _border, width: selected ? 1.5 : 1),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(title, style: TextStyle(
              color: selected ? _brand : _textPrimary, fontSize: 13, fontWeight: FontWeight.w500,
            ), overflow: TextOverflow.ellipsis),
            const SizedBox(height: 2),
            Text(subtitle, style: TextStyle(color: selected ? _brand : _textSecondary, fontSize: 10)),
          ],
        ),
      ),
    );
  }

  // ── 户型图上传/拍照 ──

  Widget _buildFloorplanUploadSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration().copyWith(
        border: Border.all(color: _border, style: BorderStyle.solid),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(children: [
            Icon(Icons.add_photo_alternate, color: _brand, size: 16),
            SizedBox(width: 6),
            Text('户型图', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
          ]),
          const SizedBox(height: 4),
          const Text('上传或拍摄户型图，辅助扫描定位和门窗标记',
              style: TextStyle(color: _textSecondary, fontSize: 11)),
          const SizedBox(height: 12),
          if (_floorplanImageUrl != null) ...[
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Container(
                height: 160,
                width: double.infinity,
                color: _bgDeep,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    // 网络图片 / 占位
                    Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.image, size: 48, color: _brand.withValues(alpha: 0.3)),
                          const SizedBox(height: 8),
                          const Text('户型图已上传', style: TextStyle(color: _textSecondary, fontSize: 12)),
                        ],
                      ),
                    ),
                    Positioned(
                      top: 8, right: 8,
                      child: GestureDetector(
                        onTap: () => setState(() => _floorplanImageUrl = null),
                        child: Container(
                          padding: const EdgeInsets.all(4),
                          decoration: BoxDecoration(
                            color: _danger.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Icon(Icons.close, size: 16, color: _danger),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
          ],
          Row(
            children: [
              Expanded(
                child: _outlineButtonSmall('上传图纸', Icons.upload_file, _pickFloorplanFromGallery),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _outlineButtonSmall('拍照', Icons.camera_alt, _pickFloorplanPhoto),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _pickFloorplanFromGallery() async {
    final picker = ImagePicker();
    final img = await picker.pickImage(source: ImageSource.gallery, imageQuality: 85);
    if (img == null) return;
    await _uploadFloorplanImage(img.path);
  }

  Future<void> _pickFloorplanPhoto() async {
    final picker = ImagePicker();
    final img = await picker.pickImage(source: ImageSource.camera, imageQuality: 85);
    if (img == null) return;
    await _uploadFloorplanImage(img.path);
  }

  Future<void> _uploadFloorplanImage(String filePath) async {
    final result = await _api.uploadFile('/files/upload', filePath: filePath, projectId: widget.projectId);
    if (result.isSuccess && mounted) {
      final url = result.data?['url'] as String?;
      setState(() => _floorplanImageUrl = url);
      // 如果已选择户型，更新其图片
      if (_selectedFloorplanId != null && url != null) {
        await _api.updateFloorplan(_selectedFloorplanId!, {'image_url': url});
      }
      _showSnack('户型图上传成功');
    } else if (mounted) {
      _showSnack('上传失败: ${result.error}');
    }
  }

  Widget _outlineButtonSmall(String label, IconData icon, VoidCallback onTap) {
    return SizedBox(
      height: 40,
      child: OutlinedButton.icon(
        onPressed: onTap,
        style: OutlinedButton.styleFrom(
          foregroundColor: _textPrimary,
          side: const BorderSide(color: _border),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
        icon: Icon(icon, size: 16),
        label: Text(label, style: const TextStyle(fontSize: 12)),
      ),
    );
  }

  Widget _buildRoomTypeGrid() {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: List.generate(_roomPresets.length, (i) {
        final p = _roomPresets[i];
        final selected = i == _selectedRoomIndex;
        return GestureDetector(
          onTap: () {
            setState(() {
              _selectedRoomIndex = i;
              _roomLength = math.sqrt(p.defaultArea / 1.5);
              _roomWidth = p.defaultArea / _roomLength;
              _roomHeight = p.defaultHeight;
            });
          },
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: selected ? _brand.withValues(alpha: 0.12) : _bgCard,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: selected ? _brand : _border, width: selected ? 1.5 : 1),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(p.icon, size: 18, color: selected ? _brand : _textSecondary),
                const SizedBox(width: 6),
                Text(p.name, style: TextStyle(
                  color: selected ? _brand : _textPrimary,
                  fontSize: 13, fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                )),
              ],
            ),
          ),
        );
      }),
    );
  }

  Widget _buildDimensionInput(RoomPreset preset) {
    final rawArea = _roomLength * _roomWidth;
    final areaUnit = _useCentimeters ? 'cm²' : '㎡';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.straighten, color: _brand, size: 16),
            const SizedBox(width: 6),
            const Text('房间尺寸', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
            const Spacer(),
            Semantics(
              label: '切换厘米/米单位',
              child: GestureDetector(
                onTap: () => setState(() => _useCentimeters = !_useCentimeters),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: _useCentimeters ? _brand.withValues(alpha: 0.15) : _bgDeep,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: _useCentimeters ? _brand : _border),
                  ),
                  child: Text(_useCentimeters ? 'cm' : 'm',
                      style: TextStyle(
                        color: _useCentimeters ? _brand : _textSecondary,
                        fontSize: 11, fontWeight: FontWeight.w600,
                      )),
                ),
              ),
            ),
          ]),
          if (preset.description.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(preset.description, style: const TextStyle(color: _textSecondary, fontSize: 11)),
            ),
          const SizedBox(height: 12),
          Row(
            children: [
              _dimField('长', _roomLength, (v) => setState(() => _roomLength = v)),
              const SizedBox(width: 10),
              _dimField('宽', _roomWidth, (v) => setState(() => _roomWidth = v)),
              const SizedBox(width: 10),
              _dimField('高', _roomHeight, (v) => setState(() => _roomHeight = v)),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Text('面积: ${rawArea.toStringAsFixed(1)} $areaUnit',
                  style: const TextStyle(color: _brand, fontSize: 12, fontWeight: FontWeight.w500)),
              const Spacer(),
              GestureDetector(
                onTap: () => setState(() {
                  if (_floorCount < 3) _floorCount++; else _floorCount = 1;
                }),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: _bgDeep, borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: _border),
                  ),
                  child: Text('$_floorCount 层', style: const TextStyle(color: _textSecondary, fontSize: 11)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _dimField(String label, double value, Function(double) onChanged) {
    final ctrl = label == '长' ? _dimLengthCtrl : label == '宽' ? _dimWidthCtrl : _dimHeightCtrl;
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: _textSecondary, fontSize: 11)),
          const SizedBox(height: 4),
          Semantics(
            label: '${label}尺寸输入',
            child: TextField(
              decoration: InputDecoration(
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                filled: true,
                fillColor: _bgDeep,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: _border),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: _border),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: _brand),
                ),
                suffixText: _useCentimeters ? 'cm' : 'm',
                suffixStyle: const TextStyle(color: _textMuted, fontSize: 11),
              ),
              style: const TextStyle(color: _textPrimary, fontSize: 13),
              keyboardType: TextInputType.number,
              controller: ctrl,
              onChanged: (v) {
                final parsed = double.tryParse(v);
                if (parsed != null) onChanged(parsed);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickFloorplanButton() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration().copyWith(
        border: Border.all(color: _brand.withValues(alpha: 0.2), style: BorderStyle.solid),
      ),
      child: Column(
        children: [
          Row(children: [
            const Icon(Icons.add_chart, color: _brand, size: 18),
            const SizedBox(width: 8),
            const Text('还没有户型？', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w500, fontSize: 14)),
          ]),
          const SizedBox(height: 4),
          const Text('创建户型后可关联扫描结果到户型图',
              style: TextStyle(color: _textSecondary, fontSize: 11)),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: SizedBox(
                  height: 36,
                  child: TextField(
                    decoration: InputDecoration(
                      hintText: '输入户型名称...',
                      hintStyle: const TextStyle(color: _textMuted, fontSize: 12),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 10),
                      filled: true, fillColor: _bgDeep,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: _border)),
                      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: _border)),
                    ),
                    style: const TextStyle(color: _textPrimary, fontSize: 12),
                    onSubmitted: (v) => _createQuickFloorplan(v),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              GestureDetector(
                onTap: () => _createQuickFloorplan('${_roomPresets[_selectedRoomIndex].name}户型'),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
                  decoration: BoxDecoration(
                    color: _brand.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Text('快速创建', style: TextStyle(color: _brand, fontSize: 12, fontWeight: FontWeight.w500)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════
  // Step 2: 扫描引导
  // ═══════════════════════════════════════════════

  Widget _buildScanGuideStep() {
    final preset = _roomPresets[_selectedRoomIndex];
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          _sectionHeader('扫描引导', Icons.live_help),
          const SizedBox(height: 12),

          // 首次引导卡片
          if (_showCoachingCard) ...[
            _buildCoachingCard(),
            const SizedBox(height: 12),
          ],

          // 扫描前检查清单
          _buildPreScanChecklist(),
          const SizedBox(height: 12),

          // 环境条件警告
          if (_envCondition != _EnvCondition.normal) ...[
            _buildEnvConditionWarning(),
            const SizedBox(height: 12),
          ],

          // 预览区域（含 reticle 追踪指示器）
          _buildScanPreview(preset),
          const SizedBox(height: 12),

          // 追踪质量指示器
          _buildTrackingQualityIndicator(),
          const SizedBox(height: 16),

          // 扫描摘要
          _buildScanSummary(preset),
          const SizedBox(height: 16),

          // 引导步骤
          _buildGuideSteps(preset),
          const SizedBox(height: 20),

          // 精度声明
          _buildAccuracyDisclaimer(),
          const SizedBox(height: 12),

          // 操作按钮
          if (_scanState == _ScanState.scanning || _scanState == _ScanState.uploading || _scanState == _ScanState.processing)
            _buildScanningIndicator()
          else if (_scanState == _ScanState.failed)
            _buildFailedState()
          else
            _buildStartScanButton(preset),
        ],
      ),
    );
  }

  // ── 最佳实践：首次引导卡片 ──
  Widget _buildCoachingCard() {
    return Semantics(
      label: 'AR扫描操作提示，可关闭',
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [_brand.withValues(alpha: 0.15), _bgCard],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: _brand.withValues(alpha: 0.25)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: _brand.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: const Icon(Icons.lightbulb_outline, color: _brand, size: 16),
              ),
              const SizedBox(width: 8),
              const Text('首次使用？', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
              const Spacer(),
              GestureDetector(
                onTap: () => setState(() => _showCoachingCard = false),
                child: Container(
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(
                    color: _bgDeep.withValues(alpha: 0.5),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Icon(Icons.close, size: 14, color: _textSecondary),
                ),
              ),
            ]),
            const SizedBox(height: 10),
            const _CoachingTip(icon: Icons.light_mode, text: '在光线充足的房间扫描，避免逆光或暗角'),
            const _CoachingTip(icon: Icons.crop_free, text: '缓慢平稳移动手机，对准墙壁和地面保持视线'),
            const _CoachingTip(icon: Icons.straighten, text: '扫描完成后用钢尺复核关键尺寸，提升精度至毫米级'),
            const _CoachingTip(icon: Icons.phone_android, text: '保持手机与地面约 1-1.5m 高度，画圈式扫过房间各个角落'),
          ],
        ),
      ),
    );
  }

  // ── 最佳实践：扫描前检查清单 ──
  Widget _buildPreScanChecklist() {
    // 如果追踪质量正常，返回紧凑样式
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: _trackingQuality == _TrackingQuality.normal ? _success.withValues(alpha: 0.08) : _bgCard,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: _trackingQuality == _TrackingQuality.normal ? _success.withValues(alpha: 0.2) : _border),
      ),
      child: Row(
        children: [
          Icon(
            _trackingQuality == _TrackingQuality.normal ? Icons.check_circle : Icons.playlist_add_check,
            size: 16,
            color: _trackingQuality == _TrackingQuality.normal ? _success : _textSecondary,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              _trackingQuality == _TrackingQuality.normal
                  ? '扫描就绪 · 光线 · 稳定 · 清除'
                  : '扫描前确认: 光线充足 · 手机稳定 · 地面无杂物',
              style: TextStyle(
                color: _trackingQuality == _TrackingQuality.normal ? _success : _textSecondary,
                fontSize: 11,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── 最佳实践：精度声明 ──
  Widget _buildAccuracyDisclaimer() {
    return Semantics(
      label: '精度声明: AR测量存在约${_estimatedAccuracyCm.toStringAsFixed(1)}厘米误差',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: _warning.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: _warning.withValues(alpha: 0.15)),
        ),
        child: Row(
          children: [
            const Icon(Icons.info_outline, size: 14, color: _warning),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                'AR 测量存在约 ±${_estimatedAccuracyCm.toStringAsFixed(1)}cm 误差，关键尺寸请用实体尺复核。使用 LiDAR 设备精度更高。',
                style: const TextStyle(color: _textSecondary, fontSize: 10, height: 1.3),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEnvConditionWarning() {
    IconData icon;
    String message;
    Color color;
    switch (_envCondition) {
      case _EnvCondition.lowLight:
        icon = Icons.light_mode;
        message = '环境光线不足，建议开启灯光或靠近窗户以提高扫描精度';
        color = _warning;
      case _EnvCondition.lowTexture:
        icon = Icons.texture;
        message = '墙面或地面纹理不足，建议添加临时标记物（如彩色胶带）辅助定位';
        color = _warning;
      case _EnvCondition.fastMotion:
        icon = Icons.speed;
        message = '移动速度过快，请缓慢平稳地移动设备以避免追踪丢失';
        color = _danger;
      case _EnvCondition.normal:
        icon = Icons.check;
        message = '';
        color = _success;
    }
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 8),
        Expanded(
          child: Text(message, style: TextStyle(color: color, fontSize: 12)),
        ),
      ]),
    );
  }

  /// AR 追踪质量指示器（Apple HIG: reticle 三态 + coaching）
  Widget _buildTrackingQualityIndicator() {
    String label;
    IconData icon;
    Color color;
    switch (_trackingQuality) {
      case _TrackingQuality.searching:
        label = _trackingHint.isNotEmpty ? _trackingHint : '正在检测平面，请缓慢移动设备...';
        icon = Icons.search;
        color = _textSecondary;
      case _TrackingQuality.limited:
        label = _trackingHint.isNotEmpty ? _trackingHint : '追踪受限，请对准纹理丰富的区域';
        icon = Icons.warning_amber;
        color = _warning;
      case _TrackingQuality.normal:
        label = '追踪正常，可以开始扫描';
        icon = Icons.check_circle;
        color = _success;
      case _TrackingQuality.lost:
        label = _trackingHint.isNotEmpty ? _trackingHint : '追踪丢失！请回到起始位置重新扫描';
        icon = Icons.gps_off;
        color = _danger;
    }
    return Semantics(
      label: 'AR追踪状态: $label',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: _bgCard,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withValues(alpha: 0.3)),
        ),
        child: Row(children: [
          if (_trackingQuality == _TrackingQuality.searching)
            SizedBox(
              width: 18, height: 18,
              child: CircularProgressIndicator(strokeWidth: 2, color: color, valueColor: AlwaysStoppedAnimation(color)),
            )
          else
            Icon(icon, size: 18, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(label, style: TextStyle(color: color, fontSize: 12)),
          ),
        ]),
      ),
    );
  }

  Widget _buildScanPreview(RoomPreset preset) {
    return AnimatedBuilder(
      animation: _pulseCtrl,
      builder: (_, __) {
        final pulse = 0.5 + 0.5 * math.sin(_pulseCtrl.value * math.pi * 2);
        // reticle 状态颜色
        final reticleColor = switch (_trackingQuality) {
          _TrackingQuality.normal => _success,
          _TrackingQuality.limited => _warning,
          _TrackingQuality.lost => _danger,
          _ => _brand,
        };
        return Container(
          height: 200,
          decoration: BoxDecoration(
            color: _bgCard,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: _trackingQuality == _TrackingQuality.normal ? _success.withValues(alpha: 0.4) : _border),
          ),
          child: Stack(
            alignment: Alignment.center,
            children: [
              // 网格背景
              CustomPaint(
                size: const Size(double.infinity, 200),
                painter: _GridPainter(opacity: 0.05 + 0.03 * pulse),
              ),
              // reticle 追踪十字准线
              CustomPaint(
                size: const Size(80, 80),
                painter: _ReticlePainter(
                  color: reticleColor,
                  pulse: pulse,
                  quality: _trackingQuality,
                ),
              ),
              // 房间轮廓
              Container(
                width: 120, height: 80,
                decoration: BoxDecoration(
                  border: Border.all(color: _brand.withValues(alpha: 0.4 + 0.2 * pulse), width: 2),
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              // 扫描动画圈
              if (_trackingQuality == _TrackingQuality.normal)
                ...List.generate(3, (i) {
                  final radius = 30.0 + i * 20.0 + _radarCtrl.value * 15;
                  final alpha = (1 - _radarCtrl.value) * 0.3 * (1 - i * 0.2);
                  return Positioned(
                    child: IgnorePointer(
                      child: Container(
                        width: radius * 2,
                        height: radius * 2,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: _brand.withValues(alpha: alpha.clamp(0.0, 1.0)),
                            width: 1.5,
                          ),
                        ),
                      ),
                    ),
                  );
                }),
              // 房间信息
              Positioned(
                bottom: 12,
                child: Column(
                  children: [
                    Text(preset.name, style: const TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
                    Text('${(_roomLength * _roomWidth).toStringAsFixed(1)} ㎡',
                        style: const TextStyle(color: _brand, fontSize: 12)),
                  ],
                ),
              ),
              // 方法标签
              Positioned(
                top: 12,
                right: 12,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: _brand.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(_methodIcon(_scanMethod), size: 12, color: _brand),
                      const SizedBox(width: 4),
                      Text(_methodLabel(_scanMethod),
                          style: const TextStyle(color: _brand, fontSize: 10, fontWeight: FontWeight.w500)),
                    ],
                  ),
                ),
              ),
              // 追踪丢失遮罩
              if (_trackingQuality == _TrackingQuality.lost)
                Positioned.fill(
                  child: Container(
                    decoration: BoxDecoration(
                      color: _danger.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildScanSummary(RoomPreset preset) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('扫描摘要', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 10),
          Row(
            children: [
              _summaryChip(Icons.home, '房间', preset.name),
              const SizedBox(width: 8),
              _summaryChip(Icons.auto_fix_high, '方法', _methodLabel(_scanMethod)),
              const SizedBox(width: 8),
              _summaryChip(Icons.speed, '预估', '${_estimatedTimeMin}分钟'),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              _summaryChip(Icons.square_foot, '面积', '${(_roomLength * _roomWidth * _floorCount).toStringAsFixed(1)} ㎡'),
              const SizedBox(width: 8),
              _summaryChip(Icons.grid_view, '尺寸', '${_roomLength.toStringAsFixed(1)}x${_roomWidth.toStringAsFixed(1)}x${_roomHeight.toStringAsFixed(1)}m'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _summaryChip(IconData icon, String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: _bgDeep, borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: _brand),
          const SizedBox(width: 4),
          Text('$label: ', style: const TextStyle(color: _textSecondary, fontSize: 10)),
          Text(value, style: const TextStyle(color: _textPrimary, fontSize: 10, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  Widget _buildGuideSteps(RoomPreset preset) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('操作指引', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 12),
          _guideStep(1, '定位', '站在${preset.name}的角落处'),
          _guideStep(2, '扫描', _scanMethod == 'lidar'
              ? '缓慢移动手机，让 LiDAR 传感器扫描墙壁和物体'
              : _scanMethod == 'visual_slam'
                  ? '缓慢绕房间行走一圈，保持手机稳定'
                  : '对房间各个角落进行拍照'),
          _guideStep(3, '校准', '尽量用钢尺测量一个对角线距离，在后续校准步骤中输入'),
          _guideStep(4, '完成', '扫描完成后上传数据，系统将自动生成测量报告和精度评估'),
        ],
      ),
    );
  }

  Widget _guideStep(int num, String title, String desc) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 24, height: 24,
            decoration: BoxDecoration(
              color: _brand.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(
              child: Text('$num', style: const TextStyle(color: _brand, fontWeight: FontWeight.bold, fontSize: 12)),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(color: _textPrimary, fontWeight: FontWeight.w500, fontSize: 13)),
                const SizedBox(height: 2),
                Text(desc, style: const TextStyle(color: _textSecondary, fontSize: 11, height: 1.3)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStartScanButton(RoomPreset preset) {
    return SizedBox(
      width: double.infinity,
      height: 56,
      child: ElevatedButton.icon(
        onPressed: _startScan,
        style: ElevatedButton.styleFrom(
          backgroundColor: _brand,
          foregroundColor: Colors.black,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          elevation: 0,
        ),
        icon: const Icon(Icons.view_in_ar, size: 24),
        label: Text('开始扫描 ${preset.name}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
      ),
    );
  }

  Widget _buildScanningIndicator() {
    return Column(
      children: [
        AnimatedBuilder(
          animation: _radarCtrl,
          builder: (_, __) {
            final alpha = 0.3 + 0.3 * math.sin(_radarCtrl.value * math.pi * 2);
            return Container(
              width: 120, height: 120,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _brand.withValues(alpha: alpha),
              ),
              child: const Center(
                child: Icon(Icons.view_in_ar, color: Colors.white, size: 48),
              ),
            );
          },
        ),
        const SizedBox(height: 16),
        Text(
          _scanState == _ScanState.scanning ? '扫描中... 请沿房间行走'
              : _scanState == _ScanState.uploading ? '上传数据中...'
              : '处理中... 解析测量数据',
          style: const TextStyle(color: _textPrimary, fontSize: 14),
        ),
        if (_scanWallsDetected > 0 || _scanPointsDetected > 0) ...[
          const SizedBox(height: 8),
          Text(
            '墙面: $_scanWallsDetected 面 · 特征点: $_scanPointsDetected',
            style: const TextStyle(color: _textSecondary, fontSize: 11),
          ),
        ],
        const SizedBox(height: 12),
        SizedBox(
          width: 200, height: 4,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: LinearProgressIndicator(
              value: _scanProgress > 0 ? _scanProgress.clamp(0.0, 1.0) : null,
              color: _brand,
              backgroundColor: _border,
            ),
          ),
        ),
        if (_scanProgress > 0) ...[
          const SizedBox(height: 4),
          Text('${(_scanProgress * 100).toStringAsFixed(0)}%',
              style: const TextStyle(color: _textSecondary, fontSize: 11)),
        ],
        const SizedBox(height: 20),
        // 取消按钮
        Semantics(
          label: '取消扫描',
          child: SizedBox(
            width: 120, height: 40,
            child: OutlinedButton.icon(
              onPressed: _cancelScan,
              style: OutlinedButton.styleFrom(
                foregroundColor: _danger,
                side: const BorderSide(color: _danger),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              icon: const Icon(Icons.stop, size: 16),
              label: const Text('取消扫描', style: TextStyle(fontSize: 13)),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildFailedState() {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: _danger.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: _danger.withValues(alpha: 0.3)),
          ),
          child: Column(
            children: [
              const Icon(Icons.error_outline, color: _danger, size: 32),
              const SizedBox(height: 8),
              Text(_errorMessage.isNotEmpty ? _errorMessage : '扫描失败',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: _danger, fontSize: 13)),
            ],
          ),
        ),
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: () {
              setState(() { _errorMessage = ''; _scanState = _ScanState.ready; });
              _startScan();
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: _brand,
              foregroundColor: Colors.black,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            ),
            icon: const Icon(Icons.refresh, size: 20),
            label: const Text('重试扫描'),
          ),
        ),
      ],
    );
  }

  // ═══════════════════════════════════════════════
  // Step 3.5: 人工复核（扫描完成 → 复核 → 结果）
  // ═══════════════════════════════════════════════

  Widget _buildReviewStep() {
    final preset = _roomPresets[_selectedRoomIndex];
    final area = _totalArea > 0 ? _totalArea : _roomLength * _roomWidth * _floorCount;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 复核指南
          _buildReviewGuidanceCard(),
          const SizedBox(height: 16),

          // 检测结果清单
          _sectionHeader('检测结果复核', Icons.fact_check),
          const SizedBox(height: 4),
          Text('请逐项确认 AR 扫描检测结果，必要时用实体尺校准',
              style: const TextStyle(color: _textSecondary, fontSize: 11)),
          const SizedBox(height: 12),

          // 房间基本信息
          _buildReviewSection('房间信息', Icons.home, [
            _ReviewItem(
              id: 'room_type',
              label: '房间类型',
              value: preset.name,
              confidence: 'high',
            ),
            _ReviewItem(
              id: 'room_area',
              label: '测量面积',
              value: '${area.toStringAsFixed(1)} ㎡',
              confidence: _accuracyLevel,
            ),
            _ReviewItem(
              id: 'room_dimensions',
              label: '长×宽×高',
              value: '${_roomLength.toStringAsFixed(1)}×${_roomWidth.toStringAsFixed(1)}×${_roomHeight.toStringAsFixed(1)}m',
              confidence: 'medium',
              hint: '建议用钢尺复核对角线',
            ),
          ]),
          const SizedBox(height: 12),

          // 墙面特征
          if (_wallFeatures > 0)
            _buildReviewSection('墙面特征', Icons.wallpaper, [
              _ReviewItem(
                id: 'walls',
                label: '检测到墙面特征',
                value: '$_wallFeatures 处',
                confidence: 'medium',
              ),
              if (_roomCount > 1)
                _ReviewItem(
                  id: 'rooms',
                  label: '检测到房间',
                  value: '$_roomCount 间',
                  confidence: 'high',
                ),
            ]),
          const SizedBox(height: 12),

          // 精度信息
          _buildReviewSection('精度评估', Icons.speed, [
            _ReviewItem(
              id: 'accuracy',
              label: '精度等级',
              value: _accuracyLabel(_accuracyLevel),
              confidence: _accuracyLevel,
            ),
            if (_rmsErrorCm != null)
              _ReviewItem(
                id: 'rms',
                label: '均方根误差 (RMS)',
                value: '${_rmsErrorCm!.toStringAsFixed(2)} cm',
                confidence: _rmsErrorCm! < 2.0 ? 'high' : 'medium',
              ),
          ]),
          const SizedBox(height: 16),

          // 内联校准入口
          _buildInlineCalibration(),
          const SizedBox(height: 20),

          // 复核备注
          _buildReviewNotesField(),
          const SizedBox(height: 20),

          // 确认按钮组
          Row(
            children: [
              Expanded(
                child: _outlineButton('重新扫描', Icons.refresh, () {
                  setState(() {
                    _scanState = _ScanState.ready;
                    _sessionId = null;
                    _errorMessage = '';
                    _calibrationPoints.clear();
                  });
                  _goToStep(_ScanStep.roomSetup);
                }),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: ElevatedButton.icon(
                  onPressed: () => _goToStep(_ScanStep.results),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _brand,
                    foregroundColor: Colors.black,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  icon: const Icon(Icons.check_circle, size: 20),
                  label: const Text('确认并查看结果', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildReviewGuidanceCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [_brand.withValues(alpha: 0.12), _bgCard],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: _brand.withValues(alpha: 0.25)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: _brand.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.tips_and_updates, color: _brand, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('人工复核指南',
                    style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
                const SizedBox(height: 4),
                Text(
                  'AR 测量存在 ±${_estimatedAccuracyCm.toStringAsFixed(1)}cm 误差。\n关键尺寸请用钢尺/激光测距仪复核，校准后精度可提升至毫米级。',
                  style: const TextStyle(color: _textSecondary, fontSize: 11, height: 1.4),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildReviewSection(String title, IconData icon, List<_ReviewItem> items) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, color: _brand, size: 14),
            const SizedBox(width: 6),
            Text(title, style: const TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 13)),
          ]),
          const SizedBox(height: 8),
          ...items.map((item) {
            final confirmed = _reviewConfirmedItems.contains(item.id);
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Semantics(
                    label: confirmed ? '${item.label}已确认' : '确认${item.label}',
                    child: GestureDetector(
                      onTap: () => setState(() {
                        if (confirmed) {
                          _reviewConfirmedItems.remove(item.id);
                        } else {
                          _reviewConfirmedItems.add(item.id);
                        }
                      }),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        width: 28, height: 28,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: confirmed ? _success.withValues(alpha: 0.15) : _bgDeep,
                          border: Border.all(color: confirmed ? _success : _border, width: confirmed ? 2 : 1),
                        ),
                        child: Icon(
                          confirmed ? Icons.check : null,
                          size: 14,
                          color: _success,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(item.label,
                            style: const TextStyle(color: _textPrimary, fontSize: 12, fontWeight: FontWeight.w500)),
                        Text(item.value,
                            style: const TextStyle(color: _textSecondary, fontSize: 11)),
                      ],
                    ),
                  ),
                  // 置信度标记
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                    decoration: BoxDecoration(
                      color: item.confidenceColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(width: 4, height: 4,
                          decoration: BoxDecoration(shape: BoxShape.circle, color: item.confidenceColor)),
                        const SizedBox(width: 4),
                        Text(item.confidenceLabel,
                            style: TextStyle(color: item.confidenceColor, fontSize: 10, fontWeight: FontWeight.w600)),
                      ],
                    ),
                  ),
                  if (item.hint != null) ...[
                    const SizedBox(width: 6),
                    Semantics(
                      label: item.hint!,
                      child: Tooltip(
                        message: item.hint!,
                        child: const Icon(Icons.info_outline, size: 14, color: _textMuted),
                      ),
                    ),
                  ],
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  /// 内联校准入口（不依赖滚动到页面底部）
  Widget _buildInlineCalibration() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration().copyWith(
        border: Border.all(color: _brand.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.tune, color: _brand, size: 16),
            const SizedBox(width: 6),
            const Expanded(
              child: Text('精度校准 (推荐)',
                  style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
            ),
            if (_calibrationPoints.isNotEmpty)
              Text('${_calibrationPoints.length} 个校准点',
                  style: const TextStyle(color: _brand, fontSize: 11)),
          ]),
          const SizedBox(height: 4),
          const Text('用钢尺测量一条对角线距离，输入实际值和 AR 测量值以提升精度',
              style: TextStyle(color: _textSecondary, fontSize: 11)),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(flex: 3, child: _tinyField(_labelCtrl, '标识 (如: 主卧对角线)')),
            const SizedBox(width: 8),
            Expanded(child: _tinyField(_arValueCtrl, 'AR值(m)', number: true)),
            const SizedBox(width: 8),
            Expanded(child: _tinyField(_refValueCtrl, '钢尺(m)', number: true)),
          ]),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: _addCalibrationPoint,
              icon: const Icon(Icons.add, size: 16),
              label: const Text('添加校准点'),
              style: TextButton.styleFrom(foregroundColor: _brand),
            ),
          ),
          if (_calibrationPoints.isNotEmpty) ...[
            const Divider(color: _border, height: 16),
            ..._calibrationPoints.map((p) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(children: [
                Expanded(flex: 2, child: Text('${p['label']}', style: const TextStyle(color: _textPrimary, fontSize: 12))),
                Expanded(child: Text('AR:${p['ar_value']}m', style: const TextStyle(color: _textSecondary, fontSize: 11))),
                Expanded(child: Text('尺:${p['reference_value']}m', style: const TextStyle(color: _textSecondary, fontSize: 11))),
                Text('${(p['deviation'] as num).toStringAsFixed(3)}m',
                    style: TextStyle(
                      color: (p['deviation'] as num).abs() < 0.03 ? _success : _danger,
                      fontSize: 11, fontWeight: FontWeight.bold,
                    )),
              ]),
            )),
          ],
        ],
      ),
    );
  }

  Widget _buildReviewNotesField() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('复核备注 (可选)', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 8),
          TextField(
            controller: _reviewNoteCtrl,
            maxLines: 2,
            decoration: InputDecoration(
              hintText: '记录复核中的发现，如 "客厅长边用钢尺核实，误差+2cm"',
              hintStyle: const TextStyle(color: _textMuted, fontSize: 12),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              filled: true, fillColor: _bgDeep,
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: _border)),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: _border)),
              focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: _brand)),
            ),
            style: const TextStyle(color: _textPrimary, fontSize: 13),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════
  // Step 4: 扫描结果
  // ═══════════════════════════════════════════════

  Widget _buildResultsStep() {
    if (_scanState != _ScanState.completed) {
      return const Center(
        child: Text('扫描尚未完成', style: TextStyle(color: _textSecondary)),
      );
    }

    final area = _totalArea > 0 ? _totalArea : _roomLength * _roomWidth * _floorCount;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 完成动画
          Center(
            child: AnimatedBuilder(
              animation: _pulseCtrl,
              builder: (_, __) {
                final scale = 1.0 + 0.05 * math.sin(_pulseCtrl.value * math.pi * 2);
                return Transform.scale(
                  scale: scale,
                  child: Container(
                    width: 100, height: 100,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        colors: [_brand, _brand.withValues(alpha: 0.3)],
                        begin: Alignment.topLeft, end: Alignment.bottomRight,
                      ),
                    ),
                    child: const Icon(Icons.check, color: Colors.white, size: 48),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16),
          const Center(
            child: Text('扫描完成', style: TextStyle(color: _textPrimary, fontSize: 20, fontWeight: FontWeight.bold)),
          ),
          const SizedBox(height: 4),
          Center(
            child: Text(_sessionName, style: const TextStyle(color: _textSecondary, fontSize: 13)),
          ),
          const SizedBox(height: 20),

          // 指标卡片
          Row(
            children: [
              _resultMetricCard('房间数', '$_roomCount', Icons.home, _brand),
              const SizedBox(width: 10),
              _resultMetricCard('总面积', '${area.toStringAsFixed(1)} ㎡', Icons.square_foot, _brand),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              _resultMetricCard('墙面特征', '$_wallFeatures', Icons.window, _brand),
              const SizedBox(width: 10),
              Expanded(
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: _cardDecoration().copyWith(
                    border: Border.all(color: _accuracyColor(_accuracyLevel)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('精度等级', style: TextStyle(color: _textSecondary, fontSize: 11)),
                      const SizedBox(height: 4),
                      Text(
                        _accuracyLabel(_accuracyLevel),
                        style: TextStyle(color: _accuracyColor(_accuracyLevel), fontWeight: FontWeight.bold, fontSize: 16),
                      ),
                      if (_rmsErrorCm != null)
                        Text('RMS: ${_rmsErrorCm!.toStringAsFixed(2)} cm',
                            style: const TextStyle(color: _textSecondary, fontSize: 10)),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // 校准
          _buildCalibrationSection(),
          const SizedBox(height: 16),

          // 操作
          _buildResultActions(),
        ],
      ),
    );
  }

  Widget _resultMetricCard(String label, String value, IconData icon, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: _cardDecoration(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(height: 8),
            Text(value, style: const TextStyle(color: _textPrimary, fontWeight: FontWeight.bold, fontSize: 18)),
            const SizedBox(height: 2),
            Text(label, style: const TextStyle(color: _textSecondary, fontSize: 11)),
          ],
        ),
      ),
    );
  }

  Widget _buildCalibrationSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(children: [
            Icon(Icons.tune, color: _brand, size: 16),
            SizedBox(width: 6),
            Text('精度校准', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
          ]),
          const SizedBox(height: 4),
          const Text('用钢尺测量对角线距离，对比 AR 值提高精度',
              style: TextStyle(color: _textSecondary, fontSize: 11)),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(flex: 3, child: _tinyField(_labelCtrl, '标识 (如: 主卧对角线)')),
            const SizedBox(width: 8),
            Expanded(child: _tinyField(_arValueCtrl, 'AR值(m)', number: true)),
            const SizedBox(width: 8),
            Expanded(child: _tinyField(_refValueCtrl, '钢尺(m)', number: true)),
          ]),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: _addCalibrationPoint,
              icon: const Icon(Icons.add, size: 16),
              label: const Text('添加校准点'),
              style: TextButton.styleFrom(foregroundColor: _brand),
            ),
          ),
          if (_calibrationPoints.isNotEmpty) ...[
            const Divider(color: _border, height: 16),
            ..._calibrationPoints.map((p) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(children: [
                Expanded(flex: 2, child: Text('${p['label']}', style: const TextStyle(color: _textPrimary, fontSize: 12))),
                Expanded(child: Text('AR:${p['ar_value']}m', style: const TextStyle(color: _textSecondary, fontSize: 11))),
                Expanded(child: Text('尺:${p['reference_value']}m', style: const TextStyle(color: _textSecondary, fontSize: 11))),
                Text('${(p['deviation'] as num).toStringAsFixed(3)}m',
                    style: TextStyle(
                      color: (p['deviation'] as num).abs() < 0.03 ? _success : _danger,
                      fontSize: 11, fontWeight: FontWeight.bold,
                    )),
              ]),
            )),
          ],
        ],
      ),
    );
  }

  Widget _tinyField(TextEditingController ctrl, String hint, {bool number = false}) {
    return TextField(
      controller: ctrl,
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: _textMuted, fontSize: 11),
        contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        filled: true, fillColor: _bgDeep,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: const BorderSide(color: _border)),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: const BorderSide(color: _border)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: const BorderSide(color: _brand)),
      ),
      style: const TextStyle(color: _textPrimary, fontSize: 12),
      keyboardType: number ? TextInputType.number : TextInputType.text,
    );
  }

  Widget _buildResultActions() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('后续操作', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 12),
          _actionButton('应用于测量记录', Icons.check_circle_outline, _brand, _applyToSurvey),
          const SizedBox(height: 8),
          _actionButton('标记门窗位置', Icons.door_sliding, _textPrimary, () => _goToStep(_ScanStep.doorWindow)),
          const SizedBox(height: 8),
          _actionButton('水电点位规划', Icons.electrical_services, _textPrimary, () => _goToStep(_ScanStep.mep)),
          const SizedBox(height: 8),
          _actionButton('查看墙面特征', Icons.window, _textPrimary, () {
            _showSnack('墙面特征已自动识别，可在测量详情中查看');
          }),
          const SizedBox(height: 8),
          _actionButton('导出测量报告 (PDF/CSV)', Icons.file_download, _textPrimary, () {
            _showSnack('导出功能开发中，敬请期待');
          }),
          const SizedBox(height: 8),
          _outlineButton('重新扫描', Icons.refresh, () {
            setState(() {
              _scanState = _ScanState.ready;
              _sessionId = null;
              _errorMessage = '';
              _calibrationPoints.clear();
            });
            _goToStep(_ScanStep.roomSetup);
          }),
        ],
      ),
    );
  }

  Widget _actionButton(String label, IconData icon, Color color, VoidCallback onTap) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: color.withValues(alpha: 0.1),
          foregroundColor: color,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          padding: const EdgeInsets.symmetric(vertical: 12),
        ),
        icon: Icon(icon, size: 18),
        label: Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
      ),
    );
  }

  // ── 通用 UI 组件 ──

  Widget _sectionHeader(String title, IconData icon) {
    return Row(children: [
      Icon(icon, color: _brand, size: 20),
      const SizedBox(width: 8),
      Text(title, style: const TextStyle(color: _textPrimary, fontSize: 18, fontWeight: FontWeight.bold)),
    ]);
  }

  Widget _buildNextStepButton(String label, VoidCallback onTap) {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: ElevatedButton.icon(
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: _brand,
          foregroundColor: Colors.black,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          elevation: 0,
        ),
        icon: const Icon(Icons.arrow_forward, size: 20),
        label: Text(label, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
      ),
    );
  }

  Widget _outlineButton(String label, IconData icon, VoidCallback onTap, {bool isLoading = false}) {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: OutlinedButton.icon(
        onPressed: isLoading ? null : onTap,
        style: OutlinedButton.styleFrom(
          foregroundColor: _textPrimary,
          side: const BorderSide(color: _border),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
        icon: isLoading ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: _border)) : Icon(icon, size: 18),
        label: Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
      ),
    );
  }

  BoxDecoration _cardDecoration() => BoxDecoration(
    color: _bgCard,
    borderRadius: BorderRadius.circular(14),
    border: Border.all(color: _border),
  );

  // ═══════════════════════════════════════════════
  // Step 4: 门窗定位
  // ═══════════════════════════════════════════════

  Widget _buildDoorWindowStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionHeader('门窗定位', Icons.door_sliding),
          const SizedBox(height: 4),
          const Text('标记房间的门、窗位置和尺寸',
              style: TextStyle(color: _textSecondary, fontSize: 11)),
          const SizedBox(height: 16),

          // 已标记的门窗列表
          if (_loadingDoorWindows)
            const Center(child: CircularProgressIndicator(color: _brand))
          else if (_doorWindows.isNotEmpty)
            _buildDwList()
          else
            _buildDwEmptyState(),

          const SizedBox(height: 16),

          // 新增门窗表单
          _buildDwForm(),
          const SizedBox(height: 20),

          Row(
            children: [
              Expanded(
                child: _outlineButton('返回结果', Icons.arrow_back, () => _goToStep(_ScanStep.results)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildNextStepButton('水电定位', () => _goToStep(_ScanStep.mep)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _loadDoorWindows() async {
    if (!mounted) return;
    setState(() => _loadingDoorWindows = true);
    try {
      final result = await _api.doorWinListSpecs(widget.projectId);
      if (result.isSuccess && mounted) {
        setState(() {
          _doorWindows = (result.data as List?)
              ?.map((e) => Map<String, dynamic>.from(e as Map))
              .toList() ?? [];
        });
      }
    } catch (_) {}
    if (mounted) setState(() => _loadingDoorWindows = false);
  }

  Widget _buildDwList() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('已标记门窗', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 13)),
          const SizedBox(height: 8),
          ..._doorWindows.map((dw) {
            final type = dw['type'] ?? dw['door_window_type'] ?? 'door';
            final width = dw['width']?.toString() ?? '?';
            final height = dw['height']?.toString() ?? '?';
            final pos = dw['position'] ?? dw['location'] ?? '未指定';
            final icon = type.toString().contains('window') ? Icons.window : Icons.door_sliding;
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(children: [
                Icon(icon, size: 18, color: _brand),
                const SizedBox(width: 8),
                Expanded(
                  child: Text('${type == "window" ? "窗" : "门"} ${width}x${height}cm · $pos',
                      style: const TextStyle(color: _textPrimary, fontSize: 12)),
                ),
                GestureDetector(
                  onTap: () async {
                    final id = dw['id'] as String?;
                    if (id != null) {
                      await _api.doorWinDeleteSpec(id);
                      _showSnack('已删除');
                      _loadDoorWindows();
                    }
                  },
                  child: const Icon(Icons.delete_outline, size: 16, color: _danger),
                ),
              ]),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildDwEmptyState() {
    return Container(
      padding: const EdgeInsets.all(32),
      decoration: _cardDecoration(),
      child: Column(
        children: [
          Icon(Icons.door_sliding, size: 40, color: _textMuted.withValues(alpha: 0.5)),
          const SizedBox(height: 12),
          const Text('暂无门窗标记', style: TextStyle(color: _textSecondary, fontSize: 14, fontWeight: FontWeight.w500)),
          const SizedBox(height: 4),
          const Text('在下方添加门窗位置和尺寸，用于装修和物料估算',
              textAlign: TextAlign.center,
              style: TextStyle(color: _textMuted, fontSize: 12)),
        ],
      ),
    );
  }

  Widget _buildDwForm() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('新增门窗', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 13)),
          const SizedBox(height: 10),
          // 类型选择
          Row(children: [
            Expanded(
              child: GestureDetector(
                onTap: () => setState(() => _dwSelectedType = 'window'),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: BoxDecoration(
                    color: _dwSelectedType == 'window' ? _brand.withValues(alpha: 0.15) : _bgDeep,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: _dwSelectedType == 'window' ? _brand : _border),
                  ),
                  child: const Column(children: [
                    Icon(Icons.window, color: _brand, size: 20),
                    SizedBox(height: 2),
                    Text('窗户', style: TextStyle(color: _textPrimary, fontSize: 11)),
                  ]),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: GestureDetector(
                onTap: () => setState(() => _dwSelectedType = 'door'),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: BoxDecoration(
                    color: _dwSelectedType == 'door' ? _brand.withValues(alpha: 0.15) : _bgDeep,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: _dwSelectedType == 'door' ? _brand : _border),
                  ),
                  child: const Column(children: [
                    Icon(Icons.door_sliding, color: _brand, size: 20),
                    SizedBox(height: 2),
                    Text('门', style: TextStyle(color: _textPrimary, fontSize: 11)),
                  ]),
                ),
              ),
            ),
          ]),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(child: _dwField(_dwWidthCtrl, '宽 (cm)', true)),
            const SizedBox(width: 8),
            Expanded(child: _dwField(_dwHeightCtrl, '高 (cm)', true)),
          ]),
          const SizedBox(height: 8),
          _dwField(_dwPosCtrl, '位置描述 (如: 南墙、靠窗)', false),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _addDoorWindow,
              style: ElevatedButton.styleFrom(
                backgroundColor: _brand.withValues(alpha: 0.15),
                foregroundColor: _brand,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              icon: const Icon(Icons.add, size: 16),
              label: const Text('添加门窗', style: TextStyle(fontSize: 12)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _dwField(TextEditingController ctrl, String hint, bool number) {
    return TextField(
      controller: ctrl,
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: _textMuted, fontSize: 11),
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        filled: true, fillColor: _bgDeep,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: const BorderSide(color: _border)),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: const BorderSide(color: _border)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: const BorderSide(color: _brand)),
      ),
      style: const TextStyle(color: _textPrimary, fontSize: 12),
      keyboardType: number ? TextInputType.number : TextInputType.text,
    );
  }

  Future<void> _addDoorWindow() async {
    final type = _dwSelectedType;
    final width = _dwWidthCtrl.text.trim();
    final height = _dwHeightCtrl.text.trim();
    final pos = _dwPosCtrl.text.trim();
    if (type != 'door' && type != 'window') {
      _showSnack('请先选择类型（门或窗）');
      return;
    }
    if (width.isEmpty || height.isEmpty) {
      _showSnack('请填写宽和高');
      return;
    }
    final result = await _api.doorWinCreateSpec({
      'project_id': widget.projectId,
      'type': type,
      'width': int.tryParse(width) ?? 0,
      'height': int.tryParse(height) ?? 0,
      'position': pos,
      'room': _roomPresets[_selectedRoomIndex].name,
    });
    if (result.isSuccess && mounted) {
      _dwTypeCtrl.clear(); // 保留用于兼容其他可能的后端字段
      _dwWidthCtrl.clear();
      _dwHeightCtrl.clear();
      _dwPosCtrl.clear();
      _dwSelectedType = 'door';
      _showSnack('门窗已添加');
      _loadDoorWindows();
    } else if (mounted) {
      _showSnack('添加失败: ${result.error}');
    }
  }

  // ═══════════════════════════════════════════════
  // Step 5: 水电定位 MEP
  // ═══════════════════════════════════════════════

  Widget _buildMepStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionHeader('水电定位', Icons.electrical_services),
          const SizedBox(height: 4),
          const Text('标记插座、开关、给排水点位等水电设施',
              style: TextStyle(color: _textSecondary, fontSize: 11)),
          const SizedBox(height: 16),

          // MEP 计划操作
          if (_mepPlanId == null)
            _buildMepCreatePlan()
          else ...[
            _buildMepPointList(),
            const SizedBox(height: 16),
            _buildMepAddForm(),
          ],

          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: _outlineButton(isLoading: _loadingMep,
                    '返回门窗', Icons.arrow_back, () => _goToStep(_ScanStep.doorWindow)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _outlineButton(isLoading: _loadingMep,
                    '完成', Icons.check, () {
                  _showSnack('水电点位已保存');
                }),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMepCreatePlan() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        children: [
          const Icon(Icons.electrical_services, color: _brand, size: 40),
          const SizedBox(height: 12),
          const Text('尚未创建水电点位计划',
              style: TextStyle(color: _textPrimary, fontSize: 15, fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          const Text('根据房间类型自动生成标准水电点位，或手动逐个添加',
              textAlign: TextAlign.center,
              style: TextStyle(color: _textSecondary, fontSize: 12)),
          const SizedBox(height: 16),
          Row(children: [
            Expanded(
              child: _actionButton('自动生成', Icons.auto_fix_high, _brand, _autoGenerateMep),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: _actionButton('手动添加', Icons.add_circle_outline, _textPrimary, _createMepPlan),
            ),
          ]),
        ],
      ),
    );
  }

  Widget _buildMepPointList() {
    if (_loadingMep) return const Center(child: CircularProgressIndicator(color: _brand));
    if (_mepPoints.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(24),
        decoration: _cardDecoration(),
        child: const Center(
          child: Text('暂无水电点位，点击下方添加', style: TextStyle(color: _textSecondary)),
        ),
      );
    }

    // 按类型分组
    final groups = <String, List<Map<String, dynamic>>>{};
    for (final p in _mepPoints) {
      final t = (p['point_type'] ?? p['type'] ?? '其他').toString();
      groups.putIfAbsent(t, () => []);
      groups[t]!.add(p);
    }

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Text('已添加点位', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 13)),
            const Spacer(),
            Text('${_mepPoints.length} 个', style: const TextStyle(color: _brand, fontSize: 12)),
          ]),
          const SizedBox(height: 8),
          ...groups.entries.map((e) {
            final icon = _mepIcon(e.key);
            return Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(children: [
                Icon(icon, size: 16, color: _brand),
                const SizedBox(width: 6),
                Text('${_mepLabel(e.key)} x${e.value.length}',
                    style: const TextStyle(color: _textPrimary, fontSize: 12)),
              ]),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildMepAddForm() {
    final presetTypes = {
      'socket': '插座',
      'switch': '开关',
      'water_supply': '给水',
      'drain': '排水',
      'light': '灯具',
      'network': '弱电',
      'gas': '燃气',
      'hvac': '暖通',
    };
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('添加点位', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 13)),
          const SizedBox(height: 10),
          // 类型选择
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: presetTypes.entries.map((e) => GestureDetector(
              onTap: () => _mepTypeCtrl.text = e.key,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: _mepTypeCtrl.text == e.key ? _brand.withValues(alpha: 0.15) : _bgDeep,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: _mepTypeCtrl.text == e.key ? _brand : _border),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(_mepIcon(e.key), size: 12, color: _mepTypeCtrl.text == e.key ? _brand : _textSecondary),
                  const SizedBox(width: 4),
                  Text(e.value, style: TextStyle(
                    color: _mepTypeCtrl.text == e.key ? _brand : _textSecondary, fontSize: 11,
                  )),
                ]),
              ),
            )).toList(),
          ),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(child: _dwField(_mepLabelCtrl, '位置/标签 (如: 床头左侧)', false)),
            const SizedBox(width: 8),
            SizedBox(
              width: 80,
              child: ElevatedButton(
                onPressed: _addMepPoint,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _brand,
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                ),
                child: const Text('添加', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
              ),
            ),
          ]),
        ],
      ),
    );
  }

  Future<void> _createMepPlan() async {
    setState(() => _loadingMep = true);
    final result = await _api.mepCreatePlan({
      'project_id': widget.projectId,
      'name': '${_roomPresets[_selectedRoomIndex].name} 水电点位',
      'room_type': _roomPresets[_selectedRoomIndex].name,
    });
    if (result.isSuccess && mounted) {
      final data = result.data as Map<String, dynamic>? ?? {};
      setState(() => _mepPlanId = data['id'] as String?);
    } else if (mounted) {
      _showSnack('创建失败: ${result.error}');
    }
    if (mounted) setState(() => _loadingMep = false);
  }

  Future<void> _autoGenerateMep() async {
    await _createMepPlan();
    if (_mepPlanId == null) return;
    setState(() => _loadingMep = true);
    final result = await _api.mepAutoGenerate(_mepPlanId!);
    if (result.isSuccess && mounted) {
      _showSnack('已根据房间类型自动生成水电点位');
      _loadMepPoints();
    } else if (mounted) {
      _showSnack('自动生成失败: ${result.error}');
    }
    if (mounted) setState(() => _loadingMep = false);
  }

  Future<void> _loadMepPoints() async {
    if (_mepPlanId == null) return;
    setState(() => _loadingMep = true);
    final result = await _api.mepListPoints(_mepPlanId!);
    if (result.isSuccess && mounted) {
      setState(() {
        _mepPoints = (result.data as List?)
            ?.map((e) => Map<String, dynamic>.from(e as Map))
            .toList() ?? [];
      });
    }
    if (mounted) setState(() => _loadingMep = false);
  }

  Future<void> _addMepPoint() async {
    if (_mepPlanId == null) {
      _showSnack('请先创建水电点位计划');
      return;
    }
    final type = _mepTypeCtrl.text.trim();
    final label = _mepLabelCtrl.text.trim();
    if (type.isEmpty) { _showSnack('请选择点位类型'); return; }
    if (label.isEmpty) { _showSnack('请填写位置/标签'); return; }

    final result = await _api.mepAddPoint(_mepPlanId!, {
      'point_type': type,
      'label': label,
      'room': _roomPresets[_selectedRoomIndex].name,
      'project_id': widget.projectId,
    });
    if (result.isSuccess && mounted) {
      _mepTypeCtrl.clear();
      _mepLabelCtrl.clear();
      _showSnack('点位已添加');
      _loadMepPoints();
    } else if (mounted) {
      _showSnack('添加失败: ${result.error}');
    }
  }

  IconData _mepIcon(String type) => switch (type) {
    'socket' => Icons.power, 'switch' => Icons.toggle_on,
    'water_supply' => Icons.water_drop, 'drain' => Icons.water,
    'light' => Icons.lightbulb, 'network' => Icons.wifi,
    'gas' => Icons.local_fire_department, 'hvac' => Icons.air,
    _ => Icons.electrical_services,
  };

  String _mepLabel(String type) => switch (type) {
    'socket' => '插座', 'switch' => '开关',
    'water_supply' => '给水', 'drain' => '排水',
    'light' => '灯具', 'network' => '弱电',
    'gas' => '燃气', 'hvac' => '暖通',
    _ => type,
  };
}

// ═══════════════════════════════════════════════
// 复核项数据模型
// ═══════════════════════════════════════════════

class _ReviewItem {
  final String id;
  final String label;
  final String value;
  final String confidence; // 'high', 'medium', 'low'
  final String? hint;

  const _ReviewItem({
    required this.id,
    required this.label,
    required this.value,
    required this.confidence,
    this.hint,
  });

  Color get confidenceColor => switch (confidence) {
    'high' => _success,
    'medium' => _warning,
    'low' => _danger,
    _ => _textSecondary,
  };

  String get confidenceLabel => switch (confidence) {
    'high' => '高置信',
    'medium' => '中置信',
    'low' => '低置信',
    _ => confidence.toUpperCase(),
  };
}

// ═══════════════════════════════════════════════
// 首次引导提示组件
// ═══════════════════════════════════════════════

class _CoachingTip extends StatelessWidget {
  final IconData icon;
  final String text;
  const _CoachingTip({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 14, color: _brand),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text,
                style: const TextStyle(color: _textSecondary, fontSize: 12, height: 1.3)),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════
// 自定义 Painter: 网格背景
// ═══════════════════════════════════════════════

class _GridPainter extends CustomPainter {
  final double opacity;
  _GridPainter({this.opacity = 0.05});

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
  bool shouldRepaint(covariant _GridPainter old) => old.opacity != opacity;
}

// ═══════════════════════════════════════════════
// 自定义 Painter: AR 追踪十字准线 (reticle)
// ═══════════════════════════════════════════════

class _ReticlePainter extends CustomPainter {
  final Color color;
  final double pulse;
  final _TrackingQuality quality;

  _ReticlePainter({
    required this.color,
    required this.pulse,
    required this.quality,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final armLength = 20.0 + pulse * 4;
    final gap = 8.0;
    final armThickness = 2.0;

    final paint = Paint()
      ..color = color.withValues(alpha: 0.6 + 0.2 * pulse)
      ..strokeWidth = armThickness
      ..strokeCap = StrokeCap.round;

    // 四角 L 形准线
    // 左上
    canvas.drawLine(
      Offset(center.dx - armLength, center.dy - gap),
      Offset(center.dx - gap, center.dy - gap),
      paint,
    );
    canvas.drawLine(
      Offset(center.dx - gap, center.dy - armLength),
      Offset(center.dx - gap, center.dy - gap),
      paint,
    );
    // 右上
    canvas.drawLine(
      Offset(center.dx + gap, center.dy - gap),
      Offset(center.dx + armLength, center.dy - gap),
      paint,
    );
    canvas.drawLine(
      Offset(center.dx + gap, center.dy - armLength),
      Offset(center.dx + gap, center.dy - gap),
      paint,
    );
    // 左下
    canvas.drawLine(
      Offset(center.dx - armLength, center.dy + gap),
      Offset(center.dx - gap, center.dy + gap),
      paint,
    );
    canvas.drawLine(
      Offset(center.dx - gap, center.dy + gap),
      Offset(center.dx - gap, center.dy + armLength),
      paint,
    );
    // 右下
    canvas.drawLine(
      Offset(center.dx + gap, center.dy + gap),
      Offset(center.dx + armLength, center.dy + gap),
      paint,
    );
    canvas.drawLine(
      Offset(center.dx + gap, center.dy + gap),
      Offset(center.dx + gap, center.dy + armLength),
      paint,
    );

    // 若追踪正常，画一个从中心渐隐的小圆
    if (quality == _TrackingQuality.normal) {
      final circlePaint = Paint()
        ..color = color.withValues(alpha: 0.15 * pulse)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5;
      canvas.drawCircle(center, 12 + 2 * pulse, circlePaint);
    }
  }

  @override
  bool shouldRepaint(covariant _ReticlePainter old) =>
      old.color != color || old.pulse != pulse || old.quality != quality;
}
