// 索克家居
import 'package:flutter/material.dart';

import '../services/api.dart';
import '../theme/suoke_theme.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// 房间类型选项（对齐 Web v2 DesignPage.tsx ROOM_TYPES，9 种）
const List<MapEntry<String, String>> kCircRoomTypes = [
  MapEntry('entryway', '玄关'),
  MapEntry('living_room', '客厅'),
  MapEntry('dining_room', '餐厅'),
  MapEntry('kitchen', '厨房'),
  MapEntry('bedroom', '卧室'),
  MapEntry('bathroom', '卫生间'),
  MapEntry('balcony', '阳台'),
  MapEntry('cloakroom', '衣帽间'),
  MapEntry('study', '书房'),
];

/// 典型两居室布局预设（坐标单位：米，左下原点）
/// 对齐 Web v2 DesignPage.tsx PRESET_ROOMS（8 间房）
const List<Map<String, dynamic>> kPresetRooms = [
  {'name': '玄关', 'type': 'entryway', 'x': 0.0, 'y': 4.0, 'w': 1.5, 'h': 2.0},
  {'name': '客厅', 'type': 'living_room', 'x': 1.5, 'y': 3.0, 'w': 5.0, 'h': 4.0},
  {'name': '餐厅', 'type': 'dining_room', 'x': 1.5, 'y': 1.0, 'w': 3.0, 'h': 2.0},
  {'name': '厨房', 'type': 'kitchen', 'x': 0.0, 'y': 1.0, 'w': 1.5, 'h': 3.0},
  {'name': '主卧', 'type': 'bedroom', 'x': 6.5, 'y': 4.0, 'w': 4.0, 'h': 3.0},
  {'name': '次卧', 'type': 'bedroom', 'x': 6.5, 'y': 1.0, 'w': 3.5, 'h': 3.0},
  {'name': '主卫', 'type': 'bathroom', 'x': 9.0, 'y': 4.0, 'w': 1.5, 'h': 2.0},
  {'name': '阳台', 'type': 'balcony', 'x': 4.5, 'y': 0.0, 'w': 5.5, 'h': 1.0},
];

/// 动线评分等级 → 中文标签
const Map<String, String> kRatingLabel = {
  'excellent': '优秀',
  'good': '良好',
  'fair': '一般',
  'poor': '需优化',
};

/// 严重程度 → 中文标签
const Map<String, String> kSeverityLabel = {
  'critical': '严重',
  'warning': '警告',
  'info': '提示',
};

/// 设计深化页面 — 双视图（平面方案 | 动线分析）
///
/// 对齐 Web v2 DesignPage.tsx 的单页双 Tab 结构：
///   ① 平面方案：对接 /api/floorplans（CRUD）
///   ② 动线分析：房间布局编辑器 → POST /api/agents/design/circulation
class DesignDeepeningPage extends StatefulWidget {
  final String projectId;
  const DesignDeepeningPage({super.key, required this.projectId});

  @override
  State<DesignDeepeningPage> createState() => _DesignDeepeningPageState();
}

