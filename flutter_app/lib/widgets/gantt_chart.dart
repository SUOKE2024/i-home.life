import 'dart:math';
import 'package:flutter/material.dart';
import '../theme/suoke_theme.dart';

// ────────────────────────────────────────────────────────────
// Data Models
// ────────────────────────────────────────────────────────────

class GanttTask {
  final String id;
  final String name;
  final String phase;
  final DateTime startDate;
  final DateTime endDate;
  final String status;
  final List<String> dependencies;
  final String? assignee;
  final double progress;

  const GanttTask({
    required this.id,
    required this.name,
    required this.phase,
    required this.startDate,
    required this.endDate,
    required this.status,
    this.dependencies = const [],
    this.assignee,
    this.progress = 0.0,
  });

  factory GanttTask.fromJson(Map<String, dynamic> json) {
    return GanttTask(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      phase: json['phase']?.toString() ?? '',
      startDate:
          DateTime.tryParse(json['start_date']?.toString() ?? '') ??
          DateTime.now(),
      endDate:
          DateTime.tryParse(json['end_date']?.toString() ?? '') ??
          DateTime.now(),
      status: json['status']?.toString() ?? 'pending',
      dependencies: (json['dependencies'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      assignee: json['assigned_to']?.toString(),
      progress: (json['progress'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

// ────────────────────────────────────────────────────────────
// Main Widget
// ────────────────────────────────────────────────────────────

class GanttChart extends StatefulWidget {
  final List<GanttTask> tasks;
  final DateTime projectStart;
  final DateTime projectEnd;
  final Function(GanttTask task)? onTaskTap;

  const GanttChart({
    super.key,
    required this.tasks,
    required this.projectStart,
    required this.projectEnd,
    this.onTaskTap,
  });

  @override
  State<GanttChart> createState() => _GanttChartState();
}

class _GanttChartState extends State<GanttChart> {
  static const double _rowHeight = 60.0;
  static const double _labelWidth = 250.0;
  static const double _headerHeight = 44.0;
  static const double _dayWidth = 36.0;

  final ScrollController _horizontalController = ScrollController();
  final ScrollController _verticalController = ScrollController();

  late final int _totalDays;
  late final double _chartAreaWidth;
  late final double _totalWidth;
  late final double _totalHeight;
  late final Set<String> _criticalPathIds;

  @override
  void initState() {
    super.initState();
    _totalDays = max(
      widget.projectEnd.difference(widget.projectStart).inDays,
      1,
    );
    _chartAreaWidth = max(_totalDays * _dayWidth, 400.0);
    _totalWidth = _labelWidth + _chartAreaWidth;
    _totalHeight =
        _headerHeight + widget.tasks.length * _rowHeight;
    _criticalPathIds = _computeCriticalPath();

    // Scroll to today after first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final today = DateTime.now();
      if (!today.isBefore(widget.projectStart) &&
          !today.isAfter(widget.projectEnd)) {
        final todayOffset =
            (today.difference(widget.projectStart).inDays /
                    _totalDays) *
                _chartAreaWidth;
        final viewportWidth =
            MediaQuery.of(context).size.width - _labelWidth;
        final targetOffset = (todayOffset - viewportWidth / 2)
            .clamp(0.0, _chartAreaWidth - viewportWidth);
        if (_horizontalController.hasClients && targetOffset > 0) {
          _horizontalController.animateTo(
            targetOffset,
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeOut,
          );
        }
      }
    });
  }

  @override
  void dispose() {
    _horizontalController.dispose();
    _verticalController.dispose();
    super.dispose();
  }

  // ── Critical Path Method ──

  Set<String> _computeCriticalPath() {
    if (widget.tasks.isEmpty) return {};

    final Map<String, _CPMData> cpm = {};
    for (final task in widget.tasks) {
      cpm[task.id] = _CPMData(
        duration: max(
          task.endDate.difference(task.startDate).inDays,
          1,
        ),
        deps: task.dependencies,
      );
    }

    // Forward pass
    final sorted = _topologicalSort(cpm);
    int maxEF = 0;
    for (final id in sorted) {
      final data = cpm[id]!;
      int es = 0;
      for (final dep in data.deps) {
        es = max(es, cpm[dep]?.ef ?? 0);
      }
      data.es = es;
      data.ef = es + data.duration;
      maxEF = max(maxEF, data.ef);
    }

    // Backward pass
    final reversed = sorted.reversed.toList();
    for (final id in reversed) {
      final data = cpm[id]!;
      int minLF = maxEF;
      for (final other in widget.tasks) {
        if (other.dependencies.contains(id)) {
          minLF = min(minLF, cpm[other.id]?.ls ?? maxEF);
        }
      }
      data.lf = minLF;
      data.ls = minLF - data.duration;
    }

    // Tasks with zero slack are on critical path
    final critical = <String>{};
    for (final entry in cpm.entries) {
      if (entry.value.es == entry.value.ls) {
        critical.add(entry.key);
      }
    }
    return critical;
  }

  List<String> _topologicalSort(Map<String, _CPMData> cpm) {
    final inDegree = <String, int>{};
    final graph = <String, List<String>>{};

    for (final entry in cpm.entries) {
      inDegree.putIfAbsent(entry.key, () => 0);
      graph.putIfAbsent(entry.key, () => []);
      for (final dep in entry.value.deps) {
        inDegree.putIfAbsent(dep, () => 0);
        graph.putIfAbsent(dep, () => []).add(entry.key);
        inDegree[entry.key] = (inDegree[entry.key] ?? 0) + 1;
      }
    }

    final queue = <String>[];
    for (final entry in inDegree.entries) {
      if (entry.value == 0) queue.add(entry.key);
    }

    final sorted = <String>[];
    while (queue.isNotEmpty) {
      final node = queue.removeAt(0);
      sorted.add(node);
      for (final neighbor in graph[node] ?? <String>[]) {
        inDegree[neighbor] = (inDegree[neighbor] ?? 1) - 1;
        if (inDegree[neighbor] == 0) queue.add(neighbor);
      }
    }

    return sorted;
  }

  // ── Coordinate helpers ──

  int _tapIndex(Offset position) {
    if (position.dy < _headerHeight) return -1;
    final index =
        ((position.dy - _headerHeight) / _rowHeight).floor();
    if (index >= widget.tasks.length || index < 0) return -1;
    return index;
  }

  // ── Tap → bottom sheet ──

  void _handleTap(TapUpDetails details) {
    final index = _tapIndex(details.localPosition);
    if (index < 0 || index >= widget.tasks.length) return;

    final task = widget.tasks[index];
    final isDark =
        Theme.of(context).brightness == Brightness.dark;

    showModalBottomSheet(
      context: context,
      backgroundColor: isDark
          ? SuokeDesignTokens.surface2
          : Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(SuokeDesignTokens.radiusLg),
        ),
      ),
      builder: (_) => _TaskDetailSheet(task: task),
    );

    widget.onTaskTap?.call(task);
  }

  // ── Build ──

  @override
  Widget build(BuildContext context) {
    final isDark =
        Theme.of(context).brightness == Brightness.dark;

    return GestureDetector(
      onTapUp: _handleTap,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        controller: _horizontalController,
        child: SingleChildScrollView(
          scrollDirection: Axis.vertical,
          controller: _verticalController,
          child: CustomPaint(
            size: Size(_totalWidth, _totalHeight),
            painter: _GanttPainter(
              tasks: widget.tasks,
              projectStart: widget.projectStart,
              totalDays: _totalDays,
              rowHeight: _rowHeight,
              headerHeight: _headerHeight,
              labelWidth: _labelWidth,
              chartAreaWidth: _chartAreaWidth,
              dayWidth: _dayWidth,
              isDark: isDark,
              criticalPathIds: _criticalPathIds,
            ),
          ),
        ),
      ),
    );
  }
}

// ────────────────────────────────────────────────────────────
// CPM helper class
// ────────────────────────────────────────────────────────────

class _CPMData {
  final int duration;
  final List<String> deps;
  int es = 0;
  int ef = 0;
  int ls = 0;
  int lf = 0;

  _CPMData({required this.duration, required this.deps});
}

// ────────────────────────────────────────────────────────────
// CustomPainter
// ────────────────────────────────────────────────────────────

class _GanttPainter extends CustomPainter {
  final List<GanttTask> tasks;
  final DateTime projectStart;
  final int totalDays;
  final double rowHeight;
  final double headerHeight;
  final double labelWidth;
  final double chartAreaWidth;
  final double dayWidth;
  final bool isDark;
  final Set<String> criticalPathIds;

  _GanttPainter({
    required this.tasks,
    required this.projectStart,
    required this.totalDays,
    required this.rowHeight,
    required this.headerHeight,
    required this.labelWidth,
    required this.chartAreaWidth,
    required this.dayWidth,
    required this.isDark,
    required this.criticalPathIds,
  });

  // ── Theme-aware color helpers ──

  Color _bgColor() =>
      isDark ? SuokeDesignTokens.surface1 : const Color(0xFFF5F5F5);

  Color _gridColor() =>
      isDark ? SuokeDesignTokens.border : const Color(0xFFE0E0E0);

  Color _textColor() =>
      isDark
          ? SuokeDesignTokens.textPrimary
          : SuokeDesignTokens.lightTextPrimary;

  Color _textSecondaryColor() =>
      isDark
          ? SuokeDesignTokens.textSecondary
          : SuokeDesignTokens.lightTextSecondary;

  Color _statusColor(String status) {
    switch (status) {
      case 'in_progress':
        return const Color(0xFF5A7EC9); // blue
      case 'completed':
        return const Color(0xFF4A9E6E); // green
      case 'delayed':
        return const Color(0xFFC94A4A); // red
      default:
        // pending
        return isDark
            ? const Color(0xFF666666)
            : const Color(0xFFBDBDBD);
    }
  }

  double _dateToX(DateTime date) {
    return labelWidth +
        (date.difference(projectStart).inDays / totalDays) *
            chartAreaWidth;
  }

  // ── Paint phases (order matters: background → grid → header
  //    → bars → labels → today → arrows) ──

  @override
  void paint(Canvas canvas, Size size) {
    _drawBackground(canvas, size);
    _drawGrid(canvas, size);
    _drawHeader(canvas);
    _drawTodayLine(canvas, size);
    _drawTaskBars(canvas);
    _drawTaskLabels(canvas);
    _drawDependencyArrows(canvas);
  }

  void _drawBackground(Canvas canvas, Size size) {
    final bgPaint = Paint()..color = _bgColor();
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.width, size.height),
      bgPaint,
    );

    // Label-area background (slightly elevated)
    final labelBgPaint = Paint()
      ..color = isDark
          ? SuokeDesignTokens.surface2
          : const Color(0xFFFAFAFA);
    canvas.drawRect(
      Rect.fromLTWH(0, 0, labelWidth, size.height),
      labelBgPaint,
    );
  }

