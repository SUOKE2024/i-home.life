import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// 质检报告仪表盘页面
/// 对应 Web 端 quality-report.html
class QualityReportPage extends StatefulWidget {
  final String? initialProjectId;
  const QualityReportPage({super.key, this.initialProjectId});

  @override
  State<QualityReportPage> createState() => _QualityReportPageState();
}

class _QualityReportPageState extends State<QualityReportPage> {
  final ApiClient _api = ApiClient();

  List<Map<String, dynamic>> _projects = [];
  String? _selectedProjectId;

  // 质检数据
  List<dynamic> _inspections = [];
  List<dynamic> _qualityIssues = [];
  List<dynamic> _progressAlerts = [];
  bool _loading = true;
  String? _error;

  static const _brand = Color(0xFFC9973B);
  static const _bg = Color(0xFF08080F);
  static const _card = Color(0xFF12121D);
  static const _textPrimary = Color(0xFFE8E6E1);
  static const _textSecondary = Color(0xFF8A8894);
  static const _success = Color(0xFF4CAF50);
  static const _danger = Color(0xFFE57373);
  static const _warning = Color(0xFFFFB74D);
  static const _info = Color(0xFF64B5F6);

  @override
  void initState() {
    super.initState();
    _selectedProjectId = widget.initialProjectId;
    _loadProjects();
  }

  Future<void> _loadProjects() async {
    final result = await _api.getProjects();
    if (result.isSuccess) {
      final list = result.data is List ? result.data as List : (result.data['items'] as List? ?? []);
      setState(() {
        _projects = list.cast<Map<String, dynamic>>();
        _error = null;
      });
      if (_selectedProjectId == null && _projects.isNotEmpty) {
        _selectedProjectId = _projects.first['id']?.toString();
      }
      await _loadData();
    } else {
      setState(() {
        _error = '项目列表加载失败，请检查网络后重试';
        _loading = false;
      });
    }
  }

  Future<void> _loadData() async {
    if (_selectedProjectId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });

    final pid = _selectedProjectId!;
    final results = await Future.wait([
      _api.projectInspections(pid),
      _api.qualityIssues(pid),
      _api.progressAlerts(pid),
    ]);

    if (!mounted) return;

    _inspections = _resultData(results[0]);
    _qualityIssues = _resultData(results[1]);
    _progressAlerts = _resultData(results[2]);

