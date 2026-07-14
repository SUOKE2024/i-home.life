import 'package:flutter/material.dart';
import '../services/api.dart';

class BathroomPage extends StatefulWidget {
  final String projectId;
  const BathroomPage({super.key, required this.projectId});

  @override
  State<BathroomPage> createState() => _BathroomPageState();
}

class _BathroomPageState extends State<BathroomPage>
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

  List<dynamic> _designs = [];
  List<dynamic> _fixtures = [];
  Map<String, dynamic>? _selectedDesign;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(_onTabChanged);
    _loadDesigns();
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

  Future<void> _loadDesigns() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.bathroomListDesigns(widget.projectId);
    if (result.isSuccess) {
      setState(() => _designs = (result.data as List?) ?? []);
    } else {
      setState(() => _error = '卫浴方案加载失败，请检查网络后重试');
    }
    setState(() => _loading = false);
  }

  Future<void> _loadFixtures(String designId) async {
    final result = await _api.bathroomListFixtures(designId);
    if (result.isSuccess) {
      setState(() => _fixtures = (result.data as List?) ?? []);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('设施加载失败：${result.error}')));
      }
    }
  }

  void _selectDesign(Map<String, dynamic> design) {
    setState(() => _selectedDesign = design);
    _loadFixtures(design['id'] as String);
    _tabController.animateTo(1);
  }

  // ── 创建卫浴方案 ──

  Future<void> _showCreateDesignDialog() async {
    final formKey = GlobalKey<FormState>();
    String roomName = '';
    String layoutType = 'dry_wet_separation';
    String roomWidthStr = '2.0';
    String roomLengthStr = '3.0';
    String ceilingHeightStr = '2.6';
    String waterproofHeightStr = '1800';

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('创建卫浴方案', style: TextStyle(color: _primaryText)),
        content: SingleChildScrollView(
          child: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  decoration: _inputDecoration('卫生间名称'),
                  style: const TextStyle(color: _primaryText),
                  validator: (v) =>
                      (v == null || v.isEmpty) ? '请输入名称' : null,
                  onSaved: (v) => roomName = v ?? '',
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: layoutType,
                  decoration: _inputDecoration('干湿分离类型'),
                  dropdownColor: _cardColor,
                  style: const TextStyle(color: _primaryText),
                  items: const [
                    DropdownMenuItem(
                        value: 'dry_wet_separation', child: Text('干湿分离')),
                    DropdownMenuItem(
                        value: 'fully_separated', child: Text('完全分离')),
                    DropdownMenuItem(
                        value: 'half_separated', child: Text('半分离')),
                    DropdownMenuItem(value: 'integrated', child: Text('一体式')),
                  ],
                  onChanged: (v) => layoutType = v ?? 'dry_wet_separation',
                  onSaved: (v) => layoutType = v ?? 'dry_wet_separation',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('宽度 (m)'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: roomWidthStr,
                  onSaved: (v) => roomWidthStr = v ?? '2.0',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('长度 (m)'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: roomLengthStr,
                  onSaved: (v) => roomLengthStr = v ?? '3.0',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('层高 (m)'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: ceilingHeightStr,
                  onSaved: (v) => ceilingHeightStr = v ?? '2.6',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('防水高度 (mm)'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: waterproofHeightStr,
                  onSaved: (v) => waterproofHeightStr = v ?? '1800',
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

    if (result != true) return;

    final width = double.tryParse(roomWidthStr) ?? 2.0;
    final length = double.tryParse(roomLengthStr) ?? 3.0;
    final height = double.tryParse(ceilingHeightStr) ?? 2.6;
    final waterproof = int.tryParse(waterproofHeightStr) ?? 1800;

    final apiResult = await _api.bathroomCreateDesign({
      'project_id': widget.projectId,
      'room_name': roomName,
      'layout_type': layoutType,
      'room_width': width,
      'room_length': length,
      'ceiling_height': height,
      'waterproof_height_mm': waterproof,
    });
    if (apiResult.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('卫浴方案已创建')),
        );
      }
      await _loadDesigns();
      final data = apiResult.data;
      if (data is Map<String, dynamic>) {
        _selectDesign(data);
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('创建失败：${apiResult.error}')));
      }
    }
  }

  // ── 添加卫浴设施 ──

  Future<void> _showAddFixtureDialog() async {
    if (_selectedDesign == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先选择卫浴方案')),
      );
      return;
    }
    final designId = _selectedDesign!['id'] as String;
    final formKey = GlobalKey<FormState>();
    String fixtureType = '';
    String brand = '';
    String model = '';
    String widthStr = '600';
    String depthStr = '500';
    String heightStr = '800';
    String posXStr = '0';
    String posYStr = '0';
    String posZStr = '0';
    String priceStr = '0';

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('添加卫浴设施', style: TextStyle(color: _primaryText)),
        content: SingleChildScrollView(
          child: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  decoration: _inputDecoration('设施类型（马桶/淋浴/浴缸/洗手台等）'),
                  style: const TextStyle(color: _primaryText),
                  validator: (v) =>
                      (v == null || v.isEmpty) ? '请输入设施类型' : null,
                  onSaved: (v) => fixtureType = v ?? '',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('品牌'),
                  style: const TextStyle(color: _primaryText),
                  onSaved: (v) => brand = v ?? '',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('型号'),
                  style: const TextStyle(color: _primaryText),
                  onSaved: (v) => model = v ?? '',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('宽度 (mm)'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: widthStr,
                  onSaved: (v) => widthStr = v ?? '600',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('深度 (mm)'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: depthStr,
                  onSaved: (v) => depthStr = v ?? '500',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('高度 (mm)'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: heightStr,
                  onSaved: (v) => heightStr = v ?? '800',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('安装位置 X'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: posXStr,
                  onSaved: (v) => posXStr = v ?? '0',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('安装位置 Y'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: posYStr,
                  onSaved: (v) => posYStr = v ?? '0',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('安装位置 Z'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: posZStr,
                  onSaved: (v) => posZStr = v ?? '0',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  decoration: _inputDecoration('价格'),
                  style: const TextStyle(color: _primaryText),
                  keyboardType: TextInputType.number,
                  initialValue: priceStr,
                  onSaved: (v) => priceStr = v ?? '0',
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

    if (result != true) return;

    final apiResult = await _api.bathroomAddFixture(designId, {
      'design_id': designId,
      'fixture_type': fixtureType,
      'brand': brand,
      'model': model,
      'width': double.tryParse(widthStr) ?? 600,
      'depth': double.tryParse(depthStr) ?? 500,
      'height': double.tryParse(heightStr) ?? 800,
      'position_x': double.tryParse(posXStr) ?? 0,
      'position_y': double.tryParse(posYStr) ?? 0,
      'position_z': double.tryParse(posZStr) ?? 0,
      'price': double.tryParse(priceStr) ?? 0,
    });
    if (apiResult.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('设施已添加')),
        );
      }
      await _loadFixtures(designId);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('添加失败：${apiResult.error}')));
      }
    }
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

  String _layoutTypeLabel(String? type) {
    switch (type) {
      case 'dry_wet_separation':
        return '干湿分离';
      case 'fully_separated':
        return '完全分离';
      case 'half_separated':
        return '半分离';
      case 'integrated':
        return '一体式';
      default:
        return type ?? '未指定';
    }
  }

  String _waterproofLevel(int? mm) {
    final h = mm ?? 0;
    if (h >= 1800) return '高（${h}mm）';
    if (h >= 1500) return '中（${h}mm）';
    if (h > 0) return '基础（${h}mm）';
    return '未设置';
  }

  String _statusLabel(String? status) {
    switch (status) {
      case 'draft':
        return '草稿';
      case 'confirmed':
        return '已确认';
      case 'completed':
        return '已完成';
      default:
        return status ?? '未知';
    }
  }

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        backgroundColor: _bgColor,
        title: const Text('卫浴设计', style: TextStyle(color: _primaryText)),
        bottom: TabBar(
          controller: _tabController,
          labelColor: _brandColor,
          unselectedLabelColor: _secondaryText,
          indicatorColor: _brandColor,
          tabs: const [
            Tab(text: '卫浴方案'),
            Tab(text: '卫浴设施'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildDesignsTab(),
          _buildFixturesTab(),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: _brandColor,
        onPressed: () {
          if (_tabController.index == 0) {
            _showCreateDesignDialog();
          } else {
            _showAddFixtureDialog();
          }
        },
        child: const Icon(Icons.add, color: _bgColor),
      ),
    );
  }

  Widget _buildDesignsTab() {
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
              onPressed: _loadDesigns,
              child: const Text('重试'),
            ),
          ],
        ),
      );
    }
    if (_designs.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.bathtub, size: 64, color: _secondaryText),
            const SizedBox(height: 16),
            const Text('暂无卫浴方案',
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
      onRefresh: _loadDesigns,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _designs.length,
        itemBuilder: (context, index) {
          final design = _designs[index] as Map<String, dynamic>;
          final isSelected = _selectedDesign?['id'] == design['id'];
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
              onTap: () => _selectDesign(design),
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            design['room_name'] ?? '未命名',
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
                    _infoRow('干湿分离', _layoutTypeLabel(design['layout_type'])),
                    _infoRow('防水等级',
                        _waterproofLevel(design['waterproof_height_mm'])),
                    _infoRow('状态', _statusLabel(design['status'])),
                    _infoRow(
                      '尺寸',
                      '${design['room_width']}×${design['room_length']}×${design['ceiling_height']} m',
                    ),
                    _infoRow('地漏数量', '${design['floor_drain_count'] ?? 1} 个'),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildFixturesTab() {
    if (_selectedDesign == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.plumbing, size: 64, color: _secondaryText),
            const SizedBox(height: 16),
            const Text('请先在「卫浴方案」中选择一个方案',
                style: TextStyle(color: _secondaryText, fontSize: 16)),
          ],
        ),
      );
    }
    if (_fixtures.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.plumbing, size: 64, color: _secondaryText),
            const SizedBox(height: 16),
            const Text('暂无设施，点击右下角添加',
                style: TextStyle(color: _secondaryText, fontSize: 16)),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _fixtures.length,
      itemBuilder: (context, index) {
        final f = _fixtures[index] as Map<String, dynamic>;
        final w = (f['width'] as num?)?.toDouble() ?? 0;
        final d = (f['depth'] as num?)?.toDouble() ?? 0;
        final h = (f['height'] as num?)?.toDouble() ?? 0;
        final px = (f['position_x'] as num?)?.toDouble() ?? 0;
        final py = (f['position_y'] as num?)?.toDouble() ?? 0;
        final pz = (f['position_z'] as num?)?.toDouble() ?? 0;
        final price = (f['price'] as num?)?.toDouble() ?? 0;
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
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        f['fixture_type'] ?? '未命名',
                        style: const TextStyle(
                          color: _primaryText,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    Text(
                      '¥${price.toStringAsFixed(0)}',
                      style: const TextStyle(color: _brandColor),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                _infoRow('品牌', '${f['brand'] ?? '-'} ${f['model'] ?? ''}'),
                _infoRow(
                    '规格', '${w.toStringAsFixed(0)}×${d.toStringAsFixed(0)}×${h.toStringAsFixed(0)} mm'),
                _infoRow('安装位置', '($px, $py, $pz)'),
                if (f['material'] != null)
                  _infoRow('材质', '${f['material']}'),
                if (f['color'] != null) _infoRow('颜色', '${f['color']}'),
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
