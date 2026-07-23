import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/floor_plan_canvas.dart';

class MepPage extends StatefulWidget {
  final String projectId;
  const MepPage({super.key, required this.projectId});

  @override
  State<MepPage> createState() => _MepPageState();
}

class _MepPageState extends State<MepPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  // 暗色主题色
  static const Color _bgColor = Color(0xFF08080F);
  static const Color _cardColor = Color(0xFF12121D);
  static const Color _brandColor = Color(0xFFC9973B);
  static const Color _borderColor = Color(0xFF1E1E32);
  static const Color _primaryText = Color(0xFFE8E6E1);
  static const Color _secondaryText = Color(0xFF8A8894);

  // 方案
  List<dynamic> _plans = [];
  bool _plansLoading = false;
  String? _error;
  String? _selectedPlanId;
  Map<String, dynamic>? _selectedPlan;

  // 点位
  List<dynamic> _points = [];
  bool _pointsLoading = false;

  // 回路
  List<dynamic> _circuits = [];
  bool _circuitsLoading = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _loadPlans();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadPlans() async {
    setState(() {
      _plansLoading = true;
      _error = null;
    });
    final result = await _api.mepListPlans(widget.projectId);
    if (result.isSuccess) {
      setState(() => _plans = _extractList(result.data));
    } else {
      setState(() => _error = '加载失败，请检查网络后重试');
    }
    setState(() => _plansLoading = false);
  }

  Future<void> _loadPoints() async {
    if (_selectedPlanId == null) return;
    setState(() => _pointsLoading = true);
    // 水电点位与燃气点位合并展示
    final pointsResult = await _api.mepListPoints(_selectedPlanId!);
    final gasResult = await _api.mepListGas(_selectedPlanId!);
    final List<dynamic> merged = [];
    if (pointsResult.isSuccess) {
      merged.addAll(_extractList(pointsResult.data));
    }
    if (gasResult.isSuccess) {
      for (final item in _extractList(gasResult.data)) {
        if (item is Map<String, dynamic>) {
          merged.add({...item, '_category': '燃气'});
        } else {
          merged.add(item);
        }
      }
    }
    setState(() {
      _points = merged;
      _pointsLoading = false;
    });
    if (!pointsResult.isSuccess && !gasResult.isSuccess) {
      _showError('加载点位失败：${pointsResult.error}');
    }
  }

  Future<void> _loadCircuits() async {
    if (_selectedPlanId == null) return;
    setState(() => _circuitsLoading = true);
    final result = await _api.mepListCircuits(_selectedPlanId!);
    if (result.isSuccess) {
      setState(() => _circuits = _extractList(result.data));
    } else {
      _showError('加载回路失败：${result.error}');
    }
    setState(() => _circuitsLoading = false);
  }

  List<dynamic> _extractList(dynamic data) {
    if (data is List) return data;
    if (data is Map<String, dynamic>) {
      for (final key in ['items', 'plans', 'points', 'circuits', 'data']) {
        if (data[key] is List) return data[key] as List;
      }
    }
    return [];
  }

  // ── 方案操作 ──

  Future<void> _createPlan(String name, String type, String status) async {
    final result = await _api.mepCreatePlan({
      'project_id': widget.projectId,
      'name': name,
      'type': type,
      'status': status,
    });
    if (result.isSuccess) {
      _showSuccess('方案已创建');
      _loadPlans();
    } else {
      _showError('创建失败：${result.error}');
    }
  }

  Future<void> _deletePlan(String planId) async {
    final result = await _api.mepDeletePlan(planId);
    if (result.isSuccess) {
      _showSuccess('方案已删除');
      if (_selectedPlanId == planId) {
        setState(() {
          _selectedPlanId = null;
          _selectedPlan = null;
          _points = [];
          _circuits = [];
        });
      }
      _loadPlans();
    } else {
      _showError('删除失败：${result.error}');
    }
  }

  void _selectPlan(Map<String, dynamic> plan) {
    final id = (plan['id'] ?? plan['plan_id'] ?? '').toString();
    setState(() {
      _selectedPlanId = id;
      _selectedPlan = plan;
      _points = [];
      _circuits = [];
    });
    _loadPoints();
    _loadCircuits();
    _showSuccess('已选择方案：${plan['name'] ?? ''}');
  }

  // ── 点位操作 ──

  Future<void> _addPoint(
      String type, String location, String spec) async {
    if (_selectedPlanId == null) return;
    final result = await _api.mepAddPoint(_selectedPlanId!, {
      'plan_id': _selectedPlanId,
      'point_type': type,
      'location': location,
      'specification': spec,
    });
    if (result.isSuccess) {
      _showSuccess('点位已添加');
      _loadPoints();
    } else {
      _showError('添加失败：${result.error}');
    }
  }

  // ── 回路操作 ──

  Future<void> _addCircuit(
      String number, String type, String load, String breaker) async {
    if (_selectedPlanId == null) return;
    final result = await _api.mepAddCircuit(_selectedPlanId!, {
      'plan_id': _selectedPlanId,
      'circuit_number': number,
      'circuit_type': type,
      'load': load,
      'breaker': breaker,
    });
    if (result.isSuccess) {
      _showSuccess('回路已添加');
      _loadCircuits();
    } else {
      _showError('添加失败：${result.error}');
    }
  }

  // ── 工具方法 ──

  String _pointTypeLabel(dynamic type) {
    final s = type?.toString() ?? '';
    switch (s.toLowerCase()) {
      case 'water':
      case '水':
      case '水路':
        return '水';
      case 'electric':
      case '电':
      case '电路':
        return '电';
      case 'gas':
      case '燃气':
        return '燃气';
      default:
        return s.isEmpty ? '未分类' : s;
    }
  }

  Color _pointTypeColor(String label) {
    switch (label) {
      case '水':
        return Colors.lightBlue;
      case '电':
        return Colors.amber;
      case '燃气':
        return Colors.orange;
      default:
        return _secondaryText;
    }
  }

  void _showSuccess(String msg) {
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  void _showError(String msg) {
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        backgroundColor: _cardColor,
        foregroundColor: _primaryText,
        title: const Text('水电工程'),
        bottom: TabBar(
          controller: _tabController,
          labelColor: _brandColor,
          unselectedLabelColor: _secondaryText,
          indicatorColor: _brandColor,
          tabs: const [
            Tab(text: '水电方案'),
            Tab(text: '点位列表'),
            Tab(text: '回路列表'),
            Tab(text: '点位图'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildPlansTab(),
          _buildPointsTab(),
          _buildCircuitsTab(),
          _buildPointsCanvasTab(),
        ],
      ),
    );
  }

  // ── Tab1: 水电方案 ──

  Widget _buildPlansTab() {
    if (_plansLoading) {
      return const Center(child: CircularProgressIndicator(color: _brandColor));
    }
    if (_error != null) {
      return _buildErrorRetry(_error!, _loadPlans);
    }
    if (_plans.isEmpty) {
      return _buildEmptyState(
        icon: Icons.plumbing,
        message: '暂无水电方案',
        actionLabel: '创建方案',
        onAction: _showCreatePlanDialog,
      );
    }
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _brandColor,
                    foregroundColor: _bgColor,
                  ),
                  onPressed: _showCreatePlanDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('创建方案'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: _primaryText,
                  side: const BorderSide(color: _borderColor),
                ),
                onPressed: _loadPlans,
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            color: _brandColor,
            onRefresh: _loadPlans,
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: _plans.length,
              itemBuilder: (context, index) {
                final plan = _plans[index] as Map<String, dynamic>;
                return _buildPlanCard(plan);
              },
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildPlanCard(Map<String, dynamic> plan) {
    final id = (plan['id'] ?? plan['plan_id'] ?? '').toString();
    final isSelected = _selectedPlanId == id;
    return Card(
      color: _cardColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
            color: isSelected ? _brandColor : _borderColor, width: 1),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.plumbing,
                    color: isSelected ? _brandColor : _primaryText, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    plan['name']?.toString() ?? '未命名方案',
                    style: const TextStyle(
                        color: _primaryText,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                if (isSelected)
                  const Icon(Icons.check_circle,
                      color: _brandColor, size: 18),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip(
                    '类型', plan['type']?.toString() ?? '-'),
                _buildInfoChip(
                    '状态', plan['status']?.toString() ?? '-'),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildActionButton(
                  '选为当前',
                  Icons.check,
                  () => _selectPlan(plan),
                ),
                _buildActionButton(
                  '删除',
                  Icons.delete_outline,
                  () => _confirmDeletePlan(id),
                  isDanger: true,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ── Tab2: 点位列表 ──

  Widget _buildPointsTab() {
    if (_selectedPlanId == null) {
      return _buildEmptyState(
        icon: Icons.place_outlined,
        message: '请先在"水电方案"中选择一个方案',
        actionLabel: '去选择方案',
        onAction: () => _tabController.animateTo(0),
      );
    }
    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          child: Card(
            color: _cardColor,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  const Icon(Icons.plumbing, color: _brandColor, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '当前方案：${_selectedPlan?['name'] ?? _selectedPlanId}',
                      style: const TextStyle(
                          color: _primaryText, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _brandColor,
                    foregroundColor: _bgColor,
                  ),
                  onPressed: _showAddPointDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('添加点位'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: _primaryText,
                  side: const BorderSide(color: _borderColor),
                ),
                onPressed: _loadPoints,
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: _pointsLoading
              ? const Center(
                  child: CircularProgressIndicator(color: _brandColor))
              : _points.isEmpty
                  ? _buildEmptyState(
                      icon: Icons.place,
                      message: '暂无点位',
                      actionLabel: '添加点位',
                      onAction: _showAddPointDialog,
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      itemCount: _points.length,
                      itemBuilder: (context, index) {
                        final point =
                            _points[index] as Map<String, dynamic>;
                        return _buildPointCard(point);
                      },
                    ),
        ),
      ],
    );
  }

  Widget _buildPointCard(Map<String, dynamic> point) {
    final rawType = point['_category'] ?? point['point_type'] ?? point['type'];
    final typeLabel = _pointTypeLabel(rawType);
    final typeColor = _pointTypeColor(typeLabel);
    return Card(
      color: _cardColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: _borderColor, width: 1),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.place, color: typeColor, size: 20),
                const SizedBox(width: 8),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: typeColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(typeLabel,
                      style: TextStyle(
                          color: typeColor,
                          fontSize: 12,
                          fontWeight: FontWeight.w600)),
                ),
                const Spacer(),
                Text(
                  point['location']?.toString() ?? '',
                  style: const TextStyle(color: _primaryText, fontSize: 14),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip(
                    '位置', point['location']?.toString() ?? '-'),
                _buildInfoChip(
                    '规格', point['specification']?.toString() ?? point['spec']?.toString() ?? '-'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ── Tab3: 回路列表 ──

  Widget _buildCircuitsTab() {
    if (_selectedPlanId == null) {
      return _buildEmptyState(
        icon: Icons.electrical_services_outlined,
        message: '请先在"水电方案"中选择一个方案',
        actionLabel: '去选择方案',
        onAction: () => _tabController.animateTo(0),
      );
    }
    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          child: Card(
            color: _cardColor,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  const Icon(Icons.electrical_services,
                      color: _brandColor, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '当前方案：${_selectedPlan?['name'] ?? _selectedPlanId}',
                      style: const TextStyle(
                          color: _primaryText, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _brandColor,
                    foregroundColor: _bgColor,
                  ),
                  onPressed: _showAddCircuitDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('添加回路'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: _primaryText,
                  side: const BorderSide(color: _borderColor),
                ),
                onPressed: _loadCircuits,
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: _circuitsLoading
              ? const Center(
                  child: CircularProgressIndicator(color: _brandColor))
              : _circuits.isEmpty
                  ? _buildEmptyState(
                      icon: Icons.electrical_services,
                      message: '暂无回路',
                      actionLabel: '添加回路',
                      onAction: _showAddCircuitDialog,
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      itemCount: _circuits.length,
                      itemBuilder: (context, index) {
                        final circuit =
                            _circuits[index] as Map<String, dynamic>;
                        return _buildCircuitCard(circuit);
                      },
                    ),
        ),
      ],
    );
  }

  Widget _buildCircuitCard(Map<String, dynamic> circuit) {
    return Card(
      color: _cardColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: _borderColor, width: 1),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.electrical_services,
                    color: _brandColor, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '回路 ${circuit['circuit_number']?.toString() ?? circuit['number']?.toString() ?? '-'}',
                    style: const TextStyle(
                        color: _primaryText,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                Text(
                  circuit['circuit_type']?.toString() ?? circuit['type']?.toString() ?? '-',
                  style: const TextStyle(color: _brandColor, fontSize: 13),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip(
                    '负载', circuit['load']?.toString() ?? '-'),
                _buildInfoChip(
                    '断路器', circuit['breaker']?.toString() ?? '-'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ── Tab4: 点位图 ──

  Widget _buildPointsCanvasTab() {
    if (_selectedPlanId == null) {
      return _buildEmptyState(
        icon: Icons.map_outlined,
        message: '请先在"水电方案"中选择一个方案',
        actionLabel: '去选择方案',
        onAction: () => _tabController.animateTo(0),
      );
    }

    if (_pointsLoading) {
      return const Center(
          child: CircularProgressIndicator(color: _brandColor));
    }

    // 从方案数据中尝试获取房间尺寸
    final roomW = (_selectedPlan?['room_width'] as num?)?.toDouble() ?? 5000;
    final roomH = (_selectedPlan?['room_height'] as num?)?.toDouble() ?? 4000;

    // 将点位转换为 MEPPoint，自动布局在网格中
    final List<MEPPoint> mepPoints = [];
    final cols = math.max(1, (math.sqrt(_points.length.toDouble())).ceil());
    const double spacing = 600; // mm
    const double margin = 400;

    for (int i = 0; i < _points.length; i++) {
      final point = _points[i] as Map<String, dynamic>;
      final rawType = point['_category'] ?? point['point_type'] ?? point['type'];
      final typeLabel = _pointTypeLabel(rawType);

      MEPType mepType;
      switch (typeLabel) {
        case '水':
          mepType = MEPType.water;
        case '燃气':
          mepType = MEPType.gas;
        default:
          mepType = MEPType.electric;
      }

      final col = i % cols;
      final row = i ~/ cols;
      final px = margin + col * spacing;
      final py = margin + row * spacing;

      mepPoints.add(MEPPoint(
        id: (point['id'] ?? i.toString()).toString(),
        position: Offset(px, py),
        type: mepType,
        label: point['location']?.toString() ?? typeLabel,
      ));
    }

    return Column(
      children: [
        // 信息栏 + 图例
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Card(
            color: _cardColor,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.map_outlined, color: _brandColor, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        '方案：${_selectedPlan?['name'] ?? _selectedPlanId}',
                        style: const TextStyle(
                            color: _primaryText, fontWeight: FontWeight.w600),
                      ),
                      const Spacer(),
                      Text(
                        '${_points.length} 个点位',
                        style: const TextStyle(color: _secondaryText, fontSize: 13),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  // 图例
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      _buildLegendItem(Colors.red, '电'),
                      const SizedBox(width: 16),
                      _buildLegendItem(Colors.blue, '水'),
                      const SizedBox(width: 16),
                      _buildLegendItem(Colors.amber, '燃气'),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
        // 画布
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: FloorPlanCanvas(
              roomWidth: roomW,
              roomHeight: roomH,
              roomLabel: '${_selectedPlan?['name'] ?? '水电方案'} · 点位布局',
              showDimensions: true,
              showGrid: true,
              showMEPLayer: true,
              mepPoints: mepPoints,
              components: const [],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildLegendItem(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 4),
        Text(label,
            style: const TextStyle(color: _secondaryText, fontSize: 12)),
      ],
    );
  }

  // ── 通用组件 ──

  Widget _buildEmptyState({
    required IconData icon,
    required String message,
    required String actionLabel,
    required VoidCallback onAction,
  }) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 64, color: _secondaryText),
          const SizedBox(height: 16),
          Text(message,
              style: const TextStyle(fontSize: 16, color: _secondaryText)),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: _brandColor,
              foregroundColor: _bgColor,
            ),
            onPressed: onAction,
            icon: const Icon(Icons.add),
            label: Text(actionLabel),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorRetry(String message, VoidCallback onRetry) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 64, color: Colors.redAccent),
          const SizedBox(height: 16),
          Text(message,
              style: const TextStyle(fontSize: 16, color: _secondaryText)),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: _brandColor,
              foregroundColor: _bgColor,
            ),
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('重试'),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoChip(String label, String value) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('$label：',
            style: const TextStyle(color: _secondaryText, fontSize: 13)),
        Text(value,
            style: const TextStyle(color: _primaryText, fontSize: 13)),
      ],
    );
  }

  Widget _buildActionButton(
    String label,
    IconData icon,
    VoidCallback onPressed, {
    bool isDanger = false,
  }) {
    return SizedBox(
      height: 32,
      child: OutlinedButton.icon(
        style: OutlinedButton.styleFrom(
          foregroundColor: isDanger ? Colors.redAccent : _brandColor,
          side: BorderSide(
              color: isDanger ? Colors.redAccent : _borderColor),
          padding: const EdgeInsets.symmetric(horizontal: 10),
        ),
        onPressed: onPressed,
        icon: Icon(icon, size: 16),
        label: Text(label, style: const TextStyle(fontSize: 13)),
      ),
    );
  }

  // ── 对话框 ──

  void _showCreatePlanDialog() {
    final nameCtrl = TextEditingController();
    const planTypes = ['水路', '电路', '综合'];
    const statuses = ['草稿', '设计中', '已确认', '施工中', '已完成'];
    String type = planTypes.first;
    String status = statuses.first;
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          backgroundColor: _cardColor,
          title: const Text('创建水电方案',
              style: TextStyle(color: _primaryText)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameCtrl,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('方案名称'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: type,
                  dropdownColor: _cardColor,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('方案类型'),
                  items: planTypes
                      .map((t) => DropdownMenuItem(
                          value: t,
                          child: Text(t,
                              style:
                                  const TextStyle(color: _primaryText))))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setState(() => type = v);
                  },
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: status,
                  dropdownColor: _cardColor,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('状态'),
                  items: statuses
                      .map((s) => DropdownMenuItem(
                          value: s,
                          child: Text(s,
                              style:
                                  const TextStyle(color: _primaryText))))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setState(() => status = v);
                  },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消',
                  style: TextStyle(color: _secondaryText)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: _brandColor, foregroundColor: _bgColor),
              onPressed: () {
                final name = nameCtrl.text.trim();
                if (name.isEmpty) {
                  _showError('请输入方案名称');
                  return;
                }
                Navigator.pop(ctx);
                _createPlan(name, type, status);
              },
              child: const Text('创建'),
            ),
          ],
        ),
      ),
    );
  }

  void _showAddPointDialog() {
    const pointTypes = ['水', '电', '燃气'];
    final locationCtrl = TextEditingController();
    final specCtrl = TextEditingController();
    String type = pointTypes.first;
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          backgroundColor: _cardColor,
          title: const Text('添加点位',
              style: TextStyle(color: _primaryText)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  initialValue: type,
                  dropdownColor: _cardColor,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('点位类型'),
                  items: pointTypes
                      .map((t) => DropdownMenuItem(
                          value: t,
                          child: Text(t,
                              style:
                                  const TextStyle(color: _primaryText))))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setState(() => type = v);
                  },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: locationCtrl,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('位置（如：厨房水槽下方）'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: specCtrl,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('规格（如：DN20 4分PPR）'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消',
                  style: TextStyle(color: _secondaryText)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: _brandColor, foregroundColor: _bgColor),
              onPressed: () {
                final location = locationCtrl.text.trim();
                if (location.isEmpty) {
                  _showError('请输入位置');
                  return;
                }
                Navigator.pop(ctx);
                _addPoint(type, location, specCtrl.text.trim());
              },
              child: const Text('添加'),
            ),
          ],
        ),
      ),
    );
  }

  void _showAddCircuitDialog() {
    final numberCtrl = TextEditingController();
    const circuitTypes = ['照明', '插座', '空调', '厨房', '卫生间', '弱电', '其他'];
    final loadCtrl = TextEditingController();
    final breakerCtrl = TextEditingController();
    String type = circuitTypes.first;
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          backgroundColor: _cardColor,
          title: const Text('添加回路',
              style: TextStyle(color: _primaryText)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: numberCtrl,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('回路编号（如：L1）'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: type,
                  dropdownColor: _cardColor,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('回路类型'),
                  items: circuitTypes
                      .map((t) => DropdownMenuItem(
                          value: t,
                          child: Text(t,
                              style:
                                  const TextStyle(color: _primaryText))))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setState(() => type = v);
                  },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: loadCtrl,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('负载（如：3000W）'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: breakerCtrl,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('断路器（如：C16 1P）'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消',
                  style: TextStyle(color: _secondaryText)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: _brandColor, foregroundColor: _bgColor),
              onPressed: () {
                final number = numberCtrl.text.trim();
                if (number.isEmpty) {
                  _showError('请输入回路编号');
                  return;
                }
                Navigator.pop(ctx);
                _addCircuit(number, type, loadCtrl.text.trim(),
                    breakerCtrl.text.trim());
              },
              child: const Text('添加'),
            ),
          ],
        ),
      ),
    );
  }

  void _confirmDeletePlan(String planId) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('确认删除',
            style: TextStyle(color: _primaryText)),
        content: const Text('确定要删除此水电方案吗？关联的点位与回路也会被清除。此操作不可撤销。',
            style: TextStyle(color: _secondaryText)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消',
                style: TextStyle(color: _secondaryText)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: Colors.redAccent,
                foregroundColor: Colors.white),
            onPressed: () {
              Navigator.pop(ctx);
              _deletePlan(planId);
            },
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }

  InputDecoration _inputDecoration(String label) {
    return InputDecoration(
      labelText: label,
      labelStyle: const TextStyle(color: _secondaryText),
      filled: true,
      fillColor: _bgColor,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: _borderColor),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: _borderColor),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: _brandColor),
      ),
    );
  }
}
