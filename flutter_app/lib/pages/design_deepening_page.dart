import 'package:flutter/material.dart';
import '../services/api.dart';

/// 设计深化页面 - 整合 F18/F21/F23/F31/F32
/// 5 Tab: 厨卫水电 / 硬装 / 门窗防水 / 智能家居 / 场景编辑
class DesignDeepeningPage extends StatefulWidget {
  final String projectId;
  const DesignDeepeningPage({super.key, required this.projectId});

  @override
  State<DesignDeepeningPage> createState() => _DesignDeepeningPageState();
}

class _DesignDeepeningPageState extends State<DesignDeepeningPage>
    with TickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  static const _brand = Color(0xFFC9973B);
  static const _bg = Color(0xFF08080F);
  static const _card = Color(0xFF12121D);
  static const _textSecondary = Color(0xFF8A8894);

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 5, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _toast(String msg) {
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _card,
        title: const Text('设计深化',
            style: TextStyle(
                fontWeight: FontWeight.bold, fontFamily: 'DM Sans')),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          labelColor: _brand,
          unselectedLabelColor: _textSecondary,
          indicatorColor: _brand,
          tabs: const [
            Tab(text: '厨卫水电'),
            Tab(text: '硬装'),
            Tab(text: '门窗防水'),
            Tab(text: '智能家居'),
            Tab(text: '场景编辑'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _MepTab(api: _api, projectId: widget.projectId, toast: _toast),
          _HardDecoTab(api: _api, projectId: widget.projectId, toast: _toast),
          _DoorWinTab(api: _api, projectId: widget.projectId, toast: _toast),
          _SmartHomeTab(api: _api, projectId: widget.projectId, toast: _toast),
          _SceneTab(api: _api, projectId: widget.projectId, toast: _toast),
        ],
      ),
    );
  }
}

/// 通用空状态
Widget _emptyState(String text, {IconData icon = Icons.inbox_outlined}) {
  return Center(
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(icon, size: 56, color: const Color(0xFF5A5866)),
        const SizedBox(height: 12),
        Text(text, style: const TextStyle(color: Color(0xFF8A8894))),
      ],
    ),
  );
}

Widget _sectionCard({required List<Widget> children}) {
  return Card(
    color: const Color(0xFF12121D),
    margin: const EdgeInsets.only(bottom: 10),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(12),
      side: const BorderSide(color: Color(0xFF1E1E32)),
    ),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    ),
  );
}

Widget _kv(String k, String v) {
  return Padding(
    padding: const EdgeInsets.symmetric(vertical: 2),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 80,
          child: Text(k,
              style: const TextStyle(color: Color(0xFF8A8894), fontSize: 12)),
        ),
        Expanded(
          child: Text(v,
              style: const TextStyle(color: Color(0xFFE8E6E1), fontSize: 13)),
        ),
      ],
    ),
  );
}

// ─────────────────────────────────────────────
// F18 厨卫水电
// ─────────────────────────────────────────────
class _MepTab extends StatefulWidget {
  final ApiClient api;
  final String projectId;
  final void Function(String) toast;
  const _MepTab({required this.api, required this.projectId, required this.toast});

  @override
  State<_MepTab> createState() => _MepTabState();
}

