import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';
import '../theme/suoke_theme.dart';

class TasksPage extends StatefulWidget {
  final String projectId;
  const TasksPage({super.key, required this.projectId});

  @override
  State<TasksPage> createState() => _TasksPageState();
}

class _TasksPageState extends State<TasksPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  // 优先级颜色
  static const Color _priorityHigh = Color(0xFFE53935);
  static const Color _priorityMid = SuokeDesignTokens.accent;
  static const Color _priorityLow = Color(0xFF43A047);

  List<dynamic> _tasks = [];
  bool _loading = false;
  String? _error;

  // 列表视图筛选
  String _filterStatus = 'all';
  String _filterPriority = 'all';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadTasks();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadTasks() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.taskListByProject(widget.projectId);
    if (result.isSuccess) {
      final data = result.data;
      setState(() {
        _tasks = (data['tasks'] as List?) ?? [];
      });
    } else {
      setState(() => _error = '任务加载失败，请检查网络后重试');
    }
    setState(() => _loading = false);
  }

  // ── 任务状态分组 ──

  List<dynamic> _tasksOfColumn(String column) {
    return _tasks.where((t) {
      final status = (t as Map<String, dynamic>)['status'] as String? ?? '';
      switch (column) {
        case 'todo':
          return status == 'pending';
        case 'doing':
          return status == 'claimed' || status == 'in_progress';
        case 'done':
          return status == 'completed';
        default:
          return false;
      }
    }).toList();
  }

  // ── 优先级映射 ──

  /// 后端 priority 为 1-10，映射为高/中/低
  String _priorityLabel(int priority) {
    if (priority >= 8) return '高';
    if (priority >= 4) return '中';
    return '低';
  }

  Color _priorityColor(int priority) {
    if (priority >= 8) return _priorityHigh;
    if (priority >= 4) return _priorityMid;
    return _priorityLow;
  }

  /// 高/中/低 → 后端 priority 数值
  int _priorityFromLabel(String label) {
    switch (label) {
      case '高':
        return 9;
      case '中':
        return 5;
      case '低':
        return 2;
      default:
        return 5;
    }
  }

  // ── 状态文案 ──

  String _statusLabel(String status) {
    switch (status) {
      case 'pending':
        return '待办';
      case 'claimed':
        return '已申领';
      case 'in_progress':
        return '进行中';
      case 'completed':
        return '已完成';
      default:
        return status;
    }
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'pending':
        return SuokeDesignTokens.textSecondary;
      case 'claimed':
      case 'in_progress':
        return const Color(0xFF2196F3);
      case 'completed':
        return _priorityLow;
      default:
        return SuokeDesignTokens.textSecondary;
    }
  }

  // ── 截止日期格式化 ──

  String _formatDeadline(String? iso) {
    if (iso == null || iso.isEmpty) return '无截止日期';
    try {
      final dt = DateTime.parse(iso);
      final now = DateTime.now();
      final diff = dt.difference(now);
      String dateStr =
          '${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
      if (diff.isNegative) return '已逾期 · $dateStr';
      if (diff.inHours < 24) return '今日截止 · $dateStr';
      if (diff.inDays < 3) return '${diff.inDays}天后截止 · $dateStr';
      return '截止 $dateStr';
    } catch (_) {
      return '无截止日期';
    }
  }

  String _formatCreated(String? iso) {
    if (iso == null || iso.isEmpty) return '';
    try {
      final dt = DateTime.parse(iso);
      return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
          '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return '';
    }
  }

  // ── 创建任务 ──

  Future<void> _showCreateDialog() async {
    final formKey = GlobalKey<FormState>();
    String title = '';
    String description = '';
    String assignee = '';
    String priorityLabel = '中';
    DateTime? deadline;

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setDialogState) {
            return AlertDialog(
              backgroundColor: SuokeDesignTokens.cardBg,
              title: const Text('创建任务', style: TextStyle(color: SuokeDesignTokens.textPrimary)),
              content: SingleChildScrollView(
                child: Form(
                  key: formKey,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      TextFormField(
                        decoration: const InputDecoration(
                          labelText: '标题',
                          labelStyle: TextStyle(color: SuokeDesignTokens.textSecondary),
                          enabledBorder: UnderlineInputBorder(
                            borderSide: BorderSide(color: SuokeDesignTokens.border),
                          ),
                          focusedBorder: UnderlineInputBorder(
                            borderSide: BorderSide(color: SuokeDesignTokens.accent),
                          ),
                        ),
                        style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                        validator: (v) =>
                            (v == null || v.isEmpty) ? '请输入标题' : null,
                        onSaved: (v) => title = v ?? '',
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        decoration: const InputDecoration(
                          labelText: '描述',
                          labelStyle: TextStyle(color: SuokeDesignTokens.textSecondary),
                          enabledBorder: UnderlineInputBorder(
                            borderSide: BorderSide(color: SuokeDesignTokens.border),
                          ),
                          focusedBorder: UnderlineInputBorder(
                            borderSide: BorderSide(color: SuokeDesignTokens.accent),
                          ),
                        ),
                        style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                        maxLines: 2,
                        onSaved: (v) => description = v ?? '',
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        decoration: const InputDecoration(
                          labelText: '负责人',
                          labelStyle: TextStyle(color: SuokeDesignTokens.textSecondary),
                          enabledBorder: UnderlineInputBorder(
                            borderSide: BorderSide(color: SuokeDesignTokens.border),
                          ),
                          focusedBorder: UnderlineInputBorder(
                            borderSide: BorderSide(color: SuokeDesignTokens.accent),
                          ),
                        ),
                        style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                        validator: (v) =>
                            (v == null || v.isEmpty) ? '请输入负责人' : null,
                        onSaved: (v) => assignee = v ?? '',
                      ),
                      const SizedBox(height: 12),
                      DropdownButtonFormField<String>(
                        initialValue: priorityLabel,
                        decoration: const InputDecoration(
                          labelText: '优先级',
                          labelStyle: TextStyle(color: SuokeDesignTokens.textSecondary),
                          enabledBorder: UnderlineInputBorder(
                            borderSide: BorderSide(color: SuokeDesignTokens.border),
                          ),
                          focusedBorder: UnderlineInputBorder(
                            borderSide: BorderSide(color: SuokeDesignTokens.accent),
                          ),
                        ),
                        dropdownColor: SuokeDesignTokens.cardBg,
                        style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                        items: const [
                          DropdownMenuItem(value: '高', child: Text('高')),
                          DropdownMenuItem(value: '中', child: Text('中')),
                          DropdownMenuItem(value: '低', child: Text('低')),
                        ],
                        onChanged: (v) {
                          if (v != null) {
                            setDialogState(() => priorityLabel = v);
                          }
                        },
                      ),
                      const SizedBox(height: 12),
                      InkWell(
                        onTap: () async {
                          final picked = await showDatePicker(
                            context: ctx,
                            initialDate: DateTime.now().add(const Duration(days: 7)),
                            firstDate: DateTime.now(),
                            lastDate: DateTime.now().add(const Duration(days: 365)),
                            builder: (innerCtx, child) {
                              return Theme(
                                data: ThemeData.dark().copyWith(
                                  colorScheme: const ColorScheme.dark(
                                    primary: SuokeDesignTokens.accent,
                                    surface: SuokeDesignTokens.cardBg,
                                  ),
                                ),
                                child: child!,
                              );
                            },
                          );
                          if (picked != null) {
                            setDialogState(() => deadline = picked);
                          }
                        },
                        child: InputDecorator(
                          decoration: const InputDecoration(
                            labelText: '截止日期',
                            labelStyle: TextStyle(color: SuokeDesignTokens.textSecondary),
                            enabledBorder: UnderlineInputBorder(
                              borderSide: BorderSide(color: SuokeDesignTokens.border),
                            ),
                          ),
                          child: Text(
                            deadline == null
                                ? '选择日期'
                                : '${deadline!.year}-${deadline!.month.toString().padLeft(2, '0')}-${deadline!.day.toString().padLeft(2, '0')}',
                            style: TextStyle(
                              color: deadline == null ? SuokeDesignTokens.textSecondary : SuokeDesignTokens.textPrimary,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx, false),
                  child: const Text('取消'),
                ),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(backgroundColor: SuokeDesignTokens.accent),
                  onPressed: () {
                    if (formKey.currentState?.validate() ?? false) {
                      formKey.currentState?.save();
                      Navigator.pop(ctx, true);
                    }
                  },
                  child: const Text('创建'),
                ),
              ],
            );
          },
        );
      },
    );

    if (result != true) return;

    final body = <String, dynamic>{
      'project_id': widget.projectId,
      'task_type': 'manual',
      'title': title,
      'description': description.isEmpty ? null : description,
      'assigned_agent': assignee,
      'priority': _priorityFromLabel(priorityLabel),
      'claimable': true,
    };
    if (deadline != null) {
      body['claim_deadline'] = deadline!.toUtc().toIso8601String();
    }

    final res = await _api.taskCreate(body);
    if (res.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('任务创建成功')),
        );
      }
      await _loadTasks();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('创建失败：${res.error}')),
        );
      }
    }
  }

  // ── 任务状态操作 ──

  Future<void> _claimTask(Map<String, dynamic> task) async {
    final taskId = task['id'] as String;
    final res = await _api.taskClaim(taskId);
    if (res.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('已申领任务')),
        );
      }
      await _loadTasks();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('申领失败：${res.error}')),
        );
      }
    }
  }

  Future<void> _completeTask(Map<String, dynamic> task) async {
    final taskId = task['id'] as String;
    final res = await _api.taskComplete(taskId);
    if (res.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('任务已完成')),
        );
      }
      await _loadTasks();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('完成失败：${res.error}')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bgDeep,
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.bgDeep,
        title: const Text('任务管理', style: TextStyle(color: SuokeDesignTokens.textPrimary)),
        iconTheme: const IconThemeData(color: SuokeDesignTokens.textPrimary),
        bottom: TabBar(
          controller: _tabController,
          labelColor: SuokeDesignTokens.accent,
          unselectedLabelColor: SuokeDesignTokens.textSecondary,
          indicatorColor: SuokeDesignTokens.accent,
          tabs: const [
            Tab(text: '任务看板'),
            Tab(text: '任务列表'),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: SuokeDesignTokens.accent,
        foregroundColor: SuokeDesignTokens.bgDeep,
        onPressed: _showCreateDialog,
        child: const Icon(Icons.add),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildKanbanView(),
          _buildListView(),
        ],
      ),
    );
  }

  // ── 看板视图 ──

  Widget _buildKanbanView() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 3, itemHeight: 120);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadTasks);
    }
    final todoTasks = _tasksOfColumn('todo');
    final doingTasks = _tasksOfColumn('doing');
    final doneTasks = _tasksOfColumn('done');

    return RefreshIndicator(
      color: SuokeDesignTokens.accent,
      onRefresh: _loadTasks,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildKanbanColumn('待办', todoTasks, SuokeDesignTokens.textSecondary),
            const SizedBox(width: 12),
            _buildKanbanColumn('进行中', doingTasks, const Color(0xFF2196F3)),
            const SizedBox(width: 12),
            _buildKanbanColumn('已完成', doneTasks, _priorityLow),
          ],
        ),
      ),
    );
  }

  Widget _buildKanbanColumn(
      String title, List<dynamic> tasks, Color accent) {
    return SizedBox(
      width: 280,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: SuokeDesignTokens.cardBg,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: SuokeDesignTokens.border),
            ),
            child: Row(
              children: [
                Container(
                  width: 4,
                  height: 16,
                  decoration: BoxDecoration(
                    color: accent,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(width: 8),
                Text(title,
                    style: const TextStyle(
                        color: SuokeDesignTokens.textPrimary, fontWeight: FontWeight.bold)),
                const Spacer(),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: SuokeDesignTokens.border,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '${tasks.length}',
                    style: const TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 12),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          if (tasks.isEmpty)
            Container(
              padding: const EdgeInsets.all(16),
              child: const Center(
                child: Text('暂无任务', style: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 13)),
              ),
            )
          else
            ...tasks.map((t) => _buildTaskCard(t as Map<String, dynamic>)),
        ],
      ),
    );
  }

  Widget _buildTaskCard(Map<String, dynamic> task) {
    final title = task['title'] as String? ?? '无标题';
    final assignee = task['assigned_user_name'] as String? ??
        task['assigned_agent'] as String? ??
        '未分配';
    final priority = (task['priority'] as num?)?.toInt() ?? 5;
    final status = task['status'] as String? ?? 'pending';
    final deadline = task['claim_deadline'] as String?;
    final taskType = task['task_type'] as String?;
    final claimRole = task['claim_role'] as String?;

    final pColor = _priorityColor(priority);
    final pLabel = _priorityLabel(priority);

    return Container(
      width: 260,
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.cardBg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: SuokeDesignTokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 标题行 + 优先级
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: pColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: pColor.withValues(alpha: 0.5)),
                ),
                child: Text(pLabel,
                    style: TextStyle(
                        color: pColor, fontSize: 11, fontWeight: FontWeight.bold)),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(title,
                    style: const TextStyle(
                        color: SuokeDesignTokens.textPrimary, fontSize: 14, fontWeight: FontWeight.w600),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis),
              ),
            ],
          ),
          const SizedBox(height: 8),
          // 负责人
          Row(
            children: [
              const Icon(Icons.person_outline, size: 14, color: SuokeDesignTokens.textSecondary),
              const SizedBox(width: 4),
              Expanded(
                child: Text(assignee,
                    style: const TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 12),
                    overflow: TextOverflow.ellipsis),
              ),
            ],
          ),
          const SizedBox(height: 6),
          // 截止日期
          Row(
            children: [
              Icon(Icons.event_outlined,
                  size: 14,
                  color: deadline == null ? SuokeDesignTokens.textSecondary : _priorityMid),
              const SizedBox(width: 4),
              Expanded(
                child: Text(_formatDeadline(deadline),
                    style: TextStyle(
                        color: deadline == null ? SuokeDesignTokens.textSecondary : _priorityMid,
                        fontSize: 12),
                    overflow: TextOverflow.ellipsis),
              ),
            ],
          ),
          const SizedBox(height: 8),
          // 标签
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              if (taskType != null && taskType.isNotEmpty)
                _buildTag(taskType, SuokeDesignTokens.border),
              if (claimRole != null && claimRole.isNotEmpty)
                _buildTag(claimRole, SuokeDesignTokens.border),
            ],
          ),
          const SizedBox(height: 8),
          // 状态 + 操作
          Row(
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: _statusColor(status).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(_statusLabel(status),
                    style: TextStyle(color: _statusColor(status), fontSize: 11)),
              ),
              const Spacer(),
              if (status == 'pending')
                _buildActionButton('申领', () => _claimTask(task))
              else if (status == 'claimed' || status == 'in_progress')
                _buildActionButton('完成', () => _completeTask(task))
              else if (status == 'completed')
                const Icon(Icons.check_circle, size: 16, color: _priorityLow),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTag(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.bgDeep,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color),
      ),
      child: Text(text,
          style: const TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 11)),
    );
  }

  Widget _buildActionButton(String label, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: SuokeDesignTokens.accent,
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(label,
            style: const TextStyle(
                color: SuokeDesignTokens.bgDeep, fontSize: 12, fontWeight: FontWeight.bold)),
      ),
    );
  }

  // ── 列表视图 ──

  Widget _buildListView() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 5, itemHeight: 90);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadTasks);
    }

    final filtered = _filteredAndSortedTasks();

    return Column(
      children: [
        _buildFilterBar(),
        Expanded(
          child: RefreshIndicator(
            color: SuokeDesignTokens.accent,
            onRefresh: _loadTasks,
            child: filtered.isEmpty
                ? ListView(
                    children: const [
                      SizedBox(height: 120),
                      Center(
                        child: Text('暂无符合条件的任务',
                            style: TextStyle(color: SuokeDesignTokens.textSecondary)),
                      ),
                    ],
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: filtered.length,
                    itemBuilder: (context, index) {
                      final task = filtered[index] as Map<String, dynamic>;
                      return _buildListTile(task);
                    },
                  ),
          ),
        ),
      ],
    );
  }

  Widget _buildFilterBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      color: SuokeDesignTokens.bgDeep,
      child: Row(
        children: [
          // 状态筛选
          Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              decoration: BoxDecoration(
                color: SuokeDesignTokens.cardBg,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: SuokeDesignTokens.border),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  value: _filterStatus,
                  dropdownColor: SuokeDesignTokens.cardBg,
                  style: const TextStyle(color: SuokeDesignTokens.textPrimary, fontSize: 13),
                  icon: const Icon(Icons.arrow_drop_down, color: SuokeDesignTokens.textSecondary),
                  items: const [
                    DropdownMenuItem(value: 'all', child: Text('全部状态')),
                    DropdownMenuItem(value: 'pending', child: Text('待办')),
                    DropdownMenuItem(value: 'doing', child: Text('进行中')),
                    DropdownMenuItem(value: 'completed', child: Text('已完成')),
                  ],
                  onChanged: (v) {
                    if (v != null) {
                      setState(() => _filterStatus = v);
                    }
                  },
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          // 优先级筛选
          Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              decoration: BoxDecoration(
                color: SuokeDesignTokens.cardBg,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: SuokeDesignTokens.border),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  value: _filterPriority,
                  dropdownColor: SuokeDesignTokens.cardBg,
                  style: const TextStyle(color: SuokeDesignTokens.textPrimary, fontSize: 13),
                  icon: const Icon(Icons.arrow_drop_down, color: SuokeDesignTokens.textSecondary),
                  items: const [
                    DropdownMenuItem(value: 'all', child: Text('全部优先级')),
                    DropdownMenuItem(value: '高', child: Text('高优先级')),
                    DropdownMenuItem(value: '中', child: Text('中优先级')),
                    DropdownMenuItem(value: '低', child: Text('低优先级')),
                  ],
                  onChanged: (v) {
                    if (v != null) {
                      setState(() => _filterPriority = v);
                    }
                  },
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  List<dynamic> _filteredAndSortedTasks() {
    var result = _tasks.where((t) {
      final task = t as Map<String, dynamic>;
      // 状态筛选
      if (_filterStatus != 'all') {
        final status = task['status'] as String? ?? '';
        if (_filterStatus == 'doing') {
          if (status != 'claimed' && status != 'in_progress') return false;
        } else if (status != _filterStatus) {
          return false;
        }
      }
      // 优先级筛选
      if (_filterPriority != 'all') {
        final priority = (task['priority'] as num?)?.toInt() ?? 5;
        if (_priorityLabel(priority) != _filterPriority) return false;
      }
      return true;
    }).toList();

    // 按创建时间倒序
    result.sort((a, b) {
      final aTime = (a as Map<String, dynamic>)['created_at'] as String? ?? '';
      final bTime = (b as Map<String, dynamic>)['created_at'] as String? ?? '';
      return bTime.compareTo(aTime);
    });

    return result;
  }

  Widget _buildListTile(Map<String, dynamic> task) {
    final title = task['title'] as String? ?? '无标题';
    final assignee = task['assigned_user_name'] as String? ??
        task['assigned_agent'] as String? ??
        '未分配';
    final priority = (task['priority'] as num?)?.toInt() ?? 5;
    final status = task['status'] as String? ?? 'pending';
    final deadline = task['claim_deadline'] as String?;
    final createdAt = task['created_at'] as String?;
    final pColor = _priorityColor(priority);
    final pLabel = _priorityLabel(priority);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.cardBg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: SuokeDesignTokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              // 优先级竖条
              Container(
                width: 3,
                height: 36,
                margin: const EdgeInsets.only(right: 10),
                decoration: BoxDecoration(
                  color: pColor,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: const TextStyle(
                            color: SuokeDesignTokens.textPrimary,
                            fontSize: 15,
                            fontWeight: FontWeight.w600),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        const Icon(Icons.person_outline,
                            size: 13, color: SuokeDesignTokens.textSecondary),
                        const SizedBox(width: 3),
                        Text(assignee,
                            style: const TextStyle(
                                color: SuokeDesignTokens.textSecondary, fontSize: 12)),
                        const SizedBox(width: 12),
                        Icon(Icons.event_outlined,
                            size: 13,
                            color:
                                deadline == null ? SuokeDesignTokens.textSecondary : _priorityMid),
                        const SizedBox(width: 3),
                        Expanded(
                          child: Text(_formatDeadline(deadline),
                              style: TextStyle(
                                  color: deadline == null
                                      ? SuokeDesignTokens.textSecondary
                                      : _priorityMid,
                                  fontSize: 12),
                              overflow: TextOverflow.ellipsis),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: pColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: pColor.withValues(alpha: 0.5)),
                ),
                child: Text(pLabel,
                    style: TextStyle(
                        color: pColor,
                        fontSize: 11,
                        fontWeight: FontWeight.bold)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: _statusColor(status).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(_statusLabel(status),
                    style:
                        TextStyle(color: _statusColor(status), fontSize: 11)),
              ),
              const SizedBox(width: 8),
              if (createdAt != null)
                Text('创建于 ${_formatCreated(createdAt)}',
                    style:
                        const TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 11)),
              const Spacer(),
              // 状态操作菜单
              PopupMenuButton<String>(
                color: SuokeDesignTokens.cardBg,
                icon: const Icon(Icons.more_vert, color: SuokeDesignTokens.textSecondary, size: 18),
                itemBuilder: (_) {
                  final items = <PopupMenuEntry<String>>[];
                  if (status == 'pending') {
                    items.add(
                        const PopupMenuItem(value: 'claim', child: Text('申领任务')));
                  }
                  if (status == 'claimed' || status == 'in_progress') {
                    items.add(const PopupMenuItem(
                        value: 'complete', child: Text('标记完成')));
                  }
                  if (items.isEmpty) {
                    items.add(const PopupMenuItem(
                        value: 'none', child: Text('无可用操作')));
                  }
                  return items;
                },
                onSelected: (v) {
                  switch (v) {
                    case 'claim':
                      _claimTask(task);
                      break;
                    case 'complete':
                      _completeTask(task);
                      break;
                  }
                },
              ),
            ],
          ),
        ],
      ),
    );
  }
}
