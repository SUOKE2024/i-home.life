import 'package:flutter/material.dart';
import '../services/api.dart';

class SoftFurnishingPage extends StatefulWidget {
  final String projectId;
  const SoftFurnishingPage({super.key, required this.projectId});

  @override
  State<SoftFurnishingPage> createState() => _SoftFurnishingPageState();
}

class _SoftFurnishingPageState extends State<SoftFurnishingPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  // 暗色主题色
  static const Color _bg = Color(0xFF08080F);
  static const Color _cardBg = Color(0xFF12121D);
  static const Color _brand = Color(0xFFC9973B);
  static const Color _border = Color(0xFF1E1E32);
  static const Color _textPrimary = Color(0xFFE8E6E1);
  static const Color _textSecondary = Color(0xFF8A8894);

  List<dynamic> _schemes = [];
  List<dynamic> _items = [];
  List<dynamic> _storages = [];
  bool _loading = false;
  String? _error;

  static const List<String> _styleOptions = [
    'modern',
    '北欧',
    '新中式',
    '美式',
    '法式',
    '工业',
    '日式',
  ];
  static const List<String> _itemTypeOptions = [
    '窗帘',
    '地毯',
    '抱枕',
    '挂画',
    '灯具',
    '花瓶',
    '床品',
    '桌布',
  ];
  static const List<String> _storageTypeOptions = [
    '衣柜',
    '鞋柜',
    '书柜',
    '储物柜',
    '橱柜',
    '吊柜',
    '斗柜',
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadAll();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final schemesResult = await _api.softListSchemes(widget.projectId);
    if (schemesResult.isSuccess) {
      _schemes = (schemesResult.data as List?) ?? [];
      // 聚合所有方案下的单品与收纳
      final List<dynamic> allItems = [];
      final List<dynamic> allStorages = [];
      for (final s in _schemes) {
        final sid = s['id'] as String;
        final itemsResult = await _api.softListItems(sid);
        if (itemsResult.isSuccess) {
          allItems.addAll((itemsResult.data as List?) ?? []);
        }
        final storagesResult = await _api.softListStorages(sid);
        if (storagesResult.isSuccess) {
          allStorages.addAll((storagesResult.data as List?) ?? []);
        }
      }
      _items = allItems;
      _storages = allStorages;
    } else {
      _error = '加载失败，请检查网络后重试';
    }
    setState(() => _loading = false);
  }

  Future<void> _createScheme(Map<String, dynamic> body) async {
    final result = await _api.softCreateScheme({
      ...body,
      'project_id': widget.projectId,
    });
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('方案创建成功')),
        );
        _loadAll();
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('创建失败：${result.error}')));
      }
    }
  }

  Future<void> _addItem(String schemeId, Map<String, dynamic> body) async {
    final result = await _api.softAddItem(schemeId, body);
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('单品添加成功')),
        );
        _loadAll();
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('添加失败：${result.error}')));
      }
    }
  }

  Future<void> _addStorage(String schemeId, Map<String, dynamic> body) async {
    final result = await _api.softAddStorage(schemeId, body);
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('收纳添加成功')),
        );
        _loadAll();
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('添加失败：${result.error}')));
      }
    }
  }

  Future<void> _deleteScheme(String schemeId) async {
    final result = await _api.softDeleteScheme(schemeId);
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('方案已删除')),
        );
        _loadAll();
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('删除失败：${result.error}')));
      }
    }
  }

  InputDecoration _inputDecoration(String label) => InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: _textSecondary),
        enabledBorder:
            const OutlineInputBorder(borderSide: BorderSide(color: _border)),
        focusedBorder:
            const OutlineInputBorder(borderSide: BorderSide(color: _brand)),
      );

  void _showCreateSchemeDialog() {
    final roomNameCtrl = TextEditingController();
    final budgetCtrl = TextEditingController(text: '0');
    String style = _styleOptions.first;
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          backgroundColor: _cardBg,
          title:
              const Text('创建软装方案', style: TextStyle(color: _textPrimary)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: roomNameCtrl,
                  style: const TextStyle(color: _textPrimary),
                  decoration: _inputDecoration('房间名称'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: style,
                  dropdownColor: _cardBg,
                  style: const TextStyle(color: _textPrimary),
                  decoration: _inputDecoration('风格'),
                  items: _styleOptions
                      .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                      .toList(),
                  onChanged: (v) =>
                      setState(() => style = v ?? _styleOptions.first),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: budgetCtrl,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: _textPrimary),
                  decoration: _inputDecoration('预算总额'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('取消')),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: _brand, foregroundColor: _bg),
              onPressed: () {
                if (roomNameCtrl.text.isEmpty) return;
                Navigator.pop(ctx);
                _createScheme({
                  'room_name': roomNameCtrl.text,
                  'style': style,
                  'budget_total': double.tryParse(budgetCtrl.text) ?? 0,
                });
              },
              child: const Text('创建'),
            ),
          ],
        ),
      ),
    );
  }

  void _showAddItemDialog() {
    if (_schemes.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先创建软装方案')),
      );
      return;
    }
    final nameCtrl = TextEditingController();
    final materialCtrl = TextEditingController();
    final widthCtrl = TextEditingController();
    final heightCtrl = TextEditingController();
    final priceCtrl = TextEditingController(text: '0');
    String schemeId = _schemes.first['id'] as String;
    String itemType = _itemTypeOptions.first;
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          backgroundColor: _cardBg,
          title:
              const Text('添加软装单品', style: TextStyle(color: _textPrimary)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  value: schemeId,
                  dropdownColor: _cardBg,
                  style: const TextStyle(color: _textPrimary),
                  decoration: _inputDecoration('所属方案'),
                  items: _schemes
                      .map((s) => DropdownMenuItem(
                            value: s['id'] as String,
                            child: Text(
                                '${s['room_name']} · ${s['style']}'),
                          ))
                      .toList(),
                  onChanged: (v) => setState(() => schemeId = v ?? schemeId),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: itemType,
                  dropdownColor: _cardBg,
                  style: const TextStyle(color: _textPrimary),
                  decoration: _inputDecoration('品类'),
                  items: _itemTypeOptions
                      .map((t) => DropdownMenuItem(value: t, child: Text(t)))
                      .toList(),
                  onChanged: (v) =>
                      setState(() => itemType = v ?? itemType),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: nameCtrl,
                  style: const TextStyle(color: _textPrimary),
                  decoration: _inputDecoration('名称'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: materialCtrl,
                  style: const TextStyle(color: _textPrimary),
                  decoration: _inputDecoration('材质'),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: widthCtrl,
                        keyboardType: TextInputType.number,
                        style: const TextStyle(color: _textPrimary),
                        decoration: _inputDecoration('宽(mm)'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextField(
                        controller: heightCtrl,
                        keyboardType: TextInputType.number,
                        style: const TextStyle(color: _textPrimary),
                        decoration: _inputDecoration('高(mm)'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: priceCtrl,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: _textPrimary),
                  decoration: _inputDecoration('价格'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('取消')),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: _brand, foregroundColor: _bg),
              onPressed: () {
                if (nameCtrl.text.isEmpty) return;
                Navigator.pop(ctx);
                final body = <String, dynamic>{
                  'item_type': itemType,
                  'name': nameCtrl.text,
                  'price': double.tryParse(priceCtrl.text) ?? 0,
                };
                if (materialCtrl.text.isNotEmpty) {
                  body['material'] = materialCtrl.text;
                }
                final w = double.tryParse(widthCtrl.text);
                if (w != null) body['width'] = w;
                final h = double.tryParse(heightCtrl.text);
                if (h != null) body['height'] = h;
                _addItem(schemeId, body);
              },
              child: const Text('添加'),
            ),
          ],
        ),
      ),
    );
  }

  void _showAddStorageDialog() {
    if (_schemes.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先创建软装方案')),
      );
      return;
    }
    final roomNameCtrl = TextEditingController();
    final capacityCtrl = TextEditingController(text: '0');
    String schemeId = _schemes.first['id'] as String;
    String storageType = _storageTypeOptions.first;
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          backgroundColor: _cardBg,
          title:
              const Text('添加收纳系统', style: TextStyle(color: _textPrimary)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  value: schemeId,
                  dropdownColor: _cardBg,
                  style: const TextStyle(color: _textPrimary),
                  decoration: _inputDecoration('所属方案'),
                  items: _schemes
                      .map((s) => DropdownMenuItem(
                            value: s['id'] as String,
                            child: Text(
                                '${s['room_name']} · ${s['style']}'),
                          ))
                      .toList(),
                  onChanged: (v) => setState(() => schemeId = v ?? schemeId),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: roomNameCtrl,
                  style: const TextStyle(color: _textPrimary),
                  decoration: _inputDecoration('位置/房间'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: storageType,
                  dropdownColor: _cardBg,
                  style: const TextStyle(color: _textPrimary),
                  decoration: _inputDecoration('类型'),
                  items: _storageTypeOptions
                      .map((t) => DropdownMenuItem(value: t, child: Text(t)))
                      .toList(),
                  onChanged: (v) =>
                      setState(() => storageType = v ?? storageType),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: capacityCtrl,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: _textPrimary),
                  decoration: _inputDecoration('容量(L)'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('取消')),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: _brand, foregroundColor: _bg),
              onPressed: () {
                if (roomNameCtrl.text.isEmpty) return;
                Navigator.pop(ctx);
                _addStorage(schemeId, {
                  'room_name': roomNameCtrl.text,
                  'storage_type': storageType,
                  'total_capacity_l':
                      double.tryParse(capacityCtrl.text) ?? 0,
                });
              },
              child: const Text('添加'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _bg,
        title: const Text('软装搭配', style: TextStyle(color: _textPrimary)),
        iconTheme: const IconThemeData(color: _textPrimary),
        bottom: TabBar(
          controller: _tabController,
          labelColor: _brand,
          unselectedLabelColor: _textSecondary,
          indicatorColor: _brand,
          tabs: const [
            Tab(text: '软装方案'),
            Tab(text: '软装单品'),
            Tab(text: '收纳系统'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSchemesTab(),
          _buildItemsTab(),
          _buildStoragesTab(),
        ],
      ),
    );
  }

  Widget _buildSchemesTab() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: _brand));
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_error!, style: const TextStyle(color: _textSecondary)),
            const SizedBox(height: 16),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: _brand, foregroundColor: _bg),
              onPressed: _loadAll,
              child: const Text('重试'),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      color: _brand,
      onRefresh: _loadAll,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _schemes.length + 1,
        itemBuilder: (context, index) {
          if (index == _schemes.length) {
            return Padding(
              padding: const EdgeInsets.only(top: 16),
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                    backgroundColor: _brand, foregroundColor: _bg),
                onPressed: _showCreateSchemeDialog,
                icon: const Icon(Icons.add),
                label: const Text('创建软装方案'),
              ),
            );
          }
          final scheme = _schemes[index] as Map<String, dynamic>;
          return _buildSchemeCard(scheme);
        },
      ),
    );
  }

  Widget _buildSchemeCard(Map<String, dynamic> scheme) {
    final colorScheme = scheme['color_scheme'] as Map<String, dynamic>?;
    final budgetTotal =
        (scheme['budget_total'] as num?)?.toDouble() ?? 0;
    final budgetUsed =
        (scheme['budget_used'] as num?)?.toDouble() ?? 0;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _cardBg,
        border: Border.all(color: _border),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  scheme['room_name'] ?? '',
                  style: const TextStyle(
                      color: _textPrimary,
                      fontSize: 16,
                      fontWeight: FontWeight.bold),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline,
                    color: _textSecondary, size: 20),
                onPressed: () =>
                    _deleteScheme(scheme['id'] as String),
              ),
            ],
          ),
          const SizedBox(height: 8),
          _infoRow('风格', scheme['style'] ?? ''),
          if (colorScheme != null && colorScheme.isNotEmpty) ...[
            const SizedBox(height: 4),
            _infoRow('色彩方案', colorScheme.toString()),
          ],
          const SizedBox(height: 4),
          _infoRow('预算',
              '¥${budgetTotal.toStringAsFixed(0)}（已用 ¥${budgetUsed.toStringAsFixed(0)}）'),
        ],
      ),
    );
  }

  Widget _buildItemsTab() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: _brand));
    }
    if (_items.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.chair, size: 64, color: _textSecondary),
            const SizedBox(height: 16),
            const Text('暂无单品', style: TextStyle(color: _textSecondary)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                  backgroundColor: _brand, foregroundColor: _bg),
              onPressed: _showAddItemDialog,
              icon: const Icon(Icons.add),
              label: const Text('添加单品'),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      color: _brand,
      onRefresh: _loadAll,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _items.length + 1,
        itemBuilder: (context, index) {
          if (index == _items.length) {
            return Padding(
              padding: const EdgeInsets.only(top: 16),
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                    backgroundColor: _brand, foregroundColor: _bg),
                onPressed: _showAddItemDialog,
                icon: const Icon(Icons.add),
                label: const Text('添加单品'),
              ),
            );
          }
          final item = _items[index] as Map<String, dynamic>;
          return _buildItemCard(item);
        },
      ),
    );
  }

  Widget _buildItemCard(Map<String, dynamic> item) {
    final width = (item['width'] as num?)?.toDouble();
    final height = (item['height'] as num?)?.toDouble();
    final price = (item['price'] as num?)?.toDouble() ?? 0;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _cardBg,
        border: Border.all(color: _border),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            item['name'] ?? '',
            style: const TextStyle(
                color: _textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          _infoRow('品类', item['item_type'] ?? ''),
          if (item['material'] != null) ...[
            const SizedBox(height: 4),
            _infoRow('材质', item['material'].toString()),
          ],
          if (width != null || height != null) ...[
            const SizedBox(height: 4),
            _infoRow('尺寸',
                '${width?.toStringAsFixed(0) ?? '-'} × ${height?.toStringAsFixed(0) ?? '-'} mm'),
          ],
          const SizedBox(height: 4),
          _infoRow('价格', '¥${price.toStringAsFixed(0)}'),
        ],
      ),
    );
  }

  Widget _buildStoragesTab() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: _brand));
    }
    if (_storages.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.inventory_2, size: 64, color: _textSecondary),
            const SizedBox(height: 16),
            const Text('暂无收纳', style: TextStyle(color: _textSecondary)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                  backgroundColor: _brand, foregroundColor: _bg),
              onPressed: _showAddStorageDialog,
              icon: const Icon(Icons.add),
              label: const Text('添加收纳'),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      color: _brand,
      onRefresh: _loadAll,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _storages.length + 1,
        itemBuilder: (context, index) {
          if (index == _storages.length) {
            return Padding(
              padding: const EdgeInsets.only(top: 16),
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                    backgroundColor: _brand, foregroundColor: _bg),
                onPressed: _showAddStorageDialog,
                icon: const Icon(Icons.add),
                label: const Text('添加收纳'),
              ),
            );
          }
          final storage = _storages[index] as Map<String, dynamic>;
          return _buildStorageCard(storage);
        },
      ),
    );
  }

  Widget _buildStorageCard(Map<String, dynamic> storage) {
    final capacity =
        (storage['total_capacity_l'] as num?)?.toDouble() ?? 0;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _cardBg,
        border: Border.all(color: _border),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            storage['storage_type'] ?? '',
            style: const TextStyle(
                color: _textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          _infoRow('位置', storage['room_name'] ?? ''),
          _infoRow('类型', storage['storage_type'] ?? ''),
          const SizedBox(height: 4),
          _infoRow('容量', '${capacity.toStringAsFixed(0)} L'),
        ],
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 64,
          child: Text(label,
              style:
                  const TextStyle(color: _textSecondary, fontSize: 13)),
        ),
        Expanded(
            child: Text(value,
                style: const TextStyle(color: _textPrimary, fontSize: 13))),
      ],
    );
  }
}
