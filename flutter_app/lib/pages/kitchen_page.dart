import 'dart:convert';
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';

class KitchenPage extends StatefulWidget {
  final String projectId;
  const KitchenPage({super.key, required this.projectId});

  @override
  State<KitchenPage> createState() => _KitchenPageState();
}

class _KitchenPageState extends State<KitchenPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  // 方案
  List<dynamic> _designs = [];
  bool _designsLoading = false;
  String? _error;
  String? _selectedDesignId;
  Map<String, dynamic>? _selectedDesign;

  // 组件
  List<dynamic> _components = [];
  bool _componentsLoading = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadDesigns();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadDesigns() async {
    setState(() {
      _designsLoading = true;
      _error = null;
    });
    final result = await _api.kitchenListDesigns(widget.projectId);
    if (result.isSuccess) {
      setState(() {
        _designs = _extractList(result.data);
      });
    } else {
      setState(() => _error = '加载失败，请检查网络后重试');
    }
    setState(() => _designsLoading = false);
  }

  Future<void> _loadComponents(String designId) async {
    setState(() => _componentsLoading = true);
    final result = await _api.kitchenListComponents(designId);
    if (result.isSuccess) {
      setState(() {
        _components = _extractList(result.data);
      });
    } else {
      _showError('加载组件失败：${result.error}');
    }
    setState(() => _componentsLoading = false);
  }

  List<dynamic> _extractList(dynamic data) {
    if (data is List) return data;
    return [];
  }

  // ── 方案操作 ──

  Future<void> _createDesign(
      String roomName, String layoutType, double width, double length) async {
    final result = await _api.kitchenCreateDesign({
      'project_id': widget.projectId,
      'room_name': roomName,
      'layout_type': layoutType,
      'room_width': width,
      'room_length': length,
    });
    if (result.isSuccess) {
      _showSuccess('方案已创建');
      _loadDesigns();
    } else {
      _showError('创建失败：${result.error}');
    }
  }

  Future<void> _deleteDesign(String designId) async {
    final result = await _api.kitchenDeleteDesign(designId);
    if (result.isSuccess) {
      _showSuccess('方案已删除');
      if (_selectedDesignId == designId) {
        setState(() {
          _selectedDesignId = null;
          _selectedDesign = null;
          _components = [];
        });
      }
      _loadDesigns();
    } else {
      _showError('删除失败：${result.error}');
    }
  }

  Future<void> _autoLayout(String designId) async {
    final result = await _api.kitchenAutoLayout(designId);
    if (result.isSuccess) {
      final data = result.data;
      final count = (data is Map) ? (data['total'] as int?) ?? 0 : 0;
      _showSuccess('已自动生成 $count 个组件');
      if (_selectedDesignId == designId) {
        _loadComponents(designId);
      }
    } else {
      _showError('自动布局失败：${result.error}');
    }
  }

  Future<void> _viewWorkflow(String designId) async {
    final result = await _api.kitchenAnalyzeWorkflow(designId);
    if (result.isSuccess) {
      _showInfoDialog('动线分析', _formatJson(result.data));
    } else {
      _showError('分析失败：${result.error}');
    }
  }

  Future<void> _viewCompliance(String designId) async {
    final result = await _api.kitchenValidateCompliance(designId);
    if (result.isSuccess) {
      _showInfoDialog('规范校验', _formatJson(result.data));
    } else {
      _showError('校验失败：${result.error}');
    }
  }

  void _selectDesign(Map<String, dynamic> design) {
    final id = (design['id'] ?? '').toString();
    setState(() {
      _selectedDesignId = id;
      _selectedDesign = design;
    });
    _loadComponents(id);
    _tabController.animateTo(1);
    _showSuccess('已选择方案：${design['room_name'] ?? ''}');
  }

  // ── 组件操作 ──

  Future<void> _addComponent(
      String type, String brand, String model, String material) async {
    if (_selectedDesignId == null) return;
    final result = await _api.kitchenAddComponent(_selectedDesignId!, {
      'design_id': _selectedDesignId,
      'component_type': type,
      'brand': brand.isEmpty ? null : brand,
      'model': model.isEmpty ? null : model,
      'material': material.isEmpty ? null : material,
    });
    if (result.isSuccess) {
      _showSuccess('组件已添加');
      _loadComponents(_selectedDesignId!);
    } else {
      _showError('添加失败：${result.error}');
    }
  }

  Future<void> _deleteComponent(String componentId) async {
    final result = await _api.kitchenDeleteComponent(componentId);
    if (result.isSuccess) {
      _showSuccess('组件已删除');
      if (_selectedDesignId != null) {
        _loadComponents(_selectedDesignId!);
      }
    } else {
      _showError('删除失败：${result.error}');
    }
  }

  // ── 工具方法 ──

  String _formatJson(dynamic data) {
    try {
      return const JsonEncoder.withIndent('  ').convert(data);
    } catch (_) {
      return data.toString();
    }
  }

  String _layoutLabel(String? code) {
    switch (code) {
      case 'L':
        return 'L型';
      case 'U':
        return 'U型';
      case 'I':
        return '一字型';
      default:
        return code ?? '-';
    }
  }

  String _formatPosition(Map<String, dynamic> comp) {
    final x = (comp['position_x'] as num?)?.toDouble() ?? 0;
    final y = (comp['position_y'] as num?)?.toDouble() ?? 0;
    final z = (comp['position_z'] as num?)?.toDouble() ?? 0;
    return '(${x.toStringAsFixed(0)}, ${y.toStringAsFixed(0)}, ${z.toStringAsFixed(0)})';
  }

  String _formatSpec(Map<String, dynamic> comp) {
    final w = (comp['width'] as num?)?.toDouble() ?? 0;
    final d = (comp['depth'] as num?)?.toDouble() ?? 0;
    final h = (comp['height'] as num?)?.toDouble() ?? 0;
    return '${w.toStringAsFixed(0)}×${d.toStringAsFixed(0)}×${h.toStringAsFixed(0)} mm';
  }

  double _calcBudget(List<dynamic> components) {
    double total = 0;
    for (final c in components) {
      if (c is Map) {
        total += (c['price'] as num?)?.toDouble() ?? 0;
      }
    }
    return total;
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

  void _showInfoDialog(String title, String content) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.cardBg,
        title: Text(title, style: const TextStyle(color: SuokeDesignTokens.textPrimary)),
        content: SizedBox(
          width: double.maxFinite,
          child: SingleChildScrollView(
            child: SelectableText(
              content,
              style: const TextStyle(
                  color: SuokeDesignTokens.textSecondary, fontFamily: 'monospace', fontSize: 13),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('关闭', style: TextStyle(color: SuokeDesignTokens.accent)),
          ),
        ],
      ),
    );
  }

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bgDeep,
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.cardBg,
        foregroundColor: SuokeDesignTokens.textPrimary,
        title: const Text('厨房设计'),
        bottom: TabBar(
          controller: _tabController,
          labelColor: SuokeDesignTokens.accent,
          unselectedLabelColor: SuokeDesignTokens.textSecondary,
          indicatorColor: SuokeDesignTokens.accent,
          tabs: const [
            Tab(text: '厨房设计方案'),
            Tab(text: '组件列表'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildDesignsTab(),
          _buildComponentsTab(),
        ],
      ),
    );
  }

  // ── Tab1: 厨房设计方案 ──

  Widget _buildDesignsTab() {
    if (_designsLoading) {
      return const Center(child: CircularProgressIndicator(color: SuokeDesignTokens.accent));
    }
    if (_error != null) {
      return _buildErrorRetry(_error!, _loadDesigns);
    }
    if (_designs.isEmpty) {
      return _buildEmptyState(
        icon: Icons.kitchen_outlined,
        message: '暂无厨房设计方案',
        actionLabel: '创建方案',
        onAction: _showCreateDesignDialog,
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
                    backgroundColor: SuokeDesignTokens.accent,
                    foregroundColor: SuokeDesignTokens.bgDeep,
                  ),
                  onPressed: _showCreateDesignDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('创建方案'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: SuokeDesignTokens.textPrimary,
                  side: const BorderSide(color: SuokeDesignTokens.border),
                ),
                onPressed: _loadDesigns,
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            color: SuokeDesignTokens.accent,
            onRefresh: _loadDesigns,
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: _designs.length,
              itemBuilder: (context, index) {
                final design = _designs[index] as Map<String, dynamic>;
                return _buildDesignCard(design);
              },
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDesignCard(Map<String, dynamic> design) {
    final id = (design['id'] ?? '').toString();
    final isSelected = _selectedDesignId == id;
    final budget = isSelected ? _calcBudget(_components) : 0.0;
    return Card(
      color: SuokeDesignTokens.cardBg,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
            color: isSelected ? SuokeDesignTokens.accent : SuokeDesignTokens.border, width: 1),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.kitchen,
                    color: isSelected ? SuokeDesignTokens.accent : SuokeDesignTokens.textPrimary, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    design['room_name'] ?? '未命名方案',
                    style: const TextStyle(
                        color: SuokeDesignTokens.textPrimary,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                if (isSelected)
                  const Icon(Icons.check_circle,
                      color: SuokeDesignTokens.accent, size: 18),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip(
                    '布局类型', _layoutLabel(design['layout_type']?.toString())),
                _buildInfoChip(
                    '台面规格',
                    '${(design['counter_height'] as num?)?.toDouble().toStringAsFixed(0) ?? '850'}×'
                    '${(design['counter_depth'] as num?)?.toDouble().toStringAsFixed(0) ?? '600'} mm'),
                _buildInfoChip('预算',
                    isSelected ? '¥${budget.toStringAsFixed(2)}' : '—'),
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
                  () => _selectDesign(design),
                ),
                _buildActionButton(
                  '自动布局',
                  Icons.auto_awesome,
                  () => _autoLayout(id),
                ),
                _buildActionButton(
                  '动线分析',
                  Icons.route,
                  () => _viewWorkflow(id),
                ),
                _buildActionButton(
                  '规范校验',
                  Icons.verified,
                  () => _viewCompliance(id),
                ),
                _buildActionButton(
                  '删除',
                  Icons.delete_outline,
                  () => _confirmDeleteDesign(id),
                  isDanger: true,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ── Tab2: 组件列表 ──

  Widget _buildComponentsTab() {
    if (_selectedDesignId == null) {
      return _buildEmptyState(
        icon: Icons.widgets_outlined,
        message: '请先在"厨房设计方案"中选择一个方案',
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
            color: SuokeDesignTokens.cardBg,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  const Icon(Icons.kitchen, color: SuokeDesignTokens.accent, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '当前方案：${_selectedDesign?['room_name'] ?? _selectedDesignId}',
                      style: const TextStyle(
                          color: SuokeDesignTokens.textPrimary, fontWeight: FontWeight.w600),
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
                    backgroundColor: SuokeDesignTokens.accent,
                    foregroundColor: SuokeDesignTokens.bgDeep,
                  ),
                  onPressed: _showAddComponentDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('添加组件'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: SuokeDesignTokens.textPrimary,
                  side: const BorderSide(color: SuokeDesignTokens.border),
                ),
                onPressed: () => _loadComponents(_selectedDesignId!),
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: _componentsLoading
              ? const Center(
                  child: CircularProgressIndicator(color: SuokeDesignTokens.accent))
              : _components.isEmpty
                  ? _buildEmptyState(
                      icon: Icons.widgets,
                      message: '暂无组件',
                      actionLabel: '添加组件',
                      onAction: _showAddComponentDialog,
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      itemCount: _components.length,
                      itemBuilder: (context, index) {
                        final comp =
                            _components[index] as Map<String, dynamic>;
                        return _buildComponentCard(comp);
                      },
                    ),
        ),
      ],
    );
  }

  Widget _buildComponentCard(Map<String, dynamic> comp) {
    final id = (comp['id'] ?? '').toString();
    final type = comp['component_type']?.toString() ?? '未分类';
    return Card(
      color: SuokeDesignTokens.cardBg,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: SuokeDesignTokens.border, width: 1),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.inventory_2, color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    type,
                    style: const TextStyle(
                        color: SuokeDesignTokens.textPrimary,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                Text(
                  '¥${(comp['price'] as num?)?.toDouble().toStringAsFixed(2) ?? '0.00'}',
                  style: const TextStyle(color: SuokeDesignTokens.accent, fontSize: 14),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip('规格', _formatSpec(comp)),
                _buildInfoChip('品牌', comp['brand']?.toString() ?? '-'),
                _buildInfoChip('型号', comp['model']?.toString() ?? '-'),
                _buildInfoChip('材质', comp['material']?.toString() ?? '-'),
                _buildInfoChip('位置', _formatPosition(comp)),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildActionButton(
                  '删除',
                  Icons.delete_outline,
                  () => _confirmDeleteComponent(id),
                  isDanger: true,
                ),
              ],
            ),
          ],
        ),
      ),
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
          Icon(icon, size: 64, color: SuokeDesignTokens.textSecondary),
          const SizedBox(height: 16),
          Text(message,
              style: const TextStyle(fontSize: 16, color: SuokeDesignTokens.textSecondary)),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: SuokeDesignTokens.accent,
              foregroundColor: SuokeDesignTokens.bgDeep,
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
              style: const TextStyle(fontSize: 16, color: SuokeDesignTokens.textSecondary)),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: SuokeDesignTokens.accent,
              foregroundColor: SuokeDesignTokens.bgDeep,
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
            style: const TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 13)),
        Text(value,
            style: const TextStyle(color: SuokeDesignTokens.textPrimary, fontSize: 13)),
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
      height: 48, // WCAG 2.2 minimum touch target
      child: OutlinedButton.icon(
        style: OutlinedButton.styleFrom(
          foregroundColor: isDanger ? Colors.redAccent : SuokeDesignTokens.accent,
          side: BorderSide(
              color: isDanger ? Colors.redAccent : SuokeDesignTokens.border),
          padding: const EdgeInsets.symmetric(horizontal: 10),
        ),
        onPressed: onPressed,
        icon: Icon(icon, size: 16),
        label: Text(label, style: const TextStyle(fontSize: 13)),
      ),
    );
  }

  // ── 对话框 ──

  void _showCreateDesignDialog() {
    final nameCtrl = TextEditingController();
    String layoutType = 'L';
    final widthCtrl = TextEditingController(text: '3.0');
    final lengthCtrl = TextEditingController(text: '3.0');
    const layouts = ['L', 'U', 'I'];
    final layoutLabels = {'L': 'L型', 'U': 'U型', 'I': '一字型'};
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          backgroundColor: SuokeDesignTokens.cardBg,
          title: const Text('创建厨房设计方案',
              style: TextStyle(color: SuokeDesignTokens.textPrimary)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameCtrl,
                  style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                  decoration: _inputDecoration('房间名称（如：主厨房）'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: layoutType,
                  dropdownColor: SuokeDesignTokens.cardBg,
                  style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                  decoration: _inputDecoration('布局类型'),
                  items: layouts
                      .map((l) => DropdownMenuItem(
                          value: l,
                          child: Text(layoutLabels[l] ?? l,
                              style:
                                  const TextStyle(color: SuokeDesignTokens.textPrimary))))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setState(() => layoutType = v);
                  },
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: widthCtrl,
                        keyboardType: TextInputType.number,
                        style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                        decoration: _inputDecoration('宽（m）'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextField(
                        controller: lengthCtrl,
                        keyboardType: TextInputType.number,
                        style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                        decoration: _inputDecoration('长（m）'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消',
                  style: TextStyle(color: SuokeDesignTokens.textSecondary)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: SuokeDesignTokens.accent, foregroundColor: SuokeDesignTokens.bgDeep),
              onPressed: () {
                final name = nameCtrl.text.trim();
                if (name.isEmpty) {
                  _showError('请输入房间名称');
                  return;
                }
                final width = double.tryParse(widthCtrl.text.trim()) ?? 3.0;
                final length = double.tryParse(lengthCtrl.text.trim()) ?? 3.0;
                Navigator.pop(ctx);
                _createDesign(name, layoutType, width, length);
              },
              child: const Text('创建'),
            ),
          ],
        ),
      ),
    );
  }

  void _showAddComponentDialog() {
    final typeCtrl = TextEditingController();
    final brandCtrl = TextEditingController();
    final modelCtrl = TextEditingController();
    final materialCtrl = TextEditingController();
    const presetTypes = ['橱柜', '抽油烟机', '灶具', '水槽', '冰箱', '洗碗机', '烤箱', '微波炉'];
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.cardBg,
        title: const Text('添加厨房组件',
            style: TextStyle(color: SuokeDesignTokens.textPrimary)),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<String>(
                dropdownColor: SuokeDesignTokens.cardBg,
                style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                decoration: _inputDecoration('组件类型'),
                items: presetTypes
                    .map((t) => DropdownMenuItem(
                        value: t,
                        child: Text(t,
                            style: const TextStyle(color: SuokeDesignTokens.textPrimary))))
                    .toList(),
                onChanged: (v) {
                  if (v != null) {
                    typeCtrl.text = v;
                  }
                },
              ),
              const SizedBox(height: 12),
              TextField(
                controller: typeCtrl,
                style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                decoration: _inputDecoration('或手动输入组件类型'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: brandCtrl,
                style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                decoration: _inputDecoration('品牌（可选）'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: modelCtrl,
                style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                decoration: _inputDecoration('型号（可选）'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: materialCtrl,
                style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                decoration: _inputDecoration('材质（可选，如：不锈钢/实木）'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消',
                style: TextStyle(color: SuokeDesignTokens.textSecondary)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: SuokeDesignTokens.accent, foregroundColor: SuokeDesignTokens.bgDeep),
            onPressed: () {
              final type = typeCtrl.text.trim();
              if (type.isEmpty) {
                _showError('请选择或输入组件类型');
                return;
              }
              Navigator.pop(ctx);
              _addComponent(type, brandCtrl.text.trim(),
                  modelCtrl.text.trim(), materialCtrl.text.trim());
            },
            child: const Text('添加'),
          ),
        ],
      ),
    );
  }

  void _confirmDeleteDesign(String designId) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.cardBg,
        title: const Text('确认删除',
            style: TextStyle(color: SuokeDesignTokens.textPrimary)),
        content: const Text('确定要删除此厨房设计方案吗？关联的组件也会被清除。此操作不可撤销。',
            style: TextStyle(color: SuokeDesignTokens.textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消',
                style: TextStyle(color: SuokeDesignTokens.textSecondary)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: Colors.redAccent,
                foregroundColor: Colors.white),
            onPressed: () {
              Navigator.pop(ctx);
              _deleteDesign(designId);
            },
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }

  void _confirmDeleteComponent(String componentId) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.cardBg,
        title: const Text('确认删除',
            style: TextStyle(color: SuokeDesignTokens.textPrimary)),
        content: const Text('确定要删除此组件吗？',
            style: TextStyle(color: SuokeDesignTokens.textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消',
                style: TextStyle(color: SuokeDesignTokens.textSecondary)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: Colors.redAccent,
                foregroundColor: Colors.white),
            onPressed: () {
              Navigator.pop(ctx);
              _deleteComponent(componentId);
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
      labelStyle: const TextStyle(color: SuokeDesignTokens.textSecondary),
      filled: true,
      fillColor: SuokeDesignTokens.bgDeep,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: SuokeDesignTokens.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: SuokeDesignTokens.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: SuokeDesignTokens.accent),
      ),
    );
  }
}
