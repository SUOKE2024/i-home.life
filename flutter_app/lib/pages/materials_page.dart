import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

class MaterialsPage extends StatefulWidget {
  const MaterialsPage({super.key});

  @override
  State<MaterialsPage> createState() => _MaterialsPageState();
}

class _MaterialsPageState extends State<MaterialsPage> {
  List<Map<String, dynamic>> _materials = [];
  List<Map<String, dynamic>> _categories = [];
  String _selectedCategory = '';
  String _search = '';
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final api = ApiClient();
    final catsResult = await api.get('/materials/categories');
    final matsResult = await api.getList('/materials?limit=200');
    if (catsResult.isSuccess && matsResult.isSuccess) {
      final catsData = catsResult.data;
      final matsData = matsResult.data;
      setState(() {
        _categories = List<Map<String, dynamic>>.from(
          (catsData is List ? catsData : (catsData['data'] as List? ?? [])));
        _materials = List<Map<String, dynamic>>.from(matsData as List);
        _loading = false;
      });
    } else {
      setState(() {
        _loading = false;
        _error = '加载失败，请检查网络后重试';
      });
    }
  }

  List<Map<String, dynamic>> get _filtered {
    return _materials.where((m) {
      final name = (m['name'] ?? '').toString().toLowerCase();
      final sku = (m['sku'] ?? '').toString().toLowerCase();
      final brand = (m['brand'] ?? '').toString().toLowerCase();
      final cat = m['category'];
      final catCode = cat is Map ? (cat['code'] ?? '') : '';

      final matchesSearch = _search.isEmpty ||
          name.contains(_search.toLowerCase()) ||
          sku.contains(_search.toLowerCase()) ||
          brand.contains(_search.toLowerCase());
      final matchesCat = _selectedCategory.isEmpty || catCode == _selectedCategory;

      return matchesSearch && matchesCat;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('物料库', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 6, itemHeight: 160);
    }
    if (_error != null) {
      return ErrorRetryWidget(
        message: _error!,
        onRetry: _load,
      );
    }
    final filtered = _filtered;
    return RefreshIndicator(
      onRefresh: _load,
      child: CustomScrollView(
        slivers: [
          SliverPadding(
            padding: const EdgeInsets.all(16),
            sliver: SliverToBoxAdapter(
              child: Column(
                children: [
                  TextField(
                    decoration: const InputDecoration(
                      hintText: '搜索物料...',
                      prefixIcon: Icon(Icons.search, color: Color(0xFF5A5866)),
                    ),
                    onChanged: (v) => setState(() => _search = v),
                  ),
                  const SizedBox(height: 12),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        _catChip('全部', ''),
                        ..._categories.map((c) => _catChip(
                          (c['name'] ?? '').toString(),
                          (c['code'] ?? '').toString(),
                        )),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
              ),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            sliver: SliverGrid(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                childAspectRatio: 1.1,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
              ),
              delegate: SliverChildBuilderDelegate(
                (ctx, i) {
                  final m = filtered[i];
                  return Card(
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            m['brand'] ?? '',
                            style: const TextStyle(fontSize: 10, color: Color(0xFFC9973B), letterSpacing: 1),
                          ),
                          const SizedBox(height: 4),
                          Expanded(
                            child: Text(
                              m['name'] ?? '',
                              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Color(0xFFE8E6E1)),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                '¥${((m['unit_price'] ?? 0) as num).toInt()}',
                                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFFE0AA4A)),
                              ),
                              Text(
                                '/${m['unit'] ?? '件'}',
                                style: const TextStyle(fontSize: 11, color: Color(0xFF5A5866)),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  );
                },
                childCount: filtered.length,
              ),
            ),
          ),
          const SliverPadding(padding: EdgeInsets.only(bottom: 80)),
        ],
      ),
    );
  }

  Widget _catChip(String label, String code) {
    final selected = _selectedCategory == code;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Container(
        decoration: BoxDecoration(
          border: Border.all(color: selected ? const Color(0xFFC9973B) : const Color(0xFF2A2A45)),
          borderRadius: BorderRadius.circular(20),
        ),
        child: ChoiceChip(
          label: Text(label, style: TextStyle(fontSize: 12, color: selected ? const Color(0xFFC9973B) : const Color(0xFF8A8894))),
          selected: selected,
          onSelected: (_) => setState(() => _selectedCategory = code),
          selectedColor: const Color(0xFFC9973B).withValues(alpha: 0.15),
          showCheckmark: false,
        ),
      ),
    );
  }
}
