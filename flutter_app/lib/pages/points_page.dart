import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

class PointsPage extends StatefulWidget {
  const PointsPage({super.key});

  @override
  State<PointsPage> createState() => _PointsPageState();
}

class _PointsPageState extends State<PointsPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  // 暗色主题色
  static const Color _bg = Color(0xFF08080F);
  static const Color _card = Color(0xFF12121D);
  static const Color _brand = Color(0xFFC9973B);
  static const Color _border = Color(0xFF1E1E32);
  static const Color _textMain = Color(0xFFE8E6E1);
  static const Color _textSub = Color(0xFF8A8894);

  Map<String, dynamic>? _account;
  List<dynamic> _transactions = [];
  List<dynamic> _mallItems = [];
  List<dynamic> _redemptions = [];
  List<dynamic> _ranking = [];

  bool _loadingAccount = false;
  bool _loadingMall = false;
  bool _loadingRedemptions = false;
  bool _loadingRanking = false;

  String? _errorAccount;
  String? _errorMall;
  String? _errorRedemptions;
  String? _errorRanking;

  bool _redemptionsLoaded = false;
  bool _rankingLoaded = false;

  // 等级阈值表（按年度获得积分）
  static const List<Map<String, int>> _levels = [
    {'min': 0, 'max': 999},
    {'min': 1000, 'max': 4999},
    {'min': 5000, 'max': 19999},
    {'min': 20000, 'max': 49999},
    {'min': 50000, 'max': 9999999},
  ];
  static const List<String> _levelNames = ['青铜', '白银', '黄金', '铂金', '钻石'];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _tabController.addListener(() {
      if (_tabController.indexIsChanging) return;
      switch (_tabController.index) {
        case 2:
          if (!_redemptionsLoaded) _loadRedemptions();
          break;
        case 3:
          if (!_rankingLoaded) _loadRanking();
          break;
      }
    });
    _loadAccount();
    _loadMallItems();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadAccount() async {
    setState(() {
      _loadingAccount = true;
      _errorAccount = null;
    });
    final result = await _api.pointsGetAccount();
    if (result.isSuccess) {
      setState(() => _account = result.data as Map<String, dynamic>?);
      await _loadTransactions();
    } else {
      if (mounted) {
        setState(() => _errorAccount = '加载失败，请检查网络后重试');
      }
    }
    if (mounted) {
      setState(() => _loadingAccount = false);
    }
  }

  Future<void> _loadTransactions() async {
    final result = await _api.pointsListTransactions(limit: 50);
    if (result.isSuccess) {
      setState(() => _transactions = (result.data as List?) ?? []);
    }
  }

  Future<void> _loadMallItems() async {
    setState(() {
      _loadingMall = true;
      _errorMall = null;
    });
    final result = await _api.pointsListMallItems();
    if (result.isSuccess) {
      setState(() => _mallItems = (result.data as List?) ?? []);
    } else {
      if (mounted) {
        setState(() => _errorMall = '加载失败，请检查网络后重试');
      }
    }
    if (mounted) {
      setState(() => _loadingMall = false);
    }
  }

  Future<void> _loadRedemptions() async {
    setState(() {
      _loadingRedemptions = true;
      _errorRedemptions = null;
    });
    final result = await _api.pointsListRedemptions();
    if (result.isSuccess) {
      setState(() {
        _redemptions = (result.data as List?) ?? [];
        _redemptionsLoaded = true;
      });
    } else {
      if (mounted) {
        setState(() => _errorRedemptions = '加载失败，请检查网络后重试');
      }
    }
    if (mounted) {
      setState(() => _loadingRedemptions = false);
    }
  }

  Future<void> _loadRanking() async {
    setState(() {
      _loadingRanking = true;
      _errorRanking = null;
    });
    final result = await _api.pointsGetRanking();
    if (result.isSuccess) {
      setState(() {
        _ranking = (result.data as List?) ?? [];
        _rankingLoaded = true;
      });
    } else {
      if (mounted) {
        setState(() => _errorRanking = '加载失败，请检查网络后重试');
      }
    }
    if (mounted) {
      setState(() => _loadingRanking = false);
    }
  }

  // ── 兑换 ──

  Future<void> _confirmRedeem(Map<String, dynamic> item) async {
    final itemName = item['name'] as String? ?? '';
    final points = item['points_required'] as int? ?? 0;
    final balance = _account?['balance'] as int? ?? 0;

    if (balance < points) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('积分不足，无法兑换')));
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _card,
        title: const Text('确认兑换', style: TextStyle(color: _textMain)),
        content: Text(
          '商品：$itemName\n消耗积分：$points\n兑换后余额：${balance - points}',
          style: const TextStyle(color: _textSub),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: _brand),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('确认兑换'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    final result = await _api.pointsRedeem(item['id'] as String);
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('兑换成功')));
      }
      await _loadAccount();
      await _loadMallItems();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('兑换失败：${result.error}')));
      }
    }
  }

  // ── 等级计算 ──

  Map<String, dynamic> _levelInfo(int yearEarned) {
    for (int i = 0; i < _levels.length; i++) {
      final min = _levels[i]['min']!;
      final max = _levels[i]['max']!;
      if (yearEarned >= min && yearEarned <= max) {
        final progress = max > min ? (yearEarned - min) / (max - min) : 1.0;
        return {
          'name': _levelNames[i],
          'min': min,
          'max': max,
          'progress': progress.clamp(0.0, 1.0),
          'index': i,
        };
      }
    }
    final last = _levels.length - 1;
    return {
      'name': _levelNames[last],
      'min': _levels[last]['min']!,
      'max': _levels[last]['max']!,
      'progress': 1.0,
      'index': last,
    };
  }

  int _todayChange() {
    final now = DateTime.now();
    int sum = 0;
    for (final t in _transactions) {
      final tx = t as Map<String, dynamic>;
      final createdAt = tx['created_at'] as String?;
      if (createdAt == null) continue;
      try {
        final dt = DateTime.parse(createdAt);
        if (dt.year == now.year && dt.month == now.month && dt.day == now.day) {
          sum += (tx['amount'] as num?)?.toInt() ?? 0;
        }
      } catch (_) {}
    }
    return sum;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _bg,
        title: const Text('积分商城', style: TextStyle(color: _textMain)),
        iconTheme: const IconThemeData(color: _textMain),
        bottom: TabBar(
          controller: _tabController,
          labelColor: _brand,
          unselectedLabelColor: _textSub,
          indicatorColor: _brand,
          tabs: const [
            Tab(text: '我的积分'),
            Tab(text: '商城'),
            Tab(text: '兑换记录'),
            Tab(text: '排行榜'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildAccountTab(),
          _buildMallTab(),
          _buildRedemptionsTab(),
          _buildRankingTab(),
        ],
      ),
    );
  }

  // ── Tab 1: 我的积分 ──

  Widget _buildAccountTab() {
    if (_loadingAccount) {
      return const LoadingSkeleton(itemCount: 4, itemHeight: 90);
    }
    if (_errorAccount != null) {
      return ErrorRetryWidget(message: _errorAccount!, onRetry: _loadAccount);
    }
    if (_account == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.stars, size: 64, color: _textSub),
            const SizedBox(height: 16),
            const Text('暂无积分账户', style: TextStyle(color: _textSub)),
            const SizedBox(height: 24),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: _brand),
              onPressed: _loadAccount,
              child: const Text('刷新'),
            ),
          ],
        ),
      );
    }

    final balance = _account!['balance'] as int? ?? 0;
    final yearEarned = _account!['year_earned'] as int? ?? 0;
    final yearSpent = _account!['year_spent'] as int? ?? 0;
    final totalEarned = _account!['total_earned'] as int? ?? 0;
    final totalSpent = _account!['total_spent'] as int? ?? 0;
    final todayChange = _todayChange();
    final lv = _levelInfo(yearEarned);

    return RefreshIndicator(
      color: _brand,
      onRefresh: _loadAccount,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 积分卡片
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF1A1A2E), Color(0xFF12121D)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: _border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      '我的积分',
                      style: TextStyle(color: _textSub, fontSize: 14),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: _brand.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: _brand),
                      ),
                      child: Text(
                        lv['name'] as String,
                        style: const TextStyle(
                          color: _brand,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  '$balance',
                  style: const TextStyle(
                    color: _textMain,
                    fontSize: 48,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(
                      todayChange >= 0
                          ? Icons.trending_up
                          : Icons.trending_down,
                      color: todayChange >= 0 ? Colors.green : Colors.red,
                      size: 16,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '今日 ${todayChange >= 0 ? '+' : ''}$todayChange',
                      style: TextStyle(
                        color: todayChange >= 0 ? Colors.green : Colors.red,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                // 等级进度条
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      '距下一等级',
                      style: TextStyle(color: _textSub, fontSize: 12),
                    ),
                    Text(
                      '$yearEarned/${lv['max']}',
                      style: const TextStyle(color: _textSub, fontSize: 12),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: lv['progress'] as double,
                    backgroundColor: _border,
                    valueColor: const AlwaysStoppedAnimation<Color>(_brand),
                    minHeight: 6,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          // 年度统计
          Row(
            children: [
              Expanded(
                child: _statCard(
                  '年度获得',
                  '$yearEarned',
                  Icons.arrow_upward,
                  Colors.green,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _statCard(
                  '年度消耗',
                  '$yearSpent',
                  Icons.arrow_downward,
                  Colors.red,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _statCard('累计获得', '$totalEarned', Icons.savings, _brand),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _statCard(
                  '累计消耗',
                  '$totalSpent',
                  Icons.shopping_bag,
                  _textSub,
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          // 快捷入口
          const Text(
            '快捷入口',
            style: TextStyle(
              color: _textMain,
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _shortcutCard(
                  Icons.store,
                  '去商城',
                  () => _tabController.animateTo(1),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _shortcutCard(
                  Icons.history,
                  '兑换记录',
                  () => _tabController.animateTo(2),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _shortcutCard(
                  Icons.leaderboard,
                  '排行榜',
                  () => _tabController.animateTo(3),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          // 最近流水
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                '最近流水',
                style: TextStyle(
                  color: _textMain,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              TextButton(
                onPressed: _loadAccount,
                child: const Text('刷新', style: TextStyle(color: _brand)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (_transactions.isEmpty)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Center(
                child: Text('暂无流水记录', style: TextStyle(color: _textSub)),
              ),
            )
          else
            ..._transactions
                .take(5)
                .map((t) => _transactionTile(t as Map<String, dynamic>)),
        ],
      ),
    );
  }

  Widget _statCard(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(height: 8),
          Text(
            value,
            style: const TextStyle(
              color: _textMain,
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(label, style: const TextStyle(color: _textSub, fontSize: 12)),
        ],
      ),
    );
  }

  Widget _shortcutCard(IconData icon, String label, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          color: _card,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _border),
        ),
        child: Column(
          children: [
            Icon(icon, color: _brand, size: 28),
            const SizedBox(height: 8),
            Text(label, style: const TextStyle(color: _textMain, fontSize: 13)),
          ],
        ),
      ),
    );
  }

  Widget _transactionTile(Map<String, dynamic> tx) {
    final amount = (tx['amount'] as num?)?.toInt() ?? 0;
    final isPositive = amount >= 0;
    final source = tx['source'] as String? ?? '';
    final description = tx['description'] as String? ?? '';
    final createdAt = tx['created_at'] as String? ?? '';
    String timeStr = '';
    try {
      timeStr = DateTime.parse(createdAt).toLocal().toString().substring(0, 16);
    } catch (_) {}

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _border),
      ),
      child: Row(
        children: [
          Icon(
            isPositive ? Icons.add_circle : Icons.remove_circle,
            color: isPositive ? Colors.green : Colors.red,
            size: 32,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  description.isNotEmpty ? description : source,
                  style: const TextStyle(color: _textMain, fontSize: 14),
                ),
                const SizedBox(height: 2),
                Text(
                  '$source · $timeStr',
                  style: const TextStyle(color: _textSub, fontSize: 11),
                ),
              ],
            ),
          ),
          Text(
            '${isPositive ? '+' : ''}$amount',
            style: TextStyle(
              color: isPositive ? Colors.green : Colors.red,
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  // ── Tab 2: 商城 ──

  Widget _buildMallTab() {
    if (_loadingMall) {
      return const LoadingSkeleton(itemCount: 4, itemHeight: 90);
    }
    if (_errorMall != null) {
      return ErrorRetryWidget(message: _errorMall!, onRetry: _loadMallItems);
    }
    if (_mallItems.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.storefront, size: 64, color: _textSub),
            const SizedBox(height: 16),
            const Text('商城暂无商品', style: TextStyle(color: _textSub)),
            const SizedBox(height: 24),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: _brand),
              onPressed: _loadMallItems,
              child: const Text('刷新'),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      color: _brand,
      onRefresh: _loadMallItems,
      child: GridView.builder(
        padding: const EdgeInsets.all(16),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 0.72,
        ),
        itemCount: _mallItems.length,
        itemBuilder: (context, index) {
          final item = _mallItems[index] as Map<String, dynamic>;
          return _mallItemCard(item);
        },
      ),
    );
  }

  Widget _mallItemCard(Map<String, dynamic> item) {
    final name = item['name'] as String? ?? '';
    final category = item['category'] as String? ?? '';
    final points = item['points_required'] as int? ?? 0;
    final stock = item['stock'] as int? ?? 0;
    final imageUrl = item['image_url'] as String?;
    final balance = _account?['balance'] as int? ?? 0;
    final canRedeem = balance >= points && stock > 0;

    return Container(
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 图片占位
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: _border,
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(12),
                ),
              ),
              width: double.infinity,
              child: imageUrl != null && imageUrl.isNotEmpty
                  ? ClipRRect(
                      borderRadius: const BorderRadius.vertical(
                        top: Radius.circular(12),
                      ),
                      child: CachedNetworkImage(
                        imageUrl: imageUrl,
                        fit: BoxFit.cover,
                        placeholder: (context, url) => _imgPlaceholder(),
                        errorWidget: (context, url, error) => _imgPlaceholder(),
                      ),
                    )
                  : _imgPlaceholder(),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: const TextStyle(
                    color: _textMain,
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 4),
                Text(
                  category,
                  style: const TextStyle(color: _textSub, fontSize: 11),
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    const Icon(Icons.stars, color: _brand, size: 14),
                    const SizedBox(width: 4),
                    Text(
                      '$points',
                      style: const TextStyle(
                        color: _brand,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  '库存 $stock',
                  style: const TextStyle(color: _textSub, fontSize: 11),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: canRedeem ? _brand : _border,
                      foregroundColor: canRedeem ? _bg : _textSub,
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      minimumSize: const Size.fromHeight(30),
                    ),
                    onPressed: canRedeem ? () => _confirmRedeem(item) : null,
                    child: const Text('兑换', style: TextStyle(fontSize: 13)),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _imgPlaceholder() {
    return const Center(
      child: Icon(Icons.card_giftcard, color: _textSub, size: 40),
    );
  }

  // ── Tab 3: 兑换记录 ──

  Widget _buildRedemptionsTab() {
    if (_loadingRedemptions) {
      return const LoadingSkeleton(itemCount: 4, itemHeight: 90);
    }
    if (_errorRedemptions != null) {
      return ErrorRetryWidget(
        message: _errorRedemptions!,
        onRetry: _loadRedemptions,
      );
    }
    if (_redemptions.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.receipt_long, size: 64, color: _textSub),
            const SizedBox(height: 16),
            const Text('暂无兑换记录', style: TextStyle(color: _textSub)),
            const SizedBox(height: 24),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: _brand),
              onPressed: _loadRedemptions,
              child: const Text('刷新'),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      color: _brand,
      onRefresh: _loadRedemptions,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _redemptions.length,
        itemBuilder: (context, index) {
          final r = _redemptions[index] as Map<String, dynamic>;
          return _redemptionCard(r);
        },
      ),
    );
  }

  Widget _redemptionCard(Map<String, dynamic> r) {
    final itemName = r['item_name'] as String? ?? '';
    final pointsSpent = r['points_spent'] as int? ?? 0;
    final status = r['status'] as String? ?? '';
    final createdAt = r['created_at'] as String? ?? '';
    final discountCode = r['discount_code'] as String?;

    String timeStr = '';
    try {
      timeStr = DateTime.parse(createdAt).toLocal().toString().substring(0, 16);
    } catch (_) {}

    String statusText;
    Color statusColor;
    switch (status) {
      case 'completed':
        statusText = '已完成';
        statusColor = Colors.green;
        break;
      case 'pending':
        statusText = '处理中';
        statusColor = Colors.orange;
        break;
      case 'expired':
        statusText = '已过期';
        statusColor = Colors.red;
        break;
      case 'cancelled':
        statusText = '已取消';
        statusColor = _textSub;
        break;
      default:
        statusText = '未知';
        statusColor = _textSub;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  itemName,
                  style: const TextStyle(
                    color: _textMain,
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  statusText,
                  style: TextStyle(color: statusColor, fontSize: 11),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              const Icon(Icons.stars, color: _brand, size: 16),
              const SizedBox(width: 4),
              Text(
                '消耗 $pointsSpent 积分',
                style: const TextStyle(color: _brand, fontSize: 14),
              ),
            ],
          ),
          if (discountCode != null && discountCode.isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: _border,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.local_offer, color: _brand, size: 16),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '兑换码：$discountCode',
                      style: const TextStyle(color: _textMain, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 8),
          Text(timeStr, style: const TextStyle(color: _textSub, fontSize: 12)),
        ],
      ),
    );
  }

  // ── Tab 4: 排行榜 ──

  Widget _buildRankingTab() {
    if (_loadingRanking) {
      return const LoadingSkeleton(itemCount: 4, itemHeight: 90);
    }
    if (_errorRanking != null) {
      return ErrorRetryWidget(message: _errorRanking!, onRetry: _loadRanking);
    }
    if (_ranking.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.leaderboard, size: 64, color: _textSub),
            const SizedBox(height: 16),
            const Text('暂无排行榜数据', style: TextStyle(color: _textSub)),
            const SizedBox(height: 24),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: _brand),
              onPressed: _loadRanking,
              child: const Text('刷新'),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      color: _brand,
      onRefresh: _loadRanking,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _ranking.length,
        itemBuilder: (context, index) {
          final r = _ranking[index] as Map<String, dynamic>;
          return _rankingTile(r);
        },
      ),
    );
  }

  Widget _rankingTile(Map<String, dynamic> r) {
    final rank = r['rank'] as int? ?? 0;
    final userName = r['user_name'] as String? ?? '匿名用户';
    final role = r['role'] as String? ?? '';
    final yearEarned = r['year_earned'] as int? ?? 0;
    final level = r['level'] as String?;

    const roleMap = {
      'homeowner': '业主',
      'designer': '设计师',
      'contractor': '施工方',
      'supplier': '供应商',
    };
    final roleText = roleMap[role] ?? role;

    Color rankColor = _textSub;
    if (rank == 1) {
      rankColor = const Color(0xFFFFD700);
    } else if (rank == 2) {
      rankColor = const Color(0xFFC0C0C0);
    } else if (rank == 3) {
      rankColor = const Color(0xFFCD7F32);
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: rank <= 3 ? rankColor : _border),
      ),
      child: Row(
        children: [
          // 排名
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: rank <= 3 ? rankColor.withValues(alpha: 0.15) : _border,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Center(
              child: rank <= 3
                  ? Icon(
                      rank == 1
                          ? Icons.looks_one
                          : rank == 2
                          ? Icons.looks_two
                          : Icons.looks_3,
                      color: rankColor,
                      size: 24,
                    )
                  : Text(
                      '$rank',
                      style: const TextStyle(
                        color: _textSub,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
            ),
          ),
          const SizedBox(width: 12),
          // 头像占位
          CircleAvatar(
            radius: 18,
            backgroundColor: _border,
            child: Text(
              userName.isNotEmpty ? userName[0] : '?',
              style: const TextStyle(color: _textMain),
            ),
          ),
          const SizedBox(width: 12),
          // 信息
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  userName,
                  style: const TextStyle(
                    color: _textMain,
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  roleText + (level != null ? ' · $level' : ''),
                  style: const TextStyle(color: _textSub, fontSize: 11),
                ),
              ],
            ),
          ),
          // 积分
          Row(
            children: [
              const Icon(Icons.stars, color: _brand, size: 16),
              const SizedBox(width: 4),
              Text(
                '$yearEarned',
                style: const TextStyle(
                  color: _brand,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
