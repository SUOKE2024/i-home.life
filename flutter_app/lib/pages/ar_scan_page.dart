/// F1 AR 空间测量页面 — Flutter 客户端
///
/// 功能:
/// 1. 设备能力检测 → 推荐扫描方法 (LiDAR/VisualSLAM/Photogrammetry/Manual)
/// 2. 扫描会话生命周期 (created → scanning → uploaded → processing → completed)
/// 3. 模型上传 (USDZ/GLB) + 点云数据上传
/// 4. 精度校验 (RMS 误差 + 校准点录入)
/// 5. 墙面特征管理 (门/窗/洞口/梁/柱)
/// 6. 应用到测量记录 (Survey)
///
/// 集成说明:
/// - iOS: 通过 MethodChannel 调用 ARKit/RoomPlan Swift API
/// - Android: 通过 MethodChannel 调用 ARCore Kotlin API
/// - HarmonyOS: 通过 MethodChannel 调用 AR Engine ArkTS API
/// - 不支持 AR 的设备: 自动降级到手动测量模式

import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/api.dart';
import '../config.dart';

// ── AR 平台通道 ──
// 实际 AR 能力通过原生代码实现,Flutter 通过 MethodChannel 调用
// iOS: ARKit + RoomPlan (Swift)
// Android: ARCore (Kotlin)
// HarmonyOS: AR Engine (ArkTS)
const _arChannel = MethodChannel('com.ihome.life/ar_scan');

class ARScanPage extends StatefulWidget {
  final String projectId;
  const ARScanPage({super.key, required this.projectId});

  @override
  State<ARScanPage> createState() => _ARScanPageState();
}

enum _ScanState { idle, detecting, ready, scanning, uploading, processing, completed, failed }
enum _Platform { ios, android, harmonyos, web, unknown }

class _ARScanPageState extends State<ARScanPage> {
  final _api = ApiClient();
  _ScanState _state = _ScanState.idle;

  // 设备能力
  _Platform _platform = _Platform.unknown;
  String _deviceModel = '';
  bool _hasLidar = false;
  bool _supportsRoomplan = false;
  String _arkitVersion = '';
  String _arcoreVersion = '';
  String _arEngineVersion = '';
  // 传感器能力
  bool _hasGyroscope = false;
  bool _hasAccelerometer = false;
  bool _hasMagnetometer = false;

  // 推荐方法
  String _recommendedMethod = 'manual';
  List<String> _availableMethods = ['manual'];
  List<String> _fallbackChain = ['manual'];
  double _estimatedAccuracyCm = 5.0;
  int _estimatedScanTimeMin = 10;

  // 扫描会话
  String? _sessionId;
  String _sessionName = 'AR 扫描';
  double _wallHeight = 2.8;
  int _floorCount = 1;

  // 扫描结果
  int _roomCount = 0;
  double _totalArea = 0.0;
  String _accuracyLevel = '';
  double? _rmsErrorCm;
  int _wallFeaturesAdded = 0;

  // 校准点
  final List<Map<String, dynamic>> _calibrationPoints = [];
  final _labelCtrl = TextEditingController();
  final _arValueCtrl = TextEditingController();
  final _refValueCtrl = TextEditingController();

  String _errorMessage = '';

  @override
  void initState() {
    super.initState();
    _detectPlatform();
  }

  @override
  void dispose() {
    _labelCtrl.dispose();
    _arValueCtrl.dispose();
    _refValueCtrl.dispose();
    super.dispose();
  }