class _MepTabState extends State<_MepTab> with AutomaticKeepAliveClientMixin {
  List<dynamic> _plans = [];
  bool _loading = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await widget.api.mepListPlans(widget.projectId);
      _plans = data is List ? data : (data['items'] as List? ?? []);
    } catch (e) {
      widget.toast('加载水电方案失败: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final name = await _showInputDialog('新建水电方案', '方案名称');
    if (name == null || name.isEmpty) return;
    try {
      await widget.api.mepCreatePlan({
        'project_id': widget.projectId,
        'name': name,
        'status': 'draft',
      });
      widget.toast('已创建');
      _load();
    } catch (e) {
      widget.toast('创建失败: $e');
    }
  }

  Future<void> _viewDetail(String planId) async {
    if (planId.isEmpty) return;
    try {
      final pointsRes = await widget.api.mepListPoints(planId);
      final circuitsRes = await widget.api.mepListCircuits(planId);
      final points = pointsRes is List ? pointsRes : <dynamic>[];
      final circuits = circuitsRes is List ? circuitsRes : <dynamic>[];
      if (!mounted) return;
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          backgroundColor: const Color(0xFF12121D),
          title: const Text('水电方案详情',
              style: TextStyle(color: Color(0xFFE8E6E1))),
          content: SizedBox(
            width: double.maxFinite,
            child: ListView(
              shrinkWrap: true,
              children: [
                Text('点位 (${points.length})',
                    style: const TextStyle(
                        color: Color(0xFFC9973B), fontWeight: FontWeight.w600)),
                ...points.map((p) => ListTile(
                      dense: true,
                      title: Text((p is Map ? p['name'] ?? '' : '').toString(),
                          style: const TextStyle(color: Color(0xFFE8E6E1))),
                      subtitle: Text(
                          (p is Map ? p['type'] ?? '' : '').toString(),
                          style: const TextStyle(color: Color(0xFF8A8894))),
                    )),
                const Divider(),
                Text('回路 (${circuits.length})',
                    style: const TextStyle(
                        color: Color(0xFFC9973B), fontWeight: FontWeight.w600)),
                ...circuits.map((c) => ListTile(
                      dense: true,
                      title: Text((c is Map ? c['name'] ?? '' : '').toString(),
                          style: const TextStyle(color: Color(0xFFE8E6E1))),
                      subtitle: Text(
                          (c is Map ? c['load']?.toString() ?? '' : '').toString(),
                          style: const TextStyle(color: Color(0xFF8A8894))),
                    )),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('关闭'),
            ),
          ],
        ),
      );
    } catch (e) {
      widget.toast('加载详情失败: $e');
    }
  }

  Future<void> _delete(String planId) async {
    final ok = await _confirm('删除该水电方案？');
    if (ok != true) return;
    try {
      await widget.api.mepDeletePlan(planId);
      widget.toast('已删除');
      _load();
    } catch (e) {
      widget.toast('删除失败: $e');
    }
  }

  Future<String?> _showInputDialog(String title, String label) {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF12121D),
        title: Text(title, style: const TextStyle(color: Color(0xFFE8E6E1))),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          decoration: InputDecoration(
            labelText: label,
            labelStyle: const TextStyle(color: Color(0xFF8A8894)),
          ),
          style: const TextStyle(color: Color(0xFFE8E6E1)),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
              child: const Text('确定')),
        ],
      ),
    );
  }

  Future<bool?> _confirm(String msg) {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF12121D),
        title: const Text('确认', style: TextStyle(color: Color(0xFFE8E6E1))),
        content: Text(msg, style: const TextStyle(color: Color(0xFF8A8894))),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('确定')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Scaffold(
      body: _buildBody(),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFFC9973B),
        foregroundColor: Colors.black,
        onPressed: _create,
        child: const Icon(Icons.add),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_plans.isEmpty) {
      return RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          children: [
            const SizedBox(height: 120),
            _emptyState('暂无水电方案，点击右下角新建', icon: Icons.water_drop_outlined),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _plans.length,
        itemBuilder: (ctx, i) {
          final p = Map<String, dynamic>.from(_plans[i] as Map);
          return _sectionCard(children: [
            Row(
              children: [
                Expanded(
                  child: Text((p['name'] ?? '水电方案').toString(),
                      style: const TextStyle(
                          color: Color(0xFFE8E6E1),
                          fontWeight: FontWeight.w600,
                          fontSize: 15)),
                ),
                Text((p['status'] ?? '').toString(),
                    style: const TextStyle(color: Color(0xFFC9973B), fontSize: 12)),
              ],
            ),
            const SizedBox(height: 8),
            _kv('方案ID', (p['id'] ?? '-').toString()),
            if (p['room_type'] != null) _kv('空间', p['room_type'].toString()),
            if (p['points_count'] != null)
              _kv('点位数', p['points_count'].toString()),
            if (p['circuits_count'] != null)
              _kv('回路数', p['circuits_count'].toString()),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton.icon(
                  onPressed: () => _viewDetail(p['id']?.toString() ?? ''),
                  icon: const Icon(Icons.visibility_outlined, size: 16),
                  label: const Text('详情'),
                ),
                TextButton.icon(
                  onPressed: () => _delete(p['id']?.toString() ?? ''),
                  icon: const Icon(Icons.delete_outline,
                      size: 16, color: Color(0xFFD9534F)),
                  label: const Text('删除',
                      style: TextStyle(color: Color(0xFFD9534F))),
                ),
              ],
            ),
          ]);
        },
      ),
    );
  }
}

