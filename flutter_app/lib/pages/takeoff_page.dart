import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

class TakeoffPage extends StatefulWidget {
  final String projectId;
  const TakeoffPage({super.key, required this.projectId});

  @override
  State<TakeoffPage> createState() => _TakeoffPageState();
}

class _TakeoffPageState extends State<TakeoffPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  // 暗色主题
  static const Color _bgColor = Color(0xFF08080F);
  static const Color _cardColor = Color(0xFF12121D);
  static const Color _brandColor = Color(0xFFC9973B);
  static const Color _borderColor = Color(0xFF1E1E32);
  static const Color _primaryText = Color(0xFFE8E6E1);
  static const Color _secondaryText = Color(0xFF8A8894);

  // 参数输入
  final _wallLengthCtrl = TextEditingController(text: '10.0');
  final _wallHeightCtrl = TextEditingController(text: '3.0');
  final _wallThicknessCtrl = TextEditingController(text: '0.24');
  final _slabAreaCtrl = TextEditingController(text: '50.0');
  final _slabThicknessCtrl = TextEditingController(text: '0.12');
  final _floorAreaCtrl = TextEditingController(text: '50.0');

  Map<String, dynamic>? _result;
  List<Map<String, dynamic>> _details = [];
  bool _loading = false;
  String? _error;

  // 参考单价（元）
  static const double _priceBrick = 380; // 元/m³ 砌筑
  static const double _priceConcrete = 450; // 元/m³ 混凝土
  static const double _priceRebar = 5; // 元/kg 钢筋
  static const double _priceTile = 30; // 元/块 瓷砖
  static const double _pricePaint = 20; // 元/m² 涂料
  static const double _priceFormwork = 50; // 元/m² 模板
  static const double _priceMortar = 300; // 元/m³ 砂浆

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    _wallLengthCtrl.dispose();
    _wallHeightCtrl.dispose();
    _wallThicknessCtrl.dispose();
    _slabAreaCtrl.dispose();
    _slabThicknessCtrl.dispose();
    _floorAreaCtrl.dispose();
    super.dispose();
  }

  Future<void> _autoCalculate() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    final body = {
      'walls': [
        {
          'length': double.tryParse(_wallLengthCtrl.text) ?? 0,
          'height': double.tryParse(_wallHeightCtrl.text) ?? 0,
          'thickness': double.tryParse(_wallThicknessCtrl.text) ?? 0.24,
          'openings_area': 0,
          'brick_type': 'standard_brick',
        }
      ],
      'slabs': [
        {
          'area': double.tryParse(_slabAreaCtrl.text) ?? 0,
          'thickness': double.tryParse(_slabThicknessCtrl.text) ?? 0.12,
          'concrete_grade': 'c25',
        }
      ],
      'floors': [
        {
          'area': double.tryParse(_floorAreaCtrl.text) ?? 0,
          'tile_size': '600x600',
        }
      ],
    };

    final result = await _api.takeoffCalcProject(body);
    if (result.isSuccess) {
      final data = result.data as Map<String, dynamic>;
      setState(() {
        _result = data;
        _details = _buildDetails(data);
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('工程量计算完成')),
        );
      }
    } else {
      if (mounted) {
        setState(() => _error = '计算失败：${result.error}');
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('计算失败：${result.error}')),
        );
      }
    }
    setState(() => _loading = false);
  }

  List<Map<String, dynamic>> _buildDetails(Map<String, dynamic> data) {
    final details = <Map<String, dynamic>>[];

    for (final w in (data['walls'] as List?) ?? []) {
      final wall = w as Map<String, dynamic>;
      final volume = (wall['volume'] as num?)?.toDouble() ?? 0;
      details.add({
        'name': '墙体砌筑（${wall['brick_type'] ?? '标准砖'}）',
        'formula': '${wall['length']}m × ${wall['height']}m × ${wall['thickness']}m',
        'quantity': volume,
        'unit': 'm³',
        'unit_price': _priceBrick,
        'total_price': volume * _priceBrick,
      });
    }

    for (final s in (data['slabs'] as List?) ?? []) {
      final slab = s as Map<String, dynamic>;
      final volume = (slab['volume'] as num?)?.toDouble() ?? 0;
      final rebar = (slab['rebar_weight'] as num?)?.toDouble() ?? 0;
      final formwork = (slab['formwork_area'] as num?)?.toDouble() ?? 0;
      details.add({
        'name': '楼板混凝土（${slab['concrete_grade'] ?? 'C25'}）',
        'formula': '${slab['area']}m² × ${slab['thickness']}m',
        'quantity': volume,
        'unit': 'm³',
        'unit_price': _priceConcrete,
        'total_price': volume * _priceConcrete,
      });
      if (rebar > 0) {
        details.add({
          'name': '楼板钢筋',
          'formula': '${slab['volume']}m³ × 80 kg/m³',
          'quantity': rebar,
          'unit': 'kg',
          'unit_price': _priceRebar,
          'total_price': rebar * _priceRebar,
        });
      }
      if (formwork > 0) {
        details.add({
          'name': '楼板模板',
          'formula': '${slab['area']}m²',
          'quantity': formwork,
          'unit': 'm²',
          'unit_price': _priceFormwork,
          'total_price': formwork * _priceFormwork,
        });
      }
    }

    for (final f in (data['floors'] as List?) ?? []) {
      final floor = f as Map<String, dynamic>;
      final tileCount = ((floor['tile_count_600x600'] as num?)?.toInt() ?? 0) +
          ((floor['tile_count_800x800'] as num?)?.toInt() ?? 0) +
          ((floor['tile_count_750x1500'] as num?)?.toInt() ?? 0);
      details.add({
        'name': '地面铺贴',
        'formula': '${floor['area']}m²',
        'quantity': tileCount.toDouble(),
        'unit': '块',
        'unit_price': _priceTile,
        'total_price': tileCount * _priceTile,
      });
    }

    return details;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        backgroundColor: _bgColor,
        title: const Text('工程量计算', style: TextStyle(color: _primaryText)),
        bottom: TabBar(
          controller: _tabController,
          labelColor: _brandColor,
          unselectedLabelColor: _secondaryText,
          indicatorColor: _brandColor,
          tabs: const [
            Tab(text: '工程量汇总'),
            Tab(text: '明细列表'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSummary(),
          _buildDetailsView(),
        ],
      ),
    );
  }

  // ── 工程量汇总 Tab ──

  Widget _buildSummary() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 4, itemHeight: 100);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _autoCalculate);
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildInputForm(),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: _loading ? null : _autoCalculate,
            icon: const Icon(Icons.calculate),
            label: const Text('自动计算'),
            style: ElevatedButton.styleFrom(
              backgroundColor: _brandColor,
              foregroundColor: _bgColor,
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
          ),
        ),
        const SizedBox(height: 24),
        if (_result != null) ...[
          _buildSummaryCards(),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _cardColor,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _borderColor),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: const [
                    Icon(Icons.summarize, color: _brandColor, size: 20),
                    SizedBox(width: 8),
                    Text('计算结果', style: TextStyle(color: _brandColor, fontWeight: FontWeight.bold)),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  _result!['reply'] ?? '',
                  style: const TextStyle(color: _primaryText, fontSize: 14, height: 1.6),
                ),
              ],
            ),
          ),
        ] else
          _buildEmptyState(),
      ],
    );
  }

  Widget _buildInputForm() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              Icon(Icons.input, color: _brandColor, size: 20),
              SizedBox(width: 8),
              Text('参数输入', style: TextStyle(color: _brandColor, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 16),
          const Text('墙体参数', style: TextStyle(color: _secondaryText, fontSize: 12)),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: _buildInputField('长度(m)', _wallLengthCtrl)),
              const SizedBox(width: 8),
              Expanded(child: _buildInputField('高度(m)', _wallHeightCtrl)),
              const SizedBox(width: 8),
              Expanded(child: _buildInputField('厚度(m)', _wallThicknessCtrl)),
            ],
          ),
          const SizedBox(height: 16),
          const Text('楼板参数', style: TextStyle(color: _secondaryText, fontSize: 12)),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: _buildInputField('面积(m²)', _slabAreaCtrl)),
              const SizedBox(width: 8),
              Expanded(child: _buildInputField('厚度(m)', _slabThicknessCtrl)),
            ],
          ),
          const SizedBox(height: 16),
          const Text('地面参数', style: TextStyle(color: _secondaryText, fontSize: 12)),
          const SizedBox(height: 8),
          _buildInputField('面积(m²)', _floorAreaCtrl),
        ],
      ),
    );
  }

  Widget _buildInputField(String label, TextEditingController controller) {
    return TextField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      style: const TextStyle(color: _primaryText, fontSize: 14),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: _secondaryText, fontSize: 12),
        filled: true,
        fillColor: _bgColor,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: _borderColor),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: _brandColor),
        ),
      ),
    );
  }

  Widget _buildSummaryCards() {
    final summary = (_result!['summary'] as Map<String, dynamic>?) ?? {};

    final totalArea =
        ((summary['total_paint_area_m2'] as num?)?.toDouble() ?? 0) +
            ((summary['total_formwork_m2'] as num?)?.toDouble() ?? 0);
    final totalVolume =
        ((summary['total_concrete_m3'] as num?)?.toDouble() ?? 0) +
            ((summary['total_mortar_m3'] as num?)?.toDouble() ?? 0);
    final totalWeight = (summary['total_rebar_kg'] as num?)?.toDouble() ?? 0;

    // 总造价 = 各分项造价之和
    final totalCost =
        ((summary['total_brick_count'] as num?)?.toDouble() ?? 0) * 0.5 +
            ((summary['total_mortar_m3'] as num?)?.toDouble() ?? 0) * _priceMortar +
            ((summary['total_concrete_m3'] as num?)?.toDouble() ?? 0) * _priceConcrete +
            totalWeight * _priceRebar +
            ((summary['total_formwork_m2'] as num?)?.toDouble() ?? 0) * _priceFormwork +
            ((summary['total_tile_count'] as num?)?.toDouble() ?? 0) * _priceTile +
            ((summary['total_paint_area_m2'] as num?)?.toDouble() ?? 0) * _pricePaint;

    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.3,
      children: [
        _buildSummaryCard('总面积', totalArea.toStringAsFixed(2), 'm²', Icons.square_foot),
        _buildSummaryCard('总体积', totalVolume.toStringAsFixed(2), 'm³', Icons.view_in_ar),
        _buildSummaryCard('总重量', totalWeight.toStringAsFixed(2), 'kg', Icons.scale),
        _buildSummaryCard('总造价', totalCost.toStringAsFixed(2), '元', Icons.payments),
      ],
    );
  }

  Widget _buildSummaryCard(String title, String value, String unit, IconData icon) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(title, style: const TextStyle(color: _secondaryText, fontSize: 13)),
              Icon(icon, color: _brandColor, size: 20),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                value,
                style: const TextStyle(color: _primaryText, fontSize: 24, fontWeight: FontWeight.bold),
              ),
              Text(unit, style: const TextStyle(color: _secondaryText, fontSize: 12)),
            ],
          ),
        ],
      ),
    );
  }

  // ── 明细列表 Tab ──

  Widget _buildDetailsView() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 4, itemHeight: 110);
    }
    if (_result == null) {
      return _buildEmptyState();
    }
    if (_details.isEmpty) {
      return const Center(child: Text('暂无明细数据', style: TextStyle(color: _secondaryText)));
    }

    final totalCost = _details.fold<double>(
      0,
      (sum, d) => sum + ((d['total_price'] as num?)?.toDouble() ?? 0),
    );

    // v1.1.27 F1: ListView.builder 懒加载明细卡片，避免 50+ 条目全量构建
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _details.length + 2, // +1 spacer +1 footer
      itemBuilder: (context, index) {
        if (index < _details.length) {
          return _buildDetailCard(_details[index]);
        }
        if (index == _details.length) {
          return const SizedBox(height: 16);
        }
        // footer: 合价总计
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: _cardColor,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: _brandColor),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('合价总计', style: TextStyle(color: _brandColor, fontSize: 16, fontWeight: FontWeight.bold)),
              Text('¥${totalCost.toStringAsFixed(2)}',
                  style: const TextStyle(color: _brandColor, fontSize: 20, fontWeight: FontWeight.bold)),
            ],
          ),
        );
      },
    );
  }

  Widget _buildDetailCard(Map<String, dynamic> detail) {
    final quantity = (detail['quantity'] as num?)?.toDouble() ?? 0;
    final unitPrice = (detail['unit_price'] as num?)?.toDouble() ?? 0;
    final totalPrice = (detail['total_price'] as num?)?.toDouble() ?? 0;
    final qtyStr = quantity == quantity.roundToDouble()
        ? quantity.round().toString()
        : quantity.toStringAsFixed(2);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            detail['name'] ?? '',
            style: const TextStyle(color: _primaryText, fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              const Text('公式：', style: TextStyle(color: _secondaryText, fontSize: 12)),
              Expanded(
                child: Text(
                  detail['formula'] ?? '',
                  style: const TextStyle(color: _secondaryText, fontSize: 12),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _buildDetailItem('数量', qtyStr)),
              Expanded(child: _buildDetailItem('单位', detail['unit'] ?? '')),
              Expanded(child: _buildDetailItem('单价', '¥${unitPrice.toStringAsFixed(2)}')),
              Expanded(child: _buildDetailItem('合价', '¥${totalPrice.toStringAsFixed(2)}')),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildDetailItem(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: _secondaryText, fontSize: 11)),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(color: _primaryText, fontSize: 14, fontWeight: FontWeight.w500)),
      ],
    );
  }

  // ── 空状态 ──

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: const [
          Icon(Icons.calculate, size: 64, color: _secondaryText),
          SizedBox(height: 16),
          Text('暂无工程量数据', style: TextStyle(color: _secondaryText, fontSize: 16)),
          SizedBox(height: 8),
          Text('请输入参数后点击「自动计算」', style: TextStyle(color: _secondaryText, fontSize: 13)),
        ],
      ),
    );
  }
}