  Future<void> _detectPlatform() async {
    setState(() => _state = _ScanState.detecting);

    _Platform platform;
    bool hasLidar = false;
    bool supportsRoomplan = false;
    String arkitVersion = '';
    String arcoreVersion = '';
    String arEngineVersion = '';
    String deviceModel = '';

    // 优先通过 MethodChannel 询问原生平台 (Flutter-OH 在鸿蒙会返回 'harmonyos')
    // 标准 Flutter 在 iOS/Android 上调用未注册的 channel 方法会抛 MissingPluginException
    String platformName = '';
    try {
      platformName = await _arChannel.invokeMethod<String>('getPlatform') ?? '';
    } on PlatformException {
      platformName = '';
    } on MissingPluginException {
      platformName = '';
    }

    if (platformName == 'harmonyos' || platformName == 'ohos') {
      platform = _Platform.harmonyos;
      // 通过 MethodChannel 询问 AR Engine 能力
      try {
        final result = await _arChannel.invokeMethod<Map>('detectCapability');
        arEngineVersion = result?['ar_engine_version'] as String? ?? '';
        deviceModel = result?['device_model'] as String? ?? 'HarmonyOS Device';
        // HarmonyOS AR Engine 6.0+ 支持视觉 SLAM
        hasLidar = result?['has_lidar'] as bool? ?? false;
      } on PlatformException {
        arEngineVersion = '6.0';
        deviceModel = 'HarmonyOS Device';
      }
    } else if (Platform.isIOS) {
      platform = _Platform.ios;
      // 通过 MethodChannel 询问原生 ARKit 能力
      try {
        final result = await _arChannel.invokeMethod<Map>('detectCapability');
        arkitVersion = result?['arkit_version'] as String? ?? '';
        hasLidar = result?['has_lidar'] as bool? ?? false;
        supportsRoomplan = result?['supports_roomplan'] as bool? ?? false;
        deviceModel = result?['device_model'] as String? ?? 'iOS Device';
      } on PlatformException {
        // 原生插件未集成时使用默认值
        arkitVersion = '6.0';
        deviceModel = 'iOS Device';
      }
    } else if (Platform.isAndroid) {
      platform = _Platform.android;
      try {
        final result = await _arChannel.invokeMethod<Map>('detectCapability');
        arcoreVersion = result?['arcore_version'] as String? ?? '';
        deviceModel = result?['device_model'] as String? ?? 'Android Device';
      } on PlatformException {
        arcoreVersion = '1.30';
        deviceModel = 'Android Device';
      }
    } else {
      platform = _Platform.unknown;
      deviceModel = 'Unknown';
    }

    setState(() {
      _platform = platform;
      _deviceModel = deviceModel;
      _hasLidar = hasLidar;
      _supportsRoomplan = supportsRoomplan;
      _arkitVersion = arkitVersion;
      _arcoreVersion = arcoreVersion;
      _arEngineVersion = arEngineVersion;
    });

    // 调用后端获取推荐方法
    await _queryDeviceCapability();
  }

  Future<void> _queryDeviceCapability() async {
    final result = await _api.post('/surveys/ar/device-capability', {
      'platform': _platform.name,
      'device_model': _deviceModel,
      'has_lidar': _hasLidar,
      'has_depth_sensor': _hasLidar,
      'has_gyroscope': _hasGyroscope,
      'has_accelerometer': _hasAccelerometer,
      'has_magnetometer': _hasMagnetometer,
      'supports_roomplan': _supportsRoomplan,
      'arkit_version': _arkitVersion,
      'arcore_version': _arcoreVersion,
      'ar_engine_version': _arEngineVersion,
      'supports_photogrammetry': true,
    });
    if (result.isSuccess) {
      final data = result.data as Map<String, dynamic>? ?? {};
      setState(() {
        _recommendedMethod = data['recommended_method'] as String? ?? 'manual';
        _availableMethods = List<String>.from(data['available_methods'] ?? ['manual']);
        _fallbackChain = List<String>.from(data['fallback_chain'] ?? ['manual']);
        _estimatedAccuracyCm = (data['estimated_accuracy_cm'] as num?)?.toDouble() ?? 5.0;
        _estimatedScanTimeMin = data['estimated_scan_time_per_room_min'] as int? ?? 10;
        _state = _ScanState.ready;
      });
    } else {
      setState(() {
        _errorMessage = '设备能力检测失败: ${result.error}';
        _state = _ScanState.ready;
        _recommendedMethod = 'manual';
        _availableMethods = ['manual'];
        _fallbackChain = ['manual'];
      });
    }
  }