// ─────────────────────────────────────────────
// F21 硬装
// ─────────────────────────────────────────────
class _HardDecoTab extends StatefulWidget {
  final ApiClient api;
  final String projectId;
  final void Function(String) toast;
  const _HardDecoTab({required this.api, required this.projectId, required this.toast});

  @override
  State<_HardDecoTab> createState() => _HardDecoTabState();
}

class _HardDecoTabState extends State<_HardDecoTab> with AutomaticKeepAliveClientMixin {
  List<dynamic> _schemes = [];
  bool _loading = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await widget.api.hardDecoListSchemes(widget.projectId);
      _schemes = data is List ? data : (data['items'] as List? ?? []);
    } catch (e) {
      widget.toast('加载硬装方案失败: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final name = await _showInputDialog('新建硬装方案', '方案名称');
    if (name == null || name.isEmpty) return;
    try {
      await widget.api.hardDecoCreateScheme({
        'project_id': widget.projectId,
        'name': name,
        'style': 'modern',
      });
      widget.toast('已创建');
      _load();
    } catch (e) {
      widget.toast('创建失败: $e');
    }
  }

  Future<String?> _showInputDialog(String title, String label) {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF12121D),
        title: Text(title, style: const TextStyle(color: Color(0xFFE8E6E1))),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          decoration: InputDecoration(
            labelText: label,
            labelStyle: const TextStyle(color: Color(0xFF8A8894)),
          ),
          style: const TextStyle(color: Color(0xFFE8E6E1)),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
              child: const Text('确定')),
        ],
      ),
    );
  }

  Future<void> _viewDetail(String schemeId) async {
    if (schemeId.isEmpty) return;
    try {
      final floorsRes = await widget.api.hardDecoListFloors(schemeId);
      final wallsRes = await widget.api.hardDecoListWalls(schemeId);
      final floors = floorsRes is List ? floorsRes : <dynamic>[];
      final walls = wallsRes is List ? wallsRes : <dynamic>[];
      if (!mounted) return;
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          backgroundColor: const Color(0xFF12121D),
          title: const Text('硬装明细',
              style: TextStyle(color: Color(0xFFE8E6E1))),
          content: SizedBox(
            width: double.maxFinite,
            child: ListView(
              shrinkWrap: true,
              children: [
                Text('地面 (${floors.length})',
                    style: const TextStyle(
                        color: Color(0xFFC9973B), fontWeight: FontWeight.w600)),
                ...floors.map((f) => ListTile(
                      dense: true,
                      title: Text((f is Map ? f['material'] ?? '' : '').toString(),
                          style: const TextStyle(color: Color(0xFFE8E6E1))),
                      subtitle: Text(
                          (f is Map ? f['area']?.toString() ?? '' : '').toString(),
                          style: const TextStyle(color: Color(0xFF8A8894))),
                    )),
                const Divider(),
                Text('墙面 (${walls.length})',
                    style: const TextStyle(
                        color: Color(0xFFC9973B), fontWeight: FontWeight.w600)),
                ...walls.map((w) => ListTile(
                      dense: true,
                      title: Text((w is Map ? w['material'] ?? '' : '').toString(),
                          style: const TextStyle(color: Color(0xFFE8E6E1))),
                    )),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('关闭'),
            ),
          ],
        ),
      );
    } catch (e) {
      widget.toast('加载明细失败: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _schemes.isEmpty
              ? RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    children: [
                      const SizedBox(height: 120),
                      _emptyState('暂无硬装方案，点击右下角新建',
                          icon: Icons.layers_outlined),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _schemes.length,
                    itemBuilder: (ctx, i) {
                      final s = Map<String, dynamic>.from(_schemes[i] as Map);
                      return _sectionCard(children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text((s['name'] ?? '硬装方案').toString(),
                                  style: const TextStyle(
                                      color: Color(0xFFE8E6E1),
                                      fontWeight: FontWeight.w600,
                                      fontSize: 15)),
                            ),
                            if (s['style'] != null)
                              Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFC9973B)
                                      .withValues(alpha: 0.12),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(s['style'].toString(),
                                    style: const TextStyle(
                                        color: Color(0xFFC9973B), fontSize: 10)),
                              ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        _kv('方案ID', (s['id'] ?? '-').toString()),
                        if (s['total_area'] != null)
                          _kv('总面积', '${s['total_area']}㎡'),
                        if (s['estimated_cost'] != null)
                          _kv('预估成本', '¥${s['estimated_cost']}'),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            TextButton.icon(
                              onPressed: () =>
                                  _viewDetail(s['id']?.toString() ?? ''),
                              icon: const Icon(Icons.visibility_outlined,
                                  size: 16),
                              label: const Text('明细'),
                            ),
                          ],
                        ),
                      ]);
                    },
                  ),
                ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFFC9973B),
        foregroundColor: Colors.black,
        onPressed: _create,
        child: const Icon(Icons.add),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// F23 门窗防水