  void _drawGrid(Canvas canvas, Size size) {
    // Separator line between labels and chart
    final separatorPaint = Paint()
      ..color = isDark
          ? SuokeDesignTokens.borderActive
          : const Color(0xFFD0D0D0)
      ..strokeWidth = 1;
    canvas.drawLine(
      Offset(labelWidth, 0),
      Offset(labelWidth, size.height),
      separatorPaint,
    );

    // Day-column grid lines + weekend shading
    for (int d = 0; d <= totalDays; d++) {
      final x = labelWidth + (d / totalDays) * chartAreaWidth;
      final date = projectStart.add(Duration(days: d));
      final isWeekend = date.weekday == DateTime.saturday ||
          date.weekday == DateTime.sunday;

      if (isWeekend) {
        final nextX =
            labelWidth + ((d + 1) / totalDays) * chartAreaWidth;
        final weekendPaint = Paint()
          ..color = isDark
              ? const Color(0xFF161620)
              : const Color(0xFFF0F0F0);
        final w = (nextX - x).clamp(0.0, double.infinity);
        canvas.drawRect(
          Rect.fromLTWH(
            x,
            headerHeight,
            w,
            size.height - headerHeight,
          ),
          weekendPaint,
        );
      }

      final gridPaint = Paint()
        ..color = _gridColor()
        ..strokeWidth = 0.5;
      canvas.drawLine(
        Offset(x, headerHeight),
        Offset(x, size.height),
        gridPaint,
      );
    }

    // Horizontal row separators
    final gridPaint = Paint()
      ..color = _gridColor()
      ..strokeWidth = 0.5;
    for (int i = 0; i <= tasks.length; i++) {
      final y = headerHeight + i * rowHeight;
      canvas.drawLine(
        Offset(0, y),
        Offset(size.width, y),
        gridPaint,
      );
    }

    // Header bottom border
    canvas.drawLine(
      Offset(0, headerHeight),
      Offset(size.width, headerHeight),
      separatorPaint,
    );
  }

