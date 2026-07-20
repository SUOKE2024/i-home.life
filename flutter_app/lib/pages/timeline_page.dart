import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// 项目进度时间线页面
/// 对应 Web 端 timeline.html，展示 7 阶段装修进度
class TimelinePage extends StatefulWidget {
  final String? initialProjectId;
  const TimelinePage({super.key, this.initialProjectId});

  @override
  State<TimelinePage> createState() => _TimelinePageState();
}

class _TimelinePageState extends State<TimelinePage> {
  final ApiClient _api = ApiClient();

  List<Map<String, dynamic>> _projects = [];
  String? _selectedProjectId;
  Map<String, dynamic>? _selectedProject;

  // 各阶段数据
  List<dynamic> _tasks = [];
  List<dynamic> _milestones = [];
  List<dynamic> _changeOrders = [];
  bool _loading = true;
  String? _error;

  static const _brand = Color(0xFFC9973B);
  static const _bg = Color(0xFF08080F);
  static const _card = Color(0xFF12121D);
  static const _textPrimary = Color(0xFFE8E6E1);
  static const _textSecondary = Color(0xFF8A8894);

  // 7 阶段定义
  static const _phases = [
    {'key': 'initiation', 'label': '立项', 'icon': Icons.flag, 'color': Color(0xFFE57373)},
    {'key': 'design', 'label': '设计', 'icon': Icons.design_services, 'color': Color(0xFF64B5F6)},
    {'key': 'budget', 'label': '预算', 'icon': Icons.account_balance_wallet, 'color': Color(0xFF81C784)},
    {'key': 'procurement', 'label': '采购', 'icon': Icons.shopping_cart, 'color': Color(0xFFFFB74D)},
    {'key': 'construction', 'label': '施工', 'icon': Icons.construction, 'color': Color(0xFFBA68C8)},
    {'key': 'inspection', 'label': '质检', 'icon': Icons.verified, 'color': Color(0xFF4DD0E1)},
    {'key': 'settlement', 'label': '结算', 'icon': Icons.payment, 'color': Color(0xFFFFD54F)},
  ];

  @override
  void initState() {
    super.initState();
    if (widget.initialProjectId != null) {
      _selectedProjectId = widget.initialProjectId;
    }
    _loadProjects();
  }

  Future<void> _loadProjects() async {
    final result = await _api.getProjects();
    if (result.isSuccess) {
      final list = result.data is List ? result.data as List : (result.data['items'] as List? ?? []);
      setState(() {
        _projects = list.cast<Map<String, dynamic>>();
        _loading = true;
        _error = null;
      });
      if (_selectedProjectId == null && _projects.isNotEmpty) {
        _selectedProjectId = _projects.first['id']?.toString();
      }
      await _loadTimeline();
    } else {
      setState(() {
        _error = '项目列表加载失败，请检查网络后重试';
        _loading = false;
      });
    }
  }

  Future<void> _loadTimeline() async {
    if (_selectedProjectId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });

    // 并行加载：项目详情 + 施工任务 + 里程碑 + 变更单
    final results = await Future.wait([
      _api.getProject(_selectedProjectId!),
      _api.get('/construction/tasks/$_selectedProjectId'),
      _api.get('/construction/milestones/$_selectedProjectId'),
      _api.get('/change-orders/project/$_selectedProjectId'),
    ]);

    if (!mounted) return;

    if (results[0].isSuccess) {
      _selectedProject = Map<String, dynamic>.from(results[0].data as Map);
    }
    _tasks = (results[1].isSuccess ? (results[1].data is List ? results[1].data as List : []) : []);
    _milestones = (results[2].isSuccess ? (results[2].data is List ? results[2].data as List : []) : []);
    _changeOrders = (results[3].isSuccess ? (results[3].data is List ? results[3].data as List : []) : []);

