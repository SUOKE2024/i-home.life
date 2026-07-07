import 'package:flutter/material.dart';
import '../services/api.dart';
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

  Future<void> _submit() async {
    final api = ApiClient();
    try {
      Map<String, dynamic> res;
      if (_isRegister) {
        res = await api.post('/auth/register', {
          'phone': _phoneCtrl.text.trim(),
          'name': _nameCtrl.text.trim().isEmpty ? '新用户' : _nameCtrl.text.trim(),
          'password': _passCtrl.text,
          'role': 'homeowner',
        });
      } else {
        res = await api.post('/auth/login', {
          'phone': _phoneCtrl.text.trim(),
          'password': _passCtrl.text,
        });
      }
      await api.saveToken(res['access_token'] as String);
      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => const HomePage()),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('操作失败: $e')),
        );
      }
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
                    color: Color(0xFFC9973B),
                    letterSpacing: 2,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  '索克家居 · AI 智能装修平台',
                  style: TextStyle(color: Color(0xFF5A5866), fontSize: 14),
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
                const SizedBox(height: 16),
                TextButton(
                  onPressed: () => setState(() => _isRegister = !_isRegister),
                  child: Text(
                    _isRegister ? '已有账号？直接登录' : '还没有账号？立即注册',
                    style: const TextStyle(color: Color(0xFFC9973B)),
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
