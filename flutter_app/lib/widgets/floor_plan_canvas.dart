import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/suoke_theme.dart';

/// 表示平面图上的一个组件（家具、设备等）
class FloorPlanComponent {
  final String id;
  final String label;
  final String type;
  final double x; // mm from top-left
  final double y;
  final double width; // mm
  final double height; // mm
  final double rotation; // degrees
  final Color? color;
  final String? iconName;

  const FloorPlanComponent({
    required this.id,
    required this.label,
    required this.type,
    required this.x,
    required this.y,
    this.width = 600,
    this.height = 600,
    this.rotation = 0,
    this.color,
    this.iconName,
  });

  /// 从 Map 创建（兼容 API 返回的组件数据）
  factory FloorPlanComponent.fromMap(Map<String, dynamic> map) {
    return FloorPlanComponent(
      id: (map['id'] ?? '').toString(),
      label: (map['component_type'] ?? map['label'] ?? '').toString(),
      type: (map['component_type'] ?? map['type'] ?? '').toString(),
      x: (map['position_x'] as num?)?.toDouble() ?? 0,
      y: (map['position_y'] as num?)?.toDouble() ?? 0,
      width: (map['width'] as num?)?.toDouble() ?? 600,
      height: (map['depth'] as num?)?.toDouble() ?? 600,
      rotation: (map['rotation'] as num?)?.toDouble() ?? 0,
      color: null,
      iconName: map['icon']?.toString(),
    );
  }
}

/// 可复用的平面图画布组件
///
/// 支持：
/// - 房间轮廓绘制（墙壁）
/// - 网格背景
/// - 组件放置与旋转
/// - 缩放/平移手势
/// - 吸附网格
/// - 选中高亮与拖拽手柄
/// - MEP 水电点位层
/// - 尺寸标注层
class FloorPlanCanvas extends StatefulWidget {
  /// 房间宽度（mm）
  final double roomWidth;

  /// 房间高度/长度（mm）
  final double roomHeight;

  /// 房间标签
  final String roomLabel;

  /// 组件列表
  final List<FloorPlanComponent> components;

  /// 组件点击回调
  final Function(String componentId)? onComponentTap;

  /// 组件移动回调
  final Function(String componentId, double newX, double newY)? onComponentMove;

  /// 是否显示网格
  final bool showGrid;

  /// 是否显示尺寸标注
  final bool showDimensions;

  /// 是否显示 MEP 水电点位层
  final bool showMEPLayer;

  /// 水电点位列表
  final List<MEPPoint>? mepPoints;

  /// 网格大小（mm），默认 100mm
  final double gridSize;

  /// 像素/mm 比，控制初始缩放
  final double pixelsPerMm;

  const FloorPlanCanvas({
    super.key,
    required this.roomWidth,
    required this.roomHeight,
    this.roomLabel = '',
    this.components = const [],
    this.onComponentTap,
    this.onComponentMove,
    this.showGrid = true,
    this.showDimensions = true,
    this.showMEPLayer = false,
    this.mepPoints,
    this.gridSize = 100,
    this.pixelsPerMm = 0.2,
  });

  @override
  State<FloorPlanCanvas> createState() => _FloorPlanCanvasState();
}

/// MEP 水电点位
enum MEPType { water, electric, gas }

class MEPPoint {
  final String id;
  final Offset position; // mm
  final MEPType type;
  final String? label;

  const MEPPoint({
    required this.id,
    required this.position,
    required this.type,
    this.label,
  });
}