// ─────────────────────────────────────────────
class _DoorWinTab extends StatefulWidget {
  final ApiClient api;
  final String projectId;
  final void Function(String) toast;
  const _DoorWinTab({required this.api, required this.projectId, required this.toast});

  @override
  State<_DoorWinTab> createState() => _DoorWinTabState();
}

class _DoorWinTabState extends State<_DoorWinTab> with AutomaticKeepAliveClientMixin {
  List<dynamic> _specs = [];
  bool _loading = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await widget.api.doorWinListSpecs(widget.projectId);
      _specs = data is List ? data : (data['items'] as List? ?? []);
    } catch (e) {
      widget.toast('加载门窗规格失败: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final name = await _showInputDialog('新建门窗规格', '位置/名称');
    if (name == null || name.isEmpty) return;
    try {
      await widget.api.doorWinCreateSpec({
        'project_id': widget.projectId,
        'name': name,
        'type': 'door',
      });
      widget.toast('已创建');
      _load();
    } catch (e) {
      widget.toast('创建失败: $e');
    }
  }

  Future<void> _validate(String specId) async {
    try {
      final result = await widget.api.doorWinValidate(specId);
      widget.toast('校验结果: ${result is Map ? result['result'] ?? '通过' : '通过'}');
    } catch (e) {
      widget.toast('校验失败: $e');
    }
  }

  Future<String?> _showInputDialog(String title, String label) {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF12121D),
        title: Text(title, style: const TextStyle(color: Color(0xFFE8E6E1))),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          decoration: InputDecoration(
            labelText: label,
            labelStyle: const TextStyle(color: Color(0xFF8A8894)),
          ),
          style: const TextStyle(color: Color(0xFFE8E6E1)),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
              child: const Text('确定')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _specs.isEmpty
              ? RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    children: [
                      const SizedBox(height: 120),
                      _emptyState('暂无门窗规格，点击右下角新建',
                          icon: Icons.door_sliding_outlined),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _specs.length,
                    itemBuilder: (ctx, i) {
                      final s = Map<String, dynamic>.from(_specs[i] as Map);
                      return _sectionCard(children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text((s['name'] ?? '门窗规格').toString(),
                                  style: const TextStyle(
                                      color: Color(0xFFE8E6E1),
                                      fontWeight: FontWeight.w600,
                                      fontSize: 15)),
                            ),
                            if (s['type'] != null)
                              Text(s['type'].toString(),
                                  style: const TextStyle(
                                      color: Color(0xFFC9973B), fontSize: 12)),
                          ],
                        ),
                        const SizedBox(height: 8),
                        _kv('规格ID', (s['id'] ?? '-').toString()),
                        if (s['width'] != null && s['height'] != null)
                          _kv('尺寸', '${s['width']} × ${s['height']} mm'),
                        if (s['material'] != null)
                          _kv('材质', s['material'].toString()),
                        if (s['waterproof_level'] != null)
                          _kv('防水等级', s['waterproof_level'].toString()),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            TextButton.icon(
                              onPressed: () => _validate(s['id']?.toString() ?? ''),
                              icon: const Icon(Icons.verified_outlined, size: 16),
                              label: const Text('校验'),
                            ),
                          ],
                        ),
                      ]);
                    },
                  ),
                ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFFC9973B),
        foregroundColor: Colors.black,
        onPressed: _create,
        child: const Icon(Icons.add),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// F31 智能家居
