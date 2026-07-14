import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

class StructuralPage extends StatefulWidget {
  final String projectId;
  const StructuralPage({super.key, required this.projectId});

  @override
  State<StructuralPage> createState() => _StructuralPageState();
}

class _StructuralPageState extends State<StructuralPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  // 暗色主题色
  static const _bg = Color(0xFF08080F);
  static const _cardColor = Color(0xFF12121D);
  static const _brand = Color(0xFFC9973B);
  static const _border = Color(0xFF1E1E32);
  static const _textMain = Color(0xFFE8E6E1);
  static const _textSub = Color(0xFF8A8894);

  List<dynamic> _walls = [];
  List<dynamic> _beams = [];
  List<dynamic> _columns = [];
  List<dynamic> _slabs = [];
  List<dynamic> _quantities = [];
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
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
    final results = await Future.wait([
      _api.structuralListWalls(widget.projectId),
      _api.structuralListBeams(widget.projectId),
      _api.structuralListColumns(widget.projectId),
      _api.structuralListSlabs(widget.projectId),
      _api.structuralListQuantityCalcs(widget.projectId),
    ]);
    final networkErr =
        results.where((r) => !r.isSuccess && r.isNetworkError).toList();
    if (networkErr.isNotEmpty) {
      setState(() => _error = '加载失败，请检查网络后重试');
    } else {
      setState(() {
        _walls = _asList(results[0]);
        _beams = _asList(results[1]);
        _columns = _asList(results[2]);
        _slabs = _asList(results[3]);
        _quantities = _asList(results[4]);
      });
    }
    setState(() => _loading = false);
  }

  List<dynamic> _asList(Result<dynamic> r) {
    if (!r.isSuccess) return [];
    final data = r.data;
    if (data is List) return data;
    return [];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _bg,
        foregroundColor: _textMain,
        title: const Text('土建结构'),
        bottom: TabBar(
          controller: _tabController,
          labelColor: _brand,
          unselectedLabelColor: _textSub,
          indicatorColor: _brand,
          tabs: const [
            Tab(text: '承重墙'),
            Tab(text: '梁/柱'),
            Tab(text: '楼板'),
            Tab(text: '工程量'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildWalls(),
          _buildBeamsColumns(),
          _buildSlabs(),
          _buildQuantities(),
        ],
      ),
    );
  }

  // ── 通用组件 ──

  Widget _card({required Widget child}) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _border),
      ),
      child: child,
    );
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: _textSub, fontSize: 13)),
          Flexible(
            child: Text(
              value,
              style: const TextStyle(color: _textMain, fontSize: 13),
              textAlign: TextAlign.right,
            ),
          ),
        ],
      ),
    );
  }

  Widget _sectionTitle(String text) {
    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 8),
      child: Text(text,
          style: const TextStyle(
              color: _textMain, fontSize: 15, fontWeight: FontWeight.bold)),
    );
  }

  Widget _emptyHint(String text, {VoidCallback? onAdd, String? addLabel}) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.foundation, size: 56, color: _textSub),
          const SizedBox(height: 12),
          Text(text, style: const TextStyle(color: _textSub, fontSize: 14)),
          if (onAdd != null && addLabel != null) ...[
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: onAdd,
              icon: const Icon(Icons.add, size: 18, color: _brand),
              label: Text(addLabel,
                  style: const TextStyle(color: _brand)),
              style: OutlinedButton.styleFrom(
                side: const BorderSide(color: _brand),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _addButton(String label, VoidCallback onPressed) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: onPressed,
        icon: const Icon(Icons.add, size: 18),
        label: Text(label),
        style: ElevatedButton.styleFrom(
          backgroundColor: _brand,
          foregroundColor: _bg,
          padding: const EdgeInsets.symmetric(vertical: 12),
        ),
      ),
    );
  }

  // ── 承重墙 ──

  Widget _buildWalls() {
    if (_loading) return const LoadingSkeleton(itemCount: 3, itemHeight: 110);
    if (_error != null) return ErrorRetryWidget(message: _error!, onRetry: _loadAll);
    if (_walls.isEmpty) {
      return _emptyHint('暂无承重墙', onAdd: _addWall, addLabel: '添加承重墙');
    }
    return RefreshIndicator(
      onRefresh: _loadAll,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ..._walls.map((w) => _card(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(w['wall_name'] ?? '',
                              style: const TextStyle(
                                  color: _textMain,
                                  fontSize: 15,
                                  fontWeight: FontWeight.bold)),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: w['is_load_bearing'] == true
                                ? _brand.withValues(alpha: 0.15)
                                : _border,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            w['is_load_bearing'] == true ? '承重' : '非承重',
                            style: TextStyle(
                              color: w['is_load_bearing'] == true
                                  ? _brand
                                  : _textSub,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    _row('厚度', '${w['thickness_mm'] ?? '—'} mm'),
                    _row('材质', '${w['material'] ?? '—'}'),
                    _row('承载力', w['is_load_bearing'] == true ? '承重结构' : '非承重'),
                  ],
                ),
              )),
          const SizedBox(height: 8),
          _addButton('添加承重墙', _addWall),
        ],
      ),
    );
  }

  // ── 梁/柱 ──

  Widget _buildBeamsColumns() {
    if (_loading) return const LoadingSkeleton(itemCount: 3, itemHeight: 110);
    if (_error != null) return ErrorRetryWidget(message: _error!, onRetry: _loadAll);
    if (_beams.isEmpty && _columns.isEmpty) {
      return _emptyHint('暂无梁/柱数据');
    }
    return RefreshIndicator(
      onRefresh: _loadAll,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _sectionTitle('梁'),
          if (_beams.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text('暂无梁', style: TextStyle(color: _textSub, fontSize: 13)),
            )
          else
            ..._beams.map((b) => _card(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(b['beam_name'] ?? '',
                          style: const TextStyle(
                              color: _textMain,
                              fontSize: 15,
                              fontWeight: FontWeight.bold)),
                      const SizedBox(height: 8),
                      _row('编号', '${b['beam_name'] ?? '—'}'),
                      _row('截面尺寸',
                          '${b['width_mm'] ?? '—'}×${b['height_mm'] ?? '—'} mm'),
                      _row('长度', '${b['length_m'] ?? '—'} m'),
                      _row('材质', '${b['material'] ?? '—'}'),
                    ],
                  ),
                )),
          const SizedBox(height: 8),
          _addButton('添加梁', _addBeam),
          _sectionTitle('柱'),
          if (_columns.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text('暂无柱', style: TextStyle(color: _textSub, fontSize: 13)),
            )
          else
            ..._columns.map((c) => _card(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(c['column_name'] ?? '',
                          style: const TextStyle(
                              color: _textMain,
                              fontSize: 15,
                              fontWeight: FontWeight.bold)),
                      const SizedBox(height: 8),
                      _row('编号', '${c['column_name'] ?? '—'}'),
                      _row('截面尺寸',
                          '${c['width_mm'] ?? '—'}×${c['depth_mm'] ?? '—'} mm'),
                      _row('高度', '${c['height_m'] ?? '—'} m'),
                      _row('材质', '${c['material'] ?? '—'}'),
                    ],
                  ),
                )),
          const SizedBox(height: 8),
          _addButton('添加柱', _addColumn),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  // ── 楼板 ──

  Widget _buildSlabs() {
    if (_loading) return const LoadingSkeleton(itemCount: 3, itemHeight: 110);
    if (_error != null) return ErrorRetryWidget(message: _error!, onRetry: _loadAll);
    if (_slabs.isEmpty) {
      return _emptyHint('暂无楼板');
    }
    return RefreshIndicator(
      onRefresh: _loadAll,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ..._slabs.map((s) {
            final rebar = (s['rebar_diameter_mm'] != null)
                ? 'Φ${s['rebar_diameter_mm']}@${s['rebar_spacing_mm'] ?? '—'}'
                : '—';
            return _card(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(s['slab_name'] ?? '',
                      style: const TextStyle(
                          color: _textMain,
                          fontSize: 15,
                          fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  _row('位置', '${s['slab_name'] ?? '—'}'),
                  _row('厚度', '${s['thickness_mm'] ?? '—'} mm'),
                  _row('面积', '${s['area_m2'] ?? '—'} m²'),
                  _row('配筋', rebar),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  // ── 工程量 ──

  Widget _buildQuantities() {
    if (_loading) return const LoadingSkeleton(itemCount: 3, itemHeight: 110);
    if (_error != null) return ErrorRetryWidget(message: _error!, onRetry: _loadAll);
    if (_quantities.isEmpty) {
      return _emptyHint('暂无工程量数据');
    }
    return RefreshIndicator(
      onRefresh: _loadAll,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ..._quantities.map((q) => _card(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(q['calc_name'] ?? '',
                              style: const TextStyle(
                                  color: _textMain,
                                  fontSize: 15,
                                  fontWeight: FontWeight.bold)),
                        ),
                        Text('¥${q['total_cost'] ?? 0}',
                            style: const TextStyle(
                                color: _brand, fontWeight: FontWeight.bold)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text('${q['calc_type'] ?? '—'} · ${q['status'] ?? '—'}',
                        style: const TextStyle(color: _textSub, fontSize: 12)),
                    const SizedBox(height: 8),
                    _row('混凝土', '${q['concrete_m3'] ?? '—'} m³'),
                    _row('钢筋', '${q['rebar_kg'] ?? '—'} kg'),
                    _row('砖块', '${q['brick_count'] ?? '—'} 块'),
                    _row('砂浆', '${q['mortar_m3'] ?? '—'} m³'),
                    _row('模板', '${q['formwork_m2'] ?? '—'} m²'),
                    _row('墙体体积', '${q['wall_volume_m3'] ?? '—'} m³'),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  // ── 添加对话框 ──

  Future<void> _addWall() async {
    final body = await _showFormDialog('添加承重墙', [
      const _Field('wall_name', '位置/名称', required: true),
      const _Field('thickness_mm', '厚度(mm)',
          isNumber: true, intField: true, initial: '240'),
      const _Field('material', '材质'),
      const _Field('length_m', '长度(m)', isNumber: true, initial: '0'),
      const _Field('height_m', '高度(m)', isNumber: true, initial: '2.8'),
    ]);
    if (body == null) return;
    final result = await _api.structuralCreateWall(body);
    _handleCreateResult(result, '承重墙');
  }

  Future<void> _addBeam() async {
    final body = await _showFormDialog('添加梁', [
      const _Field('beam_name', '编号', required: true),
      const _Field('width_mm', '宽(mm)',
          isNumber: true, intField: true, initial: '200'),
      const _Field('height_mm', '高(mm)',
          isNumber: true, intField: true, initial: '400'),
      const _Field('length_m', '长度(m)', isNumber: true, initial: '0'),
      const _Field('material', '材质',
          required: true, initial: 'reinforced_concrete'),
    ]);
    if (body == null) return;
    final result = await _api.structuralCreateBeam(body);
    _handleCreateResult(result, '梁');
  }

  Future<void> _addColumn() async {
    final body = await _showFormDialog('添加柱', [
      const _Field('column_name', '编号', required: true),
      const _Field('width_mm', '宽(mm)',
          isNumber: true, intField: true, initial: '300'),
      const _Field('depth_mm', '深(mm)',
          isNumber: true, intField: true, initial: '300'),
      const _Field('height_m', '高度(m)', isNumber: true, initial: '2.8'),
      const _Field('material', '材质',
          required: true, initial: 'reinforced_concrete'),
    ]);
    if (body == null) return;
    final result = await _api.structuralCreateColumn(body);
    _handleCreateResult(result, '柱');
  }

  void _handleCreateResult(Result<dynamic> result, String label) {
    if (!mounted) return;
    if (result.isSuccess) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已添加$label')),
      );
      _loadAll();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('添加失败：${result.error}')),
      );
    }
  }

  Future<Map<String, dynamic>?> _showFormDialog(
    String title,
    List<_Field> fields,
  ) async {
    final controllers = {
      for (final f in fields) f.key: TextEditingController(text: f.initial)
    };
    final formKey = GlobalKey<FormState>();
    return showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: Text(title, style: const TextStyle(color: _textMain)),
        content: SingleChildScrollView(
          child: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: fields
                  .map((f) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        child: TextFormField(
                          controller: controllers[f.key],
                          decoration: InputDecoration(
                            labelText: f.label,
                            labelStyle: const TextStyle(color: _textSub),
                            enabledBorder: const UnderlineInputBorder(
                              borderSide: BorderSide(color: _border),
                            ),
                            focusedBorder: const UnderlineInputBorder(
                              borderSide: BorderSide(color: _brand),
                            ),
                          ),
                          style: const TextStyle(color: _textMain),
                          keyboardType: f.isNumber
                              ? TextInputType.number
                              : TextInputType.text,
                          validator: (v) => f.required &&
                                  (v == null || v.isEmpty)
                              ? '必填'
                              : null,
                        ),
                      ))
                  .toList(),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消', style: TextStyle(color: _textSub)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: _brand,
              foregroundColor: _bg,
            ),
            child: const Text('保存'),
            onPressed: () {
              if (!formKey.currentState!.validate()) return;
              final body = <String, dynamic>{
                'project_id': widget.projectId,
              };
              for (final f in fields) {
                final raw = controllers[f.key]!.text;
                if (f.isNumber) {
                  body[f.key] = f.intField
                      ? (int.tryParse(raw) ?? 0)
                      : (double.tryParse(raw) ?? 0.0);
                } else {
                  body[f.key] = raw.isEmpty ? null : raw;
                }
              }
              Navigator.pop(ctx, body);
            },
          ),
        ],
      ),
    );
  }
}

/// 表单字段配置
class _Field {
  final String key;
  final String label;
  final String initial;
  final bool isNumber;
  final bool intField;
  final bool required;
  const _Field(
    this.key,
    this.label, {
    this.initial = '',
    this.isNumber = false,
    this.intField = false,
    this.required = false,
  });
}