    if (_selectedProject == null) {
      _error = '项目详情加载失败';
    }
    setState(() => _loading = false);
  }

  // 计算某阶段的任务数
  int _phaseTaskCount(String phaseKey) {
    final mapping = {
      'initiation': ['立项', '规划', 'initiation'],
      'design': ['设计', 'design'],
      'budget': ['预算', 'budget'],
      'procurement': ['采购', 'procurement'],
      'construction': ['施工', 'construction'],
      'inspection': ['质检', '巡检', 'inspection'],
      'settlement': ['结算', 'settlement'],
    };
    final keywords = mapping[phaseKey] ?? [];
    return _tasks.where((t) {
      final title = (t['title'] ?? t['name'] ?? '').toString();
      final category = (t['category'] ?? '').toString();
      return keywords.any((kw) => title.contains(kw) || category.contains(kw));
    }).length;
  }

  // 某阶段是否有变更单
  bool _phaseHasChangeOrder(String phaseKey) {
    final keyword = phaseKey;
    return _changeOrders.any((c) {
      final reason = (c['reason'] ?? c['description'] ?? '').toString().toLowerCase();
      return reason.contains(keyword);
    });
  }

  // 计算进度百分比
  double get _progressPercent {
    if (_milestones.isEmpty) return 0;
    final completed = _milestones.where((m) => m['completed'] == true || m['status'] == 'completed').length;
    return completed / _milestones.length;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _card,
        title: const Text('装修向导', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: _textSecondary),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: _textSecondary),
            onPressed: _loadTimeline,
          ),
        ],
      ),
      body: _loading
          ? const LoadingSkeleton(itemCount: 8)
          : _error != null
              ? ErrorRetryWidget(message: _error!, onRetry: _loadTimeline)
              : _buildContent(),
    );
  }

  Widget _buildContent() {
    return Column(
      children: [
        _buildProjectSelector(),
        _buildProgressOverview(),
        Expanded(child: _buildTimeline()),
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
          const Icon(Icons.home_work, color: _brand, size: 18),
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
                    child: Text(
                      p['name'] ?? p['title'] ?? '项目 ${p['id']}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  );
                }).toList(),
                onChanged: (v) {
                  setState(() => _selectedProjectId = v);
                  _loadTimeline();
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── 进度概览 ──

  Widget _buildProgressOverview() {
    final pct = (_progressPercent * 100).round();
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _brand.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                _selectedProject?['name'] ?? _selectedProject?['title'] ?? '项目进度',
                style: const TextStyle(color: _textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
              ),
              Text('$pct%', style: TextStyle(color: _brand, fontSize: 24, fontWeight: FontWeight.w700)),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: _progressPercent,
              backgroundColor: _brand.withOpacity(0.15),
              valueColor: const AlwaysStoppedAnimation<Color>(_brand),
              minHeight: 6,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _selectedProject?['address'] ?? '',
            style: const TextStyle(color: _textSecondary, fontSize: 12),
          ),
        ],
      ),
    );
  }

  // ── 时间线主体 ──

  Widget _buildTimeline() {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
      itemCount: _phases.length,
      itemBuilder: (context, index) {
        final phase = _phases[index];
        return _buildPhaseCard(phase, index);
      },
    );
  }

  Widget _buildPhaseCard(Map<String, dynamic> phase, int index) {
    final taskCount = _phaseTaskCount(phase['key'] as String);
    final hasChange = _phaseHasChangeOrder(phase['key'] as String);
    final isLast = index == _phases.length - 1;
    final color = phase['color'] as Color;

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 时间线节点
          SizedBox(
            width: 40,
            child: Column(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: taskCount > 0 ? color.withOpacity(0.2) : _card,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: taskCount > 0 ? color : _textSecondary.withOpacity(0.3), width: 1.5),
                  ),
                  child: Icon(
                    phase['icon'] as IconData,
                    size: 16,
                    color: taskCount > 0 ? color : _textSecondary,
                  ),
                ),
                if (!isLast)
                  Expanded(
                    child: Container(
                      width: 2,
                      margin: const EdgeInsets.symmetric(vertical: 4),
                      color: taskCount > 0 ? color.withOpacity(0.3) : _textSecondary.withOpacity(0.1),
                    ),
                  ),
              ],
            ),
          ),
          // 阶段卡片
          Expanded(
            child: Container(
              margin: EdgeInsets.only(bottom: isLast ? 0 : 12),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: _card,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: _textSecondary.withOpacity(0.1)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        phase['label'] as String,
                        style: TextStyle(
                          color: _textPrimary,
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Row(
                        children: [
                          _buildPhaseBadge('$taskCount 项', color),
                          if (hasChange) ...[
                            const SizedBox(width: 6),
                            _buildPhaseBadge('有变更', const Color(0xFFFFB74D)),
                          ],
                        ],
                      ),
                    ],
                  ),
                  if (taskCount > 0) ...[
                    const SizedBox(height: 8),
                    Text(
                      '${_getPhaseDescription(phase['key'] as String)} — 展开查看详情',
                      style: const TextStyle(color: _textSecondary, fontSize: 12),
                    ),
                  ],
                  if (taskCount == 0 && !hasChange)
                    const Padding(
                      padding: EdgeInsets.only(top: 6),
                      child: Text('暂无任务', style: TextStyle(color: _textSecondary, fontSize: 12)),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPhaseBadge(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(text, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w500)),
    );
  }

  String _getPhaseDescription(String key) {
    const descriptions = {
      'initiation': '项目立项、需求梳理、预算初估',
      'design': '户型设计、效果图、方案深化',
      'budget': '分项预算、BOM 物料清单、方案对比',
      'procurement': '采购订单、比价、供应商匹配',
      'construction': '施工任务、进度追踪、日志记录',
      'inspection': '质量检查、问题整改、验收',
      'settlement': '结算对账、支付管理、尾款',
    };
    return descriptions[key] ?? '';
  }
}
