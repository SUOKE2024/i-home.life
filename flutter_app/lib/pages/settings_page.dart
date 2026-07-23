import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../main.dart' show AuthGate;
import '../services/api.dart';

/// 用户设置页面
/// 对应 Web 端 settings.html
class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final ApiClient _api = ApiClient();

  Map<String, dynamic>? _user;
  bool _loading = true;
  String? _error;

  // 通知开关
  bool _notifyReview = true;
  bool _notifyDaily = true;
  bool _notifyInspection = true;
  bool _notifyAgent = false;

  static const _notifyReviewKey = 'settings_notify_review';
  static const _notifyDailyKey = 'settings_notify_daily';
  static const _notifyInspectionKey = 'settings_notify_inspection';
  static const _notifyAgentKey = 'settings_notify_agent';

  static const _brand = Color(0xFFC9973B);
  static const _bg = Color(0xFF08080F);
  static const _card = Color(0xFF12121D);
  static const _textPrimary = Color(0xFFE8E6E1);
  static const _textSecondary = Color(0xFF8A8894);

  @override
  void initState() {
    super.initState();
    _loadUser();
    _loadNotificationPrefs();
  }

  Future<void> _loadNotificationPrefs() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      if (mounted) {
        setState(() {
          _notifyReview = prefs.getBool(_notifyReviewKey) ?? true;
          _notifyDaily = prefs.getBool(_notifyDailyKey) ?? true;
          _notifyInspection = prefs.getBool(_notifyInspectionKey) ?? true;
          _notifyAgent = prefs.getBool(_notifyAgentKey) ?? false;
        });
      }
    } catch (_) {}
  }

  Future<void> _persistNotificationPref(String key, bool value) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(key, value);
    } catch (_) {}
  }

  Future<void> _loadUser() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.getCurrentUser();
    if (result.isSuccess && result.data != null) {
      setState(() => _user = Map<String, dynamic>.from(result.data as Map));
    } else {
      setState(() => _error = '用户信息加载失败');
    }
    setState(() => _loading = false);
  }

  Future<void> _logout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _card,
        title: const Text('退出登录', style: TextStyle(color: _textPrimary)),
        content: const Text('确定要退出登录吗？', style: TextStyle(color: _textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消', style: TextStyle(color: _textSecondary)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('退出', style: TextStyle(color: Color(0xFFE57373))),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await _api.clearToken();
      // 清除 Passkey 注册标记和登录记录
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('passkey_registered');
      await prefs.remove('last_phone');
      if (mounted) {
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (_) => const AuthGate()),
          (route) => false,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _card,
        title: const Text('设置', style: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: _textSecondary),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: _brand))
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(_error!, style: const TextStyle(color: _textSecondary)),
                      const SizedBox(height: 12),
                      TextButton(onPressed: _loadUser, child: const Text('重试', style: TextStyle(color: _brand))),
                    ],
                  ),
                )
              : ListView(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
                  children: [
                    _buildProfileSection(),
                    const SizedBox(height: 16),
                    _buildNotificationSection(),
                    const SizedBox(height: 16),
                    _buildDangerSection(),
                  ],
                ),
    );
  }

  // ── 个人资料 ──

  Widget _buildProfileSection() {
    final phone = _user?['phone']?.toString() ?? '';
    final maskedPhone = phone.length >= 7 ? '${phone.substring(0, 3)}****${phone.substring(phone.length - 4)}' : phone;
    final name = _user?['name']?.toString() ?? _user?['username']?.toString() ?? '用户';
    final role = _user?['role']?.toString() ?? '';
    final roleLabel = _roleLabel(role);

    return _sectionCard(
      title: '个人资料',
      children: [
        // 头像 + 昵称
        Center(
          child: Column(
            children: [
              CircleAvatar(
                radius: 36,
                backgroundColor: _brand.withOpacity(0.2),
                child: Text(
                  name.isNotEmpty ? name[0].toUpperCase() : '?',
                  style: const TextStyle(color: _brand, fontSize: 28, fontWeight: FontWeight.w700),
                ),
              ),
              const SizedBox(height: 12),
              Text(name, style: const TextStyle(color: _textPrimary, fontSize: 18, fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              Text('$roleLabel  ·  $maskedPhone', style: const TextStyle(color: _textSecondary, fontSize: 13)),
            ],
          ),
        ),
        const Divider(color: _textSecondary, height: 32),
        // 角色信息
        _settingRow(Icons.badge, '角色', roleLabel, trailing: _roleIcon(role)),
        _settingRow(Icons.phone_android, '手机号', maskedPhone),
        // 修改密码入口
        ListTile(
          leading: const Icon(Icons.lock_outline, color: _textSecondary),
          title: const Text('修改密码', style: TextStyle(color: _textPrimary)),
          trailing: const Icon(Icons.chevron_right, color: _textSecondary),
          enabled: false,
        ),
      ],
    );
  }

  // ── 通知设置 ──

  Widget _buildNotificationSection() {
    return _sectionCard(
      title: '通知设置',
      children: [
        _switchRow('待审批提醒', '收到变更单、结算等需要审批时通知', _notifyReview, (v) {
          setState(() => _notifyReview = v);
          _persistNotificationPref(_notifyReviewKey, v);
        }),
        _switchRow('施工日报', '每日施工进度汇总推送', _notifyDaily, (v) {
          setState(() => _notifyDaily = v);
          _persistNotificationPref(_notifyDailyKey, v);
        }),
        _switchRow('质检异常', '出现质量问题时立即通知', _notifyInspection, (v) {
          setState(() => _notifyInspection = v);
          _persistNotificationPref(_notifyInspectionKey, v);
        }),
        _switchRow('Agent 协作', 'AI Agent 协作更新通知', _notifyAgent, (v) {
          setState(() => _notifyAgent = v);
          _persistNotificationPref(_notifyAgentKey, v);
        }),
      ],
    );
  }

  // ── 危险操作 ──

  Widget _buildDangerSection() {
    return _sectionCard(
      title: '其他',
      children: [
        ListTile(
          leading: const Icon(Icons.info_outline, color: _textSecondary),
          title: const Text('版本', style: TextStyle(color: _textPrimary)),
          trailing: const Text('1.2.0', style: TextStyle(color: _textSecondary)),
        ),
        const Divider(color: _textSecondary, height: 1),
        ListTile(
          leading: const Icon(Icons.logout, color: Color(0xFFE57373)),
          title: const Text('退出登录', style: TextStyle(color: Color(0xFFE57373))),
          onTap: _logout,
        ),
      ],
    );
  }

  // ── UI 组件 ──

  Widget _sectionCard({required String title, required List<Widget> children}) {
    return Container(
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(12)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 14, 14, 4),
            child: Text(title, style: const TextStyle(color: _textSecondary, fontSize: 12, fontWeight: FontWeight.w600)),
          ),
          ...children,
        ],
      ),
    );
  }

  Widget _settingRow(IconData icon, String label, String value, {Widget? trailing}) {
    return ListTile(
      leading: Icon(icon, color: _textSecondary),
      title: Text(label, style: const TextStyle(color: _textPrimary, fontSize: 14)),
      trailing: trailing ?? Text(value, style: const TextStyle(color: _textSecondary, fontSize: 13)),
    );
  }

  Widget _switchRow(String title, String subtitle, bool value, Function(bool) onChanged) {
    return SwitchListTile(
      title: Text(title, style: const TextStyle(color: _textPrimary, fontSize: 14)),
      subtitle: Text(subtitle, style: const TextStyle(color: _textSecondary, fontSize: 12)),
      value: value,
      activeColor: _brand,
      onChanged: onChanged,
    );
  }

  String _roleLabel(String role) {
    const labels = {
      'admin': '管理员',
      'homeowner': '业主',
      'designer': '设计师',
      'contractor': '施工方',
      'supplier': '供应商',
      'inspector': '监理',
      'electrician': '电工',
      'carpenter': '木工',
    };
    return labels[role] ?? role;
  }

  Widget _roleIcon(String role) {
    IconData icon;
    switch (role) {
      case 'admin': icon = Icons.admin_panel_settings; break;
      case 'homeowner': icon = Icons.home; break;
      case 'designer': icon = Icons.design_services; break;
      case 'contractor': icon = Icons.engineering; break;
      case 'supplier': icon = Icons.inventory; break;
      case 'inspector': icon = Icons.verified; break;
      case 'electrician': icon = Icons.electrical_services; break;
      case 'carpenter': icon = Icons.carpenter; break;
      default: icon = Icons.person;
    }
    return Icon(icon, color: _brand, size: 20);
  }
}