  // ── Date header ──

  void _drawHeader(Canvas canvas) {
    // Month labels (top row)
    final monthStyle = TextStyle(
      color: _textSecondaryColor(),
      fontSize: 10,
      fontWeight: FontWeight.w500,
    );

    int? lastMonth;
    for (int d = 0; d < totalDays; d++) {
      final date = projectStart.add(Duration(days: d));
      if (date.month != lastMonth) {
        lastMonth = date.month;
        final x = labelWidth + (d / totalDays) * chartAreaWidth;
        final tp = TextPainter(
          text: TextSpan(
            text: '${date.month}月',
            style: monthStyle,
          ),
          textDirection: TextDirection.ltr,
        )..layout();

        if (x + tp.width <= labelWidth + chartAreaWidth) {
          tp.paint(canvas, Offset(x + 2, 4));
        }
      }
    }

    // Day numbers (bottom of header)
    final dayStyle = TextStyle(
      color: _textSecondaryColor(),
      fontSize: 9,
    );
    for (int d = 0; d < totalDays; d++) {
      final date = projectStart.add(Duration(days: d));
      final x = labelWidth + (d / totalDays) * chartAreaWidth;
      final tp = TextPainter(
        text: TextSpan(text: '${date.day}', style: dayStyle),
        textDirection: TextDirection.ltr,
      )..layout();

      if (x + tp.width <= labelWidth + chartAreaWidth) {
        tp.paint(
          canvas,
          Offset(x + 2, headerHeight - tp.height - 2),
        );
      }
    }

    // Label-header title
    final labelStyle = TextStyle(
      color: _textColor(),
      fontSize: 12,
      fontWeight: FontWeight.w600,
    );
    final labelTp = TextPainter(
      text: TextSpan(text: '施工任务', style: labelStyle),
      textDirection: TextDirection.ltr,
    )..layout();
    labelTp.paint(
      canvas,
      Offset(12, (headerHeight - labelTp.height) / 2),
    );
  }

