import 'dart:async';

import 'package:flutter/material.dart';

import '../services/api.dart';
import '../services/wearable_ble_service.dart';

/// 穿戴设备（BLE 手表/手环）接入页面（2026-08-27）
///
/// 功能：
/// - BLE 能力探测（鸿蒙/无 BLE 平台诚实降级）
/// - 扫描 → 连接 → 订阅心率/电量
/// - 实时心率展示 + 一键上报健康监测（health-monitor/records）
/// - 支持平台：Android/iOS；鸿蒙降级提示
class WearableDevicesPage extends StatefulWidget {
  final String projectId;
  final String schemeId;

  const WearableDevicesPage({
    super.key,
    required this.projectId,
    required this.schemeId,
  });

  @override
  State<WearableDevicesPage> createState() => _WearableDevicesPageState();
}

class _WearableDevicesPageState extends State<WearableDevicesPage> {
  final WearableBleService _ble = WearableBleService();
  final ApiClient _api = ApiClient();

  bool _initialized = false;
  bool _scanning = false;
  bool _connecting = false;
  List<Map<String, Object?>> _devices = [];
  String? _toast;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _init();
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _ble.disconnect();
    super.dispose();
  }

  Future<void> _init() async {
    await _ble.init();
    if (!mounted) return;
    setState(() => _initialized = true);
    // 周期刷新心率显示（BLE 流驱动，仅 UI 刷新）
    _refreshTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  Future<void> _scan() async {
    if (!_ble.isAvailable) return;
    setState(() {
      _scanning = true;
      _devices = [];
    });
    final results = await _ble.scan();
    if (!mounted) return;
    setState(() {
      _devices = results;
      _scanning = false;
    });
  }

  Future<void> _connect(String deviceId) async {
    setState(() => _connecting = true);
    final ok = await _ble.connect(deviceId);
    if (!mounted) return;
    setState(() {
      _connecting = false;
      _toast = ok ? '已连接 ${_ble.deviceName}' : '连接失败，请确认设备可发现';
    });
  }

  Future<void> _reportHeartRate() async {
    final bpm = _ble.heartRate;
    if (bpm == null) {
      setState(() => _toast = '暂无心率读数（请先连接并佩戴设备）');
      return;
    }
    final result = await _api.recordHealthData(
      projectId: widget.projectId,
      schemeId: widget.schemeId,
      monitorType: 'heart_rate',
      value: {'bpm': bpm},
      deviceId: _ble.device?.remoteId.str,
    );
    if (!mounted) return;
    setState(() {
      _toast = result.isSuccess
          ? '心率 $bpm bpm 已上报'
          : '上报失败: ${result.error ?? '未知错误'}';
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('穿戴设备')),
      body: _initialized ? _buildBody() : const Center(child: CircularProgressIndicator()),
    );
  }

  Widget _buildBody() {
    if (!_ble.isAvailable) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.bluetooth_disabled, size: 64, color: Colors.grey),
              SizedBox(height: 12),
              Text('当前平台不支持 BLE 穿戴设备接入\n（支持 Android/iOS）',
                  textAlign: TextAlign.center),
            ],
          ),
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildStatusCard(),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: _scanning ? null : _scan,
                icon: _scanning
                    ? const SizedBox(
                        width: 16, height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.bluetooth_searching),
                label: Text(_scanning ? '扫描中…' : '扫描附近设备'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        if (_devices.isNotEmpty) ...[
          const Text('发现设备', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          ..._devices.map(_buildDeviceTile),
        ] else if (_scanning) ...[
          const Padding(
            padding: EdgeInsets.all(16),
            child: Center(child: Text('扫描中，请保持设备可发现…')),
          ),
        ],
        if (_toast != null)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Text(_toast!, style: const TextStyle(color: Colors.orange)),
          ),
      ],
    );
  }

  Widget _buildStatusCard() {
    final connected = _ble.isConnected;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  connected ? Icons.bluetooth_connected : Icons.bluetooth,
                  color: connected ? Colors.green : Colors.blueGrey,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    connected ? '已连接: ${_ble.deviceName}' : '未连接设备',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _metricCard('心率', '${_ble.heartRate ?? "--"}', 'bpm'),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _metricCard('电量', '${_ble.batteryLevel ?? "--"}', '%'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: connected ? _reportHeartRate : null,
                icon: _connecting
                    ? const SizedBox(
                        width: 16, height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.favorite),
                label: Text(_connecting ? '连接中…' : '上报心率到健康监测'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _metricCard(String label, String value, String unit) {
    return Column(
      children: [
        Text(value,
            style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
        Text('$label ($unit)', style: const TextStyle(color: Colors.grey)),
      ],
    );
  }

  Widget _buildDeviceTile(Map<String, Object?> d) {
    final name = (d['name'] as String?) ?? '未知设备';
    final id = (d['id'] as String?) ?? '';
    final rssi = (d['rssi'] as int?) ?? 0;
    return Card(
      child: ListTile(
        leading: const Icon(Icons.watch),
        title: Text(name),
        subtitle: Text('$id · 信号 $rssi dBm'),
        trailing: _connecting ? const SizedBox(
          width: 20, height: 20,
          child: CircularProgressIndicator(strokeWidth: 2),
        ) : const Icon(Icons.link),
        onTap: () => _connect(id),
      ),
    );
  }
}
