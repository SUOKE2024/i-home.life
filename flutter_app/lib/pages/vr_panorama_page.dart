import 'dart:convert';
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';

class VRPanoramaPage extends StatefulWidget {
  final String projectId;
  const VRPanoramaPage({super.key, required this.projectId});

  @override
  State<VRPanoramaPage> createState() => _VRPanoramaPageState();
}

class _VRPanoramaPageState extends State<VRPanoramaPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  // 暗色主题
  static const Color _bgColor = Color(0xFF08080F);
  static const Color _cardColor = Color(0xFF12121D);
  static const Color _brandColor = Color(0xFFC9973B);
  static const Color _borderColor = Color(0xFF1E1E32);
  static const Color _textPrimary = Color(0xFFE8E6E1);
  static const Color _textSecondary = Color(0xFF8A8894);

  List<dynamic> _panoramas = [];
  List<dynamic> _scenes = [];
  Map<String, dynamic>? _selectedPanorama;
  List<dynamic> _hotspots = [];
  bool _loading = false;
  bool _loadingDetail = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadPanoramas();
    _loadScenes();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadPanoramas() async {
    setState(() => _loading = true);
    final result = await _api.vrListPanoramas(widget.projectId);
    if (result.isSuccess) {
      setState(() => _panoramas = (result.data as List?) ?? []);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('加载全景失败：${result.error}')));
      }
    }
    setState(() => _loading = false);
  }

  Future<void> _loadScenes() async {
    final result = await _api.vrListScenes(widget.projectId);
    if (result.isSuccess) {
      setState(() => _scenes = (result.data as List?) ?? []);
    }
  }

  Future<void> _loadHotspots(String panoId) async {
    setState(() => _loadingDetail = true);
    final result = await _api.vrListHotspots(panoId);
    if (result.isSuccess) {
      setState(() => _hotspots = (result.data as List?) ?? []);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('加载热点失败：${result.error}')));
      }
    }
    setState(() => _loadingDetail = false);
  }

  // ── 工具方法 ──

  /// 后端 panorama_ids 是 JSON 字符串，需解析。
  List<String> _parsePanoramaIds(dynamic raw) {
    if (raw == null) return [];
    if (raw is List) return raw.map((e) => e.toString()).toList();
    if (raw is String) {
      try {
        final decoded = jsonDecode(raw);
        if (decoded is List) return decoded.map((e) => e.toString()).toList();
      } catch (_) {}
    }
    return [];
  }

  /// 该全景被多少场景引用
  int _sceneCount(String panoId) {
    return _scenes
        .where((s) => _parsePanoramaIds(s['panorama_ids']).contains(panoId))
        .length;
  }

  String _fmtTime(dynamic v) {
    if (v == null) return '-';
    final s = v.toString();
    return s.length >= 16 ? s.substring(0, 16).replaceAll('T', ' ') : s;
  }

  Color _statusColor(String? status) {
    switch (status) {
      case 'draft':
        return Colors.blueGrey;
      case 'processing':
      case 'rendering':
        return Colors.orange;
      case 'published':
      case 'rendered':
        return Colors.green;
      case 'failed':
      case 'error':
        return Colors.red;
      default:
        return _brandColor;
    }
  }

  String _statusLabel(String? status) {
    switch (status) {
      case 'draft':
        return '草稿';
      case 'processing':
      case 'rendering':
        return '渲染中';
      case 'published':
        return '已发布';
      case 'rendered':
        return '已渲染';
      case 'failed':
      case 'error':
        return '失败';
      default:
        return status ?? '未知';
    }
  }

  // ── 全景操作 ──

  Future<void> _createPanorama() async {
    final formKey = GlobalKey<FormState>();
    String roomName = '';
    String panoType = 'equirectangular';
    String resolution = '4K';
    String fov = '360';
    String quality = 'standard';

    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSt) => AlertDialog(
          backgroundColor: _cardColor,
          title: const Text('创建全景图', style: TextStyle(color: _textPrimary)),
          content: SingleChildScrollView(
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextFormField(
                    decoration: const InputDecoration(labelText: '房间名称'),
                    style: const TextStyle(color: _textPrimary),
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? '请输入房间名称' : null,
                    onSaved: (v) => roomName = v?.trim() ?? '',
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: panoType,
                    decoration: const InputDecoration(labelText: '全景类型'),
                    dropdownColor: _cardColor,
                    items: [
                      DropdownItem(value: 'equirectangular', label: 'equirectangular'),
                      DropdownItem(value: 'cubemap', label: 'cubemap'),
                    ],
                    onChanged: (v) => setSt(() => panoType = v ?? panoType),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: resolution,
                    decoration: const InputDecoration(labelText: '分辨率'),
                    dropdownColor: _cardColor,
                    items: [
                      DropdownItem(value: '2K', label: '2K'),
                      DropdownItem(value: '4K', label: '4K'),
                      DropdownItem(value: '8K', label: '8K'),
                    ],
                    onChanged: (v) => setSt(() => resolution = v ?? resolution),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: quality,
                    decoration: const InputDecoration(labelText: '渲染质量'),
                    dropdownColor: _cardColor,
                    items: [
                      DropdownItem(value: 'draft', label: 'draft'),
                      DropdownItem(value: 'standard', label: 'standard'),
                      DropdownItem(value: 'high', label: 'high'),
                    ],
                    onChanged: (v) => setSt(() => quality = v ?? quality),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    initialValue: fov,
                    decoration: const InputDecoration(labelText: '视场角 FOV'),
                    keyboardType: TextInputType.number,
                    style: const TextStyle(color: _textPrimary),
                    onSaved: (v) => fov = v ?? '360',
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消'),
            ),
            ElevatedButton(
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
      ),
    );

    if (saved != true) return;
    final result = await _api.vrCreatePanorama({
      'project_id': widget.projectId,
      'room_name': roomName,
      'panorama_type': panoType,
      'resolution': resolution,
      'fov': double.tryParse(fov) ?? 360.0,
      'render_quality': quality,
    });
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('全景已创建')));
      }
      await _loadPanoramas();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('创建失败：${result.error}')));
      }
    }
  }

  Future<void> _deletePanorama(Map<String, dynamic> pano) async {
    final id = pano['id']?.toString() ?? '';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('删除全景', style: TextStyle(color: _textPrimary)),
        content: Text('确认删除「${pano['room_name'] ?? ''}」？此操作不可恢复。',
            style: const TextStyle(color: _textPrimary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消'),
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
    final result = await _api.vrDeletePanorama(id);
    if (result.isSuccess) {
      if (_selectedPanorama?['id'] == id) {
        setState(() {
          _selectedPanorama = null;
          _hotspots = [];
        });
      }
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('已删除')));
      }
      await _loadPanoramas();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('删除失败：${result.error}')));
      }
    }
  }

  Future<void> _viewDetail(Map<String, dynamic> pano) async {
    final id = pano['id']?.toString() ?? '';
    final result = await _api.vrGetPanorama(id);
    if (!result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('加载详情失败：${result.error}')));
      }
      return;
    }
    final detail = result.data;
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: Text(detail['room_name'] ?? '全景详情',
            style: const TextStyle(color: _textPrimary)),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView(
            shrinkWrap: true,
            children: [
              _detailRow('ID', detail['id']?.toString()),
              _detailRow('类型', detail['panorama_type']?.toString()),
              _detailRow('分辨率', detail['resolution']?.toString()),
              _detailRow('视场角', '${detail['fov']}°'),
              _detailRow('渲染质量', detail['render_quality']?.toString()),
              _detailRow('状态', _statusLabel(detail['status']?.toString())),
              _detailRow('文件大小', '${detail['file_size_mb']} MB'),
              _detailRow(
                  '渲染耗时', '${detail['render_duration_sec'] ?? 0} 秒'),
              _detailRow('创建时间', _fmtTime(detail['created_at'])),
              _detailRow('完成时间', _fmtTime(detail['completed_at'])),
              _detailRow('图片地址', detail['image_url']?.toString()),
              _detailRow('缩略图', detail['thumbnail_url']?.toString()),
            ],
          ),
        ),
        actions: [
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('关闭'),
          ),
        ],
      ),
    );
  }

  Widget _detailRow(String label, String? value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
            child: Text(label,
                style: const TextStyle(color: _textSecondary, fontSize: 13)),
          ),
          Expanded(
            child: Text(value ?? '-',
                style: const TextStyle(color: _textPrimary, fontSize: 13)),
          ),
        ],
      ),
    );
  }

  Future<void> _selectPanorama(Map<String, dynamic> pano) async {
    setState(() {
      _selectedPanorama = pano;
      _hotspots = [];
    });
    _tabController.animateTo(1);
    await _loadHotspots(pano['id']?.toString() ?? '');
  }

  // ── 场景操作 ──

  Future<void> _createScene() async {
    final formKey = GlobalKey<FormState>();
    String name = '';
    String transition = 'fade';
    String notes = '';
    final selectedPano = _selectedPanorama?['id']?.toString();

    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSt) => AlertDialog(
          backgroundColor: _cardColor,
          title: const Text('创建 VR 场景', style: TextStyle(color: _textPrimary)),
          content: SingleChildScrollView(
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextFormField(
                    decoration: const InputDecoration(labelText: '场景名称'),
                    style: const TextStyle(color: _textPrimary),
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? '请输入场景名称' : null,
                    onSaved: (v) => name = v?.trim() ?? '',
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: transition,
                    decoration: const InputDecoration(labelText: '转场类型'),
                    dropdownColor: _cardColor,
                    items: [
                      DropdownItem(value: 'fade', label: '淡入淡出'),
                      DropdownItem(value: 'dissolve', label: '溶解'),
                      DropdownItem(value: 'slide', label: '滑动'),
                    ],
                    onChanged: (v) => setSt(() => transition = v ?? transition),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    decoration: const InputDecoration(labelText: '备注（可选）'),
                    style: const TextStyle(color: _textPrimary),
                    maxLines: 2,
                    onSaved: (v) => notes = v ?? '',
                  ),
                  if (selectedPano != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text('将自动包含当前选中全景',
                          style: const TextStyle(
                              color: _textSecondary, fontSize: 12)),
                    ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消'),
            ),
            ElevatedButton(
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
      ),
    );

    if (saved != true) return;
    final result = await _api.vrCreateScene({
      'project_id': widget.projectId,
      'name': name,
      'transition_type': transition,
      'notes': notes,
      if (selectedPano != null) 'panorama_ids': [selectedPano],
    });
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('场景已创建')));
      }
      await _loadScenes();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('创建失败：${result.error}')));
      }
    }
  }

  Future<void> _deleteScene(Map<String, dynamic> scene) async {
    final id = scene['id']?.toString() ?? '';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('删除场景', style: TextStyle(color: _textPrimary)),
        content: Text('确认删除场景「${scene['name'] ?? ''}」？',
            style: const TextStyle(color: _textPrimary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消'),
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
    final result = await _api.vrDeleteScene(id);
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('已删除')));
      }
      await _loadScenes();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('删除失败：${result.error}')));
      }
    }
  }

  // ── 热点操作 ──

  Future<void> _addHotspot() async {
    final panoId = _selectedPanorama?['id']?.toString();
    if (panoId == null) return;
    final formKey = GlobalKey<FormState>();
    String type = 'info';
    String label = '';
    String posX = '0', posY = '0', posZ = '0';
    String? targetPanoId;

    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSt) => AlertDialog(
          backgroundColor: _cardColor,
          title: const Text('生成热点', style: TextStyle(color: _textPrimary)),
          content: SingleChildScrollView(
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DropdownButtonFormField<String>(
                    initialValue: type,
                    decoration: const InputDecoration(labelText: '热点类型'),
                    dropdownColor: _cardColor,
                    items: [
                      DropdownItem(value: 'info', label: '信息'),
                      DropdownItem(value: 'panorama', label: '跳转全景'),
                      DropdownItem(value: 'floorplan', label: '跳转户型图'),
                      DropdownItem(value: 'link', label: '外部链接'),
                    ],
                    onChanged: (v) => setSt(() => type = v ?? type),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    decoration: const InputDecoration(labelText: '标签'),
                    style: const TextStyle(color: _textPrimary),
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? '请输入标签' : null,
                    onSaved: (v) => label = v?.trim() ?? '',
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: TextFormField(
                          decoration: const InputDecoration(labelText: 'X'),
                          keyboardType: TextInputType.number,
                          style: const TextStyle(color: _textPrimary),
                          onSaved: (v) => posX = v ?? '0',
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextFormField(
                          decoration: const InputDecoration(labelText: 'Y'),
                          keyboardType: TextInputType.number,
                          style: const TextStyle(color: _textPrimary),
                          onSaved: (v) => posY = v ?? '0',
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextFormField(
                          decoration: const InputDecoration(labelText: 'Z'),
                          keyboardType: TextInputType.number,
                          style: const TextStyle(color: _textPrimary),
                          onSaved: (v) => posZ = v ?? '0',
                        ),
                      ),
                    ],
                  ),
                  if (type == 'panorama') ...[
                    const SizedBox(height: 12),
                    TextFormField(
                      decoration:
                          const InputDecoration(labelText: '目标全景 ID'),
                      style: const TextStyle(color: _textPrimary),
                      onSaved: (v) => targetPanoId = v,
                    ),
                  ],
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消'),
            ),
            ElevatedButton(
              onPressed: () {
                if (formKey.currentState?.validate() ?? false) {
                  formKey.currentState?.save();
                  Navigator.pop(ctx, true);
                }
              },
              child: const Text('生成'),
            ),
          ],
        ),
      ),
    );

    if (saved != true) return;
    final body = <String, dynamic>{
      'type': type,
      'label': label,
      'position': {
        'x': double.tryParse(posX) ?? 0.0,
        'y': double.tryParse(posY) ?? 0.0,
        'z': double.tryParse(posZ) ?? 0.0,
      },
      if (type == 'panorama' && targetPanoId != null && targetPanoId!.isNotEmpty)
        'target_panorama_id': targetPanoId,
    };
    final result = await _api.vrAddHotspot(panoId, body);
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('热点已生成')));
      }
      await _loadHotspots(panoId);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('生成失败：${result.error}')));
      }
    }
  }

  // ── 构建 UI ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        backgroundColor: _bgColor,
        title: const Text('VR 全景管理', style: TextStyle(color: _textPrimary)),
        iconTheme: const IconThemeData(color: _textPrimary),
        bottom: TabBar(
          controller: _tabController,
          labelColor: _brandColor,
          unselectedLabelColor: _textSecondary,
          indicatorColor: _brandColor,
          tabs: const [
            Tab(text: '全景列表'),
            Tab(text: '场景管理'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildPanoramaList(),
          _buildSceneManager(),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: _brandColor,
        onPressed: _createPanorama,
        child: const Icon(Icons.add, color: Colors.black),
      ),
    );
  }

  // ── Tab 1: 全景列表 ──

  Widget _buildPanoramaList() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 3, itemHeight: 120);
    }
    if (_panoramas.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.panorama_photosphere_select,
                size: 64, color: _textSecondary),
            const SizedBox(height: 16),
            const Text('暂无全景图', style: TextStyle(color: _textSecondary)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(backgroundColor: _brandColor),
              onPressed: _createPanorama,
              icon: const Icon(Icons.add, color: Colors.black),
              label: const Text('创建全景图',
                  style: TextStyle(color: Colors.black)),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadPanoramas,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _panoramas.length,
        itemBuilder: (context, index) {
          final pano = _panoramas[index] as Map<String, dynamic>;
          return _buildPanoramaCard(pano);
        },
      ),
    );
  }

  Widget _buildPanoramaCard(Map<String, dynamic> pano) {
    final id = pano['id']?.toString() ?? '';
    final status = pano['status']?.toString();
    final selected = _selectedPanorama?['id'] == id;
    return Card(
      color: _cardColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
            color: selected ? _brandColor : _borderColor, width: selected ? 1.5 : 1),
      ),
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    pano['room_name']?.toString() ?? '未命名',
                    style: const TextStyle(
                        color: _textPrimary,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                _statusChip(status),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              '类型：${pano['panorama_type'] ?? '-'} · 分辨率：${pano['resolution'] ?? '-'}',
              style: const TextStyle(color: _textSecondary, fontSize: 13),
            ),
            const SizedBox(height: 6),
            Row(
              children: [
                const Icon(Icons.view_in_ar,
                    size: 14, color: _textSecondary),
                const SizedBox(width: 4),
                Text('场景 ${_sceneCount(id)}',
                    style: const TextStyle(
                        color: _textSecondary, fontSize: 12)),
                const SizedBox(width: 12),
                const Icon(Icons.access_time,
                    size: 14, color: _textSecondary),
                const SizedBox(width: 4),
                Text(_fmtTime(pano['created_at']),
                    style: const TextStyle(
                        color: _textSecondary, fontSize: 12)),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton.icon(
                  onPressed: () => _viewDetail(pano),
                  icon: const Icon(Icons.info_outline, size: 18),
                  label: const Text('详情'),
                ),
                TextButton.icon(
                  onPressed: () => _selectPanorama(pano),
                  icon: const Icon(Icons.view_in_ar, size: 18),
                  label: const Text('场景'),
                ),
                TextButton.icon(
                  onPressed: () => _deletePanorama(pano),
                  icon: const Icon(Icons.delete_outline,
                      size: 18, color: Colors.red),
                  label:
                      const Text('删除', style: TextStyle(color: Colors.red)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _statusChip(String? status) {
    final color = _statusColor(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(
        _statusLabel(status),
        style: TextStyle(color: color, fontSize: 12),
      ),
    );
  }

  // ── Tab 2: 场景管理 ──

  Widget _buildSceneManager() {
    if (_selectedPanorama == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: const [
            Icon(Icons.touch_app, size: 64, color: _textSecondary),
            SizedBox(height: 16),
            Text('请先在「全景列表」中选择一个全景',
                style: TextStyle(color: _textSecondary)),
          ],
        ),
      );
    }
    final pano = _selectedPanorama!;
    final panoId = pano['id']?.toString() ?? '';
    final relatedScenes = _scenes.where((s) {
      final ids = _parsePanoramaIds((s as Map<String, dynamic>)['panorama_ids']);
      return ids.contains(panoId);
    }).toList();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // 当前全景
        Card(
          color: _cardColor,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: const BorderSide(color: _brandColor, width: 1.2),
          ),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.panorama_photosphere,
                        color: _brandColor, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        pano['room_name']?.toString() ?? '未命名',
                        style: const TextStyle(
                            color: _textPrimary,
                            fontSize: 16,
                            fontWeight: FontWeight.bold),
                      ),
                    ),
                    _statusChip(pano['status']?.toString()),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                            backgroundColor: _brandColor),
                        onPressed: _addHotspot,
                        icon: const Icon(Icons.add_location_alt,
                            color: Colors.black, size: 18),
                        label: const Text('生成热点',
                            style: TextStyle(color: Colors.black)),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                            backgroundColor: _cardColor,
                            side: const BorderSide(color: _brandColor)),
                        onPressed: _createScene,
                        icon: const Icon(Icons.layers, color: _brandColor),
                        label: const Text('添加场景',
                            style: TextStyle(color: _brandColor)),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 20),
        // 热点列表
        Row(
          children: [
            const Icon(Icons.location_on, color: _brandColor, size: 18),
            const SizedBox(width: 6),
            Text('热点（${_hotspots.length}）',
                style: const TextStyle(
                    color: _textPrimary,
                    fontSize: 15,
                    fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 8),
        if (_loadingDetail)
          const Padding(
            padding: EdgeInsets.all(16),
            child: Center(child: CircularProgressIndicator()),
          )
        else if (_hotspots.isEmpty)
          _buildEmptyHint('暂无热点，点击「生成热点」添加')
        else
          ..._hotspots.asMap().entries.map((e) => _buildHotspotCard(e.key, e.value)),
        const SizedBox(height: 20),
        // 场景列表
        Row(
          children: [
            const Icon(Icons.layers, color: _brandColor, size: 18),
            const SizedBox(width: 6),
            Text('场景（${relatedScenes.length}）',
                style: const TextStyle(
                    color: _textPrimary,
                    fontSize: 15,
                    fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 8),
        if (relatedScenes.isEmpty)
          _buildEmptyHint('暂无场景，点击「添加场景」创建')
        else
          ...relatedScenes.map((s) => _buildSceneCard(s as Map<String, dynamic>)),
      ],
    );
  }

  Widget _buildEmptyHint(String text) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _borderColor),
      ),
      child: Center(
        child: Text(text, style: const TextStyle(color: _textSecondary)),
      ),
    );
  }

  Widget _buildHotspotCard(int index, dynamic raw) {
    final hp = raw as Map<String, dynamic>;
    final pos = hp['position'];
    String posStr = '-';
    if (pos is Map) {
      posStr = '(${pos['x']}, ${pos['y']}, ${pos['z']})';
    } else if (pos is String) {
      posStr = pos;
    }
    return Card(
      color: _cardColor,
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: const BorderSide(color: _borderColor),
      ),
      child: ListTile(
        leading: const Icon(Icons.location_on, color: _brandColor),
        title: Text(hp['label']?.toString() ?? '热点 $index',
            style: const TextStyle(color: _textPrimary)),
        subtitle: Text(
          '类型：${hp['type'] ?? '-'} · 位置：$posStr',
          style: const TextStyle(color: _textSecondary, fontSize: 12),
        ),
      ),
    );
  }

  Widget _buildSceneCard(Map<String, dynamic> scene) {
    final panoIds = _parsePanoramaIds(scene['panorama_ids']);
    return Card(
      color: _cardColor,
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: const BorderSide(color: _borderColor),
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
                    scene['name']?.toString() ?? '未命名场景',
                    style: const TextStyle(
                        color: _textPrimary, fontWeight: FontWeight.bold),
                  ),
                ),
                _statusChip(scene['status']?.toString()),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              '视角：${scene['transition_type'] ?? '-'} · 全景 ${panoIds.length}',
              style: const TextStyle(color: _textSecondary, fontSize: 12),
            ),
            if (scene['thumbnail_url'] != null) ...[
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: Image.network(
                  scene['thumbnail_url'].toString(),
                  height: 120,
                  width: double.infinity,
                  fit: BoxFit.cover,
                  errorBuilder: (_, _, _) => Container(
                    height: 120,
                    color: _borderColor,
                    child: const Icon(Icons.broken_image,
                        color: _textSecondary),
                  ),
                ),
              ),
            ],
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton.icon(
                  onPressed: () => _deleteScene(scene),
                  icon: const Icon(Icons.delete_outline,
                      size: 18, color: Colors.red),
                  label: const Text('删除',
                      style: TextStyle(color: Colors.red)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// 下拉项封装。
class DropdownItem extends DropdownMenuItem<String> {
  DropdownItem({super.key, required String value, required String label})
      : super(value: value, child: Text(label));
}
