import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/api.dart';
import '../theme/suoke_theme.dart';
import 'home_page.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _phoneCtrl = TextEditingController(text: '13800138000');
  final _passCtrl = TextEditingController(text: '123456');
  final _nameCtrl = TextEditingController();
  bool _isRegister = false;
  bool _passkeyLoading = false;

  // ── 生物识别 ──
  bool _biometricsAvailable = false;

  Future<void> _checkBiometrics() async {
    try {
      debugPrint('生物识别：local_auth 未安装，已降级为关闭状态');
      if (mounted) setState(() => _biometricsAvailable = false);
    } catch (e) {
      debugPrint('生物识别检测失败: $e');
      if (mounted) setState(() => _biometricsAvailable = false);
    }
  }

  @override
  void initState() {
    super.initState();
    _checkBiometrics();
  }

  // ── 密码登录/注册 ──

  Future<void> _submit() async {
    final api = ApiClient();
    final result = _isRegister
        ? await api.post('/auth/register', {
            'phone': _phoneCtrl.text.trim(),
            'name': _nameCtrl.text.trim().isEmpty ? '新用户' : _nameCtrl.text.trim(),
            'password': _passCtrl.text,
            'role': 'homeowner',
          })
        : await api.post('/auth/login', {
            'phone': _phoneCtrl.text.trim(),
            'password': _passCtrl.text,
          });
    if (result.isSuccess) {
      final res = result.data as Map<String, dynamic>;
      await api.saveToken(res['access_token'] as String);
      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => const HomePage()),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('操作失败: ${result.error}')),
        );
      }
    }
  }

  // ── Passkey 登录 ──

  Future<void> _passkeyLogin() async {
    setState(() => _passkeyLoading = true);
    final api = ApiClient();

    try {
      // 1. 请求登录挑战
      final beginResult = await api.webauthnLoginBegin();
      if (!beginResult.isSuccess) {
        _showError('Passkey 服务暂不可用');
        return;
      }

      final options = beginResult.data as Map<String, dynamic>;
      // 2. 平台 Passkey 认证由操作系统处理
      //    在 Flutter 中通过 platform channel 调用原生 Credential Manager API
      //    此处为简化实现，提示用户使用密码登录
      _showError('请使用手机号密码登录，或使用 Web 端 Passkey 扫码登录');
    } catch (e) {
      _showError('Passkey 登录失败: $e');
    } finally {
      if (mounted) setState(() => _passkeyLoading = false);
    }
  }

  void _showError(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg)),
    );
  }

  // ── 生物识别（placeholder） ──

  Future<void> _authenticateWithBiometrics() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final savedPhone = prefs.getString('saved_phone');
      final savedPassword = prefs.getString('saved_password');
      if (savedPhone != null && savedPassword != null) {
        _phoneCtrl.text = savedPhone;
        _passCtrl.text = savedPassword;
        if (mounted) _submit();
      }
    } catch (e) {
      debugPrint('生物识别认证失败: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'i-home.life',
                  style: TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.bold,
                    color: SuokeDesignTokens.accent,
                    letterSpacing: 2,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  '索克家居 · AI 智能装修平台',
                  style: TextStyle(
                    color: SuokeDesignTokens.textSecondary,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 40),
                TextField(
                  controller: _phoneCtrl,
                  decoration: const InputDecoration(labelText: '手机号'),
                  keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _passCtrl,
                  decoration: const InputDecoration(labelText: '密码'),
                  obscureText: true,
                ),
                if (_isRegister) ...[
                  const SizedBox(height: 16),
                  TextField(
                    controller: _nameCtrl,
                    decoration: const InputDecoration(labelText: '姓名'),
                  ),
                ],
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _submit,
                    child: Text(_isRegister ? '注 册' : '登 录'),
                  ),
                ),

                // ── Passkey 分隔 ──
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  child: Row(
                    children: [
                      const Expanded(
                        child: Divider(color: SuokeDesignTokens.border),
                      ),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        child: Text(
                          '或使用生物识别',
                          style: TextStyle(
                            fontSize: 10,
                            color: SuokeDesignTokens.textMuted,
                          ),
                        ),
                      ),
                      const Expanded(
                        child: Divider(color: SuokeDesignTokens.border),
                      ),
                    ],
                  ),
                ),

                // ── Passkey 登录按钮 ──
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: _passkeyLoading ? null : _passkeyLogin,
                    icon: _passkeyLoading
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.fingerprint),
                    label: Text(_passkeyLoading ? '验证中…' : '使用 Passkey 登录'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: SuokeDesignTokens.accent,
                      side: const BorderSide(color: SuokeDesignTokens.accent),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ),

                if (_biometricsAvailable)
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: IconButton(
                      icon: const Icon(
                        Icons.fingerprint,
                        color: SuokeDesignTokens.accent,
                        size: 40,
                      ),
                      onPressed: _authenticateWithBiometrics,
                      tooltip: '生物识别登录',
                    ),
                  ),
                const SizedBox(height: 16),
                TextButton(
                  onPressed: () => setState(() => _isRegister = !_isRegister),
                  child: Text(
                    _isRegister ? '已有账号？直接登录' : '还没有账号？立即注册',
                    style: const TextStyle(color: SuokeDesignTokens.accent),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
