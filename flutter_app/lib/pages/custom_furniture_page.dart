import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// 定制家具页面 (F27) — 参数化设计/板材/拆单 BOM/价格估算
class CustomFurniturePage extends StatefulWidget {
  final String projectId;
  const CustomFurniturePage({super.key, required this.projectId});

  @override
  State<CustomFurniturePage> createState() => _CustomFurniturePageState();
}

class _CustomFurniturePageState extends State<CustomFurniturePage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  List<dynamic> _designs = [];
  bool _loading = false;
  String? _error;

  static const _typeLabels = {
    'wardrobe': '衣柜',
    'cabinet': '橱柜',
    'shoe_cabinet': '鞋柜',
    'bookcase': '书柜',
    'tatami': '榻榻米',
    'tv_cabinet': '电视柜',
    'sideboard': '餐边柜',
    'balcony_cabinet': '阳台柜',
    'bathroom_cabinet': '浴室柜',
    'wine_cabinet': '酒柜',
    'cloakroom': '衣帽间',
  };

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadDesigns();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadDesigns() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.getList('/custom-furniture/designs/${widget.projectId}');
    if (result.isSuccess) {
      _designs = result.data;
    } else {
      _error = '加载定制家具数据失败';
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _createDesign() async {
    final result = await _api.post('/custom-furniture/designs', {
      'project_id': widget.projectId,
      'type': 'wardrobe',
      'width': 2400.0,
      'depth': 600.0,
      'height': 2700.0,
      'material': '颗粒板',
    });
    if (result.isSuccess) {
      await _loadDesigns();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('定制方案已创建')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('创建失败：${result.error}')),
        );
      }
    }
  }

  Future<void> _viewBom(String designId) async {
    final result = await _api.get('/custom-furniture/designs/$designId/bom');
    if (result.isSuccess && mounted) {
      _showBomDialog(result.data);
    }
  }

  Future<void> _viewPrice(String designId) async {
    final result = await _api.get('/custom-furniture/designs/$designId/price');
    if (result.isSuccess && mounted) {
      _showPriceDialog(result.data);
    }
  }

  void _showBomDialog(dynamic data) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('拆单 BOM'),
        content: SizedBox(
          width: double.maxFinite,
          child: data is List && (data as List).isNotEmpty
              ? SingleChildScrollView(
                  child: DataTable(
                    columns: const [
                      DataColumn(label: Text('部件')),
                      DataColumn(label: Text('规格')),
                      DataColumn(label: Text('数量')),
                    ],
                    rows: (data as List).map<DataRow>((item) {
                      return DataRow(cells: [
                        DataCell(Text(item['name'] ?? '')),
                        DataCell(Text(item['spec'] ?? '')),
                        DataCell(Text('${item['quantity'] ?? 0}')),
                      ]);
                    }).toList(),
                  ),
                )
              : const Text('暂无 BOM 数据'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('关闭')),
        ],
      ),
    );
  }

  void _showPriceDialog(dynamic data) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('价格估算'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _priceRow('板材费', data['material_cost'] ?? 0),
            _priceRow('五金费', data['hardware_cost'] ?? 0),
            _priceRow('加工费', data['labor_cost'] ?? 0),
            _priceRow('安装费', data['install_cost'] ?? 0),
            const Divider(),
            _priceRow('合计', data['total_price'] ?? 0, bold: true),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('关闭')),
        ],
      ),
    );
  }

  Widget _priceRow(String label, dynamic amount, {bool bold = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(fontWeight: bold ? FontWeight.bold : FontWeight.normal)),
          Text('¥${(amount is num ? amount.toDouble() : 0.0).toStringAsFixed(2)}',
              style: TextStyle(fontWeight: bold ? FontWeight.bold : FontWeight.normal,
                  color: bold ? Theme.of(context).colorScheme.primary : null)),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('定制家具'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: '设计方案'),
            Tab(text: '参数化'),
            Tab(text: '拆单BOM'),
          ],
        ),
        actions: [
          IconButton(icon: const Icon(Icons.add), onPressed: _createDesign),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadDesigns),
        ],
      ),
      body: _loading
          ? const LoadingSkeleton(itemCount: 3, itemHeight: 160)
          : _error != null
              ? ErrorRetryWidget(message: _error!, onRetry: _loadDesigns)
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildDesignList(colors),
                    _buildParametricPanel(colors),
                    _buildBomPanel(colors),
                  ],
                ),
    );
  }

  Widget _buildDesignList(ColorScheme colors) {
    if (_designs.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.carpenter, size: 48, color: colors.onSurfaceVariant),
            const SizedBox(height: 12),
            Text('暂无定制方案', style: TextStyle(color: colors.onSurfaceVariant)),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _createDesign,
              icon: const Icon(Icons.add),
              label: const Text('新建定制方案'),
            ),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _designs.length,
      itemBuilder: (_, i) {
        final d = _designs[i];
        final type = _typeLabels[d['type']] ?? d['type'] ?? '未知类型';
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(type, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                    ),
                    Chip(label: Text(d['material'] ?? '', style: const TextStyle(fontSize: 11))),
                  ],
                ),
                const SizedBox(height: 6),
                Text('尺寸: ${d['width'] ?? '-'} × ${d['depth'] ?? '-'} × ${d['height'] ?? '-'} mm',
                    style: TextStyle(color: colors.onSurfaceVariant, fontSize: 13)),
                const SizedBox(height: 10),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton.icon(
                      onPressed: () => _viewBom(d['id']),
                      icon: const Icon(Icons.list_alt, size: 18),
                      label: const Text('BOM'),
                    ),
                    const SizedBox(width: 8),
                    TextButton.icon(
                      onPressed: () => _viewPrice(d['id']),
                      icon: const Icon(Icons.attach_money, size: 18),
                      label: const Text('价格'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildParametricPanel(ColorScheme colors) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.tune, size: 48, color: Color(0xFF7C5CFC)),
          const SizedBox(height: 16),
          Text('参数化定制', textAlign: TextAlign.center,
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: colors.primary)),
          const SizedBox(height: 8),
          Text('选择家具类型，调整参数尺寸，自动生成设计方案和拆单 BOM',
              textAlign: TextAlign.center,
              style: TextStyle(color: colors.onSurfaceVariant, fontSize: 14)),
          const SizedBox(height: 24),
          ..._typeLabels.entries.map((e) => ListTile(
            leading: const Icon(Icons.chevron_right),
            title: Text(e.value),
            trailing: const Icon(Icons.arrow_forward_ios, size: 14),
            onTap: _createDesign,
          )),
        ],
      ),
    );
  }

  Widget _buildBomPanel(ColorScheme colors) {
    if (_designs.isEmpty) {
      return Center(
        child: Text('请先创建设计方案', style: TextStyle(color: colors.onSurfaceVariant)),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _designs.length,
      itemBuilder: (_, i) {
        final d = _designs[i];
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            title: Text(_typeLabels[d['type']] ?? d['type'] ?? ''),
            subtitle: Text('${d['width']}×${d['depth']}×${d['height']} mm'),
            trailing: ElevatedButton(
              onPressed: () => _viewBom(d['id']),
              child: const Text('查看BOM'),
            ),
          ),
        );
      },
    );
  }
}
