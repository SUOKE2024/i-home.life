import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';

class FurnitureCatalogPage extends StatefulWidget {
  const FurnitureCatalogPage({super.key});

  @override
  State<FurnitureCatalogPage> createState() => _FurnitureCatalogPageState();
}

class _FurnitureCatalogPageState extends State<FurnitureCatalogPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  // 品类浏览
  List<dynamic> _items = [];
  bool _loading = false;
  String? _selectedCategory;
  final List<String> _categories = [
    '全部',
    '沙发',
    '床',
    '衣柜',
    '桌椅',
    '收纳',
    '灯具',
    '其他',
  ];

  // 搜索
  final TextEditingController _searchCtrl = TextEditingController();
  List<dynamic> _searchResults = [];
  bool _searching = false;
  bool _hasSearched = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadItems();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchCtrl.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadItems() async {
    setState(() => _loading = true);
    final result = await _api.furnitureListItems(
      limit: 100,
      category: _selectedCategory == '全部' ? null : _selectedCategory,
    );
    if (result.isSuccess) {
      setState(() => _items = (result.data as List?) ?? []);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('商品列表加载失败：${result.error}')),
        );
      }
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
    final result = await _api.furnitureSearch(keyword);
    if (result.isSuccess) {
      setState(() => _searchResults = (result.data as List?) ?? []);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('搜索失败：${result.error}')),
        );
      }
    }
    if (mounted) setState(() => _searching = false);
  }

  // ── 推荐商品 ──

  Future<void> _showRecommendations(String itemId, String itemName) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(
        child: CircularProgressIndicator(color: SuokeDesignTokens.accent),
      ),
    );
    final result = await _api.furnitureRecommend();
    if (mounted) Navigator.pop(context); // 关闭 loading
    if (result.isSuccess) {
      final data = result.data as Map<String, dynamic>?;
      final recommends = (data?['combos'] as List?) ?? [];
      if (mounted) {
        _showRecommendDialog(itemName, recommends);
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('推荐加载失败：${result.error}')),
        );
      }
    }
  }

  void _showRecommendDialog(String itemName, List<dynamic> recommends) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.cardBg,
        title: Text('「$itemName」推荐商品',
            style: const TextStyle(color: SuokeDesignTokens.textPrimary, fontSize: 16)),
        content: SizedBox(
          width: double.maxFinite,
          child: recommends.isEmpty
              ? const Padding(
                  padding: EdgeInsets.symmetric(vertical: 24),
                  child: Text('暂无推荐商品',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: SuokeDesignTokens.textSecondary)),
                )
              : ListView.builder(
                  shrinkWrap: true,
                  itemCount: recommends.length,
                  itemBuilder: (context, index) {
                    final r = recommends[index] as Map<String, dynamic>;
                    final price = r['price'] as num?;
                    return Container(
                      margin: const EdgeInsets.only(bottom: 8),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: SuokeDesignTokens.bgDeep,
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: SuokeDesignTokens.border),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.chair,
                              color: SuokeDesignTokens.accent, size: 20),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(r['name']?.toString() ?? '未命名',
                                    style: const TextStyle(
                                        color: SuokeDesignTokens.textPrimary,
                                        fontSize: 14,
                                        fontWeight: FontWeight.bold)),
                                const SizedBox(height: 2),
                                Text(
                                  '${r['category']?.toString() ?? '未分类'} · ${r['brand']?.toString() ?? '无品牌'}',
                                  style: const TextStyle(
                                      color: SuokeDesignTokens.textSecondary, fontSize: 12),
                                ),
                              ],
                            ),
                          ),
                          Text(
                            price != null
                                ? '¥${price.toDouble().toStringAsFixed(0)}'
                                : '-',
                            style: const TextStyle(
                                color: SuokeDesignTokens.accent,
                                fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                    );
                  },
                ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('关闭', style: TextStyle(color: SuokeDesignTokens.textSecondary)),
          ),
        ],
      ),
    );
  }

  // ── 创建商品 ──

  Future<void> _showCreateDialog() async {
    final nameCtrl = TextEditingController();
    final categoryCtrl = TextEditingController();
    final brandCtrl = TextEditingController();
    final priceCtrl = TextEditingController();
    final materialCtrl = TextEditingController();
    final specCtrl = TextEditingController();
    final formKey = GlobalKey<FormState>();

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.cardBg,
        title: const Text('新建家具商品', style: TextStyle(color: SuokeDesignTokens.textPrimary)),
        content: SingleChildScrollView(
          child: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildTextField(nameCtrl, '商品名称', '请输入商品名称', required: true),
                _buildTextField(categoryCtrl, '品类', '如：沙发 / 床 / 衣柜',
                    required: true),
                _buildTextField(brandCtrl, '品牌', '请输入品牌'),
                _buildTextField(priceCtrl, '价格 (元)', '请输入价格', isNumber: true),
                _buildTextField(materialCtrl, '材质', '如：实木 / 板材'),
                _buildTextField(specCtrl, '规格', '如：1200×600×750mm'),
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
            child: const Text('创建'),
          ),
        ],
      ),
    );

    if (result == true) {
      final createResult = await _api.furnitureCreateItem({
        'name': nameCtrl.text,
        'category': categoryCtrl.text,
        'brand': brandCtrl.text.isEmpty ? null : brandCtrl.text,
        'price': priceCtrl.text.isEmpty
            ? null
            : double.tryParse(priceCtrl.text),
        'material':
            materialCtrl.text.isEmpty ? null : materialCtrl.text,
        'specification':
            specCtrl.text.isEmpty ? null : specCtrl.text,
      });
      if (createResult.isSuccess) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('商品已创建')),
          );
        }
        _loadItems();
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('创建失败：${createResult.error}')),
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
        keyboardType:
            isNumber ? TextInputType.number : TextInputType.text,
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
        title: const Text('家具品类库', style: TextStyle(color: SuokeDesignTokens.textPrimary)),
        iconTheme: const IconThemeData(color: SuokeDesignTokens.textPrimary),
        bottom: TabBar(
          controller: _tabController,
          labelColor: SuokeDesignTokens.accent,
          unselectedLabelColor: SuokeDesignTokens.textSecondary,
          indicatorColor: SuokeDesignTokens.accent,
          tabs: const [
            Tab(text: '品类浏览'),
            Tab(text: '搜索'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildCatalogTab(),
          _buildSearchTab(),
        ],
      ),
    );
  }

  // ── Tab 1: 品类浏览 ──

  Widget _buildCatalogTab() {
    return Column(
      children: [
        // 分类筛选
        Container(
          width: double.infinity,
          color: SuokeDesignTokens.bgDeep,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: _categories.map((cat) {
                final selected = (_selectedCategory ?? '全部') == cat;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(cat),
                    selected: selected,
                    selectedColor: SuokeDesignTokens.accent,
                    backgroundColor: SuokeDesignTokens.cardBg,
                    labelStyle: TextStyle(
                      color: selected ? SuokeDesignTokens.bgDeep : SuokeDesignTokens.textSecondary,
                      fontSize: 13,
                    ),
                    side: const BorderSide(color: SuokeDesignTokens.border),
                    onSelected: (_) {
                      setState(() => _selectedCategory = cat);
                      _loadItems();
                    },
                  ),
                );
              }).toList(),
            ),
          ),
        ),
        // 商品网格
        Expanded(
          child: _loading
              ? const Center(
                  child: CircularProgressIndicator(color: SuokeDesignTokens.accent))
              : RefreshIndicator(
                  color: SuokeDesignTokens.accent,
                  onRefresh: _loadItems,
                  child: Stack(
                    children: [
                      _items.isEmpty
                          ? _buildEmptyState('暂无商品', Icons.chair)
                          : GridView.builder(
                              padding:
                                  const EdgeInsets.fromLTRB(12, 8, 12, 80),
                              gridDelegate:
                                  const SliverGridDelegateWithFixedCrossAxisCount(
                                crossAxisCount: 2,
                                mainAxisSpacing: 12,
                                crossAxisSpacing: 12,
                                childAspectRatio: 0.72,
                              ),
                              itemCount: _items.length,
                              itemBuilder: (context, index) =>
                                  _buildItemCard(
                                      _items[index] as Map<String, dynamic>),
                            ),
                      Positioned(
                        right: 16,
                        bottom: 16,
                        child: FloatingActionButton(
                          backgroundColor: SuokeDesignTokens.accent,
                          onPressed: _showCreateDialog,
                          child: const Icon(Icons.add, color: SuokeDesignTokens.bgDeep),
                        ),
                      ),
                    ],
                  ),
                ),
        ),
      ],
    );
  }

  Widget _buildItemCard(Map<String, dynamic> item) {
    final price = item['price'] as num?;
    final name = item['name']?.toString() ?? '未命名';
    final category = item['category']?.toString() ?? '未分类';
    final brand = item['brand']?.toString() ?? '无品牌';
    final itemId = item['id']?.toString() ?? '';

    return GestureDetector(
      onTap: () {
        if (itemId.isNotEmpty) {
          _showRecommendations(itemId, name);
        }
      },
      child: Container(
        decoration: BoxDecoration(
          color: SuokeDesignTokens.cardBg,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: SuokeDesignTokens.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 图片占位
            Expanded(
              flex: 3,
              child: Container(
                width: double.infinity,
                decoration: BoxDecoration(
                  color: SuokeDesignTokens.bgDeep,
                  borderRadius: const BorderRadius.only(
                    topLeft: Radius.circular(8),
                    topRight: Radius.circular(8),
                  ),
                  border: Border(
                    bottom: BorderSide(color: SuokeDesignTokens.border, width: 1),
                  ),
                ),
                child: const Icon(Icons.chair,
                    size: 48, color: SuokeDesignTokens.textSecondary),
              ),
            ),
            // 文本信息
            Expanded(
              flex: 2,
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: SuokeDesignTokens.textPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      category,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          color: SuokeDesignTokens.textSecondary, fontSize: 11),
                    ),
                    const Spacer(),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Text(
                            brand,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                color: SuokeDesignTokens.textSecondary, fontSize: 11),
                          ),
                        ),
                        Text(
                          price != null
                              ? '¥${price.toDouble().toStringAsFixed(0)}'
                              : '-',
                          style: const TextStyle(
                            color: SuokeDesignTokens.accent,
                            fontSize: 13,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
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
        // 搜索框
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchCtrl,
                  style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                  decoration: InputDecoration(
                    hintText: '搜索家具名称、品牌、品类...',
                    hintStyle: const TextStyle(color: SuokeDesignTokens.textSecondary),
                    prefixIcon:
                        const Icon(Icons.search, color: SuokeDesignTokens.textSecondary),
                    filled: true,
                    fillColor: SuokeDesignTokens.cardBg,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: SuokeDesignTokens.border),
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
                  child: const Text('搜索',
                      style: TextStyle(color: SuokeDesignTokens.bgDeep)),
                ),
              ),
            ],
          ),
        ),
        // 结果列表
        Expanded(
          child: _searching
              ? const Center(
                  child: CircularProgressIndicator(color: SuokeDesignTokens.accent))
              : _searchResults.isEmpty
                  ? _buildEmptyState(
                      _hasSearched ? '未找到匹配商品' : '输入关键词开始搜索',
                      Icons.search)
                  : ListView.builder(
                      padding: const EdgeInsets.fromLTRB(12, 4, 12, 16),
                      itemCount: _searchResults.length,
                      itemBuilder: (context, index) {
                        final item =
                            _searchResults[index] as Map<String, dynamic>;
                        return _buildSearchResultCard(item);
                      },
                    ),
        ),
      ],
    );
  }

  Widget _buildSearchResultCard(Map<String, dynamic> item) {
    final price = item['price'] as num?;
    final name = item['name']?.toString() ?? '未命名';
    final category = item['category']?.toString() ?? '未分类';
    final brand = item['brand']?.toString() ?? '无品牌';
    final material = item['material']?.toString();
    final itemId = item['id']?.toString() ?? '';

    return GestureDetector(
      onTap: () {
        if (itemId.isNotEmpty) {
          _showRecommendations(itemId, name);
        }
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: SuokeDesignTokens.cardBg,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: SuokeDesignTokens.border),
        ),
        child: Row(
          children: [
            // 图片占位
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: SuokeDesignTokens.bgDeep,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: SuokeDesignTokens.border),
              ),
              child: const Icon(Icons.chair,
                  color: SuokeDesignTokens.textSecondary, size: 28),
            ),
            const SizedBox(width: 12),
            // 信息
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: SuokeDesignTokens.textPrimary,
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '$category · $brand',
                    style: const TextStyle(
                        color: SuokeDesignTokens.textSecondary, fontSize: 12),
                  ),
                  if (material != null && material.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(
                      '材质：$material',
                      style: const TextStyle(
                          color: SuokeDesignTokens.textSecondary, fontSize: 12),
                    ),
                  ],
                ],
              ),
            ),
            // 价格
            Text(
              price != null
                  ? '¥${price.toDouble().toStringAsFixed(0)}'
                  : '-',
              style: const TextStyle(
                color: SuokeDesignTokens.accent,
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── 辅助组件 ──

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
