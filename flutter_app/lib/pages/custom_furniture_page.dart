import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';
import '../widgets/floor_plan_canvas.dart';

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
  String? _selectedDesignId;

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
    _tabController = TabController(length: 4, vsync: this);
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

  // ── Tab4: 布局图 ──

  /// 模块类型 -> 颜色映射
  static Color _moduleColor(String moduleType) {
    switch (moduleType.toLowerCase()) {
      case 'top_panel':
      case 'top':
        return Colors.amber;
      case 'bottom_panel':
      case 'bottom':
      case 'base':
        return Colors.brown;
      case 'side_panel':
      case 'side':
      case 'left_panel':
      case 'right_panel':
        return Colors.grey;
      case 'back_panel':
      case 'back':
        return Colors.blueGrey;
      case 'shelf':
        return Colors.blue;
      case 'drawer':
        return Colors.orange;
      case 'door':
        return Colors.green;
      default:
        return Colors.purple;
    }
  }

  Widget _buildLayoutCanvasTab(ColorScheme colors) {
    if (_selectedDesignId == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.grid_view, size: 48, color: colors.onSurfaceVariant),
            const SizedBox(height: 12),
            Text('请先在"设计方案"中选择一个设计',
                style: TextStyle(color: colors.onSurfaceVariant, fontSize: 14)),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: () => _tabController.animateTo(0),
              icon: const Icon(Icons.arrow_back),
              label: const Text('去选择设计'),
            ),
          ],
        ),
      );
    }

    final design = _designs.firstWhere(
      (d) => (d['id'] ?? '').toString() == _selectedDesignId,
      orElse: () => <String, dynamic>{},
    );

    if (design.isEmpty) {
      return Center(
        child: Text('设计数据加载中...',
            style: TextStyle(color: colors.onSurfaceVariant)),
      );
    }

    // 房间尺寸：优先 width_override/depth_override，否则使用设计的 width/depth
    final roomW = (design['width_override'] as num?)?.toDouble() ??
        (design['width'] as num?)?.toDouble() ??
        2400;
    final roomH = (design['depth_override'] as num?)?.toDouble() ??
        (design['depth'] as num?)?.toDouble() ??
        600;
    final designName = _typeLabels[design['type']] ?? design['type'] ?? '设计方案';

    // 将家具模块转换为 FloorPlanComponent
    final List<FloorPlanComponent> components = [];
    final modules = design['modules'] as List<dynamic>? ?? [];

    if (modules.isNotEmpty) {
      for (int i = 0; i < modules.length; i++) {
        final module = modules[i] as Map<String, dynamic>;
        final moduleType = (module['module_type'] ?? module['type'] ?? '').toString();
        final moduleName = (module['name'] ?? moduleType).toString();
        final mw = (module['width'] as num?)?.toDouble() ?? 200;
        final mh = (module['height'] as num?)?.toDouble() ?? 200;
        final px = (module['position_x'] as num?)?.toDouble() ??
            (module['x'] as num?)?.toDouble() ??
            (i * 250.0 % roomW);
        final py = (module['position_y'] as num?)?.toDouble() ??
            (module['y'] as num?)?.toDouble() ??
            ((i * 250.0 ~/ roomW) * 250.0);

        components.add(FloorPlanComponent(
          id: (module['id'] ?? 'module_$i').toString(),
          label: moduleName,
          type: moduleType,
          x: px,
          y: py,
          width: mw,
          height: mh,
          color: _moduleColor(moduleType),
        ));
      }
    }

    // 如果没有模块数据，使用拆解后的面板数据
    if (components.isEmpty) {
      final panels = design['panels'] as List<dynamic>? ?? [];
      for (int i = 0; i < panels.length; i++) {
        final panel = panels[i] as Map<String, dynamic>;
        final panelType = (panel['type'] ?? panel['panel_type'] ?? '').toString();
        final panelName = (panel['name'] ?? panelType).toString();
        final pw = (panel['width'] as num?)?.toDouble() ?? 200;
        final ph = (panel['height'] as num?)?.toDouble() ?? 200;
        final px = (panel['position_x'] as num?)?.toDouble() ?? (i * 250.0 % roomW);
        final py = (panel['position_y'] as num?)?.toDouble() ?? ((i * 250.0 ~/ roomW) * 250.0);

        components.add(FloorPlanComponent(
          id: (panel['id'] ?? 'panel_$i').toString(),
          label: panelName,
          type: panelType,
          x: px,
          y: py,
          width: pw,
          height: ph,
          color: _moduleColor(panelType),
        ));
      }
    }

    // BOM 摘要信息栏
    return Column(
      children: [
        // 信息栏 + BOM 摘要 + 图例
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Card(
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.grid_view, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        '$designName · 布局图',
                        style: const TextStyle(
                            fontWeight: FontWeight.w600, fontSize: 15),
                      ),
                      const Spacer(),
                      Text(
                        '${components.length} 个模块',
                        style: TextStyle(
                            color: colors.onSurfaceVariant, fontSize: 13),
                      ),
                    ],
                  ),
                  // BOM 摘要
                  const SizedBox(height: 6),
                  const Divider(height: 1),
                  const SizedBox(height: 6),
                  _buildBomSummary(design),
                  const SizedBox(height: 6),
                  const Divider(height: 1),
                  const SizedBox(height: 6),
                  // 图例
                  Wrap(
                    spacing: 12,
                    runSpacing: 4,
                    children: [
                      _buildModuleLegend(Colors.amber, '顶板'),
                      _buildModuleLegend(Colors.brown, '底板'),
                      _buildModuleLegend(Colors.grey, '侧板'),
                      _buildModuleLegend(Colors.blueGrey, '背板'),
                      _buildModuleLegend(Colors.blue, '层板'),
                      _buildModuleLegend(Colors.orange, '抽屉'),
                      _buildModuleLegend(Colors.green, '门板'),
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
              roomHeight: math.max(roomH, 600),
              roomLabel: '$designName Layout',
              showDimensions: true,
              showGrid: true,
              showMEPLayer: false,
              components: components,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildBomSummary(Map<String, dynamic> design) {
    // 如果没有 BOM 数据，尝试显示尺寸信息
    final w = design['width'] ?? '-';
    final d = design['depth'] ?? '-';
    final h = design['height'] ?? '-';
    final material = design['material'] ?? '-';

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceAround,
      children: [
        _buildSummaryChip('尺寸', '${w}×${d}×${h}'),
        _buildSummaryChip('材质', material.toString()),
        _buildSummaryChip('类型', _typeLabels[design['type']] ?? design['type'] ?? '-'),
      ],
    );
  }

  Widget _buildSummaryChip(String label, String value) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(label,
            style: const TextStyle(fontSize: 11, color: Colors.grey)),
        const SizedBox(height: 2),
        Text(value,
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
      ],
    );
  }

  Widget _buildModuleLegend(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
      ],
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
            Tab(text: '布局图'),
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
                    _buildLayoutCanvasTab(colors),
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
        final id = (d['id'] ?? '').toString();
        final isSelected = _selectedDesignId == id;
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(
              color: isSelected ? Theme.of(context).colorScheme.primary : Colors.transparent,
              width: isSelected ? 2 : 0,
            ),
          ),
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
                    if (isSelected)
                      const Icon(Icons.check_circle, color: Colors.green, size: 18),
                    const SizedBox(width: 4),
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
                      onPressed: () {
                        setState(() => _selectedDesignId = id);
                        _tabController.animateTo(3);
                      },
                      icon: const Icon(Icons.grid_view, size: 18),
                      label: const Text('布局'),
                    ),
                    const SizedBox(width: 8),
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