// ─────────────────────────────────────────────
class _SmartHomeTab extends StatefulWidget {
  final ApiClient api;
  final String projectId;
  final void Function(String) toast;
  const _SmartHomeTab({required this.api, required this.projectId, required this.toast});

  @override
  State<_SmartHomeTab> createState() => _SmartHomeTabState();
}

class _SmartHomeTabState extends State<_SmartHomeTab> with AutomaticKeepAliveClientMixin {
  List<dynamic> _schemes = [];
  bool _loading = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await widget.api.smartHomeListSchemes(widget.projectId);
      _schemes = data is List ? data : (data['items'] as List? ?? []);
    } catch (e) {
      widget.toast('加载智家方案失败: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final name = await _showInputDialog('新建智家方案', '方案名称');
    if (name == null || name.isEmpty) return;
    try {
      await widget.api.smartHomeCreateScheme({
        'project_id': widget.projectId,
        'name': name,
      });
      widget.toast('已创建');
      _load();
    } catch (e) {
      widget.toast('创建失败: $e');
    }
  }

  Future<void> _autoRecommend(String schemeId) async {
    try {
      final result = await widget.api.smartHomeAutoRecommend(schemeId);
      final devices = result is Map ? result['devices'] : null;
      widget.toast('已推荐 ${devices is List ? devices.length : 0} 个设备');
    } catch (e) {
      widget.toast('推荐失败: $e');
    }
  }

  Future<String?> _showInputDialog(String title, String label) {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF12121D),
        title: Text(title, style: const TextStyle(color: Color(0xFFE8E6E1))),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          decoration: InputDecoration(
            labelText: label,
            labelStyle: const TextStyle(color: Color(0xFF8A8894)),
          ),
          style: const TextStyle(color: Color(0xFFE8E6E1)),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
              child: const Text('确定')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _schemes.isEmpty
              ? RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    children: [
                      const SizedBox(height: 120),
                      _emptyState('暂无智家方案，点击右下角新建',
                          icon: Icons.home_outlined),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _schemes.length,
                    itemBuilder: (ctx, i) {
                      final s = Map<String, dynamic>.from(_schemes[i] as Map);
                      return _sectionCard(children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text((s['name'] ?? '智家方案').toString(),
                                  style: const TextStyle(
                                      color: Color(0xFFE8E6E1),
                                      fontWeight: FontWeight.w600,
                                      fontSize: 15)),
                            ),
                            if (s['protocol'] != null)
                              Text(s['protocol'].toString(),
                                  style: const TextStyle(
                                      color: Color(0xFFC9973B), fontSize: 12)),
                          ],
                        ),
                        const SizedBox(height: 8),
                        _kv('方案ID', (s['id'] ?? '-').toString()),
                        if (s['devices_count'] != null)
                          _kv('设备数', s['devices_count'].toString()),
                        if (s['scenes_count'] != null)
                          _kv('场景数', s['scenes_count'].toString()),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            TextButton.icon(
                              onPressed: () =>
                                  _autoRecommend(s['id']?.toString() ?? ''),
                              icon: const Icon(Icons.auto_awesome, size: 16),
                              label: const Text('AI 推荐'),
                            ),
                          ],
                        ),
                      ]);
                    },
                  ),
                ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFFC9973B),
        foregroundColor: Colors.black,
        onPressed: _create,
        child: const Icon(Icons.add),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// F32 场景编辑
// ─────────────────────────────────────────────
class _SceneTab extends StatefulWidget {
  final ApiClient api;
  final String projectId;
  final void Function(String) toast;
  const _SceneTab({required this.api, required this.projectId, required this.toast});

  @override
  State<_SceneTab> createState() => _SceneTabState();
}

