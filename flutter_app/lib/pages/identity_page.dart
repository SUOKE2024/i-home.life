import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

class IdentityPage extends StatefulWidget {
  const IdentityPage({super.key});

  @override
  State<IdentityPage> createState() => _IdentityPageState();
}

class _IdentityPageState extends State<IdentityPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _realNameController = TextEditingController();
  final TextEditingController _idCardController = TextEditingController();

  Map<String, dynamic>? _status;
  bool _loading = false;
  bool _submitting = false;
  String? _error;
  String? _selectedRole;
  String? _frontPath;
  String? _backPath;

  static const List<Map<String, String>> _roles = [
    {'value': 'homeowner', 'label': '业主'},
    {'value': 'designer', 'label': '设计师'},
    {'value': 'contractor', 'label': '工长'},
    {'value': 'supplier', 'label': '供应商'},
    {'value': 'supervisor', 'label': '监理'},
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadStatus();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _realNameController.dispose();
    _idCardController.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadStatus() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.identityGetStatus();
    if (result.isSuccess) {
      setState(() => _status = result.data as Map<String, dynamic>?);
    } else {
      if (mounted) {
        setState(() => _error = '认证状态加载失败，请检查网络后重试');
      }
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _pickImage(bool isFront) async {
    try {
      final result = await FilePicker.pickFiles(type: FileType.image);
      if (result == null || result.files.isEmpty) return;
      final file = result.files.first;
      if (file.path == null) return;
      setState(() {
        if (isFront) {
          _frontPath = file.path;
        } else {
          _backPath = file.path;
        }
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('选择文件失败：$e')));
      }
    }
  }

  // ── 提交认证 ──

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_selectedRole == null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('请选择角色')));
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('确认提交'),
        content: const Text('请确认您提交的身份信息真实有效，提交后将进入审核流程。'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('确认提交')),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _submitting = true);
    final result = await _api.identitySubmit(
      realName: _realNameController.text.trim(),
      idCard: _idCardController.text.trim(),
      idCardFront: _frontPath,
      idCardBack: _backPath,
      roleAttributes: {'requested_role': _selectedRole},
    );
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('认证申请已提交，请等待审核')),
        );
        _loadStatus();
        _tabController.animateTo(0);
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('提交失败：${result.error}')));
      }
    }
    if (mounted) setState(() => _submitting = false);
  }

  // ── 工具方法 ──

  String _roleLabel(String? role) {
    if (role == null) return '未设置';
    for (final r in _roles) {
      if (r['value'] == role) return r['label']!;
    }
    return role;
  }

  String _statusLabel(String? status) {
    switch (status) {
      case 'pending':
        return '待审核';
      case 'approved':
        return '已认证';
      case 'rejected':
        return '已拒绝';
      case 'not_submitted':
      default:
        return '未认证';
    }
  }

  String _formatDateTime(String iso) {
    if (iso.isEmpty) return '-';
    try {
      final dt = DateTime.parse(iso);
      return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-'
          '${dt.day.toString().padLeft(2, '0')} '
          '${dt.hour.toString().padLeft(2, '0')}:'
          '${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return iso;
    }
  }

  // ── 页面骨架 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('身份认证'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: '认证状态'),
            Tab(text: '提交认证'),
            Tab(text: '认证历史'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildStatusTab(),
          _buildSubmitTab(),
          _buildHistoryTab(),
        ],
      ),
    );
  }

  // ── Tab 1: 认证状态 ──

  Widget _buildStatusTab() {
    if (_loading) return const LoadingSkeleton(itemCount: 3, itemHeight: 110);
    if (_error != null) return ErrorRetryWidget(message: _error!, onRetry: _loadStatus);

    final status = _status?['status'] as String? ?? 'not_submitted';

    if (status == 'not_submitted') {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.verified_user, size: 64, color: Colors.grey),
            const SizedBox(height: 16),
            const Text('您尚未完成身份认证',
                style: TextStyle(fontSize: 16, color: Colors.grey)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () => _tabController.animateTo(1),
              icon: const Icon(Icons.upload_file),
              label: const Text('去认证'),
            ),
          ],
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildStatusCard(status),
        const SizedBox(height: 16),
        _buildInfoCard(),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: ElevatedButton.icon(
                onPressed: _loadStatus,
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ),
            if (status == 'rejected') ...[
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _tabController.animateTo(1),
                  icon: const Icon(Icons.edit),
                  label: const Text('重新提交'),
                ),
              ),
            ],
          ],
        ),
      ],
    );
  }

  Widget _buildStatusCard(String status) {
    Color color;
    IconData icon;
    switch (status) {
      case 'pending':
        color = Colors.blue;
        icon = Icons.hourglass_top;
        break;
      case 'approved':
        color = Colors.green;
        icon = Icons.check_circle;
        break;
      case 'rejected':
        color = Colors.red;
        icon = Icons.cancel;
        break;
      default:
        color = Colors.grey;
        icon = Icons.person_outline;
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            if (status == 'pending')
              SizedBox(
                width: 48,
                height: 48,
                child: CircularProgressIndicator(
                  strokeWidth: 3,
                  valueColor: AlwaysStoppedAnimation<Color>(color),
                ),
              )
            else
              Icon(icon, size: 48, color: color),
            const SizedBox(height: 12),
            Text(
              _statusLabel(status),
              style: TextStyle(
                  fontSize: 20, fontWeight: FontWeight.bold, color: color),
            ),
            if (status == 'rejected') ...[
              const SizedBox(height: 8),
              const Text(
                '您的认证申请未通过审核，请联系管理员或重新提交',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey, fontSize: 13),
              ),
            ],
            if (status == 'approved') ...[
              const SizedBox(height: 8),
              const Text(
                '您已完成身份认证',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey, fontSize: 13),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildInfoCard() {
    final role = _status?['role'] as String?;
    final submittedAt = _status?['submitted_at'] as String?;
    final isVerified = _status?['is_verified'] as bool? ?? false;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('认证信息',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const Divider(height: 24),
            _infoRow('角色', _roleLabel(role)),
            _infoRow('认证状态', isVerified ? '已通过' : '未通过'),
            _infoRow('提交时间', _formatDateTime(submittedAt ?? '')),
          ],
        ),
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value),
        ],
      ),
    );
  }

  // ── Tab 2: 提交认证 ──

  Widget _buildSubmitTab() {
    final status = _status?['status'] as String?;
    if (status == 'pending') {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: const [
            Icon(Icons.hourglass_top, size: 64, color: Colors.blue),
            SizedBox(height: 16),
            Text('您的认证申请正在审核中', style: TextStyle(color: Colors.grey)),
            SizedBox(height: 8),
            Text('审核完成后可在此重新提交',
                style: TextStyle(color: Colors.grey, fontSize: 12)),
          ],
        ),
      );
    }

    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('实名认证信息',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),
          TextFormField(
            controller: _realNameController,
            decoration: const InputDecoration(
              labelText: '真实姓名',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.person),
            ),
            validator: (v) {
              if (v == null || v.trim().isEmpty) return '请输入真实姓名';
              if (v.trim().length < 2) return '姓名至少 2 个字符';
              return null;
            },
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _idCardController,
            decoration: const InputDecoration(
              labelText: '身份证号',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.badge),
            ),
            validator: (v) {
              if (v == null || v.trim().isEmpty) return '请输入身份证号';
              final s = v.trim();
              if (s.length != 15 && s.length != 18) {
                return '身份证号应为 15 或 18 位';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),
          DropdownButtonFormField<String>(
            initialValue: _selectedRole,
            decoration: const InputDecoration(
              labelText: '角色',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.work),
            ),
            items: _roles
                .map((r) => DropdownMenuItem(
                      value: r['value'],
                      child: Text(r['label']!),
                    ))
                .toList(),
            onChanged: (v) => setState(() => _selectedRole = v),
            validator: (v) => v == null ? '请选择角色' : null,
          ),
          const SizedBox(height: 24),
          const Text('上传证件照片',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          _buildImagePicker('身份证正面', _frontPath, true),
          const SizedBox(height: 12),
          _buildImagePicker('身份证反面', _backPath, false),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _submitting ? null : _submit,
              icon: _submitting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.send),
              label: Text(_submitting ? '提交中…' : '提交认证'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildImagePicker(String label, String? path, bool isFront) {
    return InkWell(
      onTap: () => _pickImage(isFront),
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
          prefixIcon: const Icon(Icons.credit_card),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                path != null ? path.split('/').last : '点击上传图片',
                style:
                    TextStyle(color: path != null ? null : Colors.grey),
              ),
            ),
            Icon(Icons.upload_file,
                color: path != null ? Colors.green : Colors.grey),
          ],
        ),
      ),
    );
  }

  // ── Tab 3: 认证历史 ──

  Widget _buildHistoryTab() {
    final status = _status?['status'] as String? ?? 'not_submitted';

    if (status == 'not_submitted' || _status == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: const [
            Icon(Icons.history, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('暂无认证记录', style: TextStyle(color: Colors.grey)),
          ],
        ),
      );
    }

    final role = _status?['role'] as String?;
    final submittedAt = _status?['submitted_at'] as String?;

    IconData histIcon;
    Color histColor;
    switch (status) {
      case 'approved':
        histIcon = Icons.check_circle;
        histColor = Colors.green;
        break;
      case 'rejected':
        histIcon = Icons.cancel;
        histColor = Colors.red;
        break;
      case 'pending':
        histIcon = Icons.hourglass_top;
        histColor = Colors.blue;
        break;
      default:
        histIcon = Icons.person_outline;
        histColor = Colors.grey;
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: ListTile(
            leading: Icon(histIcon, color: histColor),
            title: Text('认证申请 - ${_statusLabel(status)}'),
            subtitle: Text('提交时间：${_formatDateTime(submittedAt ?? '')}'),
            trailing: Text(_roleLabel(role)),
          ),
        ),
      ],
    );
  }
}
