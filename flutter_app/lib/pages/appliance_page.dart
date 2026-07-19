import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';

class AppliancePage extends StatefulWidget {
  final String projectId;
  const AppliancePage({super.key, required this.projectId});

  @override
  State<AppliancePage> createState() => _AppliancePageState();
}

class _AppliancePageState extends State<AppliancePage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  List<dynamic> _points = [];
  List<dynamic> _appliances = [];
  Map<String, dynamic>? _loadCalcResult;
  bool _loadingPoints = false;
  bool _loadingAppliances = false;
  bool _loadingLoadCalc = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadPoints();
    _loadAppliances();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadPoints() async {
    setState(() => _loadingPoints = true);
    final result = await _api.applianceListPoints(widget.projectId);
    if (result.isSuccess) {
      setState(() => _points = (result.data as List?) ?? []);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('点位加载失败：${result.error}')),
        );
      }
    }
    if (mounted) setState(() => _loadingPoints = false);
  }

  Future<void> _loadAppliances() async {
    setState(() => _loadingAppliances = true);
    final result = await _api.applianceSearch();
    if (result.isSuccess) {
      setState(() => _appliances = (result.data as List?) ?? []);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('电器列表加载失败：${result.error}')),
        );
      }
    }
    if (mounted) setState(() => _loadingAppliances = false);
  }

  Future<void> _computeLoadCalc() async {
    setState(() => _loadingLoadCalc = true);
    final result = await _api.applianceComputeLoadCalc(widget.projectId);
    if (result.isSuccess) {
      setState(() => _loadCalcResult = result.data as Map<String, dynamic>?);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('负荷计算已完成')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('负荷计算失败：${result.error}')),
        );
      }
    }
    if (mounted) setState(() => _loadingLoadCalc = false);
  }

  // ── 添加点位 ──

  Future<void> _showAddPointDialog() async {
    final nameCtrl = TextEditingController();
    final locationCtrl = TextEditingController();
    final circuitCtrl = TextEditingController();
    final powerCtrl = TextEditingController();
    final outletTypeCtrl = TextEditingController();
    final formKey = GlobalKey<FormState>();

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.cardBg,
        title: const Text('添加电器点位', style: TextStyle(color: SuokeDesignTokens.textPrimary)),
        content: SingleChildScrollView(
          child: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildTextField(nameCtrl, '点位名称', '请输入点位名称', required: true),
                _buildTextField(locationCtrl, '位置', '请输入位置'),
                _buildTextField(circuitCtrl, '回路编号', '请输入回路编号'),
                _buildTextField(powerCtrl, '功率 (W)', '请输入功率', isNumber: true),
                _buildTextField(outletTypeCtrl, '插座类型', '请输入插座类型'),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消', style: TextStyle(color: SuokeDesignTokens.textSecondary)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: SuokeDesignTokens.accent),
            onPressed: () {
              if (formKey.currentState!.validate()) {
                Navigator.pop(ctx, true);
              }
            },
            child: const Text('确定'),
          ),
        ],
      ),
    );

    if (result == true) {
      final apiResult = await _api.applianceCreatePoint({
        'project_id': widget.projectId,
        'name': nameCtrl.text,
        'location': locationCtrl.text.isEmpty ? null : locationCtrl.text,
        'circuit': circuitCtrl.text.isEmpty ? null : circuitCtrl.text,
        'power_w':
            powerCtrl.text.isEmpty ? null : double.tryParse(powerCtrl.text),
        'outlet_type':
            outletTypeCtrl.text.isEmpty ? null : outletTypeCtrl.text,
      });
      if (apiResult.isSuccess) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('点位已添加')),
          );
        }
        _loadPoints();
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('添加失败：${apiResult.error}')),
          );
        }
      }
    }
  }

  // ── 添加电器 ──

  Future<void> _showAddApplianceDialog() async {
    final nameCtrl = TextEditingController();
    final brandCtrl = TextEditingController();
    final modelCtrl = TextEditingController();
    final powerCtrl = TextEditingController();
    final energyCtrl = TextEditingController();
    final categoryCtrl = TextEditingController();
    final subcategoryCtrl = TextEditingController();
    final formKey = GlobalKey<FormState>();

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.cardBg,
        title: const Text('添加电器', style: TextStyle(color: SuokeDesignTokens.textPrimary)),
        content: SingleChildScrollView(
          child: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildTextField(nameCtrl, '电器名称', '请输入电器名称', required: true),
                _buildTextField(brandCtrl, '品牌', '请输入品牌'),
                _buildTextField(modelCtrl, '型号', '请输入型号'),
                _buildTextField(powerCtrl, '功率 (W)', '请输入功率', isNumber: true),
                _buildTextField(energyCtrl, '能效等级', '请输入能效等级'),
                _buildTextField(categoryCtrl, '品类 ID', '请输入品类 ID', required: true),
                _buildTextField(subcategoryCtrl, '子类型', '请输入子类型'),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消', style: TextStyle(color: SuokeDesignTokens.textSecondary)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: SuokeDesignTokens.accent),
            onPressed: () {
              if (formKey.currentState!.validate()) {
                Navigator.pop(ctx, true);
              }
            },
            child: const Text('确定'),
          ),
        ],
      ),
    );

    if (result == true) {
      final apiResult = await _api.applianceCreate({
        'name': nameCtrl.text,
        'brand': brandCtrl.text.isEmpty ? null : brandCtrl.text,
        'model': modelCtrl.text.isEmpty ? null : modelCtrl.text,
        'power_rating': powerCtrl.text.isEmpty
            ? null
            : double.tryParse(powerCtrl.text),
        'energy_label': energyCtrl.text.isEmpty ? null : energyCtrl.text,
        'category_id': categoryCtrl.text,
        'subcategory':
            subcategoryCtrl.text.isEmpty ? 'other' : subcategoryCtrl.text,
      });
      if (apiResult.isSuccess) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('电器已添加')),
          );
        }
        _loadAppliances();
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('添加失败：${apiResult.error}')),
          );
        }
      }
    }
  }

  // ── 表单字段 ──

  Widget _buildTextField(
    TextEditingController controller,
    String label,
    String hint, {
    bool isNumber = false,
    bool required = false,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: controller,
        keyboardType: isNumber ? TextInputType.number : TextInputType.text,
        style: const TextStyle(color: SuokeDesignTokens.textPrimary),
        decoration: InputDecoration(
          labelText: label,
          labelStyle: const TextStyle(color: SuokeDesignTokens.textSecondary),
          hintText: hint,
          hintStyle: const TextStyle(color: SuokeDesignTokens.textSecondary),
          enabledBorder: const UnderlineInputBorder(
            borderSide: BorderSide(color: SuokeDesignTokens.border),
          ),
          focusedBorder: const UnderlineInputBorder(
            borderSide: BorderSide(color: SuokeDesignTokens.accent),
          ),
        ),
        validator: (v) {
          if (required && (v == null || v.isEmpty)) return '请填写$label';
          return null;
        },
      ),
    );
  }

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bgDeep,
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.bgDeep,
        title: const Text('电器管理', style: TextStyle(color: SuokeDesignTokens.textPrimary)),
        iconTheme: const IconThemeData(color: SuokeDesignTokens.textPrimary),
        bottom: TabBar(
          controller: _tabController,
          labelColor: SuokeDesignTokens.accent,
          unselectedLabelColor: SuokeDesignTokens.textSecondary,
          indicatorColor: SuokeDesignTokens.accent,
          tabs: const [
            Tab(text: '电器点位规划'),
            Tab(text: '电器列表'),
            Tab(text: '负荷计算'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildPointsTab(),
          _buildAppliancesTab(),
          _buildLoadCalcTab(),
        ],
      ),
    );
  }

  // ── Tab 1: 电器点位规划 ──

  Widget _buildPointsTab() {
    if (_loadingPoints) {
      return const Center(child: CircularProgressIndicator(color: SuokeDesignTokens.accent));
    }
    return RefreshIndicator(
      color: SuokeDesignTokens.accent,
      onRefresh: _loadPoints,
      child: Stack(
        children: [
          _points.isEmpty
              ? _buildEmptyState('暂无电器点位', Icons.electrical_services)
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 80),
                  itemCount: _points.length,
                  itemBuilder: (context, index) =>
                      _buildPointCard(_points[index] as Map<String, dynamic>),
                ),
          Positioned(
            right: 16,
            bottom: 16,
            child: FloatingActionButton(
              backgroundColor: SuokeDesignTokens.accent,
              onPressed: _showAddPointDialog,
              child: const Icon(Icons.add, color: SuokeDesignTokens.bgDeep),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPointCard(Map<String, dynamic> p) {
    final power = p['power_w'];
    final powerStr = power != null
        ? '${(power as num).toDouble().toStringAsFixed(0)} W'
        : '未指定';
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.cardBg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.electrical_services,
                  color: SuokeDesignTokens.accent, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  p['name'] ?? '未命名',
                  style: const TextStyle(
                    color: SuokeDesignTokens.textPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildInfoRow('位置', p['location']?.toString() ?? '未指定'),
          _buildInfoRow('电器类型', p['name']?.toString() ?? '未指定'),
          _buildInfoRow('功率', powerStr),
          _buildInfoRow('回路编号', p['circuit']?.toString() ?? '未指定'),
        ],
      ),
    );
  }

  // ── Tab 2: 电器列表 ──

  Widget _buildAppliancesTab() {
    if (_loadingAppliances) {
      return const Center(child: CircularProgressIndicator(color: SuokeDesignTokens.accent));
    }
    return RefreshIndicator(
      color: SuokeDesignTokens.accent,
      onRefresh: _loadAppliances,
      child: Stack(
        children: [
          _appliances.isEmpty
              ? _buildEmptyState('暂无电器', Icons.kitchen)
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 80),
                  itemCount: _appliances.length,
                  itemBuilder: (context, index) => _buildApplianceCard(
                      _appliances[index] as Map<String, dynamic>),
                ),
          Positioned(
            right: 16,
            bottom: 16,
            child: FloatingActionButton(
              backgroundColor: SuokeDesignTokens.accent,
              onPressed: _showAddApplianceDialog,
              child: const Icon(Icons.add, color: SuokeDesignTokens.bgDeep),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildApplianceCard(Map<String, dynamic> a) {
    final power = a['power_rating'];
    final powerStr = power != null
        ? '${(power as num).toDouble().toStringAsFixed(0)} W'
        : '未指定';
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.cardBg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.kitchen, color: SuokeDesignTokens.accent, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  a['name'] ?? '未命名',
                  style: const TextStyle(
                    color: SuokeDesignTokens.textPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildInfoRow('品牌', a['brand']?.toString() ?? '未指定'),
          _buildInfoRow('型号', a['model']?.toString() ?? '未指定'),
          _buildInfoRow('功率', powerStr),
          _buildInfoRow('能效等级', a['energy_label']?.toString() ?? '未指定'),
        ],
      ),
    );
  }

  // ── Tab 3: 负荷计算 ──

  Widget _buildLoadCalcTab() {
    if (_loadingLoadCalc) {
      return const Center(child: CircularProgressIndicator(color: SuokeDesignTokens.accent));
    }
    if (_loadCalcResult == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.bolt, size: 64, color: SuokeDesignTokens.textSecondary),
            const SizedBox(height: 16),
            const Text('点击下方按钮进行负荷计算',
                style: TextStyle(color: SuokeDesignTokens.textSecondary)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(backgroundColor: SuokeDesignTokens.accent),
              onPressed: _computeLoadCalc,
              icon: const Icon(Icons.calculate),
              label: const Text('开始负荷计算'),
            ),
          ],
        ),
      );
    }

    final totalPower =
        (_loadCalcResult!['total_power'] as num?)?.toDouble() ?? 0;
    final totalCurrent =
        (_loadCalcResult!['total_current'] as num?)?.toDouble() ?? 0;
    final circuits = (_loadCalcResult!['circuits'] as List?) ?? [];
    final isCompliant =
        _loadCalcResult!['is_overall_compliant'] as bool? ?? true;
    final warnings = (_loadCalcResult!['warnings'] as List?) ?? [];
    final mainBreaker = _loadCalcResult!['main_breaker_advice']?.toString();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: SuokeDesignTokens.cardBg,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: SuokeDesignTokens.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('全屋负荷概览',
                  style: TextStyle(
                      color: SuokeDesignTokens.textPrimary,
                      fontSize: 16,
                      fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('总功率', style: TextStyle(color: SuokeDesignTokens.textSecondary)),
                  Text('${totalPower.toStringAsFixed(0)} W',
                      style: const TextStyle(
                          color: SuokeDesignTokens.accent, fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('总电流', style: TextStyle(color: SuokeDesignTokens.textSecondary)),
                  Text('${totalCurrent.toStringAsFixed(1)} A',
                      style: const TextStyle(
                          color: SuokeDesignTokens.accent, fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('整体合规', style: TextStyle(color: SuokeDesignTokens.textSecondary)),
                  Text(isCompliant ? '合规' : '不合规',
                      style: TextStyle(
                          color: isCompliant ? Colors.green : Colors.red,
                          fontWeight: FontWeight.bold)),
                ],
              ),
              if (mainBreaker != null && mainBreaker.isNotEmpty) ...[
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('总闸建议', style: TextStyle(color: SuokeDesignTokens.textSecondary)),
                    Expanded(
                      child: Text(mainBreaker,
                          textAlign: TextAlign.right,
                          style: const TextStyle(color: SuokeDesignTokens.textPrimary)),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
        if (warnings.isNotEmpty) ...[
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: SuokeDesignTokens.cardBg,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.orange),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(children: [
                  Icon(Icons.warning, color: Colors.orange, size: 18),
                  SizedBox(width: 6),
                  Text('警告',
                      style: TextStyle(
                          color: Colors.orange, fontWeight: FontWeight.bold)),
                ]),
                const SizedBox(height: 8),
                ...warnings.map((w) => Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Text('• $w',
                          style: const TextStyle(
                              color: SuokeDesignTokens.textPrimary, fontSize: 13)),
                    )),
              ],
            ),
          ),
        ],
        const SizedBox(height: 16),
        const Text('回路明细',
            style: TextStyle(
                color: SuokeDesignTokens.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ...circuits.map(
            (c) => _buildLoadCard(c as Map<String, dynamic>)),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            style: ElevatedButton.styleFrom(backgroundColor: SuokeDesignTokens.accent),
            onPressed: _computeLoadCalc,
            icon: const Icon(Icons.refresh),
            label: const Text('重新计算'),
          ),
        ),
      ],
    );
  }

  Widget _buildLoadCard(Map<String, dynamic> c) {
    final power = c['total_power'] as num?;
    final current = c['max_current'] as num?;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.cardBg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.electrical_services,
                  color: SuokeDesignTokens.accent, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  c['circuit_name']?.toString() ?? '未命名回路',
                  style: const TextStyle(
                    color: SuokeDesignTokens.textPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildInfoRow(
              '总功率',
              power != null
                  ? '${power.toDouble().toStringAsFixed(0)} W'
                  : '未指定'),
          _buildInfoRow(
              '计算电流',
              current != null
                  ? '${current.toDouble().toStringAsFixed(1)} A'
                  : '未指定'),
          _buildInfoRow(
              '断路器规格', c['breaker_rating']?.toString() ?? '未指定'),
        ],
      ),
    );
  }

  // ── 辅助组件 ──

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: const TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 13)),
          Text(value,
              style: const TextStyle(color: SuokeDesignTokens.textPrimary, fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildEmptyState(String message, IconData icon) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 64, color: SuokeDesignTokens.textSecondary),
          const SizedBox(height: 16),
          Text(message, style: const TextStyle(color: SuokeDesignTokens.textSecondary)),
        ],
      ),
    );
  }
}