class _SceneTabState extends State<_SceneTab> with AutomaticKeepAliveClientMixin {
  List<dynamic> _scenes = [];
  List<dynamic> _ecosystems = [];
  bool _loading = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _loadEcosystems();
  }

  Future<void> _loadEcosystems() async {
    setState(() => _loading = true);
    try {
      final data = await widget.api.sceneListEcosystems();
      _ecosystems = data is List ? data : (data['items'] as List? ?? []);
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _loadScenes(String schemeId) async {
    setState(() => _loading = true);
    try {
      final data = await widget.api.sceneListScenes(schemeId);
      _scenes = data is List ? data : (data['items'] as List? ?? []);
    } catch (e) {
      widget.toast('加载场景失败: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _parseNl() async {
    final text = await _showInputDialog('自然语言生成场景', '描述（如：晚上 10 点关灯）');
    if (text == null || text.isEmpty) return;
    try {
      final result = await widget.api.sceneParseNl(text);
      widget.toast('已解析: ${result is Map ? result['name'] ?? '场景' : '场景'}');
    } catch (e) {
      widget.toast('解析失败: $e');
    }
  }

  Future<void> _simulate(String sceneId) async {
    try {
      final result = await widget.api.sceneSimulate(sceneId);
      widget.toast('已模拟: ${result is Map ? result['status'] ?? '完成' : '完成'}');
    } catch (e) {
      widget.toast('模拟失败: $e');
    }
  }

  Future<String?> _showInputDialog(String title, String label) {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF12121D),
        title: Text(title, style: const TextStyle(color: Color(0xFFE8E6E1))),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          decoration: InputDecoration(
            labelText: label,
            labelStyle: const TextStyle(color: Color(0xFF8A8894)),
          ),
          style: const TextStyle(color: Color(0xFFE8E6E1)),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
              child: const Text('确定')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                const Text('生态列表',
                    style: TextStyle(
                        color: Color(0xFFE8E6E1),
                        fontWeight: FontWeight.w600,
                        fontSize: 15)),
                const SizedBox(height: 8),
                if (_ecosystems.isEmpty)
                  _emptyState('暂无生态', icon: Icons.eco_outlined)
                else
                  ..._ecosystems.map((e) {
                    final m = Map<String, dynamic>.from(e as Map);
                    return _sectionCard(children: [
                      Text((m['name'] ?? '生态').toString(),
                          style: const TextStyle(
                              color: Color(0xFFE8E6E1),
                              fontWeight: FontWeight.w600,
                              fontSize: 14)),
                      const SizedBox(height: 4),
                      _kv('生态ID', (m['id'] ?? '-').toString()),
                      if (m['vendor'] != null)
                        _kv('厂商', m['vendor'].toString()),
                      if (m['protocol'] != null)
                        _kv('协议', m['protocol'].toString()),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: [
                          TextButton.icon(
                            onPressed: () =>
                                _loadScenes(m['id']?.toString() ?? ''),
                            icon: const Icon(Icons.list_alt, size: 16),
                            label: const Text('查看场景'),
                          ),
                        ],
                      ),
                    ]);
                  }),
                const SizedBox(height: 16),
                if (_scenes.isNotEmpty) ...[
                  const Text('场景列表',
                      style: TextStyle(
                          color: Color(0xFFE8E6E1),
                          fontWeight: FontWeight.w600,
                          fontSize: 15)),
                  const SizedBox(height: 8),
                  ..._scenes.map((s) {
                    final m = Map<String, dynamic>.from(s as Map);
                    return _sectionCard(children: [
                      Text((m['name'] ?? '场景').toString(),
                          style: const TextStyle(
                              color: Color(0xFFE8E6E1),
                              fontWeight: FontWeight.w600,
                              fontSize: 14)),
                      const SizedBox(height: 4),
                      _kv('场景ID', (m['id'] ?? '-').toString()),
                      if (m['trigger'] != null)
                        _kv('触发', m['trigger'].toString()),
                      if (m['actions_count'] != null)
                        _kv('动作数', m['actions_count'].toString()),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: [
                          TextButton.icon(
                            onPressed: () => _simulate(m['id']?.toString() ?? ''),
                            icon: const Icon(Icons.play_arrow, size: 16),
                            label: const Text('模拟'),
                          ),
                        ],
                      ),
                    ]);
                  }),
                ],
              ],
            ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFFC9973B),
        foregroundColor: Colors.black,
        onPressed: _parseNl,
        child: const Icon(Icons.auto_awesome),
      ),
    );
  }
}
