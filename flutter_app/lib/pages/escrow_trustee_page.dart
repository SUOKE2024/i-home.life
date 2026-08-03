import 'dart:async';
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// F43 资金托管页面（v1.5.0）
class EscrowTrusteePage extends StatefulWidget {
  final String projectId;
  const EscrowTrusteePage({super.key, required this.projectId});

  @override
  State<EscrowTrusteePage> createState() => _EscrowTrusteePageState();
}

class _EscrowTrusteePageState extends State<EscrowTrusteePage> {
  final ApiClient _api = ApiClient();

  List<dynamic> _accounts = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadAccounts();
  }

  Future<void> _loadAccounts() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.trusteeListAccounts(widget.projectId);
    if (!mounted) return;
    if (result.isSuccess) {
      setState(() {
        _accounts = _extractList(result.data, 'accounts');
        _loading = false;
      });
    } else {
      setState(() {
        _error = result.error ?? '加载失败，请检查网络后重试';
        _loading = false;
      });
    }
  }

  List<dynamic> _extractList(dynamic data, String key) {
    if (data is List) return data;
    if (data is Map) return (data[key] as List?) ?? [];
    return [];
  }

  Future<void> _createAccount(Map<String, dynamic> body) async {
    final result = await _api.trusteeCreateAccount(body);
    if (!mounted) return;
    if (result.isSuccess) {
      _toast('存管账户已开通');
      unawaited(_loadAccounts());
    } else {
      _toast('开通失败：${result.error}');
    }
  }

  Future<void> _confirmAcceptance(
      Map<String, dynamic> account, String role) async {
    final id = (account['id'] ?? '').toString();
    final result = await _api.trusteeAcceptance(id, role);
    if (!mounted) return;
    if (result.isSuccess) {
      _toast('已确认（${role == 'owner' ? '业主' : '承包方'}）');
      unawaited(_loadAccounts());
    } else {
      _toast('确认失败：${result.error}');
    }
  }

  Future<void> _releaseFunds(Map<String, dynamic> account) async {
    final id = (account['id'] ?? '').toString();
    final result = await _api.trusteeRelease(id);
    if (!mounted) return;
    if (result.isSuccess) {
      _toast('放款成功');
      unawaited(_loadAccounts());
    } else {
      _toast('放款失败：${result.error}');
    }
  }

  Future<void> _showInterest(Map<String, dynamic> account) async {
    final id = (account['id'] ?? '').toString();
    final result = await _api.trusteeInterest(id);
    if (!mounted) return;
    if (result.isSuccess && result.data is Map) {
      final data = result.data as Map<String, dynamic>;
      final toOwner = data['interest_to_owner'] == true;
      unawaited(showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: SuokeDesignTokens.card(context),
          title: Text('托管利息说明',
              style: TextStyle(color: SuokeDesignTokens.text(context))),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('利息归属：${toOwner ? '业主' : '平台'}',
                  style: TextStyle(color: SuokeDesignTokens.text(context))),
              const SizedBox(height: 8),
              Text(data['note']?.toString() ?? '',
                  style:
                      TextStyle(color: SuokeDesignTokens.textSub(context))),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text('知道了',
                  style: TextStyle(
                      color: SuokeDesignTokens.textSub(context))),
            ),
          ],
        ),
      ));
    } else {
      _toast('查询失败：${result.error}');
    }
  }

  String _statusLabel(String? status) {
    switch (status) {
      case 'active':
        return '存管中';
      case 'release_requested':
        return '待放款';
      case 'released':
        return '已放款';
      default:
        return status ?? '存管中';
    }
  }

  Color _statusColor(String? status) {
    switch (status) {
      case 'released':
        return SuokeDesignTokens.success;
      case 'release_requested':
        return SuokeDesignTokens.warning;
      default:
        return SuokeDesignTokens.info;
    }
  }

  String _trusteeTypeLabel(String? type) {
    switch (type) {
      case 'bank':
        return '银行存管';
      case 'third_party':
        return '第三方监管';
      default:
        return type ?? '-';
    }
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
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.card(context),
        foregroundColor: SuokeDesignTokens.text(context),
        title: const Text('资金托管'),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const LoadingSkeleton(itemHeight: 130);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadAccounts);
    }
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: SuokeDesignTokens.accent,
                    foregroundColor: SuokeDesignTokens.bg(context),
                  ),
                  onPressed: _showCreateDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('开通账户'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: SuokeDesignTokens.text(context),
                  side: BorderSide(
                      color: SuokeDesignTokens.borderClr(context)),
                ),
                onPressed: _loadAccounts,
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            color: SuokeDesignTokens.accent,
            onRefresh: _loadAccounts,
            child: _accounts.isEmpty
                ? ListView(
                    children: [
                      const SizedBox(height: 120),
                      Center(
                        child: Column(
                          children: [
                            Icon(Icons.account_balance_wallet,
                                size: 64,
                                color: SuokeDesignTokens.textSub(context)),
                            const SizedBox(height: 16),
                            Text('暂无托管账户',
                                style: TextStyle(
                                    fontSize: 16,
                                    color:
                                        SuokeDesignTokens.textSub(context))),
                          ],
                        ),
                      ),
                    ],
                  )
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    itemCount: _accounts.length,
                    itemBuilder: (context, index) {
                      final account =
                          _accounts[index] as Map<String, dynamic>;
                      return _buildAccountCard(account);
                    },
                  ),
          ),
        ),
      ],
    );
  }

  Widget _buildAccountCard(Map<String, dynamic> account) {
    final status = (account['status'] ?? '').toString();
    final ownerConfirmed = account['owner_confirmed'] == true;
    final contractorConfirmed = account['contractor_confirmed'] == true;
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.savings_outlined,
                    color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '账号 ${account['account_no_masked'] ?? '-'}',
                    style: TextStyle(
                        color: SuokeDesignTokens.text(context),
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color:
                        _statusColor(status).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _statusLabel(status),
                    style: TextStyle(
                        color: _statusColor(status), fontSize: 12),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip('类型',
                    _trusteeTypeLabel(account['trustee_type']?.toString())),
                _buildInfoChip(
                    '担保支付', account['escrow_payment_id']?.toString() ?? '-'),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildStatusTag('业主确认', ownerConfirmed),
                _buildStatusTag('承包方确认', contractorConfirmed),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildActionButton('业主确认', Icons.how_to_reg,
                    () => _confirmAcceptance(account, 'owner'),
                    enabled: !ownerConfirmed),
                _buildActionButton('承包方确认', Icons.engineering,
                    () => _confirmAcceptance(account, 'contractor'),
                    enabled: !contractorConfirmed),
                _buildActionButton('放款', Icons.paid,
                    () => _releaseFunds(account)),
                _buildActionButton('利息', Icons.percent,
                    () => _showInterest(account)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoChip(String label, String value) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('$label：',
            style: TextStyle(
                color: SuokeDesignTokens.textSub(context), fontSize: 13)),
        Flexible(
          child: Text(value,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                  color: SuokeDesignTokens.text(context), fontSize: 13)),
        ),
      ],
    );
  }

  Widget _buildStatusTag(String label, bool enabled) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: enabled
            ? SuokeDesignTokens.success.withValues(alpha: 0.15)
            : Colors.grey.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        enabled ? '$label：已确认' : '$label：未确认',
        style: TextStyle(
          color: enabled
              ? SuokeDesignTokens.success
              : SuokeDesignTokens.textSub(context),
          fontSize: 12,
        ),
      ),
    );
  }

  Widget _buildActionButton(
    String label,
    IconData icon,
    VoidCallback onPressed, {
    bool enabled = true,
  }) {
    return SizedBox(
      height: 48,
      child: OutlinedButton.icon(
        style: OutlinedButton.styleFrom(
          foregroundColor:
              enabled ? SuokeDesignTokens.accent : SuokeDesignTokens.textSub(context),
          side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
          padding: const EdgeInsets.symmetric(horizontal: 10),
        ),
        onPressed: enabled ? onPressed : null,
        icon: Icon(icon, size: 16),
        label: Text(label, style: const TextStyle(fontSize: 13)),
      ),
    );
  }

  void _showCreateDialog() {
    final paymentCtrl = TextEditingController();
    final accountNoCtrl = TextEditingController();
    String trusteeType = 'bank';
    bool interestToOwner = true;
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: SuokeDesignTokens.card(context),
          title: Text('开通存管账户',
              style: TextStyle(color: SuokeDesignTokens.text(context))),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: paymentCtrl,
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('担保支付 ID'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: trusteeType,
                  dropdownColor: SuokeDesignTokens.card(context),
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('托管类型'),
                  items: const [
                    DropdownMenuItem(
                        value: 'bank', child: Text('银行存管')),
                    DropdownMenuItem(
                        value: 'third_party', child: Text('第三方监管')),
                  ],
                  onChanged: (v) {
                    if (v != null) setDialogState(() => trusteeType = v);
                  },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: accountNoCtrl,
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('脱敏账号（如 6222 **** 1234）'),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: Text('利息归属业主',
                          style: TextStyle(
                              color: SuokeDesignTokens.text(context))),
                    ),
                    Switch(
                      value: interestToOwner,
                      onChanged: (v) =>
                          setDialogState(() => interestToOwner = v),
                      activeTrackColor: SuokeDesignTokens.accent,
                    ),
                  ],
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text('取消',
                  style: TextStyle(
                      color: SuokeDesignTokens.textSub(context))),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: SuokeDesignTokens.accent,
                  foregroundColor: SuokeDesignTokens.bg(context)),
              onPressed: () {
                final paymentId = paymentCtrl.text.trim();
                final accountNo = accountNoCtrl.text.trim();
                if (paymentId.isEmpty) {
                  _toast('请输入担保支付 ID');
                  return;
                }
                if (accountNo.isEmpty) {
                  _toast('请输入脱敏账号');
                  return;
                }
                Navigator.pop(ctx);
                _createAccount({
                  'escrow_payment_id': paymentId,
                  'trustee_type': trusteeType,
                  'account_no_masked': accountNo,
                  'interest_to_owner': interestToOwner,
                });
              },
              child: const Text('开通'),
            ),
          ],
        ),
      ),
    );
  }

  InputDecoration _inputDecoration(String label) {
    return InputDecoration(
      labelText: label,
      labelStyle: TextStyle(color: SuokeDesignTokens.textSub(context)),
      filled: true,
      fillColor: SuokeDesignTokens.bg(context),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: SuokeDesignTokens.accent),
      ),
    );
  }
}