  // ── Task bars ──

  void _drawTaskBars(Canvas canvas) {
    for (int i = 0; i < tasks.length; i++) {
      final task = tasks[i];
      final y = headerHeight + i * rowHeight + 8;
      final barHeight = rowHeight - 16;
      final barLeft = _dateToX(task.startDate);
      final barRight = _dateToX(task.endDate);
      final barWidth = max(barRight - barLeft, 4.0);

      final isCritical = criticalPathIds.contains(task.id);
      final statusColor = _statusColor(task.status);

      // Critical-path glow
      if (isCritical) {
        final glowPaint = Paint()
          ..color = const Color(0xFFC94A4A).withValues(alpha: 0.15)
          ..style = PaintingStyle.fill;
        final glowRect = RRect.fromRectAndRadius(
          Rect.fromLTWH(
            barLeft - 2,
            y - 2,
            barWidth + 4,
            barHeight + 4,
          ),
          const Radius.circular(6),
        );
        canvas.drawRRect(glowRect, glowPaint);
      }

      // Bar background (unfilled portion)
      final barRect = RRect.fromRectAndRadius(
        Rect.fromLTWH(barLeft, y, barWidth, barHeight),
        const Radius.circular(4),
      );
      final bgPaint = Paint()
        ..color = statusColor.withValues(alpha: 0.25);
      canvas.drawRRect(barRect, bgPaint);

      // Progress fill
      if (task.progress > 0) {
        final progressWidth = barWidth * task.progress.clamp(0.0, 1.0);
        final progressRect = RRect.fromRectAndRadius(
          Rect.fromLTWH(barLeft, y, progressWidth, barHeight),
          const Radius.circular(4),
        );
        final progressPaint = Paint()..color = statusColor;
        canvas.drawRRect(progressRect, progressPaint);
      }

      // Bar border
      final borderPaint = Paint()
        ..color = statusColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = isCritical ? 1.5 : 1.0;
      canvas.drawRRect(barRect, borderPaint);

      // Progress percentage text (when bar is wide enough)
      if (barWidth > 44) {
        final pctText =
            '${(task.progress * 100).toInt()}%';
        final tp = TextPainter(
          text: TextSpan(
            text: pctText,
            style: TextStyle(
              color: _textColor(),
              fontSize: 10,
              fontWeight: FontWeight.w600,
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout();

        if (barWidth > tp.width + 12) {
          tp.paint(
            canvas,
            Offset(
              barLeft + (barWidth - tp.width) / 2,
              y + (barHeight - tp.height) / 2,
            ),
          );
        }
      }
    }
  }

  // ── Task labels ──

  void _drawTaskLabels(Canvas canvas) {
    for (int i = 0; i < tasks.length; i++) {
      final task = tasks[i];
      final y = headerHeight + i * rowHeight;

      // Name
      final nameTp = TextPainter(
        text: TextSpan(
          text: task.name,
          style: TextStyle(
            color: _textColor(),
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
        textDirection: TextDirection.ltr,
        maxLines: 1,
        ellipsis: '…',
      )..layout(maxWidth: labelWidth - 24);
      nameTp.paint(canvas, Offset(12, y + 8));

      // Phase + assignee
      final subText = StringBuffer(task.phase);
      if (task.assignee != null && task.assignee!.isNotEmpty) {
        subText.write(' · ${task.assignee}');
      }
      final phaseTp = TextPainter(
        text: TextSpan(
          text: subText.toString(),
          style: TextStyle(
            color: _textSecondaryColor(),
            fontSize: 10,
          ),
        ),
        textDirection: TextDirection.ltr,
        maxLines: 1,
        ellipsis: '…',
      )..layout(maxWidth: labelWidth - 24);
      phaseTp.paint(canvas, Offset(12, y + 24));

      // Date range
      final dateStr =
          '${task.startDate.month}/${task.startDate.day} → '
          '${task.endDate.month}/${task.endDate.day}';
      final dateTp = TextPainter(
        text: TextSpan(
          text: dateStr,
          style: TextStyle(
            color: _textSecondaryColor(),
            fontSize: 9,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      dateTp.paint(canvas, Offset(12, y + 38));
    }
  }

  // ── Today line ──

  void _drawTodayLine(Canvas canvas, Size size) {
    final today = DateTime.now();
    if (today.isBefore(projectStart) ||
        today.isAfter(projectStart.add(Duration(days: totalDays)))) {
      return;
    }

    final x = _dateToX(today);

    // Dashed vertical line
    final dashPaint = Paint()
      ..color = SuokeDesignTokens.accent
      ..strokeWidth = 1.5;
    const dashH = 6.0;
    const gapH = 4.0;
    var dy = headerHeight;
    while (dy < size.height) {
      canvas.drawLine(
        Offset(x, dy),
        Offset(x, min(dy + dashH, size.height)),
        dashPaint,
      );
      dy += dashH + gapH;
    }

    // "今天" label
    final tp = TextPainter(
      text: const TextSpan(
        text: '今天',
        style: const TextStyle(
          color: SuokeDesignTokens.accent,
          fontSize: 10,
          fontWeight: FontWeight.w600,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();

    final labelBg = Paint()
      ..color = SuokeDesignTokens.accent.withValues(alpha: 0.15);
    canvas.drawRect(
      Rect.fromLTWH(
        x - tp.width / 2 - 4,
        headerHeight,
        tp.width + 8,
        tp.height + 4,
      ),
      labelBg,
    );
    tp.paint(
      canvas,
      Offset(x - tp.width / 2, headerHeight + 2),
    );
  }

  // ── Dependency arrows ──

  void _drawDependencyArrows(Canvas canvas) {
    final Map<String, int> taskIndex = {};
    for (int i = 0; i < tasks.length; i++) {
      taskIndex[tasks[i].id] = i;
    }

    final arrowColor = isDark
        ? SuokeDesignTokens.textMuted
        : const Color(0xFF999999);

    for (int i = 0; i < tasks.length; i++) {
      final task = tasks[i];
      for (final depId in task.dependencies) {
        final depIndex = taskIndex[depId];
        if (depIndex == null) continue;

        final depTask = tasks[depIndex];
        final fromY = headerHeight +
            depIndex * rowHeight +
            rowHeight / 2;
        final toY =
            headerHeight + i * rowHeight + rowHeight / 2;
        final fromX = _dateToX(depTask.endDate);
        final toX = _dateToX(task.startDate);

        final pathPaint = Paint()
          ..color = arrowColor
          ..strokeWidth = 1.2
          ..style = PaintingStyle.stroke;

        final path = Path();
        final midX = (fromX + toX) / 2;
        path.moveTo(fromX, fromY);
        path.cubicTo(midX, fromY, midX, toY, toX - 7, toY);
        canvas.drawPath(path, pathPaint);

        // Arrowhead
        final headPaint = Paint()
          ..color = arrowColor
          ..style = PaintingStyle.fill;
        final headPath = Path()
          ..moveTo(toX, toY)
          ..lineTo(toX - 9, toY - 4.5)
          ..lineTo(toX - 9, toY + 4.5)
          ..close();
        canvas.drawPath(headPath, headPaint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _GanttPainter oldDelegate) {
    return tasks != oldDelegate.tasks ||
        isDark != oldDelegate.isDark ||
        criticalPathIds != oldDelegate.criticalPathIds;
  }
}

// ────────────────────────────────────────────────────────────
// Task detail bottom sheet
// ────────────────────────────────────────────────────────────

class _TaskDetailSheet extends StatelessWidget {
  final GanttTask task;
  const _TaskDetailSheet({required this.task});

  static const _statusNames = {
    'pending': '待开始',
    'in_progress': '进行中',
    'completed': '已完成',
    'delayed': '已延期',
  };

  static const _statusColors = {
    'pending': Color(0xFF888888),
    'in_progress': Color(0xFF5A7EC9),
    'completed': Color(0xFF4A9E6E),
    'delayed': Color(0xFFC94A4A),
  };

  @override
  Widget build(BuildContext context) {
    final isDark =
        Theme.of(context).brightness == Brightness.dark;

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Drag handle
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: isDark
                    ? SuokeDesignTokens.border
                    : const Color(0xFFE0E0E0),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 20),

          // Task name
          Text(
            task.name,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 14),

          // Status chip + progress
          Row(
            children: [
              _StatusChip(
                label: _statusNames[task.status] ?? task.status,
                color: _statusColors[task.status] ??
                    Colors.grey,
              ),
              const SizedBox(width: 12),
              Text(
                '${(task.progress * 100).toInt()}% 完成',
                style: TextStyle(
                  color: isDark
                      ? SuokeDesignTokens.textSecondary
                      : SuokeDesignTokens.lightTextSecondary,
                  fontSize: 12,
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),

          // Details
          _DetailRow(
            icon: Icons.category_outlined,
            label: '阶段',
            value: task.phase,
          ),
          if (task.assignee != null &&
              task.assignee!.isNotEmpty)
            _DetailRow(
              icon: Icons.person_outline,
              label: '负责人',
              value: task.assignee!,
            ),
          _DetailRow(
            icon: Icons.calendar_today,
            label: '开始',
            value:
                '${task.startDate.year}/${task.startDate.month.toString().padLeft(2, '0')}/${task.startDate.day.toString().padLeft(2, '0')}',
          ),
          _DetailRow(
            icon: Icons.event,
            label: '结束',
            value:
                '${task.endDate.year}/${task.endDate.month.toString().padLeft(2, '0')}/${task.endDate.day.toString().padLeft(2, '0')}',
          ),
          _DetailRow(
            icon: Icons.timelapse,
            label: '工期',
            value:
                '${task.endDate.difference(task.startDate).inDays} 天',
          ),
          if (task.dependencies.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.link,
                    size: 18,
                    color: SuokeDesignTokens.textSecondary,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '前置任务：${task.dependencies.length} 项',
                    style: const TextStyle(
                      color: SuokeDesignTokens.textSecondary,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }
}

// ── Tiny helpers used only in the bottom sheet ──

class _StatusChip extends StatelessWidget {
  final String label;
  final Color color;
  const _StatusChip({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 10,
        vertical: 4,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  const _DetailRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    final isDark =
        Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        children: [
          Icon(
            icon,
            size: 18,
            color: isDark
                ? SuokeDesignTokens.textSecondary
                : SuokeDesignTokens.lightTextSecondary,
          ),
          const SizedBox(width: 8),
          Text(
            '$label：',
            style: TextStyle(
              color: isDark
                  ? SuokeDesignTokens.textSecondary
                  : SuokeDesignTokens.lightTextSecondary,
              fontSize: 13,
            ),
          ),
          Flexible(
            child: Text(
              value,
              style: TextStyle(
                color: isDark
                    ? SuokeDesignTokens.textPrimary
                    : SuokeDesignTokens.lightTextPrimary,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
