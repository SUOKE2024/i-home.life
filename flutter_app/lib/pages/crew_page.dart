import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// 工程队匹配页面 (F36)
class CrewPage extends StatefulWidget {
  final String projectId;
  const CrewPage({super.key, required this.projectId});

  @override
  State<CrewPage> createState() => _CrewPageState();
}

class _CrewPageState extends State<CrewPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  List<dynamic> _crews = [];
  List<dynamic> _matches = [];
  bool _loading = false;
  String? _error;

  static const _phaseLabels = {
    'demolition': '拆除',
    'mep': '水电',
    'tiling': '泥瓦',
    'carpentry': '木工',
    'painting': '油漆',
    'installation': '安装',
    'finishing': '收尾',
    'acceptance': '验收',
  };

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final crewResult = await _api.getList('/crews');
    if (crewResult.isSuccess) {
      _crews = crewResult.data;
    }
    final matchResult = await _api.getList('/crews/matches/${widget.projectId}');
    if (matchResult.isSuccess) {
      _matches = matchResult.data;
    }
    if (!crewResult.isSuccess && !matchResult.isSuccess) {
      _error = '加载工程队数据失败';
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _matchCrew() async {
    final result = await _api.post('/crews/match', {
      'project_id': widget.projectId,
    });
    if (result.isSuccess) {
      await _loadData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('匹配请求已发送')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('匹配失败：${result.error}')),
        );
      }
    }
  }

  Future<void> _updateMatchStatus(String matchId, String status) async {
    final result = await _api.patch('/crews/matches/$matchId/status', {'status': status});
    if (result.isSuccess) {
      await _loadData();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('更新失败：${result.error}')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('工程队匹配'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: '工程队列表'),
            Tab(text: '匹配记录'),
            Tab(text: '智能匹配'),
          ],
        ),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadData),
        ],
      ),
      body: _loading
          ? const LoadingSkeleton(itemCount: 3, itemHeight: 140)
          : _error != null
              ? ErrorRetryWidget(message: _error!, onRetry: _loadData)
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildCrewList(colors),
                    _buildMatchList(colors),
                    _buildMatchPanel(colors),
                  ],
                ),
    );
  }

  Widget _buildCrewList(ColorScheme colors) {
    if (_crews.isEmpty) {
      return Center(child: Text('暂无可选工程队', style: TextStyle(color: colors.onSurfaceVariant)));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _crews.length,
      itemBuilder: (_, i) {
        final crew = _crews[i];
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    CircleAvatar(
                      backgroundColor: colors.primary.withValues(alpha: 0.1),
                      child: Icon(Icons.engineering, color: colors.primary, size: 20),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        crew['name'] ?? '未命名工程队',
                        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
                      ),
                    ),
                    _buildRatingStars(crew['rating'] ?? 0),
                  ],
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    _buildChip('专长: ${_phaseLabels[crew['specialty']] ?? crew['specialty'] ?? '综合'}'),
                    _buildChip('团队: ${crew['team_size'] ?? '-'}人'),
                    _buildChip('完成: ${crew['completed_projects'] ?? '-'} 项目'),
                    _buildChip('评分: ${crew['rating'] ?? '-'}'),
                  ],
                ),
                if (crew['description'] != null) ...[
                  const SizedBox(height: 6),
                  Text(crew['description'], style: TextStyle(color: colors.onSurfaceVariant, fontSize: 13)),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildMatchList(ColorScheme colors) {
    if (_matches.isEmpty) {
      return Center(child: Text('暂无匹配记录', style: TextStyle(color: colors.onSurfaceVariant)));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _matches.length,
      itemBuilder: (_, i) {
        final match = _matches[i];
        final status = match['status'] ?? 'pending';
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        match['crew_name'] ?? '工程队',
                        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
                      ),
                    ),
                    _buildStatusChip(status),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('匹配分数: ${match['score'] ?? '-'}',
                        style: TextStyle(color: colors.onSurfaceVariant, fontSize: 13)),
                    if (status == 'pending')
                      Row(
                        children: [
                          TextButton(
                            onPressed: () => _updateMatchStatus(match['id'], 'accepted'),
                            child: const Text('接受'),
                          ),
                          const SizedBox(width: 4),
                          TextButton(
                            onPressed: () => _updateMatchStatus(match['id'], 'rejected'),
                            child: const Text('拒绝', style: TextStyle(color: Colors.red)),
                          ),
                        ],
                      ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildMatchPanel(ColorScheme colors) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.auto_awesome, size: 48, color: Color(0xFF7C5CFC)),
          const SizedBox(height: 16),
          Text('智能匹配工程队',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: colors.primary)),
          const SizedBox(height: 8),
          Text('根据项目类型、面积、预算和施工阶段，智能推荐最合适的工程队组合',
              textAlign: TextAlign.center,
              style: TextStyle(color: colors.onSurfaceVariant, fontSize: 14)),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _matchCrew,
            icon: const Icon(Icons.auto_awesome),
            label: const Text('开始匹配'),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRatingStars(dynamic rating) {
    final r = (rating is num) ? rating.toDouble() : 0.0;
    final filled = r.round();
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(5, (i) {
        return Icon(
          i < filled ? Icons.star : Icons.star_border,
          size: 16,
          color: const Color(0xFFFFB800),
        );
      }),
    );
  }

  Widget _buildChip(String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A2E),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(label, style: const TextStyle(fontSize: 11, color: Color(0xFFA0A0C0))),
    );
  }

  Widget _buildStatusChip(String status) {
    final (label, color) = switch (status) {
      'pending' => ('待响应', Colors.orange),
      'accepted' => ('已接受', Colors.green),
      'rejected' => ('已拒绝', Colors.red),
      'hired' => ('已雇佣', Colors.blue),
      _ => (status, Colors.grey),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(label, style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w500)),
    );
  }
}
