import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';
import 'project_detail_page.dart';

class ProjectsPage extends StatefulWidget {
  const ProjectsPage({super.key});

  @override
  State<ProjectsPage> createState() => _ProjectsPageState();
}

class _ProjectsPageState extends State<ProjectsPage> {
  List<Map<String, dynamic>> _projects = [];
  bool _loading = true;
  String? _error;
  bool _showForm = false;
  bool _submitting = false;

  final _nameCtrl = TextEditingController();
  final _addrCtrl = TextEditingController();
  final _areaCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final api = ApiClient();
    final result = await api.getList('/projects');
    if (result.isSuccess) {
      final data = result.data as List;
      setState(() {
        _projects = List<Map<String, dynamic>>.from(data);
        _loading = false;
      });
    } else {
      setState(() {
        _loading = false;
        _error = '加载失败，请检查网络后重试';
      });
    }
  }

  Future<void> _create() async {
    if (_submitting) return;
    setState(() => _submitting = true);
    try {
      final api = ApiClient();
      final area = double.tryParse(_areaCtrl.text);
      final result = await api.post('/projects', {
        'name': _nameCtrl.text.trim(),
        'address': _addrCtrl.text.trim(),
        'total_area': area,
        'floors': [
          {'name': '1层', 'floor_number': 1, 'area': area, 'rooms': []}
        ],
      });
      if (result.isSuccess) {
        _nameCtrl.clear();
        _addrCtrl.clear();
        _areaCtrl.clear();
        if (mounted) setState(() => _showForm = false);
        _load();
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('创建失败: ${result.error}')));
        }
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  String _statusText(String s) {
    return s == 'draft' ? '草稿' : s == 'in_progress' ? '施工中' : '已完成';
  }

  Color _statusColor(String s) {
    return s == 'draft' ? const Color(0xFF8A8894) : s == 'in_progress' ? const Color(0xFF4A9E6E) : const Color(0xFF5B8EC4);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('我的项目', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: Icon(_showForm ? Icons.close : Icons.add),
            onPressed: () => setState(() => _showForm = !_showForm),
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 4, itemHeight: 80);
    }
    if (_error != null) {
      return ErrorRetryWidget(
        message: _error!,
        onRetry: _load,
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_showForm) ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    TextField(controller: _nameCtrl, decoration: const InputDecoration(labelText: '项目名称', hintText: '例如：朝阳小区')),
                    const SizedBox(height: 12),
                    TextField(controller: _addrCtrl, decoration: const InputDecoration(labelText: '地址', hintText: '详细地址')),
                    const SizedBox(height: 12),
                    TextField(controller: _areaCtrl, decoration: const InputDecoration(labelText: '面积 (㎡)', hintText: '126'), keyboardType: TextInputType.number),
                    const SizedBox(height: 16),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: _submitting ? null : _create,
                        child: _submitting
                            ? const SizedBox(
                                width: 20, height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Text('创建项目'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
          ],
          if (_projects.isEmpty && !_showForm)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(48),
                child: Column(
                  children: [
                    const Icon(Icons.home_work_outlined, size: 48, color: Color(0xFF5A5866)),
                    const SizedBox(height: 12),
                    const Text('还没有项目，点击下方按钮创建', style: TextStyle(color: Color(0xFF5A5866))),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: () => setState(() => _showForm = true),
                      icon: const Icon(Icons.add, size: 18),
                      label: const Text('创建项目'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: const Color(0xFFC9973B),
                        side: const BorderSide(color: Color(0xFFC9973B)),
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            ..._projects.map((p) => Card(
              child: InkWell(
                onTap: () async {
                  final deleted = await Navigator.push<bool>(
                    context,
                    MaterialPageRoute(
                      builder: (_) => ProjectDetailPage(
                        projectId: (p['id'] ?? '').toString(),
                      ),
                    ),
                  );
                  if (deleted == true) _load();
                },
                borderRadius: BorderRadius.circular(12),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              p['name'] ?? '-',
                              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFFE8E6E1)),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: _statusColor(p['status'] ?? 'draft').withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(100),
                            ),
                            child: Text(
                              _statusText(p['status'] ?? 'draft'),
                              style: TextStyle(fontSize: 12, color: _statusColor(p['status'] ?? 'draft')),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${p['address'] ?? '未填写地址'} · ${p['total_area'] ?? '-'}㎡',
                        style: const TextStyle(color: Color(0xFF8A8894), fontSize: 13),
                      ),
                    ],
                  ),
                ),
              ),
            )),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _addrCtrl.dispose();
    _areaCtrl.dispose();
    super.dispose();
  }
}