  Future<void> _createSession() async {
    setState(() => _errorMessage = '');
    final result = await _api.post('/surveys/ar/sessions', {
      'project_id': widget.projectId,
      'name': _sessionName,
      'platform': _platform.name,
      'requested_method': _recommendedMethod,
      'device_capability': {
        'platform': _platform.name,
        'device_model': _deviceModel,
        'has_lidar': _hasLidar,
        'has_depth_sensor': _hasLidar,
        'has_gyroscope': _hasGyroscope,
        'has_accelerometer': _hasAccelerometer,
        'has_magnetometer': _hasMagnetometer,
        'supports_roomplan': _supportsRoomplan,
        'arkit_version': _arkitVersion,
        'arcore_version': _arcoreVersion,
        'ar_engine_version': _arEngineVersion,
      },
      'floor_count': _floorCount,
      'wall_height': _wallHeight,
    });
    if (result.isSuccess) {
      final session = result.data as Map<String, dynamic>;
      setState(() => _sessionId = session['id']);
      await _startScan();
    } else {
      setState(() => _errorMessage = '创建扫描会话失败: ${result.error}');
    }
  }

  Future<void> _startScan() async {
    if (_sessionId == null) return;
    final startResult = await _api.post('/surveys/ar/sessions/$_sessionId/start', {});
    if (!startResult.isSuccess) {
      setState(() => _errorMessage = '启动扫描失败: ${startResult.error}');
      return;
    }
    setState(() => _state = _ScanState.scanning);

    // 调用原生 AR 扫描
    try {
      final scanResult = await _arChannel.invokeMethod<Map>('startScan', {
        'session_id': _sessionId,
        'method': _recommendedMethod,
      });
      final modelPath = scanResult?['model_path'] as String?;
      final modelFormat = scanResult?['model_format'] as String? ?? 'usdz';
      final pointsCount = scanResult?['points_count'] as int? ?? 0;
      final durationSec = scanResult?['duration_sec'] as int? ?? 0;
      await _uploadAndProcess(modelPath, modelFormat, pointsCount, durationSec);
    } on PlatformException catch (e) {
      // 原生 AR 不可用,使用 mock 数据测试
      if (AppConfig.debugMode) {
        await _uploadAndProcess(null, 'usdz', 50000, 180);
      } else {
        setState(() {
          _errorMessage = 'AR 扫描失败: ${e.message}\n建议切换到手动测量模式';
          _state = _ScanState.failed;
        });
      }
    }
  }

  Future<void> _uploadAndProcess(
    String? modelPath, String modelFormat, int pointsCount, int durationSec,
  ) async {
    setState(() => _state = _ScanState.uploading);

    String? modelUrl;
    if (modelPath != null) {
      final uploadResult = await _api.uploadFile(
        '/files/upload',
        filePath: modelPath,
        projectId: widget.projectId,
      );
      if (uploadResult.isSuccess) {
        modelUrl = uploadResult.data?['url'] as String?;
      } else {
        // 上传失败仍可处理 (使用 mock 数据)
        debugPrint('模型上传失败: ${uploadResult.error}');
      }
    }

    setState(() => _state = _ScanState.processing);
    final result = await _api.post('/surveys/ar/sessions/$_sessionId/process', {
      'model_url': modelUrl,
      'model_format': modelFormat,
      'scan_points_count': pointsCount,
      'scan_duration_sec': durationSec,
    });
    if (result.isSuccess) {
      final data = result.data as Map<String, dynamic>? ?? {};
      setState(() {
        _state = _ScanState.completed;
        _roomCount = data['room_count'] as int? ?? 0;
        _totalArea = (data['total_area'] as num?)?.toDouble() ?? 0.0;
        _wallFeaturesAdded = data['wall_features_added'] as int? ?? 0;
        final accuracy = data['accuracy_report'] as Map<String, dynamic>?;
        if (accuracy != null) {
          _accuracyLevel = accuracy['accuracy_level'] as String? ?? '';
          _rmsErrorCm = (accuracy['rms_error_cm'] as num?)?.toDouble();
        }
      });
    } else {
      setState(() {
        _errorMessage = '处理扫描数据失败: ${result.error}';
        _state = _ScanState.failed;
      });
    }
  }