class _FloorPlanCanvasState extends State<FloorPlanCanvas>
    with SingleTickerProviderStateMixin {
  final TransformationController _transformCtrl = TransformationController();
  String? _selectedComponentId;

  // --- Drag state ---
  bool _isDragging = false;
  Offset? _dragPositionMm;
  Offset? _originalDragPositionMm;

  // --- Animation ---
  late final AnimationController _animController;

  // --- Viewport size (set in build) ---
  Size _viewportSize = Size.zero;

  /// 将屏幕像素坐标转换为 mm 坐标
  Offset _screenToMm(Offset screenPoint) {
    final matrix = _transformCtrl.value;
    final scale = matrix.getMaxScaleOnAxis();
    final dx = (screenPoint.dx - matrix.getTranslation().x) /
        (widget.pixelsPerMm * scale);
    final dy = (screenPoint.dy - matrix.getTranslation().y) /
        (widget.pixelsPerMm * scale);
    return Offset(dx, dy);
  }

  void _handleTapUp(TapUpDetails details) {
    final localPos = details.localPosition;
    final mmPos = _screenToMm(localPos);

    // 查找被点击的组件（从上层开始）
    String? hitId;
    for (final comp in widget.components.reversed) {
      if (_hitTestComponent(comp, mmPos)) {
        hitId = comp.id;
        break;
      }
    }

    setState(() {
      _selectedComponentId = hitId;
    });

    if (hitId != null && widget.onComponentTap != null) {
      widget.onComponentTap!(hitId);
    }
  }

  bool _hitTestComponent(FloorPlanComponent comp, Offset mmPos) {
    // 如果组件有旋转，需要反向旋转点击位置
    final dx = mmPos.dx - comp.x;
    final dy = mmPos.dy - comp.y;

    if (comp.rotation != 0) {
      final rad = -comp.rotation * math.pi / 180;
      final cos = math.cos(rad);
      final sin = math.sin(rad);
      final rx = dx * cos - dy * sin;
      final ry = dx * sin + dy * cos;
      return rx >= 0 && rx <= comp.width && ry >= 0 && ry <= comp.height;
    }

    return dx >= 0 && dx <= comp.width && dy >= 0 && dy <= comp.height;
  }

  // --- Drag handlers ---

  void _handleDragStart(DragStartDetails details) {
    if (_selectedComponentId == null) return;

    final mmPos = _screenToMm(details.localPosition);
    final selectedComp = widget.components.cast<FloorPlanComponent?>().firstWhere(
      (c) => c!.id == _selectedComponentId,
      orElse: () => null,
    );
    if (selectedComp == null) return;

    // Only start drag if the gesture begins on the selected component
    if (!_hitTestComponent(selectedComp, mmPos)) return;

    setState(() {
      _isDragging = true;
      _originalDragPositionMm = Offset(selectedComp.x, selectedComp.y);
      // Seed drag position with original component position
      _dragPositionMm = Offset(selectedComp.x, selectedComp.y);
    });
  }

  void _handleDragUpdate(DragUpdateDetails details) {
    if (!_isDragging) return;

    final matrix = _transformCtrl.value;
    final scale = matrix.getMaxScaleOnAxis();
    final mmDelta = Offset(
      details.delta.dx / (widget.pixelsPerMm * scale),
      details.delta.dy / (widget.pixelsPerMm * scale),
    );

    final rawX = _dragPositionMm!.dx + mmDelta.dx;
    final rawY = _dragPositionMm!.dy + mmDelta.dy;

    // Snap to grid
    final snappedX = (rawX / widget.gridSize).round() * widget.gridSize;
    final snappedY = (rawY / widget.gridSize).round() * widget.gridSize;

    setState(() {
      _dragPositionMm = Offset(snappedX, snappedY);
    });
  }

  void _handleDragEnd(DragEndDetails details) {
    if (!_isDragging || _selectedComponentId == null) return;

    final snappedX = _dragPositionMm!.dx;
    final snappedY = _dragPositionMm!.dy;

    widget.onComponentMove?.call(_selectedComponentId!, snappedX, snappedY);

    setState(() {
      _isDragging = false;
      _dragPositionMm = null;
      _originalDragPositionMm = null;
    });
  }

  // --- Double-tap reset ---

  VoidCallback? _currentAnimationListener;

  void _handleDoubleTap() {
    final viewportW = _viewportSize.width;
    final viewportH = _viewportSize.height;
    if (viewportW <= 0 || viewportH <= 0) return;

    final roomWPx = widget.roomWidth * widget.pixelsPerMm;
    final roomHPx = widget.roomHeight * widget.pixelsPerMm;

    final fitScale = math.min(viewportW / roomWPx, viewportH / roomHPx);
    final tx = (viewportW - roomWPx * fitScale) / 2;
    final ty = (viewportH - roomHPx * fitScale) / 2;

    final targetMatrix = Matrix4.identity()
      ..translate(tx, ty)
      ..scale(fitScale);

    _animateToMatrix(targetMatrix);
  }

  void _animateToMatrix(Matrix4 target) {
    // Remove previous listener if any
    if (_currentAnimationListener != null) {
      _animController.removeListener(_currentAnimationListener!);
    }
    _animController.stop();

    final begin = _transformCtrl.value.clone();
    final animation = Matrix4Tween(begin: begin, end: target).animate(
      CurvedAnimation(parent: _animController, curve: Curves.easeInOut),
    );

    _currentAnimationListener = () {
      _transformCtrl.value = animation.value;
      if (_animController.isCompleted) {
        _animController.removeListener(_currentAnimationListener!);
        _currentAnimationListener = null;
      }
    };

    _animController.addListener(_currentAnimationListener!);
    _animController.reset();
    _animController.forward();
  }

  // --- Zoom controls ---

  void _applyZoomDelta(double delta) {
    final matrix = _transformCtrl.value.clone();
    final currentScale = matrix.getMaxScaleOnAxis();
    final newScale = (currentScale + delta).clamp(0.3, 5.0);
    final ratio = newScale / currentScale;

    matrix.scale(ratio);
    _transformCtrl.value = matrix;
    setState(() {});
  }

  // --- Zoom badge ---

  Widget _buildZoomBadge() {
    final scale = _transformCtrl.value.getMaxScaleOnAxis();
    final percentage = (scale * 100).round();
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final surface = isDark ? Colors.grey.shade800 : Colors.white;
    final onSurface = isDark ? Colors.white70 : Colors.black87;
    final borderColor = isDark ? Colors.white24 : Colors.black12;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Zoom percentage badge
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: surface.withValues(alpha: 0.85),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: borderColor),
          ),
          child: Text(
            '$percentage%',
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: onSurface),
          ),
        ),
        const SizedBox(height: 4),
        // Zoom in button
        _buildZoomButton(Icons.add, () => _applyZoomDelta(0.1), surface, onSurface, borderColor),
        const SizedBox(height: 2),
        // Zoom out button
        _buildZoomButton(Icons.remove, () => _applyZoomDelta(-0.1), surface, onSurface, borderColor),
      ],
    );
  }

  Widget _buildZoomButton(
    IconData icon,
    VoidCallback onTap,
    Color surface,
    Color onSurface,
    Color borderColor,
  ) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 24,
        height: 24,
        decoration: BoxDecoration(
          color: surface.withValues(alpha: 0.85),
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: borderColor),
        ),
        alignment: Alignment.center,
        child: Icon(icon, size: 14, color: onSurface),
      ),
    );
  }

  // --- Minimap ---

  Widget _buildMinimap() {
    if (_viewportSize.width <= 0 || _viewportSize.height <= 0) {
      return const SizedBox.shrink();
    }

    return Container(
      width: 80,
      height: 80,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.85),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.3),
        ),
      ),
      padding: const EdgeInsets.all(2),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(4),
        child: CustomPaint(
          painter: _MinimapPainter(
            roomWidth: widget.roomWidth,
            roomHeight: widget.roomHeight,
            components: widget.components,
            transformMatrix: _transformCtrl.value.clone(),
            viewportSize: _viewportSize,
            pixelsPerMm: widget.pixelsPerMm,
            colorScheme: Theme.of(context).colorScheme,
            brightness: Theme.of(context).brightness,
          ),
        ),
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    _transformCtrl.addListener(_onTransformChanged);
  }

  void _onTransformChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  void dispose() {
    _transformCtrl.removeListener(_onTransformChanged);
    _animController.dispose();
    _transformCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        _viewportSize = Size(constraints.maxWidth, constraints.maxHeight);

        final canvasWidth = widget.roomWidth * widget.pixelsPerMm;
        final canvasHeight = widget.roomHeight * widget.pixelsPerMm;
        final viewportW = _viewportSize.width;
        final viewportH = _viewportSize.height;

        final showMinimap = (_transformCtrl.value.getMaxScaleOnAxis() - 1.0).abs() > 0.05;

        return Stack(
          children: [
            // --- Layer 0: InteractiveViewer + canvas ---
            IgnorePointer(
              ignoring: _selectedComponentId != null,
              child: GestureDetector(
                onTapUp: _handleTapUp,
                onDoubleTap: _handleDoubleTap,
                child: InteractiveViewer(
                  transformationController: _transformCtrl,
                  boundaryMargin: const EdgeInsets.all(200),
                  minScale: 0.3,
                  maxScale: 5.0,
                  constrained: false,
                  child: SizedBox(
                    width: math.max(canvasWidth, viewportW),
                    height: math.max(canvasHeight, viewportH),
                    child: CustomPaint(
                      painter: _CompositePainter(
                        roomWidth: widget.roomWidth,
                        roomHeight: widget.roomHeight,
                        roomLabel: widget.roomLabel,
                        components: widget.components,
                        selectedComponentId: _selectedComponentId,
                        showGrid: widget.showGrid,
                        showDimensions: widget.showDimensions,
                        showMEPLayer: widget.showMEPLayer,
                        mepPoints: widget.mepPoints,
                        gridSize: widget.gridSize,
                        pixelsPerMm: widget.pixelsPerMm,
                        colorScheme: Theme.of(context).colorScheme,
                        brightness: Theme.of(context).brightness,
                        draggedComponentId: _isDragging ? _selectedComponentId : null,
                        dragPositionMm: _dragPositionMm,
                        originalDragPositionMm: _originalDragPositionMm,
                      ),
                    ),
                  ),
                ),
              ),
            ),

            // --- Layer 1: Drag overlay (only when a component is selected) ---
            if (_selectedComponentId != null)
              Positioned.fill(
                child: GestureDetector(
                  behavior: HitTestBehavior.translucent,
                  onTapUp: _handleTapUp,
                  onDoubleTap: _handleDoubleTap,
                  onPanStart: _handleDragStart,
                  onPanUpdate: _handleDragUpdate,
                  onPanEnd: _handleDragEnd,
                  child: Container(color: Colors.transparent),
                ),
              ),

            // --- Layer 2: Zoom badge (top-right) ---
            Positioned(
              top: 8,
              right: 8,
              child: _buildZoomBadge(),
            ),

            // --- Layer 3: Minimap (bottom-left, when zoomed) ---
            if (showMinimap)
              Positioned(
                bottom: 8,
                left: 8,
                child: _buildMinimap(),
              ),
          ],
        );
      },
    );
  }
}

