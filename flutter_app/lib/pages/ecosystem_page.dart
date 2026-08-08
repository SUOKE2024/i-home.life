import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';
import '../widgets/empty_state.dart';

/// F46 生态桥接页面（v1.5.0）
class EcosystemPage extends StatefulWidget {
  final String projectId;
  const EcosystemPage({super.key, required this.projectId});

  @override
  State<EcosystemPage> createState() => _EcosystemPageState();
}

class _EcosystemPageState extends State<EcosystemPage> {
  final ApiClient _api = ApiClient();

  List<dynamic> _bridges = [];
  String _honestNote = '';
  String _priorityStrategy = '';
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final statusResult = await _api.ecosystemStatus();
    final bridgesResult = await _api.ecosystemBridges();
    if (!mounted) return;
    if (statusResult.isSuccess && bridgesResult.isSuccess) {
      final statusData =
          statusResult.data is Map ? statusResult.data as Map : <String, dynamic>{};
      final bridgesData = bridgesResult.data is Map
          ? bridgesResult.data as Map
          : <String, dynamic>{};
      setState(() {
        final bridges = statusData['bridges'];
        _bridges = bridges is List ? bridges : [];
        _honestNote = statusData['honest_note']?.toString() ?? '';
        _priorityStrategy =
            bridgesData['priority_strategy']?.toString() ?? '';
        _loading = false;
      });
    } else {
      setState(() {
        _error = (statusResult.error ?? bridgesResult.error) ??
            '加载失败，请检查网络后重试';
        _loading = false;
      });
    }
  }

  String _statusLabel(String? status) {
    switch (status) {
      case 'ready':
        return '已就绪';
      case 'requires_api_key':
        return '待配置';
      default:
        return status ?? '-';
    }
  }

  Color _statusColor(String? status) {
    switch (status) {
      case 'ready':
        return SuokeDesignTokens.success;
      case 'requires_api_key':
        return SuokeDesignTokens.warning;
      default:
        return SuokeDesignTokens.info;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.card(context),
        foregroundColor: SuokeDesignTokens.text(context),
        title: const Text('生态桥接'),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const LoadingSkeleton(itemHeight: 100);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _load);
    }
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        if (_honestNote.isNotEmpty)
          Container(
            width: double.infinity,
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: SuokeDesignTokens.warning.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                  color: SuokeDesignTokens.warning.withValues(alpha: 0.4)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.info_outline,
                    color: SuokeDesignTokens.warning, size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(_honestNote,
                      style: TextStyle(
                          color: SuokeDesignTokens.textSub(context),
                          fontSize: 12)),
                ),
              ],
            ),
          ),
        if (_bridges.isEmpty)
          const EmptyStateWidget(
            icon: Icons.link_off,
            title: '暂无生态接入',
            description: '生态桥接需在服务端配置 API Key，接入后即可联动 HomeKit / HarmonyOS / Matter / Tuya 设备',
          ),
        for (final bridge in _bridges)
          _buildBridgeCard(bridge as Map<String, dynamic>),
        if (_priorityStrategy.isNotEmpty) ...[
          const SizedBox(height: 8),
          Card(
            color: SuokeDesignTokens.card(context),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side:
                  BorderSide(color: SuokeDesignTokens.borderClr(context)),
            ),
            margin: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.priority_high,
                          color: SuokeDesignTokens.accent, size: 20),
                      const SizedBox(width: 8),
                      Text('优先级策略',
                          style: TextStyle(
                              color: SuokeDesignTokens.text(context),
                              fontSize: 15,
                              fontWeight: FontWeight.w600)),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(_priorityStrategy,
                      style: TextStyle(
                          color: SuokeDesignTokens.textSub(context),
                          fontSize: 13)),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildBridgeCard(Map<String, dynamic> bridge) {
    final status = (bridge['status'] ?? '').toString();
    final configured = bridge['configured'] == true;
    final priority = bridge['priority'];
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  configured
                      ? Icons.link
                      : Icons.link_off,
                  color: configured
                      ? SuokeDesignTokens.success
                      : SuokeDesignTokens.warning,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    bridge['name']?.toString() ?? bridge['key'] ?? '-',
                    style: TextStyle(
                        color: SuokeDesignTokens.text(context),
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color:
                        _statusColor(status).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _statusLabel(status),
                    style: TextStyle(
                        color: _statusColor(status), fontSize: 12),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip('KEY', bridge['key']?.toString() ?? '-'),
                _buildInfoChip('优先级', '$priority'),
              ],
            ),
            if (bridge['required_env_keys'] is List &&
                (bridge['required_env_keys'] as List).isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  '依赖配置：${(bridge['required_env_keys'] as List).join(' / ')}',
                  style: TextStyle(
                      color: SuokeDesignTokens.textSub(context),
                      fontSize: 12),
                ),
              ),
            if ((bridge['note']?.toString() ?? '').isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(bridge['note'].toString(),
                    style: TextStyle(
                        color: SuokeDesignTokens.textSub(context),
                        fontSize: 12)),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoChip(String label, String value) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('$label：',
            style: TextStyle(
                color: SuokeDesignTokens.textSub(context), fontSize: 13)),
        Text(value,
            style:
                TextStyle(color: SuokeDesignTokens.text(context), fontSize: 13)),
      ],
    );
  }
}