class _DesignDeepeningPageState extends State<DesignDeepeningPage>
    with SingleTickerProviderStateMixin {
  final ApiClient _api = ApiClient();
  late TabController _tabController;

  // ── 平面方案状态 ──
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _plans = [];

  // ── 动线分析状态 ──
  final List<_RoomInput> _rooms = [_RoomInput.empty()];
  bool _circLoading = false;
  String? _circError;
  Map<String, dynamic>? _circResult;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(_onTabChanged);
    _loadPlans();
  }

  void _onTabChanged() {
    // TabController 在动画过程中会多次回调，仅在最终 index 稳定后重建以切换 FAB
    if (!_tabController.indexIsChanging) {
      setState(() {});
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    for (final r in _rooms) {
      r.dispose();
    }
    super.dispose();
  }

  // ── 平面方案数据加载 ──

  Future<void> _loadPlans() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.get('/floorplans/project/${widget.projectId}');
    if (!mounted) return;
    if (result.isSuccess) {
      final data = result.data;
      if (data is List) {
        setState(() {
          _plans = data.cast<Map<String, dynamic>>();
          _loading = false;
        });
      } else {
        setState(() {
          _plans = [];
          _loading = false;
        });
      }
    } else {
      setState(() {
        _error = result.error;
        _loading = false;
      });
    }
  }

  Future<void> _createPlan() async {
    final nameController = TextEditingController(text: '新方案');
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('新建方案'),
        content: TextField(
          controller: nameController,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: '输入方案名称',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('创建'),
          ),
        ],
      ),
    );
    if (ok != true) return;

    final result = await _api.post('/floorplans', {
      'project_id': widget.projectId,
      'name': nameController.text,
      'data': '{}',
    });
    if (!mounted) return;
    if (result.isSuccess) {
      await _loadPlans();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('创建失败: ${result.error}')),
      );
    }
  }

  Future<void> _toggleActive(String planId, bool currentActive) async {
    final result = await _api.patch('/floorplans/$planId', {
      'is_active': !currentActive,
    });
    if (!mounted) return;
    if (result.isSuccess) {
      await _loadPlans();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('操作失败: ${result.error}')),
      );
    }
  }

  Future<void> _deletePlan(String planId, String name) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('确认删除'),
        content: Text('确定要删除方案「$name」吗？此操作不可撤销。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('删除'),
          ),
        ],
      ),
    );
    if (ok != true) return;

    final result = await _api.delete('/floorplans/$planId');
    if (!mounted) return;
    if (result.isSuccess) {
      await _loadPlans();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('删除失败: ${result.error}')),
      );
    }
  }

  // ── 动线分析操作 ──

  void _addRoom() {
    setState(() {
      _rooms.add(_RoomInput.empty());
    });
  }

  void _removeRoom(int idx) {
    setState(() {
      _rooms[idx].dispose();
      _rooms.removeAt(idx);
      if (_rooms.isEmpty) {
        _rooms.add(_RoomInput.empty());
      }
    });
  }

  void _loadPreset() {
    setState(() {
      for (final r in _rooms) {
        r.dispose();
      }
      _rooms.clear();
      for (final p in kPresetRooms) {
        _rooms.add(_RoomInput.fromMap(p));
      }
      _circResult = null;
      _circError = null;
    });
  }

  Future<void> _analyzeCirculation() async {
    final valid = _rooms
        .map((r) => r.toJson())
        .where((r) => (r['name'] as String).trim().isNotEmpty && r['type'] != null)
        .toList();
    if (valid.isEmpty) {
      setState(() {
        _circError = '请至少添加一个房间（含名称和类型）';
        _circResult = null;
      });
      return;
    }

    setState(() {
      _circLoading = true;
      _circError = null;
      _circResult = null;
    });

    final result = await _api.analyzeCirculation(valid);
    if (!mounted) return;

    if (result.isSuccess) {
      final data = result.data;
      if (data is Map<String, dynamic>) {
        // 后端在 rooms 为空时返回 {error: ...}，此处 valid 已非空，但仍防御
        if (data.containsKey('error')) {
          setState(() {
            _circError = data['error'].toString();
            _circLoading = false;
          });
        } else {
          setState(() {
            _circResult = data;
            _circLoading = false;
          });
        }
      } else {
        setState(() {
          _circError = '响应格式异常';
          _circLoading = false;
        });
      }
    } else {
      setState(() {
        _circError = result.error ?? '分析失败';
        _circLoading = false;
      });
    }
  }

  // ── 颜色辅助 ──

  Color _statusColor(String status) {
    switch (status) {
      case 'active':
        return SuokeDesignTokens.success;
      case 'draft':
        return SuokeDesignTokens.accent;
      default:
        return SuokeDesignTokens.textSecondary;
    }
  }

  Color _statusBg(String status) {
    switch (status) {
      case 'active':
        return SuokeDesignTokens.success.withValues(alpha: 0.15);
      case 'draft':
        return SuokeDesignTokens.accent.withValues(alpha: 0.15);
      default:
        return SuokeDesignTokens.textSecondary.withValues(alpha: 0.15);
    }
  }

  /// rating → 语义颜色（excellent=success / good=accent / fair=warning / poor=danger）
  Color _ratingColor(String rating) {
    switch (rating) {
      case 'excellent':
        return SuokeDesignTokens.success;
      case 'good':
        return SuokeDesignTokens.accent;
      case 'fair':
        return SuokeDesignTokens.warning;
      case 'poor':
        return SuokeDesignTokens.danger;
      default:
        return SuokeDesignTokens.textSecondary;
    }
  }

  /// 数值分数 → 等级字符串
  String _scoreRating(int score) {
    if (score >= 85) return 'excellent';
    if (score >= 70) return 'good';
    if (score >= 60) return 'fair';
    return 'poor';
  }

  Color _severityColor(String severity) {
    switch (severity) {
      case 'critical':
        return SuokeDesignTokens.danger;
      case 'warning':
        return SuokeDesignTokens.warning;
      case 'info':
        return SuokeDesignTokens.info;
      default:
        return SuokeDesignTokens.textSecondary;
    }
  }

  // ── 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('设计深化'),
        backgroundColor: SuokeDesignTokens.cardBg,
        foregroundColor: SuokeDesignTokens.textPrimary,
        bottom: TabBar(
          controller: _tabController,
          labelColor: SuokeDesignTokens.accent,
          unselectedLabelColor: SuokeDesignTokens.textSecondary,
          indicatorColor: SuokeDesignTokens.accent,
          tabs: const [
            Tab(text: '平面方案'),
            Tab(text: '动线分析'),
          ],
        ),
      ),
      body: Container(
        color: SuokeDesignTokens.bg(context),
        child: TabBarView(
          controller: _tabController,
          children: [
            _buildPlanView(),
            _buildCirculationView(),
          ],
        ),
      ),
      floatingActionButton: _tabController.index == 0
          ? FloatingActionButton(
              onPressed: _createPlan,
              backgroundColor: SuokeDesignTokens.accent,
              // 金色底必须深墨字（on-accent 7.56:1），白字仅 2.64:1 不达 WCAG AA
              child: const Icon(Icons.add, color: SuokeDesignTokens.onAccent),
            )
          : null,
    );
  }

  // ── 视图 1：平面方案 ──

  Widget _buildPlanView() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 3, itemHeight: 160);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadPlans);
    }
    if (_plans.isEmpty) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.design_services_outlined,
                size: 48, color: SuokeDesignTokens.textMuted),
            SizedBox(height: 12),
            Text('暂无设计方案',
                style: TextStyle(color: SuokeDesignTokens.textSecondary)),
            SizedBox(height: 8),
            Text('点击右下角 + 新建方案',
                style: TextStyle(
                    color: SuokeDesignTokens.textSecondary,
                    fontSize: SuokeDesignTokens.fontSizeSm)),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadPlans,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _plans.length,
        itemBuilder: (ctx, i) {
          final plan = _plans[i];
          final name = (plan['name'] ?? '未命名方案').toString();
          final area = (plan['total_area'] ?? 0.0).toDouble();
          final rooms = (plan['room_count'] ?? 0) as int;
          final height = (plan['wall_height'] ?? 2.8).toDouble();
          final createdAt = (plan['created_at'] ?? '').toString();
          final isActive = plan['is_active'] == true;
          final status = isActive ? 'active' : 'draft';

          return Card(
            color: SuokeDesignTokens.cardBgHover,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
            margin: const EdgeInsets.only(bottom: 12),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Expanded(
                      child: Text(name,
                          style: const TextStyle(
                              color: SuokeDesignTokens.textPrimary,
                              fontWeight: FontWeight.bold,
                              fontSize: 15)),
                    ),
                    Container(
                      padding:
                          const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: _statusBg(status),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        isActive ? '激活' : '草稿',
                        style: TextStyle(
                            color: _statusColor(status), fontSize: 11),
                      ),
                    ),
                  ]),
                  const SizedBox(height: 8),
                  Row(children: [
                    _infoChip(Icons.square_foot, '${area.toStringAsFixed(1)} m²'),
                    const SizedBox(width: 12),
                    _infoChip(Icons.meeting_room, '$rooms 房间'),
                    const SizedBox(width: 12),
                    _infoChip(Icons.height, '层高 ${height.toStringAsFixed(1)}m'),
                  ]),
                  const SizedBox(height: 8),
                  Text(
                    _formatDate(createdAt),
                    style: const TextStyle(
                        color: SuokeDesignTokens.textMuted, fontSize: 11),
                  ),
                  const Divider(
                      color: SuokeDesignTokens.borderActive, height: 24),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      Semantics(
                        label: isActive ? '停用方案$name' : '激活方案$name',
                        button: true,
                        child: TextButton.icon(
                          onPressed: () =>
                              _toggleActive(plan['id'], isActive),
                          icon: Icon(
                            isActive ? Icons.visibility_off : Icons.visibility,
                            size: 16,
                          ),
                          label: Text(isActive ? '停用' : '激活'),
                          style: TextButton.styleFrom(
                              foregroundColor: SuokeDesignTokens.accent),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Semantics(
                        label: '删除方案$name',
                        button: true,
                        child: TextButton.icon(
                          onPressed: () => _deletePlan(plan['id'], name),
                          icon: const Icon(Icons.delete_outline, size: 16),
                          label: const Text('删除'),
                          style: TextButton.styleFrom(
                              foregroundColor: SuokeDesignTokens.danger),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  // ── 视图 2：动线分析 ──

  Widget _buildCirculationView() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
        // 房间布局编辑器
        const Padding(
          padding: EdgeInsets.only(bottom: 8),
          child: Text(
            '房间布局（坐标单位：米）',
            style: TextStyle(
              color: SuokeDesignTokens.textSecondary,
              fontSize: SuokeDesignTokens.fontSizeSm,
            ),
          ),
        ),
        ..._rooms.asMap().entries.map((entry) {
          return _buildRoomRow(entry.key, entry.value);
        }),
        const SizedBox(height: 8),
        // 操作按钮
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton.icon(
              key: const Key('design-circ-add-room-btn'),
              onPressed: _addRoom,
              icon: const Icon(Icons.add, size: 16),
              label: const Text('添加房间'),
              style: OutlinedButton.styleFrom(
                foregroundColor: SuokeDesignTokens.accent,
                side: const BorderSide(color: SuokeDesignTokens.borderActive),
              ),
            ),
            OutlinedButton.icon(
              key: const Key('design-circ-preset-btn'),
              onPressed: _loadPreset,
              icon: const Icon(Icons.content_paste, size: 16),
              label: const Text('加载典型两居室预设'),
              style: OutlinedButton.styleFrom(
                foregroundColor: SuokeDesignTokens.accent,
                side: const BorderSide(color: SuokeDesignTokens.borderActive),
              ),
            ),
            FilledButton.icon(
              key: const Key('design-circ-analyze-btn'),
              onPressed: _circLoading ? null : _analyzeCirculation,
              icon: _circLoading
                  ? const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: SuokeDesignTokens.bgDeep,
                      ),
                    )
                  : const Icon(Icons.analytics_outlined, size: 16),
              label: Text(_circLoading ? '分析中…' : '分析动线'),
              style: FilledButton.styleFrom(
                backgroundColor: SuokeDesignTokens.accent,
                foregroundColor: SuokeDesignTokens.bgDeep,
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        // 错误状态
        if (_circError != null) ...[
          Container(
            key: const Key('design-circ-error'),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: SuokeDesignTokens.danger.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                  color: SuokeDesignTokens.danger.withValues(alpha: 0.3)),
            ),
            child: Row(
              children: [
                const Icon(Icons.error_outline,
                    color: SuokeDesignTokens.danger, size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _circError!,
                    style: const TextStyle(
                        color: SuokeDesignTokens.danger, fontSize: 13),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],
        // 加载状态
        if (_circLoading)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: Center(
              child: CircularProgressIndicator(
                color: SuokeDesignTokens.accent,
              ),
            ),
          ),
        // 空态提示
        if (_circResult == null && !_circLoading && _circError == null)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: Center(
              child: Text(
                '填写房间布局后点击「分析动线」',
                style: TextStyle(
                  color: SuokeDesignTokens.textMuted,
                  fontSize: SuokeDesignTokens.fontSizeSm,
                ),
              ),
            ),
          ),
        // 分析结果
        if (_circResult != null && !_circLoading && _circError == null)
          _buildCirculationResult(_circResult!),
      ],
      ),
    );
  }

  Widget _buildRoomRow(int idx, _RoomInput room) {
    return Card(
      key: ValueKey('design-circ-room-row-${room.id}'),
      color: SuokeDesignTokens.cardBgHover,
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  flex: 3,
                  child: TextField(
                    controller: room.nameCtrl,
                    decoration: const InputDecoration(
                      labelText: '名称',
                      isDense: true,
                      border: OutlineInputBorder(),
                      contentPadding:
                          EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                    ),
                    style: const TextStyle(
                        color: SuokeDesignTokens.textPrimary, fontSize: 13),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  flex: 3,
                  child: DropdownButtonFormField<String>(
                    key: ValueKey('design-circ-room-type-${room.id}'),
                    initialValue: room.type,
                    decoration: const InputDecoration(
                      labelText: '类型',
                      isDense: true,
                      border: OutlineInputBorder(),
                      contentPadding:
                          EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                    ),
                    dropdownColor: SuokeDesignTokens.cardBgHover,
                    style: const TextStyle(
                        color: SuokeDesignTokens.textPrimary, fontSize: 13),
                    items: kCircRoomTypes
                        .map((e) => DropdownMenuItem(
                              value: e.key,
                              child: Text(e.value),
                            ))
                        .toList(),
                    onChanged: (v) {
                      if (v != null) {
                        setState(() {
                          room.type = v;
                        });
                      }
                    },
                  ),
                ),
                const SizedBox(width: 4),
                IconButton(
                  icon: const Icon(Icons.close,
                      size: 16, color: SuokeDesignTokens.danger),
                  tooltip: '删除房间 ${idx + 1}',
                  onPressed: () => _removeRoom(idx),
                  constraints: const BoxConstraints(
                    minWidth: SuokeDesignTokens.touchTargetAa,
                    minHeight: SuokeDesignTokens.touchTargetAa,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: _numField(room.xCtrl, 'x'),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _numField(room.yCtrl, 'y'),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _numField(room.wCtrl, '宽 w'),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _numField(room.hCtrl, '高 h'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _numField(TextEditingController ctrl, String label) {
    return TextField(
      controller: ctrl,
      keyboardType:
          const TextInputType.numberWithOptions(decimal: true, signed: true),
      decoration: InputDecoration(
        labelText: label,
        isDense: true,
        border: const OutlineInputBorder(),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      ),
      style: const TextStyle(
          color: SuokeDesignTokens.textPrimary, fontSize: 13),
    );
  }

  // ── 动线分析结果展示 ──

  Widget _buildCirculationResult(Map<String, dynamic> data) {
    // 后端 overall_score 为 float，rooms_count 等为 int；JSON 解析后数值类型可能为
    // int 或 double，统一用 num.toInt() 兼容（避免 `as int` 在 double 时抛错）。
    // overall_score 后端返回 float（如 90.0），保留 num 类型以便原样展示，
    // 同时与 circulations[].score（int）的展示区分（避免 find.text 冲突）。
    final num overallScore = (data['overall_score'] ?? 0) as num;
    final String rating = (data['rating'] ?? '').toString();
    final String ratingText =
        (data['rating_text'] ?? kRatingLabel[rating] ?? rating).toString();
    final int roomsCount = _asInt(data['rooms_count']);
    final int totalIssues = _asInt(data['total_issues']);
    final int criticalCount = _asInt(data['critical_count']);
    final int warningCount = _asInt(data['warning_count']);
    final String reply = (data['reply'] ?? '').toString();
    final List circulations = (data['circulations'] ?? []) as List;
    final List issues = (data['issues'] ?? []) as List;
    final List suggestions = (data['suggestions'] ?? []) as List;

    return Column(
      key: const Key('design-circ-result'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 综合评分卡
        Card(
          key: const Key('design-circ-score-card'),
          color: SuokeDesignTokens.cardBgHover,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(
                color: _ratingColor(rating).withValues(alpha: 0.4)),
          ),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '综合评分',
                  style: TextStyle(
                    color: SuokeDesignTokens.textSecondary,
                    fontSize: SuokeDesignTokens.fontSizeSm,
                  ),
                ),
                const SizedBox(height: 6),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      '$overallScore',
                      key: const Key('design-circ-overall-score'),
                      style: TextStyle(
                        color: _ratingColor(rating),
                        fontSize: 32,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Container(
                        key: const Key('design-circ-rating-text'),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: _ratingColor(rating).withValues(alpha: 0.18),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          ratingText,
                          style: TextStyle(
                            color: _ratingColor(rating),
                            fontSize: SuokeDesignTokens.fontSizeSm,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  '$roomsCount 房间 · $totalIssues 问题'
                  '（$criticalCount 严重 / $warningCount 警告）',
                  style: const TextStyle(
                    color: SuokeDesignTokens.textMuted,
                    fontSize: SuokeDesignTokens.fontSizeSm,
                  ),
                ),
                if (reply.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    reply,
                    style: const TextStyle(
                      color: SuokeDesignTokens.textPrimary,
                      fontSize: SuokeDesignTokens.fontSizeMd,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),

        // 三大动线明细
        if (circulations.isNotEmpty) ...[
          Text(
            '三大动线（${circulations.length}）',
            style: const TextStyle(
              color: SuokeDesignTokens.textSecondary,
              fontSize: SuokeDesignTokens.fontSizeSm,
            ),
          ),
          const SizedBox(height: 8),
          ...circulations.asMap().entries.map((entry) {
            return _buildCirculationItem(entry.key, entry.value);
          }),
          const SizedBox(height: 12),
        ],

        // 全局问题列表
        if (issues.isNotEmpty) ...[
          Text(
            '问题清单（${issues.length}）',
            style: const TextStyle(
              color: SuokeDesignTokens.textSecondary,
              fontSize: SuokeDesignTokens.fontSizeSm,
            ),
          ),
          const SizedBox(height: 8),
          ...issues.asMap().entries.map((entry) {
            return _buildIssueItem(entry.key, entry.value);
          }),
          const SizedBox(height: 12),
        ],

        // 优化建议
        if (suggestions.isNotEmpty) ...[
          Text(
            '优化建议（${suggestions.length}）',
            style: const TextStyle(
              color: SuokeDesignTokens.textSecondary,
              fontSize: SuokeDesignTokens.fontSizeSm,
            ),
          ),
          const SizedBox(height: 8),
          Card(
            key: const Key('design-circ-suggestions'),
            color: SuokeDesignTokens.cardBgHover,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: suggestions.asMap().entries.map((entry) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('💡 ',
                            style: TextStyle(fontSize: SuokeDesignTokens.fontSizeMd)),
                        Expanded(
                          child: Text(
                            entry.value.toString(),
                            style: const TextStyle(
                              color: SuokeDesignTokens.textPrimary,
                              fontSize: SuokeDesignTokens.fontSizeMd,
                            ),
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildCirculationItem(int idx, dynamic item) {
    if (item is! Map<String, dynamic>) return const SizedBox.shrink();
    final String name = (item['name'] ?? '').toString();
    final int score = _asInt(item['score']);
    final String rating = (item['rating'] ?? _scoreRating(score)).toString();
    final String description = (item['description'] ?? '').toString();
    final List issues = (item['issues'] ?? []) as List;
    final List itemSuggestions = (item['suggestions'] ?? []) as List;

    return Card(
      key: ValueKey('design-circ-circ-item-$idx'),
      color: SuokeDesignTokens.cardBgHover,
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
            color: _ratingColor(rating).withValues(alpha: 0.25)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    name,
                    style: const TextStyle(
                      color: SuokeDesignTokens.textPrimary,
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: _ratingColor(rating).withValues(alpha: 0.18),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    '$score',
                    style: TextStyle(
                      color: _ratingColor(rating),
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            if (description.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                description,
                style: const TextStyle(
                  color: SuokeDesignTokens.textSecondary,
                  fontSize: SuokeDesignTokens.fontSizeMd,
                ),
              ),
            ],
            if (issues.isNotEmpty) ...[
              const SizedBox(height: 6),
              ...issues.map((iss) {
                if (iss is! Map<String, dynamic>) return const SizedBox.shrink();
                final sev = (iss['severity'] ?? 'info').toString();
                final detail =
                    (iss['detail'] ?? iss['message'] ?? '').toString();
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        margin: const EdgeInsets.only(top: 2),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 4, vertical: 1),
                        decoration: BoxDecoration(
                          color: _severityColor(sev).withValues(alpha: 0.18),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          kSeverityLabel[sev] ?? sev,
                          style: TextStyle(
                            color: _severityColor(sev),
                            fontSize: SuokeDesignTokens.fontSizeXs,
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          detail,
                          style: const TextStyle(
                            color: SuokeDesignTokens.textPrimary,
                            fontSize: SuokeDesignTokens.fontSizeMd,
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              }),
            ],
            if (itemSuggestions.isNotEmpty) ...[
              const SizedBox(height: 4),
              ...itemSuggestions.map((s) {
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 1),
                  child: Text(
                    '💡 ${s.toString()}',
                    style: const TextStyle(
                      color: SuokeDesignTokens.textSecondary,
                      fontSize: SuokeDesignTokens.fontSizeMd,
                    ),
                  ),
                );
              }),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildIssueItem(int idx, dynamic item) {
    if (item is! Map<String, dynamic>) return const SizedBox.shrink();
    final sev = (item['severity'] ?? 'info').toString();
    final message =
        (item['message'] ?? item['detail'] ?? '').toString();

    return Container(
      key: ValueKey('design-circ-issue-item-$idx'),
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.cardBgHover,
        borderRadius: BorderRadius.circular(8),
        border:
            Border.all(color: _severityColor(sev).withValues(alpha: 0.3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            margin: const EdgeInsets.only(top: 2),
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: _severityColor(sev).withValues(alpha: 0.18),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              kSeverityLabel[sev] ?? sev,
              style: TextStyle(
                color: _severityColor(sev),
                fontSize: SuokeDesignTokens.fontSizeXs,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                color: SuokeDesignTokens.textPrimary,
                fontSize: SuokeDesignTokens.fontSizeMd,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── 通用小组件 ──

  Widget _infoChip(IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: SuokeDesignTokens.textSecondary),
        const SizedBox(width: 4),
        Text(text,
            style: const TextStyle(
                color: SuokeDesignTokens.textSecondary,
                fontSize: SuokeDesignTokens.fontSizeSm)),
      ],
    );
  }

  String _formatDate(String iso) {
    try {
      final dt = DateTime.parse(iso);
      return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
    } catch (_) {
      return iso;
    }
  }

  /// 安全 int 转换：兼容后端返回 int/double 与 JSON 解析后的 num 类型。
  int _asInt(dynamic v) {
    if (v is int) return v;
    if (v is num) return v.toInt();
    if (v is String) return int.tryParse(v) ?? 0;
    return 0;
  }
}

/// 动线分析房间输入行 — 持有 TextEditingController 避免 rebuild 丢焦点。
class _RoomInput {
  static int _nextId = 0;

  /// 唯一标识，用于 Widget key（预设加载时整批替换 → 全新 widget）
  final int id;
  final TextEditingController nameCtrl;
  final TextEditingController xCtrl;
  final TextEditingController yCtrl;
  final TextEditingController wCtrl;
  final TextEditingController hCtrl;
  String type;

  _RoomInput({
    required this.id,
    required this.nameCtrl,
    required this.xCtrl,
    required this.yCtrl,
    required this.wCtrl,
    required this.hCtrl,
    required this.type,
  });

  factory _RoomInput.empty() => _RoomInput(
        id: _nextId++,
        nameCtrl: TextEditingController(text: ''),
        xCtrl: TextEditingController(text: '0'),
        yCtrl: TextEditingController(text: '0'),
        wCtrl: TextEditingController(text: '3'),
        hCtrl: TextEditingController(text: '3'),
        type: 'living_room',
      );

  factory _RoomInput.fromMap(Map<String, dynamic> p) => _RoomInput(
        id: _nextId++,
        nameCtrl: TextEditingController(text: p['name']?.toString() ?? ''),
        xCtrl:
            TextEditingController(text: _formatNum(p['x'])),
        yCtrl:
            TextEditingController(text: _formatNum(p['y'])),
        wCtrl:
            TextEditingController(text: _formatNum(p['w'])),
        hCtrl:
            TextEditingController(text: _formatNum(p['h'])),
        type: p['type']?.toString() ?? 'living_room',
      );

  /// 转换为 API 请求体中的房间对象。
  Map<String, dynamic> toJson() => {
        'name': nameCtrl.text,
        'type': type,
        'x': double.tryParse(xCtrl.text) ?? 0,
        'y': double.tryParse(yCtrl.text) ?? 0,
        'w': double.tryParse(wCtrl.text) ?? 0,
        'h': double.tryParse(hCtrl.text) ?? 0,
      };

  void dispose() {
    nameCtrl.dispose();
    xCtrl.dispose();
    yCtrl.dispose();
    wCtrl.dispose();
    hCtrl.dispose();
  }

  static String _formatNum(dynamic v) {
    if (v is int) return v.toString();
    if (v is double) {
      if (v == v.roundToDouble()) return v.toInt().toString();
      return v.toString();
    }
    return v?.toString() ?? '0';
  }
}
