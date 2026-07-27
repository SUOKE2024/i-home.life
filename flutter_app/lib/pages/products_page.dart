import 'package:flutter/material.dart';
import '../theme/suoke_theme.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

class ProductsPage extends StatefulWidget {
  const ProductsPage({super.key});

  @override
  State<ProductsPage> createState() => _ProductsPageState();
}

class _ProductsPageState extends State<ProductsPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  // 产品浏览
  List<dynamic> _products = [];
  bool _loading = false;
  String? _error;
  String _selectedCategory = '全部';

  // 分类映射（中文标签 -> 后端 code）
  static const Map<String, String> _categoryMap = {
    '全部': '',
    '瓷砖': 'tile',
    '地板': 'flooring',
    '橱柜': 'cabinet',
    '涂料': 'paint',
    '灯具': 'lighting',
    '电器': 'appliance',
    '窗帘': 'curtain',
    '定制家具': 'custom_furniture',
    '服务': 'service',
    '其他': 'other',
  };

  // 搜索
  final TextEditingController _searchCtrl = TextEditingController();
  List<dynamic> _searchResults = [];
  bool _searching = false;
  bool _hasSearched = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadProducts();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchCtrl.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadProducts() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final category = _categoryMap[_selectedCategory] ?? '';
    final result = await _api.productList(
      category: category.isEmpty ? null : category,
      status: 'published',
      limit: 100,
    );
    if (result.isSuccess) {
      setState(() => _products = (result.data as List?) ?? []);
    } else {
      setState(() => _error = '产品加载失败，请检查网络后重试');
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _doSearch() async {
    final keyword = _searchCtrl.text.trim();
    if (keyword.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请输入搜索关键词')),
      );
      return;
    }
    setState(() {
      _searching = true;
      _hasSearched = true;
    });
    // 后端产品列表无关键词搜索端点，加载全部已发布产品后客户端过滤
    final result = await _api.productList(status: 'published', limit: 100);
    if (result.isSuccess) {
      final all = (result.data as List?) ?? [];
      final kw = keyword.toLowerCase();
      setState(() {
        _searchResults = all.where((p) {
          final m = p as Map<String, dynamic>;
          final name = (m['name']?.toString() ?? '').toLowerCase();
          final desc = (m['description']?.toString() ?? '').toLowerCase();
          final category = (m['category']?.toString() ?? '').toLowerCase();
          final tags = (m['tags'] as List?)
                  ?.map((t) => t.toString().toLowerCase())
                  .join(' ') ??
              '';
          return name.contains(kw) ||
              desc.contains(kw) ||
              category.contains(kw) ||
              tags.contains(kw);
        }).toList();
      });
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('搜索失败：${result.error}')),
        );
      }
    }
    if (mounted) setState(() => _searching = false);
  }

  // ── 产品详情 ──

  Future<void> _showDetail(String productId) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(
        child: CircularProgressIndicator(color: SuokeDesignTokens.accent),
      ),
    );
    final result = await _api.productGet(productId);
    if (mounted) Navigator.pop(context); // 关闭 loading
    if (result.isSuccess) {
      if (mounted) {
        _showDetailDialog(result.data as Map<String, dynamic>);
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('详情加载失败：${result.error}')),
        );
      }
    }
  }

  void _showDetailDialog(Map<String, dynamic> p) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.card(context),
        title: Text(p['name']?.toString() ?? '产品详情',
            style: const TextStyle(color: SuokeDesignTokens.text(context), fontSize: 16)),
        content: SizedBox(
          width: double.maxFinite,
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _detailRow('品类', _categoryLabel(p['category']?.toString())),
                _detailRow('品牌', _extractBrand(p) ?? '—'),
                _detailRow('价格', _priceText(p)),
                _detailRow('评分', '暂无评分'),
                _detailRow('库存状态',
                    _stockLabel(p['stock_status']?.toString())),
                _detailRow('单位', p['unit']?.toString() ?? '-'),
                if (p['description'] != null &&
                    p['description'].toString().isNotEmpty) ...[
                  const SizedBox(height: 12),
                  const Text('描述',
                      style: TextStyle(
                          color: SuokeDesignTokens.accent,
                          fontSize: 13,
                          fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text(p['description'].toString(),
                      style: const TextStyle(
                          color: SuokeDesignTokens.text(context), fontSize: 13)),
                ],
                if ((p['tags'] as List?)?.isNotEmpty ?? false) ...[
                  const SizedBox(height: 12),
                  const Text('标签',
                      style: TextStyle(
                          color: SuokeDesignTokens.accent,
                          fontSize: 13,
                          fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: (p['tags'] as List)
                        .map((t) => Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: SuokeDesignTokens.bg(context),
                                borderRadius: BorderRadius.circular(4),
                                border: Border.all(color: SuokeDesignTokens.borderClr(context)),
                              ),
                              child: Text(t.toString(),
                                  style: const TextStyle(
                                      color: SuokeDesignTokens.textSub(context), fontSize: 11)),
                            ))
                        .toList(),
                  ),
                ],
                if (p['ai_generated'] == true) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: SuokeDesignTokens.accent.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.auto_awesome,
                            color: SuokeDesignTokens.accent, size: 14),
                        SizedBox(width: 4),
                        Text('AI 辅助生成',
                            style:
                                TextStyle(color: SuokeDesignTokens.accent, fontSize: 11)),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child:
                const Text('关闭', style: TextStyle(color: SuokeDesignTokens.textSub(context))),
          ),
        ],
      ),
    );
  }

  Widget _detailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 72,
            child: Text(label,
                style:
                    const TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
          ),
          Expanded(
            child: Text(value,
                style: const TextStyle(color: SuokeDesignTokens.text(context), fontSize: 13)),
          ),
        ],
      ),
    );
  }

  // ── 辅助方法 ──

  String _categoryLabel(String? code) {
    if (code == null || code.isEmpty) return '未分类';
    for (final e in _categoryMap.entries) {
      if (e.value == code) return e.key;
    }
    return code;
  }

  String? _extractBrand(Map<String, dynamic> p) {
    final specs = p['specs'];
    if (specs is Map) {
      final brand = specs['brand'];
      if (brand != null && brand.toString().isNotEmpty) return brand.toString();
    }
    return null;
  }

  String _priceText(Map<String, dynamic> p) {
    final min = p['price_min'] as num?;
    final max = p['price_max'] as num?;
    final unit = p['unit']?.toString() ?? '';
    if (min != null && max != null) {
      return '¥${min.toStringAsFixed(0)} - ${max.toStringAsFixed(0)}/$unit';
    } else if (min != null) {
      return '¥${min.toStringAsFixed(0)}/$unit 起';
    } else if (max != null) {
      return '¥${max.toStringAsFixed(0)}/$unit';
    }
    return '价格面议';
  }

  String _stockLabel(String? status) {
    switch (status) {
      case 'in_stock':
        return '有货';
      case 'pre_order':
        return '可预订';
      case 'out_of_stock':
        return '缺货';
      default:
        return '—';
    }
  }

  Color _stockColor(String? status) {
    switch (status) {
      case 'in_stock':
        return Colors.green;
      case 'pre_order':
        return Colors.orange;
      case 'out_of_stock':
        return Colors.red;
      default:
        return SuokeDesignTokens.textSub(context);
    }
  }

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.bg(context),
        title: const Text('产品库', style: TextStyle(color: SuokeDesignTokens.text(context))),
        iconTheme: const IconThemeData(color: SuokeDesignTokens.text(context)),
        bottom: TabBar(
          controller: _tabController,
          labelColor: SuokeDesignTokens.accent,
          unselectedLabelColor: SuokeDesignTokens.textSub(context),
          indicatorColor: SuokeDesignTokens.accent,
          tabs: const [
            Tab(text: '产品浏览'),
            Tab(text: '搜索'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildBrowseTab(),
          _buildSearchTab(),
        ],
      ),
    );
  }

  // ── Tab 1: 产品浏览 ──

  Widget _buildBrowseTab() {
    return Column(
      children: [
        // 分类筛选
        Container(
          width: double.infinity,
          color: SuokeDesignTokens.bg(context),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: _categoryMap.keys.map((cat) {
                final selected = _selectedCategory == cat;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(cat),
                    selected: selected,
                    selectedColor: SuokeDesignTokens.accent,
                    backgroundColor: SuokeDesignTokens.card(context),
                    labelStyle: TextStyle(
                      color: selected ? SuokeDesignTokens.bg(context) : SuokeDesignTokens.textSub(context),
                      fontSize: 13,
                    ),
                    side: const BorderSide(color: SuokeDesignTokens.borderClr(context)),
                    onSelected: (_) {
                      setState(() => _selectedCategory = cat);
                      _loadProducts();
                    },
                  ),
                );
              }).toList(),
            ),
          ),
        ),
        Expanded(
          child: _loading
              ? const LoadingSkeleton(itemCount: 4, itemHeight: 110)
              : _error != null
                  ? ErrorRetryWidget(message: _error!, onRetry: _loadProducts)
                  : RefreshIndicator(
                      color: SuokeDesignTokens.accent,
                      onRefresh: _loadProducts,
                      child: _products.isEmpty
                          ? _buildEmptyState('暂无产品', Icons.inventory_2_outlined)
                          : ListView.builder(
                              padding:
                                  const EdgeInsets.fromLTRB(12, 8, 12, 16),
                              itemCount: _products.length,
                              itemBuilder: (context, index) =>
                                  _buildProductCard(
                                      _products[index] as Map<String, dynamic>),
                            ),
                    ),
        ),
      ],
    );
  }

  Widget _buildProductCard(Map<String, dynamic> p) {
    final name = p['name']?.toString() ?? '未命名';
    final category = _categoryLabel(p['category']?.toString());
    final brand = _extractBrand(p) ?? '—';
    final stock = p['stock_status']?.toString();
    final productId = p['id']?.toString() ?? '';

    return GestureDetector(
      onTap: () {
        if (productId.isNotEmpty) _showDetail(productId);
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: SuokeDesignTokens.card(context),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: SuokeDesignTokens.borderClr(context)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                // 图片占位
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    color: SuokeDesignTokens.bg(context),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: SuokeDesignTokens.borderClr(context)),
                  ),
                  child: const Icon(Icons.inventory_2_outlined,
                      color: SuokeDesignTokens.textSub(context), size: 24),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: SuokeDesignTokens.text(context),
                          fontSize: 15,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '$category · $brand',
                        style: const TextStyle(
                            color: SuokeDesignTokens.textSub(context), fontSize: 12),
                      ),
                    ],
                  ),
                ),
                // 库存状态
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: _stockColor(stock).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    _stockLabel(stock),
                    style:
                        TextStyle(color: _stockColor(stock), fontSize: 11),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    _priceText(p),
                    style: const TextStyle(
                      color: SuokeDesignTokens.accent,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                Row(
                  children: [
                    Icon(Icons.star,
                        size: 14,
                        color: SuokeDesignTokens.accent.withValues(alpha: 0.5)),
                    const SizedBox(width: 2),
                    const Text('暂无评分',
                        style:
                            TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 11)),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ── Tab 2: 搜索 ──

  Widget _buildSearchTab() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchCtrl,
                  style: const TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: InputDecoration(
                    hintText: '搜索产品名称、品类、描述...',
                    hintStyle: const TextStyle(color: SuokeDesignTokens.textSub(context)),
                    prefixIcon:
                        const Icon(Icons.search, color: SuokeDesignTokens.textSub(context)),
                    filled: true,
                    fillColor: SuokeDesignTokens.card(context),
                    contentPadding:
                        const EdgeInsets.symmetric(horizontal: 12),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: SuokeDesignTokens.borderClr(context)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: SuokeDesignTokens.accent),
                    ),
                  ),
                  onSubmitted: (_) => _doSearch(),
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                height: 48,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: SuokeDesignTokens.accent,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  onPressed: _searching ? null : _doSearch,
                  child:
                      const Text('搜索', style: TextStyle(color: SuokeDesignTokens.bg(context))),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: _searching
              ? const Center(
                  child: CircularProgressIndicator(color: SuokeDesignTokens.accent))
              : _searchResults.isEmpty
                  ? _buildEmptyState(
                      _hasSearched ? '未找到匹配产品' : '输入关键词开始搜索',
                      Icons.search)
                  : ListView.builder(
                      padding: const EdgeInsets.fromLTRB(12, 4, 12, 16),
                      itemCount: _searchResults.length,
                      itemBuilder: (context, index) {
                        final p =
                            _searchResults[index] as Map<String, dynamic>;
                        return _buildProductCard(p);
                      },
                    ),
        ),
      ],
    );
  }

  // ── 辅助组件 ──

  Widget _buildEmptyState(String message, IconData icon) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 64, color: SuokeDesignTokens.textSub(context)),
          const SizedBox(height: 16),
          Text(message, style: const TextStyle(color: SuokeDesignTokens.textSub(context))),
        ],
      ),
    );
  }
}