    setState(() => _loading = false);
  }

  List<dynamic> _resultData(dynamic r) {
    // Result<T> from ApiClient has .data property
    if (r is Map && r['data'] != null) {
      final data = r['data'];
      if (data is List) return data;
      if (data is Map && data['items'] != null) return data['items'] as List;
    }
    if (r is List) return r;
    return [];
  }

  // ── 统计计算 ──

  int get _totalInspections => _inspections.length;
  int get _passedInspections => _inspections.where((i) => i['status'] == 'passed' || i['result'] == 'pass').length;
  int get _failedInspections => _inspections.where((i) => i['status'] == 'failed' || i['result'] == 'fail').length;
  int get _pendingInspections => _inspections.where((i) => i['status'] == 'pending' || i['result'] == null).length;
  double get _passRate => _totalInspections > 0 ? _passedInspections / _totalInspections : 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _card,
        title: const Text('质检报告', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: _textSecondary),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: _textSecondary),
            onPressed: _loadData,
          ),
        ],
      ),
      body: _loading
          ? const LoadingSkeleton(itemCount: 6)
          : _error != null
              ? ErrorRetryWidget(message: _error!, onRetry: _loadData)
              : _buildContent(),
    );
  }

  Widget _buildContent() {
    return Column(
      children: [
        _buildProjectSelector(),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
            children: [
              _buildSummaryCards(),
              const SizedBox(height: 16),
              _buildPassRateGauge(),
              const SizedBox(height: 16),
              _buildInspectionList(),
              if (_qualityIssues.isNotEmpty) ...[
                const SizedBox(height: 16),
                _buildQualityIssues(),
              ],
              if (_progressAlerts.isNotEmpty) ...[
                const SizedBox(height: 16),
                _buildAlertsList(),
              ],
            ],
          ),
        ),
      ],
    );
  }

  // ── 项目选择器 ──

  Widget _buildProjectSelector() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: _card,
      child: Row(
        children: [
          const Icon(Icons.verified, color: _brand, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: _selectedProjectId,
                isExpanded: true,
                dropdownColor: _card,
                style: const TextStyle(color: _textPrimary, fontSize: 14),
                icon: const Icon(Icons.expand_more, color: _textSecondary),
                items: _projects.map<DropdownMenuItem<String>>((p) {
                  return DropdownMenuItem(
                    value: p['id']?.toString(),
                    child: Text(p['name'] ?? p['title'] ?? '项目 ${p['id']}', overflow: TextOverflow.ellipsis),
                  );
                }).toList(),
                onChanged: (v) {
                  setState(() => _selectedProjectId = v);
                  _loadData();
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── 汇总卡片（4 格） ──

  Widget _buildSummaryCards() {
    return Row(
      children: [
        _summaryCard('总计', '$_totalInspections', '项', _info),
        const SizedBox(width: 8),
        _summaryCard('通过', '$_passedInspections', '项', _success),
        const SizedBox(width: 8),
        _summaryCard('未通过', '$_failedInspections', '项', _danger),
        const SizedBox(width: 8),
        _summaryCard('待验收', '$_pendingInspections', '项', _warning),
      ],
    );
  }

  Widget _summaryCard(String label, String value, String unit, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: _card,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withOpacity(0.15)),
        ),
        child: Column(
          children: [
            Text(value, style: TextStyle(color: color, fontSize: 22, fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            Text('$label ($unit)', style: const TextStyle(color: _textSecondary, fontSize: 11)),
          ],
        ),
      ),
    );
  }

  // ── 通过率仪表盘 ──

  Widget _buildPassRateGauge() {
    final pct = (_passRate * 100).round();
    final color = _passRate >= 0.8 ? _success : (_passRate >= 0.5 ? _warning : _danger);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(12)),
      child: Row(
        children: [
          // 环形进度
          SizedBox(
            width: 80,
            height: 80,
            child: CustomPaint(
              painter: _GaugePainter(progress: _passRate, color: color),
              child: Center(
                child: Text('$pct%', style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.w700)),
              ),
            ),
          ),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('综合通过率', style: TextStyle(color: _textPrimary, fontSize: 15, fontWeight: FontWeight.w600)),
                const SizedBox(height: 6),
                Text(
                  _passRate >= 0.8 ? '质量良好，继续推进' : (_passRate >= 0.5 ? '存在改进空间，需关注' : '质量问题严重，需立即整改'),
                  style: TextStyle(color: color, fontSize: 13),
                ),
                const SizedBox(height: 8),
                LinearProgressIndicator(
                  value: _passRate,
                  backgroundColor: color.withOpacity(0.15),
                  valueColor: AlwaysStoppedAnimation<Color>(color),
                  minHeight: 4,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── 验收清单 ──

  Widget _buildInspectionList() {
    if (_inspections.isEmpty) {
      return _emptyCard('暂无验收记录');
    }
    return _sectionCard(
      title: '验收清单 (${_inspections.length})',
      icon: Icons.checklist,
      children: _inspections.take(10).map((inv) {
        final status = inv['status']?.toString() ?? '';
        final isPassed = status == 'passed' || inv['result'] == 'pass';
        final isFailed = status == 'failed' || inv['result'] == 'fail';
        final statusColor = isPassed ? _success : (isFailed ? _danger : _warning);
        final statusText = isPassed ? '通过' : (isFailed ? '未通过' : '待验收');

        return _listTile(
          title: inv['name']?.toString() ?? inv['title']?.toString() ?? '验收项',
          subtitle: '${inv['_task_name'] ?? ''}  ·  ${inv['inspector'] ?? inv['inspector_name'] ?? '-'}',
          trailing: _statusChip(statusText, statusColor),
        );
      }).toList(),
    );
  }

  // ── 质量问题 ──

  Widget _buildQualityIssues() {
    return _sectionCard(
      title: '质量问题 (${_qualityIssues.length})',
      icon: Icons.warning_amber,
      color: _danger,
      children: _qualityIssues.take(8).map((issue) {
        final severity = issue['severity']?.toString() ?? 'low';
        final severityColor = severity == 'high' ? _danger : (severity == 'medium' ? _warning : _info);
        return _listTile(
          title: issue['title']?.toString() ?? issue['description']?.toString() ?? '质量问题',
          subtitle: '${issue['_task_name'] ?? ''}',
          trailing: _statusChip(severity == 'high' ? '严重' : (severity == 'medium' ? '中等' : '轻微'), severityColor),
        );
      }).toList(),
    );
  }

  // ── 进度预警 ──

  Widget _buildAlertsList() {
    return _sectionCard(
      title: '进度预警 (${_progressAlerts.length})',
      icon: Icons.schedule,
      color: _warning,
      children: _progressAlerts.take(5).map((alert) {
        return _listTile(
          title: alert['message']?.toString() ?? alert['title']?.toString() ?? '预警',
          subtitle: alert['created_at']?.toString() ?? '',
          trailing: Icon(Icons.chevron_right, color: _textSecondary.withOpacity(0.5), size: 18),
        );
      }).toList(),
    );
  }

  // ── UI 组件 ──

  Widget _sectionCard({required String title, required IconData icon, Color? color, required List<Widget> children}) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(12)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 18, color: color ?? _brand),
              const SizedBox(width: 8),
              Text(title, style: TextStyle(color: _textPrimary, fontSize: 14, fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 10),
          ...children,
        ],
      ),
    );
  }

  Widget _listTile({required String title, required String subtitle, required Widget trailing}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(color: _textPrimary, fontSize: 13), maxLines: 1, overflow: TextOverflow.ellipsis),
                if (subtitle.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(subtitle, style: const TextStyle(color: _textSecondary, fontSize: 11), maxLines: 1, overflow: TextOverflow.ellipsis),
                ],
              ],
            ),
          ),
          const SizedBox(width: 8),
          trailing,
        ],
      ),
    );
  }

  Widget _statusChip(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: color.withOpacity(0.15), borderRadius: BorderRadius.circular(6)),
      child: Text(text, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w500)),
    );
  }

  Widget _emptyCard(String text) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(12)),
      child: Center(child: Text(text, style: const TextStyle(color: _textSecondary))),
    );
  }
}

// ── 环形进度绘制器 ──

class _GaugePainter extends CustomPainter {
  final double progress;
  final Color color;
  _GaugePainter({required this.progress, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 4;
    final bgPaint = Paint()
      ..color = color.withOpacity(0.12)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5;
    final fgPaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;

    canvas.drawCircle(center, radius, bgPaint);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      2 * math.pi * progress,
      false,
      fgPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _GaugePainter old) => old.progress != progress;
}
