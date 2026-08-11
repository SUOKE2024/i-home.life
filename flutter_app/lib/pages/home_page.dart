import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';

import '../services/offline_cache_service.dart';
import '../services/api.dart';
import '../services/a2ui_renderer.dart';
import '../theme/suoke_theme.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/user_avatar.dart';
import 'ai_chat_page.dart';
import 'settings_page.dart';

/// 家的生命线 — 首页（2026 空间智能 × 时间叙事落地）
///
/// 结构（自上而下）：
///   1. 项目卡片（项目切换 + 阶段状态）
///   2. 生命线：7 节点时间轴（量房→设计→预算→施工→质检→结算→入住）
///   3. 施工健康分环（按进度预警严重度估算，诚实标注）
///   4. 空间状态（户型方案列表）
///   5. Ambient 主动卡片流（Health OS 进度预警 + Agent 归因）
///   6. 对话 AI 管家入口（聊天降为次入口）
class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  bool _isOffline = false;
  StreamSubscription<bool>? _connectivitySub;

  final ApiClient _api = ApiClient();

  List<dynamic> _projects = [];
  String? _projectId;
  Map<String, dynamic>? _project;
  List<dynamic> _floorplans = [];
  List<dynamic> _alerts = [];
  List<dynamic> _milestones = [];
  Map<String, dynamic>? _activePlan; // 激活户型详情（户型图逐房间渲染数据源）
  List<dynamic> _feedCards = [];     // A2UI 主动卡片流（8 类卡片并入首页 feed）
  bool _loading = true;
  String? _error;

  static const _labels = ['量房', '设计', '预算', '施工', '质检', '结算', '入住'];

  @override
  void initState() {
    super.initState();
    _initConnectivity();
    _load();
  }

  Future<void> _initConnectivity() async {
    final online = await OfflineCacheService().isConnected();
    if (mounted) setState(() => _isOffline = !online);
    _connectivitySub =
        OfflineCacheService().onConnectivityChanged.listen((online) {
      if (mounted) {
        setState(() => _isOffline = !online);
        unawaited(SemanticsService.sendAnnouncement(
          View.of(context),
          online ? '已恢复在线连接' : '已进入离线模式，显示缓存数据',
          TextDirection.ltr,
        ));
      }
    });
  }

  @override
  void dispose() {
    _connectivitySub?.cancel();
    super.dispose();
  }

  /// 加载项目列表 → 默认选中（首个进行中，否则首个）→ 并行拉取该项目的
  /// 户型/预警/里程碑。
  Future<void> _load({String? selectProjectId}) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final projectsResult = await _api.getProjects();
    if (!projectsResult.isSuccess) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = projectsResult.error ?? '加载失败，请检查网络后重试';
        });
      }
      return;
    }
    final projects = (projectsResult.data as List<dynamic>? ?? []);
    var projectId = selectProjectId ?? _projectId;
    if (projectId == null) {
      final inProgress = projects
          .where((p) => p['status'] == 'in_progress')
          .toList();
      projectId =
          (inProgress.isNotEmpty ? inProgress.first : projects.isNotEmpty ? projects.first : null)?['id']
              as String?;
    }
    Map<String, dynamic>? project;
    List<dynamic> floorplans = [];
    List<dynamic> alerts = [];
    List<dynamic> milestones = [];
    List<dynamic> feedCards = [];
    Map<String, dynamic>? activePlan;
    if (projectId != null) {
      for (final p in projects) {
        if (p['id'] == projectId) project = p;
      }
      final results = await Future.wait([
        _api.getList('/floorplans/project/$projectId'),
        _api.get('/construction/progress-alerts/$projectId'),
        _api.get('/construction/milestones/$projectId'),
        _api.get('/feed/$projectId'),
      ]);
      if (results[0].isSuccess) floorplans = results[0].data as List<dynamic>? ?? [];
      if (results[1].isSuccess) alerts = results[1].data as List<dynamic>? ?? [];
      if (results[2].isSuccess) milestones = results[2].data as List<dynamic>? ?? [];
      if (results[3].isSuccess) {
        final feed = results[3].data;
        if (feed is Map && feed['cards'] is List) feedCards = feed['cards'] as List;
      }
      // 空间即导航：拉取激活户型详情（data JSON 含 rooms 几何），用于户型图逐房间状态
      if (floorplans.isNotEmpty) {
        final active = floorplans.where((f) => f['is_active'] == true).firstOrNull ??
            floorplans.first;
        final detail = await _api.get('/floorplans/${active['id']}');
        if (detail.isSuccess && detail.data is Map) {
          activePlan = detail.data as Map<String, dynamic>;
        }
      }
    }
    if (mounted) {
      setState(() {
        _projects = projects;
        _projectId = projectId;
        _project = project;
        _floorplans = floorplans;
        _alerts = alerts;
        _milestones = milestones;
        _feedCards = feedCards;
        _activePlan = activePlan;
        _loading = false;
      });
    }
  }

  // ── 数据派生 ──

  String? get _status => _project?['status']?.toString();

  /// 生命线 7 节点：基于项目状态 + 户型存在性 + 里程碑完成度诚实推断
  List<bool> _nodeDone() {
    final status = _status;
    final hasPlan = _floorplans.isNotEmpty;
    final ms = _milestones;
    final doneMs = ms.where((m) => m['actual_date'] != null).length;
    final ratio = ms.isEmpty ? 0.0 : doneMs / ms.length;
    final completed = status == 'completed';
    final inProgress = status == 'in_progress';
    return [
      hasPlan, // 量房（有户型数据）
      hasPlan, // 设计（户型方案）
      inProgress || completed, // 预算
      inProgress || completed, // 施工
      completed || (inProgress && ratio >= 0.6), // 质检
      completed || (inProgress && ratio >= 0.9), // 结算
      completed, // 入住
    ];
  }

  /// 施工健康分（0-100）：按未解决预警严重度扣分，诚实标注为估算
  int _healthScore() {
    const sev = {'critical': 28.0, 'high': 14.0, 'medium': 6.0, 'low': 2.0};
    var penalty = 0.0;
    for (final a in _alerts) {
      if (a['status'] == 'resolved') continue;
      penalty += sev[a['severity']?.toString()] ?? 6.0;
    }
    return max(0, 100 - penalty).round().clamp(0, 100);
  }

  int get _unresolvedCount => _alerts.where((a) => a['status'] != 'resolved').length;

  // ── UI ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          if (_isOffline) _buildOfflineBanner(),
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildOfflineBanner() {
    return Semantics(
      container: true,
      label: '离线模式横幅：当前离线，显示缓存数据',
      child: Container(
        color: const Color(0xFFBF360C),
        padding: EdgeInsets.only(
          top: MediaQuery.of(context).padding.top,
          bottom: 8,
          left: 16,
          right: 16,
        ),
        child: const Row(
          children: [
            Icon(Icons.cloud_off, color: Colors.white, size: 16),
            SizedBox(width: 8),
            Text('离线模式 · 显示缓存数据',
                style: TextStyle(color: Colors.white, fontSize: 13)),
          ],
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 5, itemHeight: 96);
    }
    if (_error != null && _projects.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_error!, style: TextStyle(color: SuokeDesignTokens.textSub(context))),
            const SizedBox(height: 12),
            TextButton(
              onPressed: _load,
              child: const Text('重试', style: TextStyle(color: SuokeDesignTokens.accent)),
            ),
          ],
        ),
      );
    }
    if (_projectId == null) {
      return _buildEmptyProjects();
    }
    return RefreshIndicator(
      onRefresh: () => _load(),
      child: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          SliverAppBar(
            pinned: true,
            backgroundColor: SuokeDesignTokens.card(context),
            surfaceTintColor: Colors.transparent,
            elevation: 0,
            scrolledUnderElevation: 0,
            title: Row(
              children: [
                Image.asset('assets/images/suoke-logo.png',
                    width: 26, height: 26, fit: BoxFit.contain),
                const SizedBox(width: 8),
                const Text('家的生命线',
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              ],
            ),
            actions: [
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: GestureDetector(
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const SettingsPage()),
                  ),
                  child: const UserAvatar(size: 34),
                ),
              ),
            ],
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            sliver: SliverList.list(
              children: [
                _buildProjectCard(),
                const SizedBox(height: 12),
                _buildLifelineCard(),
                const SizedBox(height: 12),
                _buildHealthCard(),
                const SizedBox(height: 12),
                _buildSpacesCard(),
                const SizedBox(height: 12),
                _buildFeedCard(),
                const SizedBox(height: 12),
                _buildChatCta(),
                const SizedBox(height: 24),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyProjects() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.home_work_outlined, size: 48, color: SuokeDesignTokens.accent),
            const SizedBox(height: 12),
            Text('还没有项目', style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 6),
            Text('创建第一个家装项目，开始你的家的生命线',
                style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: () => _load(),
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('刷新'),
            ),
          ],
        ),
      ),
    );
  }

  // ── ① 项目卡片 ──

  Widget _buildProjectCard() {
    final status = _status;
    final statusLabel = switch (status) {
      'completed' => '已完成',
      'in_progress' => '施工中',
      _ => '草稿',
    };
    final area = _project?['total_area'];
    final address = _project?['address']?.toString() ?? '';
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_project?['name']?.toString() ?? '未命名项目',
                        style: TextStyle(
                            color: SuokeDesignTokens.text(context),
                            fontSize: 16,
                            fontWeight: FontWeight.w700)),
                    const SizedBox(height: 4),
                    Text(
                      [
                        if (area != null) '$area ㎡',
                        if (address.isNotEmpty) address,
                      ].join(' · '),
                      style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12),
                    ),
                  ],
                ),
              ),
              _statusChip(statusLabel, status),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 44,
            child: PopupMenuButton<String>(
              tooltip: '切换项目',
              color: SuokeDesignTokens.card(context),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(SuokeDesignTokens.radius),
                side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
              ),
              onSelected: (id) => _load(selectProjectId: id),
              itemBuilder: (ctx) => [
                for (final p in _projects)
                  PopupMenuItem(
                    value: p['id']?.toString(),
                    child: Row(
                      children: [
                        Icon(
                          p['id'] == _projectId ? Icons.check : Icons.circle_outlined,
                          size: 16,
                          color: p['id'] == _projectId
                              ? SuokeDesignTokens.accent
                              : SuokeDesignTokens.textSub(context),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            p['name']?.toString() ?? '未命名',
                            style: TextStyle(color: SuokeDesignTokens.text(ctx), fontSize: 13),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: SuokeDesignTokens.borderClr(context)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('切换项目', style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12)),
                    const SizedBox(width: 4),
                    Icon(Icons.expand_more, size: 18, color: SuokeDesignTokens.textSub(context)),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _statusChip(String label, String? status) {
    final color = switch (status) {
      'completed' => SuokeDesignTokens.success,
      'in_progress' => SuokeDesignTokens.accent,
      _ => SuokeDesignTokens.textSub(context),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(label,
          style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600)),
    );
  }

  // ── ② 生命线 7 节点 ──

  Widget _buildLifelineCard() {
    final done = _nodeDone();
    final currentIdx = done.indexOf(false);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('家的生命线', style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 14, fontWeight: FontWeight.w700)),
              const Spacer(),
              Text('阶段概览 · 按现有数据推断',
                  style: TextStyle(color: SuokeDesignTokens.textMutedClr(context), fontSize: 10)),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: List.generate(_labels.length, (i) {
              final isDone = done[i];
              final isNow = i == currentIdx;
              return Expanded(
                child: Column(
                  children: [
                    Container(
                      width: 30,
                      height: 30,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isDone
                            ? SuokeDesignTokens.accent.withValues(alpha: 0.16)
                            : isNow
                                ? SuokeDesignTokens.accent
                                : SuokeDesignTokens.surface2.withValues(alpha: 0.4),
                        border: Border.all(
                          color: isDone || isNow
                              ? SuokeDesignTokens.accent
                              : SuokeDesignTokens.borderClr(context),
                          width: isNow ? 2 : 1,
                        ),
                      ),
                      child: Center(
                        child: isDone
                            ? const Icon(Icons.check, size: 15, color: SuokeDesignTokens.accent)
                            : Text('${i + 1}',
                                style: TextStyle(
                                    color: isNow
                                        ? SuokeDesignTokens.bgDeep
                                        : SuokeDesignTokens.textSub(context),
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700)),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(_labels[i],
                        style: TextStyle(
                            fontSize: 9.5,
                            color: isNow || isDone
                                ? SuokeDesignTokens.accent
                                : SuokeDesignTokens.textMutedClr(context),
                            fontWeight: isNow ? FontWeight.w700 : FontWeight.w500)),
                  ],
                ),
              );
            }),
          ),
          if (currentIdx >= 0 && currentIdx < _labels.length) ...[
            const SizedBox(height: 12),
            Text('当前阶段 · ${_labels[currentIdx]}',
                style: const TextStyle(color: SuokeDesignTokens.accent, fontSize: 12, fontWeight: FontWeight.w600)),
          ] else ...[
            const SizedBox(height: 12),
            const Text('全流程已完成，欢迎入住新家',
                style: TextStyle(color: SuokeDesignTokens.success, fontSize: 12, fontWeight: FontWeight.w600)),
          ],
        ],
      ),
    );
  }

  // ── ③ 健康分 ──

  Widget _buildHealthCard() {
    final score = _healthScore();
    final color = score >= 80
        ? SuokeDesignTokens.success
        : score >= 50
            ? SuokeDesignTokens.warning
            : SuokeDesignTokens.danger;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Row(
        children: [
          SizedBox(
            width: 96,
            height: 96,
            child: Stack(
              alignment: Alignment.center,
              children: [
                SizedBox(
                  width: 96,
                  height: 96,
                  child: CircularProgressIndicator(
                    value: score / 100,
                    strokeWidth: 10,
                    strokeCap: StrokeCap.round,
                    backgroundColor: SuokeDesignTokens.surface2.withValues(alpha: 0.5),
                    color: color,
                  ),
                ),
                Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('$score',
                        style: TextStyle(
                            color: SuokeDesignTokens.text(context),
                            fontSize: 26,
                            fontWeight: FontWeight.w800)),
                    Text('健康分',
                        style: TextStyle(
                            color: SuokeDesignTokens.textMutedClr(context), fontSize: 10)),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('施工健康分',
                    style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 14, fontWeight: FontWeight.w700)),
                const SizedBox(height: 6),
                Text(
                  '由 $_unresolvedCount 条未解决进度预警按严重度估算，仅供参考。',
                  style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12, height: 1.6),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── ④ 空间状态（户型图逐房间状态） ──

  /// 房间状态 map（{"客厅": "in_progress", ...}）
  Map<String, String> _roomStatusMap(Map<String, dynamic> plan) {
    final raw = plan['room_status'];
    if (raw is Map) {
      return raw.map((k, v) => MapEntry(k.toString(), v.toString()));
    }
    return {};
  }

  /// 从户型 data JSON 解析 rooms（[{name, area, room_type}, ...]）
  List<Map<String, dynamic>> _roomsFromData(dynamic data) {
    if (data is! String || data.isEmpty) return [];
    try {
      final parsed = jsonDecode(data);
      if (parsed is Map && parsed['rooms'] is List) {
        return (parsed['rooms'] as List)
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList();
      }
    } catch (_) {}
    return [];
  }

  /// 房间状态 → (颜色, 文案)
  (Color, String) _roomStatusStyle(String? status) {
    return switch (status) {
      'completed' => (SuokeDesignTokens.success, '已完成'),
      'in_progress' => (SuokeDesignTokens.accent, '施工中'),
      'attention' => (SuokeDesignTokens.danger, '需关注'),
      'not_started' => (SuokeDesignTokens.textSub(context), '未开始'),
      _ => (SuokeDesignTokens.textMutedClr(context), '待标注'),
    };
  }

  /// 户型图逐房间网格（激活户型：rooms 几何 + room_status 着色）
  Widget _buildRoomGrid() {
    final plan = _activePlan;
    if (plan == null) return const SizedBox.shrink();
    final statusMap = _roomStatusMap(plan);
    var rooms = _roomsFromData(plan['data']);
    if (rooms.isEmpty) {
      rooms = statusMap.keys.map((k) => {'name': k}).toList();
    }
    if (rooms.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('户型图',
                style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 12, fontWeight: FontWeight.w600)),
            const SizedBox(width: 8),
            Text('逐房间状态 · 按现有数据标注',
                style: TextStyle(color: SuokeDesignTokens.textMutedClr(context), fontSize: 10)),
          ],
        ),
        const SizedBox(height: 10),
        LayoutBuilder(builder: (context, constraints) {
          final tileWidth = (constraints.maxWidth - 16) / 3;
          return Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final r in rooms.take(9))
                _buildRoomTile(
                  r['name']?.toString() ?? '房间',
                  area: r['area'],
                  status: statusMap[r['name']?.toString()],
                  width: tileWidth,
                ),
            ],
          );
        }),
        if (statusMap.isEmpty) ...[
          const SizedBox(height: 8),
          Text('房间施工状态暂未标注，可在 AI 管家对话中更新',
              style: TextStyle(color: SuokeDesignTokens.textMutedClr(context), fontSize: 10)),
        ],
      ],
    );
  }

  Widget _buildRoomTile(String name, {dynamic area, String? status, required double width}) {
    final (color, label) = _roomStatusStyle(status);
    return Container(
      width: width,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(name,
              style: TextStyle(
                  color: SuokeDesignTokens.text(context),
                  fontSize: 12,
                  fontWeight: FontWeight.w700),
              overflow: TextOverflow.ellipsis),
          const SizedBox(height: 3),
          Text(
            [if (area != null) '$area ㎡', if (status != null) label].join(' · '),
            style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w600),
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _buildSpacesCard() {
    final activePlan = _activePlan;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('空间状态', style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 14, fontWeight: FontWeight.w700)),
              const SizedBox(width: 8),
              Text('户型方案', style: TextStyle(color: SuokeDesignTokens.textMutedClr(context), fontSize: 11)),
            ],
          ),
          const SizedBox(height: 12),
          if (_floorplans.isEmpty)
            Text('暂无户型方案，可让 AI 管家协助量房与户型规划',
                style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12, height: 1.6))
          else ...[
            // 户型图逐房间状态（激活户型）
            _buildRoomGrid(),
            const SizedBox(height: 12),
            for (final fp in _floorplans.take(4))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 34,
                          height: 34,
                          decoration: BoxDecoration(
                            color: SuokeDesignTokens.accent.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: const Icon(Icons.home_outlined, size: 18, color: SuokeDesignTokens.accent),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(fp['name']?.toString() ?? '户型',
                              style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 13, fontWeight: FontWeight.w600)),
                        ),
                        Text(
                          '${fp['room_count'] ?? 0} 间 · ${fp['total_area'] ?? 0} ㎡',
                          style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12),
                        ),
                        if (fp['is_active'] == true) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: SuokeDesignTokens.success.withValues(alpha: 0.14),
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: const Text('当前',
                                style: TextStyle(color: SuokeDesignTokens.success, fontSize: 10, fontWeight: FontWeight.w600)),
                          ),
                        ],
                      ],
                    ),
                    if (fp['id'] != activePlan?['id']) _buildPlanRoomSummary(fp),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }

  /// 非激活户型的逐房间状态摘要（如 "客厅·施工中 主卧·未开始"）
  Widget _buildPlanRoomSummary(Map<String, dynamic> fp) {
    final statusMap = _roomStatusMap(fp);
    if (statusMap.isEmpty) return const SizedBox.shrink();
    final parts = statusMap.entries
        .take(4)
        .map((e) => '${e.key}·${_roomStatusStyle(e.value).$2}')
        .join('  ');
    return Padding(
      padding: const EdgeInsets.only(left: 46, top: 4),
      child: Text(parts,
          style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 11),
          overflow: TextOverflow.ellipsis),
    );
  }

  // ── ⑤ Ambient 主动卡片流（A2UI 8 类卡片 + 进度预警回退） ──

  Widget _buildFeedCard() {
    final alertFeeds = _alerts.where((a) => a['status'] != 'resolved').toList();
    final cards = _feedCards;
    final useCards = cards.isNotEmpty;
    final count = useCards ? cards.length : alertFeeds.length;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('管家主动卡片', style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 14, fontWeight: FontWeight.w700)),
              const Spacer(),
              if (count > 0)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: SuokeDesignTokens.warning.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text('$count 条待处理',
                      style: const TextStyle(color: SuokeDesignTokens.warning, fontSize: 10, fontWeight: FontWeight.w600)),
                ),
            ],
          ),
          const SizedBox(height: 12),
          if (useCards)
            for (final c in cards.take(6))
              A2UIRenderer(
                card: c is Map ? Map<String, dynamic>.from(c) : const {},
                onAction: _onFeedAction,
              )
          else if (alertFeeds.isEmpty)
            Text('暂无待处理事项，一切正常。',
                style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12))
          else
            for (final a in alertFeeds.take(6)) _buildFeedItem(a),
          if (useCards) ...[
            const SizedBox(height: 4),
            Text('卡片由项目现有数据按 A2UI 协议生成，仅供导航参考',
                style: TextStyle(color: SuokeDesignTokens.textMutedClr(context), fontSize: 10)),
          ],
        ],
      ),
    );
  }

  /// A2UI 卡片操作回调：统一跳转 AI 管家，携带卡片文案作为上下文
  void _onFeedAction(String action, Map<String, dynamic> payload) {
    final text = payload['title'] ?? payload['message'] ?? payload['name'];
    _openChat(prefill: text is String && text.isNotEmpty ? text : null);
  }

  Widget _buildFeedItem(Map<String, dynamic> alert) {
    final severity = alert['severity']?.toString() ?? 'medium';
    final (color, label) = switch (severity) {
      'critical' => (SuokeDesignTokens.danger, '严重'),
      'high' => (SuokeDesignTokens.warning, '高'),
      'low' => (SuokeDesignTokens.success, '低'),
      _ => (SuokeDesignTokens.accent, '中'),
    };
    final phase = alert['phase']?.toString() ?? '';
    final message = alert['message']?.toString() ?? '';
    final suggestion = alert['suggestion']?.toString();
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(9),
            ),
            child: Icon(Icons.notifications_active_outlined, size: 16, color: color),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.14),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(label,
                          style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700)),
                    ),
                    if (phase.isNotEmpty) ...[
                      const SizedBox(width: 6),
                      Text(phase,
                          style: TextStyle(color: SuokeDesignTokens.textMutedClr(context), fontSize: 10)),
                    ],
                  ],
                ),
                const SizedBox(height: 5),
                Text(message,
                    style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 12.5, height: 1.5)),
                if (suggestion != null && suggestion.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text('建议：$suggestion',
                      style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 11.5, height: 1.5)),
                ],
                const SizedBox(height: 6),
                Row(
                  children: [
                    Expanded(
                      child: Text('进度预警 · Health OS 自动生成',
                          style: TextStyle(color: SuokeDesignTokens.textMutedClr(context), fontSize: 10)),
                    ),
                    TextButton(
                      onPressed: () => _openChat(prefill: message),
                      style: TextButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        minimumSize: const Size(44, 36),
                      ),
                      child: const Text('问管家',
                          style: TextStyle(color: SuokeDesignTokens.accent, fontSize: 11.5)),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── ⑥ 对话入口 ──

  Widget _buildChatCta() {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [Color(0xFFC9973B), Color(0xFFE0AA4A)]),
        borderRadius: BorderRadius.circular(16),
      ),
      child: ElevatedButton(
        onPressed: () => _openChat(),
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.transparent,
          shadowColor: Colors.transparent,
          foregroundColor: const Color(0xFF1C1915),
          minimumSize: const Size(double.infinity, 56),
          padding: const EdgeInsets.symmetric(horizontal: 16),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
        ),
        child: const Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.auto_awesome, size: 18),
            SizedBox(width: 8),
            Text('对话 AI 管家'),
          ],
        ),
      ),
    );
  }

  void _openChat({String? prefill}) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => AIChatPage(projectId: _projectId, prefillText: prefill)),
    );
  }

  BoxDecoration _cardDecoration() {
    return BoxDecoration(
      color: SuokeDesignTokens.card(context),
      borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusLg),
      border: Border.all(color: SuokeDesignTokens.borderClr(context)),
    );
  }
}