  Future<void> _addCalibrationPoint() async {
    if (_sessionId == null) return;
    final label = _labelCtrl.text.trim();
    final arValue = double.tryParse(_arValueCtrl.text);
    final refValue = double.tryParse(_refValueCtrl.text);
    if (label.isEmpty || arValue == null || refValue == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请填写完整的校准点信息')),
      );
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
          'label': label,
          'ar_value': arValue,
          'reference_value': refValue,
          'deviation': point['deviation'],
          'deviation_percent': point['deviation_percent'],
        });
        _rmsErrorCm = (point['rms_error_cm'] as num?)?.toDouble() ?? _rmsErrorCm;
      });
      _labelCtrl.clear();
      _arValueCtrl.clear();
      _refValueCtrl.clear();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('添加校准点失败: ${result.error}')),
      );
    }
  }

  Future<void> _applyToSurvey() async {
    if (_sessionId == null) return;
    final result = await _api.post('/surveys/ar/sessions/$_sessionId/apply', {});
    if (result.isSuccess) {
      final data = result.data as Map<String, dynamic>? ?? {};
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已应用到测量记录: ${data['rooms_added']} 个房间')),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('应用失败: ${result.error}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AR 空间测量'),
        backgroundColor: const Color(0xFF12121D),
        foregroundColor: Colors.white,
      ),
      body: Container(
        color: const Color(0xFF0E0E1A),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _buildDeviceCapabilityCard(),
            const SizedBox(height: 16),
            _buildScanControlCard(),
            const SizedBox(height: 16),
            if (_state == _ScanState.completed) ...[
              _buildResultCard(),
              const SizedBox(height: 16),
              _buildCalibrationCard(),
              const SizedBox(height: 16),
              _buildActionsCard(),
            ],
            if (_errorMessage.isNotEmpty)
              Container(
                margin: const EdgeInsets.only(top: 16),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.red.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.red.withValues(alpha: 0.3)),
                ),
                child: Text(_errorMessage, style: const TextStyle(color: Colors.redAccent)),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildDeviceCapabilityCard() {
    final methodLabels = {
      'lidar': 'LiDAR 激光雷达',
      'visual_slam': '视觉 SLAM',
      'photogrammetry': '照片建模',
      'manual': '手动测量',
    };
    // 平台友好显示
    String platformDisplay;
    switch (_platform) {
      case _Platform.ios:
        platformDisplay = 'iOS';
        break;
      case _Platform.android:
        platformDisplay = 'Android';
        break;
      case _Platform.harmonyos:
        platformDisplay = 'HarmonyOS';
        break;
      case _Platform.web:
        platformDisplay = 'Web';
        break;
      case _Platform.unknown:
        platformDisplay = 'Unknown';
        break;
    }
    return Card(
      color: const Color(0xFF1A1A2E),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.phone_android, color: Color(0xFFC9973B), size: 20),
                const SizedBox(width: 8),
                const Text('设备能力', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                const Spacer(),
                if (_state == _ScanState.detecting)
                  const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFFC9973B))),
              ],
            ),
            const SizedBox(height: 12),
            _infoRow('平台', platformDisplay),
            _infoRow('设备', _deviceModel),
            _infoRow('LiDAR', _hasLidar ? '✓ 支持' : '✗ 不支持'),
            if (_supportsRoomplan) _infoRow('RoomPlan', '✓ 支持 (iOS 16+)'),
            if (_arkitVersion.isNotEmpty) _infoRow('ARKit', _arkitVersion),
            if (_arcoreVersion.isNotEmpty) _infoRow('ARCore', _arcoreVersion),
            if (_arEngineVersion.isNotEmpty) _infoRow('AR Engine', _arEngineVersion),
            const Divider(color: Color(0xFF2A2A3E), height: 24),
            _infoRow('推荐方法', methodLabels[_recommendedMethod] ?? _recommendedMethod),
            _infoRow('预计精度', '±${_estimatedAccuracyCm.toStringAsFixed(1)} cm'),
            _infoRow('预计耗时', '$_estimatedScanTimeMin 分钟/房间'),
            _infoRow('降级链', _fallbackChain.map((m) => methodLabels[m] ?? m).join(' → ')),
          ],
        ),
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 96,
            child: Text(label, style: const TextStyle(color: Color(0xFF8A8894), fontSize: 13)),
          ),
          Expanded(child: Text(value, style: const TextStyle(color: Colors.white, fontSize: 13))),
        ],
      ),
    );
  }

  Widget _buildScanControlCard() {
    return Card(
      color: const Color(0xFF1A1A2E),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('扫描配置', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 12),
            TextField(
              decoration: const InputDecoration(labelText: '会话名称', labelStyle: TextStyle(color: Color(0xFF8A8894))),
              style: const TextStyle(color: Colors.white),
              onChanged: (v) => _sessionName = v,
              controller: TextEditingController(text: _sessionName),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    decoration: const InputDecoration(labelText: '层高 (m)', labelStyle: TextStyle(color: Color(0xFF8A8894))),
                    style: const TextStyle(color: Colors.white),
                    keyboardType: TextInputType.number,
                    onChanged: (v) => _wallHeight = double.tryParse(v) ?? 2.8,
                    controller: TextEditingController(text: _wallHeight.toString()),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    decoration: const InputDecoration(labelText: '楼层数', labelStyle: TextStyle(color: Color(0xFF8A8894))),
                    style: const TextStyle(color: Colors.white),
                    keyboardType: TextInputType.number,
                    onChanged: (v) => _floorCount = int.tryParse(v) ?? 1,
                    controller: TextEditingController(text: _floorCount.toString()),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _state == _ScanState.scanning || _state == _ScanState.processing || _state == _ScanState.uploading
                    ? null
                    : _createSession,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFC9973B),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                icon: _state == _ScanState.scanning || _state == _ScanState.processing || _state == _ScanState.uploading
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.camera_alt),
                label: Text(_stateLabel()),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _stateLabel() {
    switch (_state) {
      case _ScanState.idle:
      case _ScanState.detecting:
        return '开始 AR 扫描';
      case _ScanState.ready:
        return '开始 AR 扫描';
      case _ScanState.scanning:
        return '扫描中... 请沿房间行走';
      case _ScanState.uploading:
        return '上传数据中...';
      case _ScanState.processing:
        return '处理中... 解析 USDZ 模型';
      case _ScanState.completed:
        return '重新扫描';
      case _ScanState.failed:
        return '重试扫描';
    }
  }

  Widget _buildResultCard() {
    final levelColor = {
      'high': const Color(0xFF4CAF50),
      'medium': const Color(0xFFFFA726),
      'low': const Color(0xFFEF5350),
    };
    return Card(
      color: const Color(0xFF1A1A2E),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('扫描结果', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 12),
            Row(
              children: [
                _metricCard('房间数', '$_roomCount', Icons.home),
                const SizedBox(width: 12),
                _metricCard('总面积', '${_totalArea.toStringAsFixed(1)} ㎡', Icons.square_foot),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                _metricCard('墙面特征', '$_wallFeaturesAdded', Icons.window),
                const SizedBox(width: 12),
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0E0E1A),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: levelColor[_accuracyLevel] ?? const Color(0xFF8A8894),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('精度等级', style: TextStyle(color: Color(0xFF8A8894), fontSize: 12)),
                        const SizedBox(height: 4),
                        Text(
                          _accuracyLevel.isEmpty ? '-' : _accuracyLevel.toUpperCase(),
                          style: TextStyle(
                            color: levelColor[_accuracyLevel] ?? const Color(0xFF8A8894),
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                        if (_rmsErrorCm != null)
                          Text(
                            'RMS: ${_rmsErrorCm!.toStringAsFixed(2)} cm',
                            style: const TextStyle(color: Color(0xFF8A8894), fontSize: 11),
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _metricCard(String label, String value, IconData icon) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFF0E0E1A),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: const Color(0xFFC9973B), size: 16),
                const SizedBox(width: 4),
                Text(label, style: const TextStyle(color: Color(0xFF8A8894), fontSize: 12)),
              ],
            ),
            const SizedBox(height: 4),
            Text(value, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
          ],
        ),
      ),
    );
  }

  Widget _buildCalibrationCard() {
    return Card(
      color: const Color(0xFF1A1A2E),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('精度校准 (推荐)', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 4),
            const Text(
              '在每个房间对角线方向用钢尺测量一个距离,与 AR 测量值对比,用于校验扫描精度。',
              style: TextStyle(color: Color(0xFF8A8894), fontSize: 12),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(flex: 2, child: _textField(_labelCtrl, '标识 (如:主卧对角线)')),
                const SizedBox(width: 8),
                Expanded(flex: 1, child: _textField(_arValueCtrl, 'AR 值 (m)', isNumber: true)),
                const SizedBox(width: 8),
                Expanded(flex: 1, child: _textField(_refValueCtrl, '钢尺值 (m)', isNumber: true)),
              ],
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: _addCalibrationPoint,
                icon: const Icon(Icons.add, size: 18),
                label: const Text('添加校准点'),
                style: TextButton.styleFrom(foregroundColor: const Color(0xFFC9973B)),
              ),
            ),
            if (_calibrationPoints.isNotEmpty) ...[
              const Divider(color: Color(0xFF2A2A3E), height: 16),
              ...(_calibrationPoints.map((p) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        Expanded(flex: 2, child: Text(p['label'], style: const TextStyle(color: Colors.white, fontSize: 13))),
                        Expanded(
                          child: Text('AR: ${p['ar_value']}m', style: const TextStyle(color: Color(0xFF8A8894), fontSize: 12)),
                        ),
                        Expanded(
                          child: Text('尺: ${p['reference_value']}m', style: const TextStyle(color: Color(0xFF8A8894), fontSize: 12)),
                        ),
                        Text(
                          '${(p['deviation'] as num).toStringAsFixed(3)}m',
                          style: TextStyle(
                            color: (p['deviation'] as num).abs() < 0.03 ? const Color(0xFF4CAF50) : const Color(0xFFEF5350),
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ))),
            ],
          ],
        ),
      ),
    );
  }

  Widget _textField(TextEditingController ctrl, String label, {bool isNumber = false}) {
    return TextField(
      controller: ctrl,
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Color(0xFF8A8894), fontSize: 12),
        enabledBorder: const UnderlineInputBorder(borderSide: BorderSide(color: Color(0xFF2A2A3E))),
        focusedBorder: const UnderlineInputBorder(borderSide: BorderSide(color: Color(0xFFC9973B))),
      ),
      style: const TextStyle(color: Colors.white, fontSize: 13),
      keyboardType: isNumber ? TextInputType.number : TextInputType.text,
    );
  }

  Widget _buildActionsCard() {
    return Card(
      color: const Color(0xFF1A1A2E),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('后续操作', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _applyToSurvey,
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFFC9973B),
                  side: const BorderSide(color: Color(0xFFC9973B)),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                icon: const Icon(Icons.check_circle_outline),
                label: const Text('应用到测量记录'),
              ),
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () {
                  // 跳转到墙面特征列表页
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('墙面特征已通过 AI 自动识别,可在测量详情查看')),
                  );
                },
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Color(0xFF2A2A3E)),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                icon: const Icon(Icons.window),
                label: const Text('查看墙面特征'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