/// 组合 Painter，按层绘制
class _CompositePainter extends CustomPainter {
  final double roomWidth;
  final double roomHeight;
  final String roomLabel;
  final List<FloorPlanComponent> components;
  final String? selectedComponentId;
  final bool showGrid;
  final bool showDimensions;
  final bool showMEPLayer;
  final List<MEPPoint>? mepPoints;
  final double gridSize;
  final double pixelsPerMm;
  final ColorScheme colorScheme;
  final Brightness brightness;

  // Drag state
  final String? draggedComponentId;
  final Offset? dragPositionMm;
  final Offset? originalDragPositionMm;

  _CompositePainter({
    required this.roomWidth,
    required this.roomHeight,
    required this.roomLabel,
    required this.components,
    required this.selectedComponentId,
    required this.showGrid,
    required this.showDimensions,
    required this.showMEPLayer,
    required this.mepPoints,
    required this.gridSize,
    required this.pixelsPerMm,
    required this.colorScheme,
    required this.brightness,
    this.draggedComponentId,
    this.dragPositionMm,
    this.originalDragPositionMm,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // Layer 1: Grid（最底层）
    if (showGrid) {
      _drawGrid(canvas, size);
    }

    // Layer 2: Room outline
    _drawRoom(canvas);

    // Layer 4: MEP points（在组件下方）
    if (showMEPLayer && mepPoints != null) {
      _drawMEPPoints(canvas);
    }

    // Layer 3: Components (skip the dragged one, it is drawn separately)
    for (final comp in components) {
      if (comp.id == draggedComponentId) continue;
      _drawComponent(canvas, comp);
    }

    // Ghost outline at original position during drag
    if (draggedComponentId != null && originalDragPositionMm != null) {
      final draggedComp = components.cast<FloorPlanComponent?>().firstWhere(
        (c) => c!.id == draggedComponentId,
        orElse: () => null,
      );
      if (draggedComp != null) {
        _drawDragGhost(canvas, draggedComp, originalDragPositionMm!);
      }
    }

    // Dragged component at new position
    if (draggedComponentId != null && dragPositionMm != null) {
      final draggedComp = components.cast<FloorPlanComponent?>().firstWhere(
        (c) => c!.id == draggedComponentId,
        orElse: () => null,
      );
      if (draggedComp != null) {
        _drawDraggedComponent(canvas, draggedComp, dragPositionMm!);
      }
    }

    // Selection overlay（not during drag, since dragged component shows its own highlight）
    if (selectedComponentId != null && draggedComponentId == null) {
      final selectedComp = components.cast<FloorPlanComponent?>().firstWhere(
        (c) => c!.id == selectedComponentId,
        orElse: () => null,
      );
      if (selectedComp != null) {
        _drawSelectionHighlight(canvas, selectedComp);
      }
    }
  }

  /// 绘制网格背景
  void _drawGrid(Canvas canvas, Size size) {
    final gridColor = brightness == Brightness.dark
        ? const Color(0x15FFFFFF)
        : const Color(0x15000000);
    final paint = Paint()
      ..color = gridColor
      ..strokeWidth = 0.5;

    final totalWidth = roomWidth * pixelsPerMm;
    final totalHeight = roomHeight * pixelsPerMm;
    final gridPx = gridSize * pixelsPerMm;

    // 竖线
    for (double x = 0; x <= totalWidth; x += gridPx) {
      canvas.drawLine(Offset(x, 0), Offset(x, totalHeight), paint);
    }
    // 横线
    for (double y = 0; y <= totalHeight; y += gridPx) {
      canvas.drawLine(Offset(0, y), Offset(totalWidth, y), paint);
    }
  }

  /// 绘制房间轮廓
  void _drawRoom(Canvas canvas) {
    final roomW = roomWidth * pixelsPerMm;
    final roomH = roomHeight * pixelsPerMm;
    final rect = Rect.fromLTWH(0, 0, roomW, roomH);

    // 半透明填充
    final fillPaint = Paint()
      ..color = (brightness == Brightness.dark
              ? SuokeDesignTokens.surface2
              : const Color(0xFFF0EFEB))
          .withValues(alpha: 0.6)
      ..style = PaintingStyle.fill;
    canvas.drawRect(rect, fillPaint);

    // 墙壁边框（3px）
    final borderPaint = Paint()
      ..color = brightness == Brightness.dark
          ? SuokeDesignTokens.textSecondary
          : SuokeDesignTokens.lightTextSecondary
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke;
    canvas.drawRect(rect, borderPaint);

    // 房间标签
    if (roomLabel.isNotEmpty) {
      final textPainter = TextPainter(
        text: TextSpan(
          text: roomLabel,
          style: TextStyle(
            color: brightness == Brightness.dark
                ? SuokeDesignTokens.textSecondary
                : SuokeDesignTokens.lightTextSecondary,
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: roomW - 20);

      textPainter.paint(
        canvas,
        const Offset(10, 10),
      );
    }

    // 尺寸标注
    if (showDimensions) {
      _drawDimensions(canvas, roomW, roomH);
    }
  }

  /// 绘制尺寸标注
  void _drawDimensions(Canvas canvas, double roomWPx, double roomHPx) {
    final dimStyle = TextStyle(
      color: brightness == Brightness.dark
          ? SuokeDesignTokens.textMuted
          : SuokeDesignTokens.lightTextMuted,
      fontSize: 10,
    );

    // 底部宽度标注
    final widthText = '${(roomWidth / 1000).toStringAsFixed(2)}m';
    final widthTp = TextPainter(
      text: TextSpan(text: widthText, style: dimStyle),
      textDirection: TextDirection.ltr,
    )..layout();
    widthTp.paint(
      canvas,
      Offset((roomWPx - widthTp.width) / 2, roomHPx + 6),
    );

    // 右侧高度标注
    final heightText = '${(roomHeight / 1000).toStringAsFixed(2)}m';
    final heightTp = TextPainter(
      text: TextSpan(text: heightText, style: dimStyle),
      textDirection: TextDirection.ltr,
    )..layout();
    // 旋转绘制
    canvas.save();
    canvas.translate(roomWPx + 6, (roomHPx + heightTp.width) / 2);
    canvas.rotate(math.pi / 2);
    heightTp.paint(canvas, const Offset(0, 0));
    canvas.restore();

    // 标注线（底部）
    final dimPaint = Paint()
      ..color = brightness == Brightness.dark
          ? SuokeDesignTokens.textMuted.withValues(alpha: 0.4)
          : SuokeDesignTokens.lightTextMuted.withValues(alpha: 0.4)
      ..strokeWidth = 0.5;

    canvas.drawLine(
      Offset(0, roomHPx + 3),
      Offset(roomWPx, roomHPx + 3),
      dimPaint,
    );

    // 标注线（右侧）
    canvas.drawLine(
      Offset(roomWPx + 3, 0),
      Offset(roomWPx + 3, roomHPx),
      dimPaint,
    );
  }

  /// 绘制组件
  void _drawComponent(Canvas canvas, FloorPlanComponent comp) {
    canvas.save();

    // 移动到组件中心，旋转
    final cx = (comp.x + comp.width / 2) * pixelsPerMm;
    final cy = (comp.y + comp.height / 2) * pixelsPerMm;
    canvas.translate(cx, cy);

    if (comp.rotation != 0) {
      canvas.rotate(comp.rotation * math.pi / 180);
    }

    final w = comp.width * pixelsPerMm;
    final h = comp.height * pixelsPerMm;
    final rect = RRect.fromRectAndRadius(
      Rect.fromLTWH(-w / 2, -h / 2, w, h),
      const Radius.circular(4),
    );

    // 是否选中
    final isSelected = comp.id == selectedComponentId;

    // 组件颜色
    final compColor = comp.color ?? _colorForType(comp.type);

    // 填充
    final fillPaint = Paint()
      ..color = compColor.withValues(alpha: 0.4)
      ..style = PaintingStyle.fill;
    canvas.drawRRect(rect, fillPaint);

    // 边框
    final borderPaint = Paint()
      ..color = isSelected ? Colors.blue : compColor.withValues(alpha: 0.8)
      ..strokeWidth = isSelected ? 2 : 1
      ..style = PaintingStyle.stroke;
    canvas.drawRRect(rect, borderPaint);

    // 标签文字
    final textPainter = TextPainter(
      text: TextSpan(
        text: comp.label,
        style: TextStyle(
          color: brightness == Brightness.dark
              ? SuokeDesignTokens.textPrimary
              : SuokeDesignTokens.lightTextPrimary,
          fontSize: 10,
          fontWeight: FontWeight.w500,
        ),
      ),
      textDirection: TextDirection.ltr,
      textAlign: TextAlign.center,
    )..layout(maxWidth: w - 8);

    textPainter.paint(
      canvas,
      Offset(-textPainter.width / 2, -textPainter.height / 2),
    );

    canvas.restore();
  }

  /// 绘制拖拽中的组件（带阴影和放大效果）
  void _drawDraggedComponent(
    Canvas canvas,
    FloorPlanComponent comp,
    Offset positionMm,
  ) {
    canvas.save();

    final cx = (positionMm.dx + comp.width / 2) * pixelsPerMm;
    final cy = (positionMm.dy + comp.height / 2) * pixelsPerMm;
    canvas.translate(cx, cy);

    if (comp.rotation != 0) {
      canvas.rotate(comp.rotation * math.pi / 180);
    }

    // Slightly larger during drag
    const dragScale = 1.08;
    final w = comp.width * pixelsPerMm * dragScale;
    final h = comp.height * pixelsPerMm * dragScale;
    final rect = RRect.fromRectAndRadius(
      Rect.fromLTWH(-w / 2, -h / 2, w, h),
      const Radius.circular(4),
    );

    final compColor = comp.color ?? _colorForType(comp.type);

    // Shadow layer
    final shadowPaint = Paint()
      ..color = Colors.black.withValues(alpha: 0.18)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6);
    canvas.drawRRect(
      rect.shift(const Offset(3, 3)),
      shadowPaint,
    );

    // Fill
    final fillPaint = Paint()
      ..color = compColor.withValues(alpha: 0.55)
      ..style = PaintingStyle.fill;
    canvas.drawRRect(rect, fillPaint);

    // Blue selection border
    final borderPaint = Paint()
      ..color = Colors.blue
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke;
    canvas.drawRRect(rect, borderPaint);

    // Label
    final textPainter = TextPainter(
      text: TextSpan(
        text: comp.label,
        style: TextStyle(
          color: brightness == Brightness.dark
              ? SuokeDesignTokens.textPrimary
              : SuokeDesignTokens.lightTextPrimary,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
      textDirection: TextDirection.ltr,
      textAlign: TextAlign.center,
    )..layout(maxWidth: w - 8);
    textPainter.paint(
      canvas,
      Offset(-textPainter.width / 2, -textPainter.height / 2),
    );

    canvas.restore();
  }

  /// 绘制原始位置的虚线轮廓（拖拽时显示）
  void _drawDragGhost(
    Canvas canvas,
    FloorPlanComponent comp,
    Offset positionMm,
  ) {
    canvas.save();

    final cx = (positionMm.dx + comp.width / 2) * pixelsPerMm;
    final cy = (positionMm.dy + comp.height / 2) * pixelsPerMm;
    canvas.translate(cx, cy);

    if (comp.rotation != 0) {
      canvas.rotate(comp.rotation * math.pi / 180);
    }

    final w = comp.width * pixelsPerMm;
    final h = comp.height * pixelsPerMm;
    final rect = RRect.fromRectAndRadius(
      Rect.fromLTWH(-w / 2, -h / 2, w, h),
      const Radius.circular(4),
    );

    final ghostColor = brightness == Brightness.dark
        ? Colors.white54
        : Colors.black54;

    // Dashed outline using a stroke + semi-transparent approach
    final ghostPaint = Paint()
      ..color = ghostColor.withValues(alpha: 0.4)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    // Draw dash segments manually
    const dashLength = 6.0;
    const gapLength = 4.0;
    final path = Path();

    // Top edge
    _addDashedLineToPath(path, -w / 2, -h / 2, w / 2, -h / 2, dashLength, gapLength);
    // Right edge
    _addDashedLineToPath(path, w / 2, -h / 2, w / 2, h / 2, dashLength, gapLength);
    // Bottom edge
    _addDashedLineToPath(path, w / 2, h / 2, -w / 2, h / 2, dashLength, gapLength);
    // Left edge
    _addDashedLineToPath(path, -w / 2, h / 2, -w / 2, -h / 2, dashLength, gapLength);

    canvas.drawPath(path, ghostPaint);

    // Faint fill
    final fillPaint = Paint()
      ..color = ghostColor.withValues(alpha: 0.08)
      ..style = PaintingStyle.fill;
    canvas.drawRRect(rect, fillPaint);

    canvas.restore();
  }

  void _addDashedLineToPath(
    Path path,
    double x1,
    double y1,
    double x2,
    double y2,
    double dashLength,
    double gapLength,
  ) {
    final dx = x2 - x1;
    final dy = y2 - y1;
    final length = math.sqrt(dx * dx + dy * dy);
    final ux = dx / length;
    final uy = dy / length;

    var pos = 0.0;
    var drawing = true;
    while (pos < length) {
      final segLen = drawing ? dashLength : gapLength;
      final end = math.min(pos + segLen, length);
      if (drawing) {
        path.moveTo(x1 + ux * pos, y1 + uy * pos);
        path.lineTo(x1 + ux * end, y1 + uy * end);
      }
      pos = end;
      drawing = !drawing;
    }
  }

  /// 绘制选中高亮和拖拽手柄
  void _drawSelectionHighlight(Canvas canvas, FloorPlanComponent comp) {
    canvas.save();

    final cx = (comp.x + comp.width / 2) * pixelsPerMm;
    final cy = (comp.y + comp.height / 2) * pixelsPerMm;
    canvas.translate(cx, cy);

    if (comp.rotation != 0) {
      canvas.rotate(comp.rotation * math.pi / 180);
    }

    final w = comp.width * pixelsPerMm;
    final h = comp.height * pixelsPerMm;
    final rect = Rect.fromLTWH(-w / 2, -h / 2, w, h);

    // 蓝色选中边框
    final selPaint = Paint()
      ..color = Colors.blue
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;

    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(4)),
      selPaint,
    );

    // 四个角的拖拽手柄（小方块）
    final handlePaint = Paint()
      ..color = Colors.blue
      ..style = PaintingStyle.fill;

    const handleSize = 8.0;
    final corners = [
      Offset(rect.left, rect.top),
      Offset(rect.right, rect.top),
      Offset(rect.left, rect.bottom),
      Offset(rect.right, rect.bottom),
    ];

    for (final corner in corners) {
      canvas.drawRect(
        Rect.fromCenter(center: corner, width: handleSize, height: handleSize),
        handlePaint,
      );
    }

    canvas.restore();
  }

  /// 绘制 MEP 水电点位
  void _drawMEPPoints(Canvas canvas) {
    if (mepPoints == null) return;

    for (final point in mepPoints!) {
      final px = point.position.dx * pixelsPerMm;
      final py = point.position.dy * pixelsPerMm;

      Color dotColor;
      switch (point.type) {
        case MEPType.water:
          dotColor = Colors.blue;
        case MEPType.electric:
          dotColor = Colors.red;
        case MEPType.gas:
          dotColor = Colors.amber;
      }

      // 外圈
      final outerPaint = Paint()
        ..color = dotColor.withValues(alpha: 0.3)
        ..style = PaintingStyle.fill;
      canvas.drawCircle(Offset(px, py), 6, outerPaint);

      // 内圈
      final innerPaint = Paint()
        ..color = dotColor
        ..style = PaintingStyle.fill;
      canvas.drawCircle(Offset(px, py), 3, innerPaint);

      // 标签
      if (point.label != null && point.label!.isNotEmpty) {
        final tp = TextPainter(
          text: TextSpan(
            text: point.label,
            style: TextStyle(
              color: brightness == Brightness.dark
                  ? SuokeDesignTokens.textMuted
                  : SuokeDesignTokens.lightTextMuted,
              fontSize: 8,
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        tp.paint(canvas, Offset(px + 8, py - 4));
      }
    }
  }

  /// 根据组件类型返回默认颜色
  Color _colorForType(String type) {
    final t = type.toLowerCase();
    if (t.contains('cabinet') || t.contains('柜') || t.contains('橱')) {
      return const Color(0xFFB8860B); // 深金色
    }
    if (t.contains('sink') || t.contains('水槽') || t.contains('洗')) {
      return const Color(0xFF4682B4); // 钢蓝
    }
    if (t.contains('stove') || t.contains('灶') || t.contains('炉')) {
      return const Color(0xFFCD5C5C); // 印度红
    }
    if (t.contains('fridge') || t.contains('冰箱') || t.contains('冷藏')) {
      return const Color(0xFF87CEEB); // 天蓝
    }
    if (t.contains('hood') || t.contains('油烟') || t.contains('排烟')) {
      return const Color(0xFF708090); // 石板灰
    }
    if (t.contains('dishwasher') || t.contains('洗碗')) {
      return const Color(0xFFC0C0C0); // 银色
    }
    if (t.contains('oven') || t.contains('烤')) {
      return const Color(0xFF8B0000); // 暗红
    }
    if (t.contains('microwave') || t.contains('微波')) {
      return const Color(0xFFA9A9A9); // 深灰
    }
    if (t.contains('toilet') || t.contains('马桶') || t.contains('坐便')) {
      return const Color(0xFFF5F5F5); // 白烟
    }
    if (t.contains('bathtub') || t.contains('浴缸') || t.contains('沐浴')) {
      return const Color(0xFFADD8E6); // 浅蓝
    }
    if (t.contains('light') || t.contains('灯') || t.contains('照明')) {
      return const Color(0xFFFFD700); // 金色
    }
    return const Color(0xFF9370DB); // 默认：中紫
  }

  @override
  bool shouldRepaint(covariant _CompositePainter oldDelegate) {
    return oldDelegate.roomWidth != roomWidth ||
        oldDelegate.roomHeight != roomHeight ||
        oldDelegate.roomLabel != roomLabel ||
        oldDelegate.components != components ||
        oldDelegate.selectedComponentId != selectedComponentId ||
        oldDelegate.showGrid != showGrid ||
        oldDelegate.showDimensions != showDimensions ||
        oldDelegate.showMEPLayer != showMEPLayer ||
        oldDelegate.mepPoints != mepPoints ||
        oldDelegate.gridSize != gridSize ||
        oldDelegate.pixelsPerMm != pixelsPerMm ||
        oldDelegate.colorScheme != colorScheme ||
        oldDelegate.brightness != brightness ||
        oldDelegate.draggedComponentId != draggedComponentId ||
        oldDelegate.dragPositionMm != dragPositionMm ||
        oldDelegate.originalDragPositionMm != originalDragPositionMm;
  }
}

/// 缩略小地图 Painter
class _MinimapPainter extends CustomPainter {
  final double roomWidth;
  final double roomHeight;
  final List<FloorPlanComponent> components;
  final Matrix4 transformMatrix;
  final Size viewportSize;
  final double pixelsPerMm;
  final ColorScheme colorScheme;
  final Brightness brightness;

  _MinimapPainter({
    required this.roomWidth,
    required this.roomHeight,
    required this.components,
    required this.transformMatrix,
    required this.viewportSize,
    required this.pixelsPerMm,
    required this.colorScheme,
    required this.brightness,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final roomWPx = roomWidth * pixelsPerMm;
    final roomHPx = roomHeight * pixelsPerMm;

    final mapScale = math.min(size.width / roomWPx, size.height / roomHPx);
    final offsetX = (size.width - roomWPx * mapScale) / 2;
    final offsetY = (size.height - roomHPx * mapScale) / 2;

    final isDark = brightness == Brightness.dark;
    final bgColor = isDark ? Colors.grey.shade900 : Colors.grey.shade200;
    final borderColor = isDark ? Colors.white30 : Colors.black45;
    final componentColor = isDark ? Colors.white54 : Colors.black54;
    final viewportOverlay = Colors.blue.withValues(alpha: 0.25);
    final viewportStroke = Colors.blue.withValues(alpha: 0.7);

    // Background
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.width, size.height),
      Paint()..color = bgColor,
    );

    // Room outline
    canvas.drawRect(
      Rect.fromLTWH(offsetX, offsetY, roomWPx * mapScale, roomHPx * mapScale),
      Paint()
        ..color = borderColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1,
    );

    // Component markers (tiny dots)
    final dotPaint = Paint()
      ..color = componentColor
      ..style = PaintingStyle.fill;
    for (final comp in components) {
      final cx = offsetX + comp.x * pixelsPerMm * mapScale;
      final cy = offsetY + comp.y * pixelsPerMm * mapScale;
      canvas.drawCircle(Offset(cx, cy), 1.2, dotPaint);
    }

    // Viewport rectangle
    try {
      final inverse = Matrix4.inverted(transformMatrix);
      final topLeft = MatrixUtils.transformPoint(inverse, Offset.zero);
      final bottomRight = MatrixUtils.transformPoint(
        inverse,
        Offset(viewportSize.width, viewportSize.height),
      );

      final vpX = offsetX + topLeft.dx * mapScale;
      final vpY = offsetY + topLeft.dy * mapScale;
      final vpW = (bottomRight.dx - topLeft.dx) * mapScale;
      final vpH = (bottomRight.dy - topLeft.dy) * mapScale;

      // Clamp to minimap bounds
      final vpRect = Rect.fromLTWH(vpX, vpY, vpW, vpH);
      final clippedRect = vpRect.intersect(
        Rect.fromLTWH(0, 0, size.width, size.height),
      );

      canvas.drawRect(
        clippedRect,
        Paint()..color = viewportOverlay ..style = PaintingStyle.fill,
      );
      canvas.drawRect(
        clippedRect,
        Paint()..color = viewportStroke ..style = PaintingStyle.stroke ..strokeWidth = 1,
      );
    } catch (_) {
      // If matrix inversion fails, skip viewport rect
    }
  }

  @override
  bool shouldRepaint(covariant _MinimapPainter oldDelegate) {
    return oldDelegate.roomWidth != roomWidth ||
        oldDelegate.roomHeight != roomHeight ||
        oldDelegate.components != components ||
        oldDelegate.transformMatrix != transformMatrix ||
        oldDelegate.viewportSize != viewportSize ||
        oldDelegate.pixelsPerMm != pixelsPerMm ||
        oldDelegate.colorScheme != colorScheme ||
        oldDelegate.brightness != brightness;
  }
}
