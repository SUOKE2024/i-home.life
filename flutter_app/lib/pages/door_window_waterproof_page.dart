import 'package:flutter/material.dart';
import '../services/api.dart';

class DoorWindowWaterproofPage extends StatefulWidget {
  final String projectId;
  const DoorWindowWaterproofPage({super.key, required this.projectId});

  @override
  State<DoorWindowWaterproofPage> createState() =>
      _DoorWindowWaterproofPageState();
}

class _DoorWindowWaterproofPageState extends State<DoorWindowWaterproofPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  // 暗色主题色
  static const Color _bgColor = Color(0xFF08080F);
  static const Color _cardColor = Color(0xFF12121D);
  static const Color _brandColor = Color(0xFFC9973B);
  static const Color _borderColor = Color(0xFF1E1E32);
  static const Color _primaryText = Color(0xFFE8E6E1);
  static const Color _secondaryText = Color(0xFF8A8894);

  List<dynamic> _specs = [];
  List<dynamic> _waterproofs = [];
  Map<String, dynamic>? _selectedSpec;
  bool _loading = false;
  bool _waterproofLoading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(_onTabChanged);
    _loadSpecs();
  }

  void _onTabChanged() {
    if (!_tabController.indexIsChanging) {
      setState(() {});
    }
  }

  @override
  void dispose() {
    _tabController.removeListener(_onTabChanged);
    _tabController.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadSpecs() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.doorWinListSpecs(widget.projectId);
    if (result.isSuccess) {
      setState(() => _specs = (result.data as List?) ?? []);
    } else {
      setState(() => _error = '门窗规格加载失败，请检查网络后重试');
    }
    setState(() => _loading = false);
  }

  Future<void> _loadWaterproofs() async {
    setState(() => _waterproofLoading = true);
    final result = await _api.doorWinListWaterproof(widget.projectId);
    if (result.isSuccess) {
      setState(() => _waterproofs = (result.data as List?) ?? []);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('防水方案加载失败：${result.error ?? '未知错误'}')),
        );
      }
    }
    if (mounted) setState(() => _waterproofLoading = false);
  }

  void _selectSpec(Map<String, dynamic> spec) {
    setState(() => _selectedSpec = spec);
    _loadWaterproofs();
    _tabController.animateTo(1);
  }

  // ── 创建门窗规格 ──

  Future<void> _showCreateSpecDialog() async {
    final formKey = GlobalKey<FormState>();
    String name = '';
    String specType = 'door';
    String material = '';
    String widthStr = '900';
    String heightStr = '2100';
    String thicknessStr = '40';
    String openingMethod = 'side_hung';

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('创建门窗规格', style: TextStyle(color: _primaryText)),
        content: SingleChildScrollView(
          child: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  decoration: _inputDecoration('名称'),
                  style: const TextStyle(color: _primaryText),
                  validator: (v) =>
                      (v == null || v.isEmpty) ? '请输入名称' : null,
                  onSaved: (v) => name = v ?? '',
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: specType,
                  decoration: _inputDecoration('类型'),
                  dropdownColor: _cardColor,
                  style: const TextStyle(color: _primaryText),
                  items: const [
                    DropdownMenuItem(value: 'door', child: Text('门')),
                    DropdownMenuItem(value: 'window', child: Text('窗')),
                  ],
                  onChanged: (v) => specType = v ?? 'door',
                  onSaved: (v) => specType = v ?? 'door',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('材质'),
                  style: const TextStyle(color: _primaryText),
                  onSaved: (v) => material = v ?? '',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('宽度 (mm)'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: widthStr,
                  onSaved: (v) => widthStr = v ?? '900',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('高度 (mm)'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: heightStr,
                  onSaved: (v) => heightStr = v ?? '2100',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('厚度 (mm)'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: thicknessStr,
                  onSaved: (v) => thicknessStr = v ?? '40',
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: openingMethod,
                  decoration: _inputDecoration('开启方式'),
                  dropdownColor: _cardColor,
                  style: const TextStyle(color: _primaryText),
                  items: const [
                    DropdownMenuItem(value: 'side_hung', child: Text('平开')),
                    DropdownMenuItem(value: 'sliding', child: Text('推拉')),
                    DropdownMenuItem(value: 'casement', child: Text('悬窗')),
                    DropdownMenuItem(value: 'fixed', child: Text('固定')),
                    DropdownMenuItem(value: 'folding', child: Text('折叠')),
                  ],
                  onChanged: (v) => openingMethod = v ?? 'side_hung',
                  onSaved: (v) => openingMethod = v ?? 'side_hung',
                ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消', style: TextStyle(color: _secondaryText)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: _brandColor),
            onPressed: () {
              if (formKey.currentState?.validate() ?? false) {
                formKey.currentState?.save();
                Navigator.pop(ctx, true);
              }
            },
            child: const Text('创建'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    final result = await _api.doorWinCreateSpec({
      'project_id': widget.projectId,
      'name': name,
      'spec_type': specType,
      'material': material,
      'width_mm': double.tryParse(widthStr) ?? 900,
      'height_mm': double.tryParse(heightStr) ?? 2100,
      'thickness_mm': double.tryParse(thicknessStr) ?? 40,
      'opening_method': openingMethod,
    });
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('门窗规格已创建')),
        );
      }
      await _loadSpecs();
      final data = result.data;
      if (data is Map<String, dynamic>) {
        _selectSpec(data);
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('创建失败：${result.error ?? '未知错误'}')),
        );
      }
    }
  }

  // ── 添加防水方案 ──

  Future<void> _showAddWaterproofDialog() async {
    if (_selectedSpec == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先选择门窗规格')),
      );
      return;
    }
    final formKey = GlobalKey<FormState>();
    String area = '';
    String waterproofLevel = 'level_2';
    String material = '';
    String constructionMethod = 'coating';
    String thicknessStr = '1.5';
    String heightStr = '300';

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('添加防水方案', style: TextStyle(color: _primaryText)),
        content: SingleChildScrollView(
          child: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  decoration: _inputDecoration('区域'),
                  style: const TextStyle(color: _primaryText),
                  validator: (v) =>
                      (v == null || v.isEmpty) ? '请输入区域' : null,
                  onSaved: (v) => area = v ?? '',
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: waterproofLevel,
                  decoration: _inputDecoration('防水等级'),
                  dropdownColor: _cardColor,
                  style: const TextStyle(color: _primaryText),
                  items: const [
                    DropdownMenuItem(value: 'level_1', child: Text('一级防水')),
                    DropdownMenuItem(value: 'level_2', child: Text('二级防水')),
                    DropdownMenuItem(value: 'level_3', child: Text('三级防水')),
                  ],
                  onChanged: (v) => waterproofLevel = v ?? 'level_2',
                  onSaved: (v) => waterproofLevel = v ?? 'level_2',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('材料'),
                  style: const TextStyle(color: _primaryText),
                  onSaved: (v) => material = v ?? '',
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: constructionMethod,
                  decoration: _inputDecoration('施工方式'),
                  dropdownColor: _cardColor,
                  style: const TextStyle(color: _primaryText),
                  items: const [
                    DropdownMenuItem(value: 'coating', child: Text('涂膜防水')),
                    DropdownMenuItem(value: 'membrane', child: Text('卷材防水')),
                    DropdownMenuItem(
                        value: 'cementitious', child: Text('水泥基防水')),
                    DropdownMenuItem(value: 'sealant', child: Text('密封胶防水')),
                  ],
                  onChanged: (v) => constructionMethod = v ?? 'coating',
                  onSaved: (v) => constructionMethod = v ?? 'coating',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('涂刷厚度 (mm)'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: thicknessStr,
                  onSaved: (v) => thicknessStr = v ?? '1.5',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('上翻高度 (mm)'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: heightStr,
                  onSaved: (v) => heightStr = v ?? '300',
                ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消', style: TextStyle(color: _secondaryText)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: _brandColor),
            onPressed: () {
              if (formKey.currentState?.validate() ?? false) {
                formKey.currentState?.save();
                Navigator.pop(ctx, true);
              }
            },
            child: const Text('添加'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    final result = await _api.doorWinAddWaterproof({
      'project_id': widget.projectId,
      'room_name': area.isEmpty ? (_selectedSpec?['room_name'] ?? '默认房间') : area,
      'room_type': 'bathroom',
      'waterproof_material': material,
      'thickness_mm': double.tryParse(thicknessStr) ?? 1.5,
      'wall_height_mm': double.tryParse(heightStr)?.toInt() ?? 300,
    });
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('防水方案已添加')),
        );
      }
      await _loadWaterproofs();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('添加失败：${result.error ?? '未知错误'}')),
        );
      }
    }
  }

  // ── 删除规格 ──

  Future<void> _deleteSpec(Map<String, dynamic> spec) async {
    final specId = spec['id'] as String;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('删除规格', style: TextStyle(color: _primaryText)),
        content: Text('确定要删除「${spec['name'] ?? '该规格'}」吗？',
            style: const TextStyle(color: _primaryText)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消', style: TextStyle(color: _secondaryText)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('删除'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    final result = await _api.doorWinDeleteSpec(specId);
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('规格已删除')),
        );
      }
      if (_selectedSpec?['id'] == specId) {
        setState(() {
          _selectedSpec = null;
          _waterproofs = [];
        });
      }
      await _loadSpecs();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('删除失败：${result.error ?? '未知错误'}')),
        );
      }
    }
  }

  // ── 验证防水方案 ──

  Future<void> _validateSpec() async {
    if (_waterproofs.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('暂无防水方案可验证，请先添加')),
      );
      return;
    }
    final planId = _waterproofs.last['id'] as String;
    final result = await _api.doorWinValidateWaterproof(planId);
    if (!mounted) return;
    if (!result.isSuccess) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('验证失败：${result.error ?? '未知错误'}')),
      );
      return;
    }
    final data = result.data;
    final valid = data is Map
        ? (data['valid'] ?? data['is_valid'] ?? false)
        : false;
    final issues = data is Map
        ? (data['issues'] ?? data['errors'] ?? [])
        : [];
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(valid
            ? '验证通过'
            : '验证未通过：${issues is List ? issues.join('；') : issues}'),
      ),
    );
  }

  // ── 工具方法 ──

  InputDecoration _inputDecoration(String label) => InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: _secondaryText),
        enabledBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: _borderColor),
        ),
        focusedBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: _brandColor),
        ),
      );

  String _specTypeLabel(String? type) {
    switch (type) {
      case 'door':
        return '门';
      case 'window':
        return '窗';
      default:
        return type ?? '未指定';
    }
  }

  String _openingMethodLabel(String? method) {
    switch (method) {
      case 'side_hung':
        return '平开';
      case 'sliding':
        return '推拉';
      case 'casement':
        return '悬窗';
      case 'fixed':
        return '固定';
      case 'folding':
        return '折叠';
      default:
        return method ?? '未指定';
    }
  }

  String _waterproofLevelLabel(String? level) {
    switch (level) {
      case 'level_1':
        return '一级防水';
      case 'level_2':
        return '二级防水';
      case 'level_3':
        return '三级防水';
      default:
        return level ?? '未指定';
    }
  }

  String _constructionMethodLabel(String? method) {
    switch (method) {
      case 'coating':
        return '涂膜防水';
      case 'membrane':
        return '卷材防水';
      case 'cementitious':
        return '水泥基防水';
      case 'sealant':
        return '密封胶防水';
      default:
        return method ?? '未指定';
    }
  }

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        backgroundColor: _bgColor,
        title: const Text('门窗防水', style: TextStyle(color: _primaryText)),
        bottom: TabBar(
          controller: _tabController,
          labelColor: _brandColor,
          unselectedLabelColor: _secondaryText,
          indicatorColor: _brandColor,
          tabs: const [
            Tab(text: '门窗规格'),
            Tab(text: '防水方案'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSpecsTab(),
          _buildWaterproofTab(),
        ],
      ),
      floatingActionButton: _buildFab(),
    );
  }

  Widget? _buildFab() {
    if (_tabController.index == 0) {
      return FloatingActionButton(
        backgroundColor: _brandColor,
        onPressed: _showCreateSpecDialog,
        child: const Icon(Icons.add, color: _bgColor),
      );
    }
    if (_selectedSpec == null) return null;
    return Column(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        FloatingActionButton(
          heroTag: 'validate',
          backgroundColor: _cardColor,
          onPressed: _validateSpec,
          child: const Icon(Icons.verified, color: _brandColor),
        ),
        const SizedBox(height: 12),
        FloatingActionButton(
          heroTag: 'add_waterproof',
          backgroundColor: _brandColor,
          onPressed: _showAddWaterproofDialog,
          child: const Icon(Icons.add, color: _bgColor),
        ),
      ],
    );
  }

  Widget _buildSpecsTab() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: _brandColor));
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_error!, style: const TextStyle(color: _secondaryText)),
            const SizedBox(height: 16),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: _brandColor),
              onPressed: _loadSpecs,
              child: const Text('重试'),
            ),
          ],
        ),
      );
    }
    if (_specs.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.door_front_door,
                size: 64, color: _secondaryText),
            const SizedBox(height: 16),
            const Text('暂无门窗规格',
                style: TextStyle(color: _secondaryText, fontSize: 16)),
            const SizedBox(height: 8),
            const Text('点击右下角按钮创建',
                style: TextStyle(color: _secondaryText, fontSize: 12)),
          ],
        ),
      );
    }
    return RefreshIndicator(
      color: _brandColor,
      onRefresh: _loadSpecs,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _specs.length,
        itemBuilder: (context, index) {
          final spec = _specs[index] as Map<String, dynamic>;
          final isSelected = _selectedSpec?['id'] == spec['id'];
          final width = spec['width_mm'] ?? spec['width'];
          final height = spec['height_mm'] ?? spec['height'];
          final thickness = spec['thickness_mm'] ?? spec['thickness'];
          return Card(
            color: _cardColor,
            margin: const EdgeInsets.only(bottom: 12),
            shape: RoundedRectangleBorder(
              side: BorderSide(
                  color: isSelected ? _brandColor : _borderColor),
              borderRadius: BorderRadius.circular(8),
            ),
            child: InkWell(
              borderRadius: BorderRadius.circular(8),
              onTap: () => _selectSpec(spec),
              onLongPress: () => _deleteSpec(spec),
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            spec['name'] ?? '未命名',
                            style: const TextStyle(
                              color: _primaryText,
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        if (isSelected)
                          const Icon(Icons.check_circle,
                              color: _brandColor, size: 18),
                      ],
                    ),
                    const SizedBox(height: 10),
                    _infoRow('类型',
                        _specTypeLabel(spec['spec_type'] ?? spec['type'])),
                    _infoRow('材质', '${spec['material'] ?? '-'}'),
                    _infoRow('尺寸', '$width × $height × $thickness mm'),
                    _infoRow('开启方式',
                        _openingMethodLabel(spec['opening_method'])),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildWaterproofTab() {
    if (_selectedSpec == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.water_drop,
                size: 64, color: _secondaryText),
            const SizedBox(height: 16),
            const Text('请先在「门窗规格」中选择一个规格',
                style: TextStyle(color: _secondaryText, fontSize: 16)),
          ],
        ),
      );
    }
    if (_waterproofLoading) {
      return const Center(child: CircularProgressIndicator(color: _brandColor));
    }
    if (_waterproofs.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.water_drop,
                size: 64, color: _secondaryText),
            const SizedBox(height: 16),
            const Text('暂无防水方案',
                style: TextStyle(color: _secondaryText, fontSize: 16)),
            const SizedBox(height: 8),
            const Text('点击右下角按钮添加',
                style: TextStyle(color: _secondaryText, fontSize: 12)),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _waterproofs.length,
      itemBuilder: (context, index) {
        final w = _waterproofs[index] as Map<String, dynamic>;
        final thickness = w['thickness_mm'] ?? w['thickness'];
        final height = w['height_mm'] ?? w['height'];
        return Card(
          color: _cardColor,
          margin: const EdgeInsets.only(bottom: 12),
          shape: RoundedRectangleBorder(
            side: const BorderSide(color: _borderColor),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  w['area'] ?? '未命名区域',
                  style: const TextStyle(
                    color: _primaryText,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 10),
                _infoRow('防水等级',
                    _waterproofLevelLabel(w['waterproof_level'] ?? w['level'])),
                _infoRow('材料', '${w['material'] ?? '-'}'),
                _infoRow('施工方式',
                    _constructionMethodLabel(w['construction_method'])),
                if (thickness != null)
                  _infoRow('涂刷厚度', '$thickness mm'),
                if (height != null)
                  _infoRow('上翻高度', '$height mm'),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 72,
            child: Text(label,
                style: const TextStyle(color: _secondaryText, fontSize: 12)),
          ),
          Expanded(
            child: Text(value,
                style: const TextStyle(color: _primaryText, fontSize: 12)),
          ),
        ],
      ),
    );
  }
}
