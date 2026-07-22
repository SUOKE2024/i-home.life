import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:local_auth/local_auth.dart';
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
  final _formKey = GlobalKey<FormState>();
  final _phoneCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();
  bool _isRegister = false;
  bool _passkeyLoading = false;
  bool _biometricsLoading = false;
  bool _submitting = false;
  String _role = 'homeowner';
  String _subRole = '';

  // ── 生物识别 ──
  final LocalAuthentication _localAuth = LocalAuthentication();

  /// 设备是否支持生物识别（仅平台能力，与 token 无关）
  /// 用于决定 Passkey 按钮是否显示
  bool _biometricsSupported = false;

  /// 设备支持生物识别 且 本地已有登录 token（用于"指纹/面容快速登录"按钮）
  bool _biometricsAvailable = false;

  /// SharedPreferences 中标记本设备是否已注册 Passkey（简化方案：
  /// Flutter 无标准 WebAuthn API，注册标记 = 密码登录成功后置位）
  static const String _kPasskeyRegisteredKey = 'passkey_registered';

  @override
  void initState() {
    super.initState();
    _checkBiometrics();
  }

  @override
  void dispose() {
    _phoneCtrl.dispose();
    _passCtrl.dispose();
    _nameCtrl.dispose();
    super.dispose();
  }

  // 检测设备是否支持生物识别
  Future<void> _checkBiometrics() async {
    bool supported = false;
    try {
      final canCheck = await _localAuth.canCheckBiometrics;
      final isDeviceSupported = await _localAuth.isDeviceSupported();
      supported = canCheck && isDeviceSupported;
    } on PlatformException catch (e) {
      // 鸿蒙等不支持的平台会抛 PlatformException，优雅降级
      debugPrint('生物识别不可用（可能当前平台不支持）: ${e.code} - ${e.message}');
      supported = false;
    } catch (e) {
      debugPrint('生物识别检测失败: $e');
      supported = false;
    }

    if (!mounted) return;
    setState(() => _biometricsSupported = supported);

    if (!supported) {
      setState(() => _biometricsAvailable = false);
      return;
    }

    // 设备支持生物识别时，再判断是否已有 token（控制"快速登录"按钮）
    try {
      final prefs = await SharedPreferences.getInstance();
      final hasToken = prefs.getString('paseto_token') != null;
      if (mounted) setState(() => _biometricsAvailable = hasToken);
    } catch (e) {
      debugPrint('读取 token 失败: $e');
      if (mounted) setState(() => _biometricsAvailable = false);
    }
  }

  // ── 密码登录/注册 ──

  /// 构建细分工种下拉选项（与 Web 端 SUB_ROLES 保持一致）
  List<DropdownMenuItem<String>> _buildSubRoleItems() {
    final options = <MapEntry<String, String>>[];
    options.add(const MapEntry('', '-- 请选择工种 --'));
    if (_role == 'contractor') {
      options.addAll(const [
        MapEntry('', '工长（总包）'),
        MapEntry('electrician', '电工'),
        MapEntry('plumber', '水电安装工'),
        MapEntry('mason', '泥瓦工'),
        MapEntry('carpenter', '木工'),
        MapEntry('painter', '油漆工'),
        MapEntry('installer', '安装工'),
        MapEntry('curtain_installer', '窗帘安装工'),
        MapEntry('supervisor', '监理'),
      ]);
    } else if (_role == 'designer') {
      options.addAll(const [
        MapEntry('', '通用设计师'),
        MapEntry('curtain_designer', '窗帘设计师'),
      ]);
    }
    return options.map((e) => DropdownMenuItem(
      value: e.key,
      child: Text(e.value),
    )).toList();
  }

  Future<void> _submit() async {
    if (_submitting) return;
    if (!_formKey.currentState!.validate()) return;
    setState(() => _submitting = true);

    try {
      final api = ApiClient();
      final data = <String, dynamic>{
              'phone': _phoneCtrl.text.trim(),
              'name': _nameCtrl.text.trim().isEmpty ? '新用户' : _nameCtrl.text.trim(),
              'password': _passCtrl.text,
              'role': _role,
            };
      if (_subRole.isNotEmpty) {
        data['sub_role'] = _subRole;
      }
      final result = _isRegister
          ? await api.post('/auth/register', data)
          : await api.post('/auth/login', {
              'phone': _phoneCtrl.text.trim(),
              'password': _passCtrl.text,
            });
      if (result.isSuccess) {
        final res = result.data as Map<String, dynamic>;
        await api.saveToken(res['access_token'] as String);
        // 保存手机号用于下次生物识别提示（不保存密码）
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('last_phone', _phoneCtrl.text.trim());
        // 密码登录成功后，标记本设备已"注册 Passkey"（简化方案）
        // 真正的 WebAuthn 注册需要平台 Credential Manager，Flutter 暂无标准 API
        await prefs.setBool(_kPasskeyRegisteredKey, true);
        // 刷新生物识别可用状态（现在有 token 了）
        if (mounted) {
          setState(() {
            _biometricsAvailable = _biometricsSupported;
          });
        }
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
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  // ── Passkey 登录（简化方案：local_auth + 保存的 token） ──
  //
  // Flutter 没有标准的 WebAuthn 浏览器 API（navigator.credentials），
  // 因此移动端"Passkey"实际表现为"生物识别快速登录"：
  // 1. 检查 SharedPreferences 中 passkey_registered 标记
  // 2. 若已注册：用 local_auth 验证生物特征 → 用保存的 token 登录
  // 3. 若未注册：提示用户先用密码登录（登录后会自动置位标记）
  Future<void> _passkeyLogin() async {
    if (_passkeyLoading) return;
    setState(() => _passkeyLoading = true);

    try {
      final prefs = await SharedPreferences.getInstance();
      final passkeyRegistered = prefs.getBool(_kPasskeyRegisteredKey) ?? false;
      final hasToken = prefs.getString('paseto_token') != null;

      if (!passkeyRegistered || !hasToken) {
        // 设备未注册 Passkey：提示用户先密码登录
        // 真正的 WebAuthn 注册需登录态 + 平台 Credential Manager，Flutter 暂不支持
        _showError('本设备尚未启用 Passkey，请先使用密码登录（登录后将自动启用快速登录）');
        return;
      }

      // 1. 先用 local_auth 验证生物特征（指纹/面容）
      bool authenticated = false;
      try {
        authenticated = await _localAuth.authenticate(
          localizedReason: '请验证您的指纹或面容以使用 Passkey 登录',
        );
      } on PlatformException catch (e) {
        debugPrint('Passkey 生物识别异常: ${e.code} - ${e.message}');
        _showError('生物识别不可用（当前平台可能不支持），请使用密码登录');
        if (mounted) setState(() => _biometricsSupported = false);
        return;
      }

      if (!authenticated) {
        _showError('生物识别验证未通过');
        return;
      }

      // 2. 验证通过，尝试调用后端 webauthnLoginBegin（不带 phone，discoverable 模式）
      //    由于 Flutter 无标准 WebAuthn API，无法构造完整 credential 断言，
      //    此处仅用作服务可达性探测；真正的"登录"使用已保存的 PASETO token。
      final api = ApiClient();
      await api.loadToken();

      if (!api.isLoggedIn) {
        _showError('未找到登录记录，请使用密码登录');
        await prefs.remove(_kPasskeyRegisteredKey);
        if (mounted) setState(() => _biometricsAvailable = false);
        return;
      }

      // 3. 探测后端 Passkey 服务可用性（失败不阻断本地快速登录）
      try {
        final beginResult = await api.webauthnLoginBegin();
        if (beginResult.isSuccess && beginResult.data != null) {
          final options = beginResult.data as Map<String, dynamic>;
          debugPrint('Passkey 登录挑战已获取: ${options["challenge"]}');
        }
      } catch (e) {
        debugPrint('Passkey 后端探测失败（不阻断本地登录）: $e');
      }

      // 4. 用保存的 token 验证有效性（等同 Passkey 快速登录）
      final meResult = await api.get('/auth/me');
      if (meResult.isSuccess) {
        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => const HomePage()),
          );
        }
      } else {
        // token 已失效，清除并提示重新登录
        await api.clearToken();
        await prefs.remove(_kPasskeyRegisteredKey);
        _showError('Passkey 登录已过期，请使用密码重新登录');
        if (mounted) {
          setState(() {
            _biometricsAvailable = false;
          });
        }
      }
    } catch (e) {
      debugPrint('Passkey 登录失败: $e');
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

  // ── 生物识别快速登录（基于已保存的 token） ──

  Future<void> _authenticateWithBiometrics() async {
    if (_biometricsLoading) return;
    setState(() => _biometricsLoading = true);

    try {
      final authenticated = await _localAuth.authenticate(
        localizedReason: '请验证您的指纹或面容以快速登录',
      );

      if (!authenticated) {
        _showError('生物识别验证未通过');
        return;
      }

      // 验证通过，使用已保存的 token 登录
      final api = ApiClient();
      await api.loadToken(); // 从 SharedPreferences 加载 token
      if (api.isLoggedIn) {
        // 可选：验证 token 是否仍然有效
        final meResult = await api.get('/auth/me');
        if (meResult.isSuccess) {
          if (mounted) {
            Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (_) => const HomePage()),
            );
          }
          return;
        } else {
          // token 已失效，清除并提示重新登录
          await api.clearToken();
          _showError('登录已过期，请重新输入密码登录');
          if (mounted) setState(() => _biometricsAvailable = false);
        }
      } else {
        _showError('未找到登录记录，请使用密码登录');
        if (mounted) setState(() => _biometricsAvailable = false);
      }
    } on PlatformException catch (e) {
      debugPrint('生物识别认证异常: ${e.code} - ${e.message}');
      _showError('生物识别不可用，请使用密码登录');
      if (mounted) setState(() => _biometricsAvailable = false);
    } catch (e) {
      debugPrint('生物识别认证失败: $e');
      _showError('生物识别认证失败: $e');
    } finally {
      if (mounted) setState(() => _biometricsLoading = false);
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
                Form(
                  key: _formKey,
                  autovalidateMode: AutovalidateMode.onUserInteraction,
                  child: Column(
                    children: [
                      TextFormField(
                        controller: _phoneCtrl,
                        decoration: const InputDecoration(labelText: '手机号'),
                        keyboardType: TextInputType.phone,
                        validator: (v) {
                          if (v == null || v.trim().isEmpty) return '请输入手机号';
                          if (v.trim().length < 11) return '手机号格式不正确';
                          return null;
                        },
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _passCtrl,
                        decoration: const InputDecoration(labelText: '密码'),
                        obscureText: true,
                        keyboardType: TextInputType.visiblePassword,
                        validator: (v) {
                          if (v == null || v.isEmpty) return '请输入密码';
                          if (v.length < 6) return '密码至少6位';
                          return null;
                        },
                      ),
                      if (_isRegister) ...[
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _nameCtrl,
                          decoration: const InputDecoration(labelText: '姓名'),
                          validator: (v) {
                            if (v == null || v.trim().isEmpty) return '请输入姓名';
                            return null;
                          },
                        ),
                        const SizedBox(height: 16),
                        DropdownButtonFormField<String>(
                          value: _role,
                          decoration: const InputDecoration(labelText: '角色'),
                          items: const [
                            DropdownMenuItem(value: 'homeowner', child: Text('业主')),
                            DropdownMenuItem(value: 'designer', child: Text('设计师')),
                            DropdownMenuItem(value: 'contractor', child: Text('施工方（工长/工人）')),
                            DropdownMenuItem(value: 'supplier', child: Text('供应商')),
                          ],
                          onChanged: (v) {
                            setState(() { _role = v!; _subRole = ''; });
                          },
                        ),
                        if (_role == 'contractor' || _role == 'designer') ...[
                          const SizedBox(height: 16),
                          DropdownButtonFormField<String>(
                            value: _subRole,
                            decoration: const InputDecoration(labelText: '细分工种'),
                            items: _buildSubRoleItems(),
                            onChanged: (v) => setState(() => _subRole = v ?? ''),
                          ),
                        ],
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _submitting ? null : _submit,
                    style: ElevatedButton.styleFrom(minimumSize: const Size(double.infinity, 48)),
                    child: _submitting
                        ? const SizedBox(
                            width: 20, height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : Text(_isRegister ? '注册' : '登录'),
                  ),
                ),

                // ── 生物识别分隔（仅设备支持时显示） ──
                if (_biometricsSupported)
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
                            '或使用 Passkey',
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

                // ── Passkey 登录按钮（仅设备支持生物识别时显示） ──
                if (_biometricsSupported)
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

                // ── 生物识别快速登录按钮（仅当设备支持且有登录记录时显示） ──
                if (_biometricsAvailable)
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        onPressed: _biometricsLoading
                            ? null
                            : _authenticateWithBiometrics,
                        icon: _biometricsLoading
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.face,
                                size: 28),
                        label: const Text('指纹 / 面容 快速登录'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: SuokeDesignTokens.accent,
                          side: const BorderSide(color: SuokeDesignTokens.border),
                          padding: const EdgeInsets.symmetric(vertical: 14),
                        ),
                      ),
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
