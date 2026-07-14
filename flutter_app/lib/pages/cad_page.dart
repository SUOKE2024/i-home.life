import 'dart:convert';
import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'cad_element.dart';
import '../services/api.dart';

class CADPage extends StatefulWidget {
  const CADPage({super.key});
  @override
  State<CADPage> createState() => _CADPageState();
}

class _CADPageState extends State<CADPage> {
  final List<DrawingElement> _elements = [];
  String _tool = 'select';
  DrawingElement? _drawing;
  DrawingElement? _dragTarget;
  Offset _dragStart = Offset.zero;
  Offset _dragElementStart = Offset.zero;
  double _scale = 1.0;
  double _initialScale = 1.0;
  Offset _offset = const Offset(300, 100);
  Offset? _panStart;
  bool _orthoLock = true;
  bool _snapEnabled = true;
  final double _pxPerMeter = 50.0;
  final double _snapThreshold = 0.5;

  // 撤销/重做历史栈
  final List<List<DrawingElement>> _undoStack = [];
  final List<List<DrawingElement>> _redoStack = [];

  // 图层管理
  final List<Map<String, dynamic>> _layers = [
    {'name': '墙体', 'visible': true, 'color': '#4A4A4A'},
    {'name': '门窗', 'visible': true, 'color': '#5A7EC9'},
    {'name': '尺寸标注', 'visible': true, 'color': '#8A8894'},
  ];
  int _activeLayerIdx = 0;

  static const _colors = [Colors.blueGrey, Colors.brown, Colors.teal, Colors.indigo, Colors.orange, Colors.pink, Colors.green, Colors.amber];

  final Map<String, String> _toolNames = {
    'select': '选择', 'line': '直线', 'rect': '矩形', 'arc': '圆弧',
    'dim': '标注', 'delete': '删除', 'move': '移动',
  };

  Offset _toWorld(Offset p) =>
      Offset((p.dx - _offset.dx) / _pxPerMeter / _scale, (p.dy - _offset.dy) / _pxPerMeter / _scale);

  double _snapVal(double v) => (v * 2).roundToDouble() / 2;

  Offset _snapPoint(Offset p) {
    if (!_snapEnabled) return p;
    double sx = _snapVal(p.dx);
    double sy = _snapVal(p.dy);
    for (final el in _elements) {
      final sp = el.nearestSnap(sx, sy, _snapThreshold);
      if (sp != null) return sp;
    }
    return Offset(sx, sy);
  }

  void _onScaleStart(ScaleStartDetails d) {
    _initialScale = _scale;
    if (d.pointerCount >= 2) return; // pinch-to-zoom
    var wp = _toWorld(d.localFocalPoint);
    wp = _snapPoint(wp);
    if (_orthoLock && _drawing != null && _drawing!.type == 'line' && _drawing!.x1 != _drawing!.x2) {
      final dx = (wp.dx - _drawing!.x1).abs();
      final dy = (wp.dy - _drawing!.y1).abs();
      if (dx > dy * 3) wp = Offset(wp.dx, _drawing!.y1);
      else if (dy > dx * 3) wp = Offset(_drawing!.x1, wp.dy);
    }
    if (_tool == 'rect') {
      _drawing = DrawingElement.rect(wp.dx, wp.dy, 0, 0, color: _colors[_elements.length % _colors.length]);
    } else if (_tool == 'line') {
      _drawing = DrawingElement.line(wp.dx, wp.dy, wp.dx, wp.dy);
    } else if (_tool == 'delete') {
      final hit = _hitTest(wp.dx, wp.dy);
      if (hit >= 0) {
        _pushUndo();
        _elements.removeAt(hit);
      }
    } else if (_tool == 'move') {
      final hit = _hitTest(wp.dx, wp.dy);
      if (hit >= 0) {
        _pushUndo();
        _dragTarget = _elements[hit];
        _dragStart = wp;
        _dragElementStart = Offset(_dragTarget!.x, _dragTarget!.y);
      }
    } else {
      _panStart = d.localFocalPoint;
    }
    setState(() {});
  }

  void _onScaleUpdate(ScaleUpdateDetails d) {
    if (d.pointerCount >= 2) {
      setState(() {
        _scale = (_initialScale * d.scale).clamp(0.2, 5.0);
      });
      return;
    }
    var wp = _toWorld(d.localFocalPoint);
    wp = _snapPoint(wp);
    if (_orthoLock && _drawing != null && _drawing!.type == 'line') {
      final dx = (wp.dx - _drawing!.x1).abs();
      final dy = (wp.dy - _drawing!.y1).abs();
      if (dx > dy * 2) wp = Offset(wp.dx, _drawing!.y1);
      else if (dy > dx * 2) wp = Offset(_drawing!.x1, wp.dy);
    }
    if (_drawing != null && _drawing!.type == 'rect') {
      _drawing!.w = math.max(0.3, (wp.dx - _drawing!.x).abs());
      _drawing!.h = math.max(0.3, (wp.dy - _drawing!.y).abs());
      if (wp.dx < _drawing!.x) { _drawing!.w = _drawing!.x - wp.dx; _drawing!.x = wp.dx; }
      if (wp.dy < _drawing!.y) { _drawing!.h = _drawing!.y - wp.dy; _drawing!.y = wp.dy; }
    } else if (_drawing != null && _drawing!.type == 'line') {
      _drawing!.x2 = wp.dx; _drawing!.y2 = wp.dy;
    } else if (_dragTarget != null) {
      final dx = wp.dx - _dragStart.dx, dy = wp.dy - _dragStart.dy;
      _dragTarget!.x = _snapVal(_dragElementStart.dx + dx);
      _dragTarget!.y = _snapVal(_dragElementStart.dy + dy);
      if (_dragTarget!.type == 'rect') {
        _dragTarget!.x1 = _dragTarget!.x; _dragTarget!.y1 = _dragTarget!.y;
        _dragTarget!.x2 = _dragTarget!.x + _dragTarget!.w; _dragTarget!.y2 = _dragTarget!.y + _dragTarget!.h;
      }
    } else if (_panStart != null) {
      _offset += d.focalPointDelta;
    }
    setState(() {});
  }

  void _onScaleEnd(ScaleEndDetails d) {
    if (_drawing != null) {
      _elements.add(_drawing!); _drawing = null;
      _pushUndo();
    }
    _dragTarget = null; _dragStart = Offset.zero; _panStart = null;
    setState(() {});
  }

  int _hitTest(double wx, double wy) {
    for (int i = _elements.length - 1; i >= 0; i--) {
      if (_elements[i].hitTest(wx, wy)) return i;
    }
    return -1;
  }

  void _pushUndo() {
    _undoStack.add(List<DrawingElement>.from(_elements));
    _redoStack.clear();
  }

  void _undo() {
    if (_undoStack.isEmpty) return;
    _redoStack.add(List<DrawingElement>.from(_elements));
    setState(() {
      _elements.clear();
      _elements.addAll(_undoStack.removeLast());
    });
  }

  void _redo() {
    if (_redoStack.isEmpty) return;
    _undoStack.add(List<DrawingElement>.from(_elements));
    setState(() {
      _elements.clear();
      _elements.addAll(_redoStack.removeLast());
    });
  }

  void _saveProject() {
    final data = {
      'type': 'floorplan', 'version': '2.0',
      'elements': _elements.map((e) => e.toJson()).toList(),
      'layers': _layers,
      'scale': _scale, 'offset': {'x': _offset.dx, 'y': _offset.dy},
      'saved_at': DateTime.now().toIso8601String(),
    };
    Clipboard.setData(ClipboardData(text: jsonEncode(data)));
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('项目文件已复制到剪贴板（JSON）')));
  }

  void _loadProject() {
    showDialog(
      context: context,
      builder: (ctx) {
        final ctrl = TextEditingController();
        return AlertDialog(
          backgroundColor: const Color(0xFF12121D),
          title: const Text('加载项目', style: TextStyle(color: Color(0xFFE8E6E1))),
          content: TextField(
            controller: ctrl,
            maxLines: 8,
            style: const TextStyle(color: Color(0xFFE8E6E1), fontSize: 12, fontFamily: 'monospace'),
            decoration: const InputDecoration(
              hintText: '粘贴 JSON 项目数据...',
              hintStyle: TextStyle(color: Color(0xFF5A5866)),
              border: OutlineInputBorder(borderSide: BorderSide(color: Color(0xFF2A2A3E))),
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
            TextButton(
              onPressed: () {
                try {
                  final data = jsonDecode(ctrl.text);
                  setState(() {
                    _elements.clear();
                    for (final e in data['elements']) {
                      _elements.add(DrawingElement.fromJson(e));
                    }
                  });
                  Navigator.pop(ctx);
                } catch (e) {
                  ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('解析失败: $e')));
                }
              },
              child: const Text('加载', style: TextStyle(color: Color(0xFFC9973B))),
            ),
          ],
        );
      },
    );
  }

  void _showLayerPanel() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF12121D),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => Container(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('图层面板', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 16),
              ..._layers.asMap().entries.map((entry) {
                final idx = entry.key;
                final layer = entry.value;
                return ListTile(
                  leading: Icon(Icons.layers, color: layer['visible'] ? const Color(0xFFC9973B) : const Color(0xFF5A5866)),
                  title: Text(layer['name'], style: TextStyle(color: layer['visible'] ? Colors.white : const Color(0xFF5A5866))),
                  trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                    IconButton(
                      icon: Icon(layer['visible'] ? Icons.visibility : Icons.visibility_off, color: const Color(0xFF8A8894), size: 20),
                      onPressed: () => setModalState(() => _layers[idx]['visible'] = !_layers[idx]['visible']),
                    ),
                    Radio<int>(value: idx, groupValue: _activeLayerIdx, activeColor: const Color(0xFFC9973B),
                      onChanged: (v) => setModalState(() => _activeLayerIdx = v as int)),
                  ]),
                );
              }),
            ],
          ),
        ),
      ),
    );
  }

  void _reset() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF12121D),
        title: const Text('确认清空', style: TextStyle(color: Color(0xFFE8E6E1))),
        content: const Text('将删除所有绘图元素，此操作不可恢复。', style: TextStyle(color: Color(0xFF8A8894))),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          TextButton(
            onPressed: () {
              setState(() => _elements.clear());
              Navigator.pop(ctx);
            },
            child: const Text('确认清空', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }

  void _exportJSON() {
    final data = {
      'type': 'floorplan', 'version': '1.0',
      'elements': _elements.map((e) => e.toJson()).toList(),
    };
    Clipboard.setData(ClipboardData(text: const JsonEncoder.withIndent('  ').convert(data)));
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('JSON 已复制到剪贴板')));
  }

  Future<void> _exportDXF() async {
    final buf = StringBuffer();
    buf.writeln('  0\nSECTION\n  2\nHEADER\n  0\nENDSEC');
    buf.writeln('  0\nSECTION\n  2\nENTITIES');
    for (final el in _elements) { buf.writeln(el.toDxf()); }
    buf.writeln('  0\nENDSEC\n  0\nEOF');
    await Clipboard.setData(ClipboardData(text: buf.toString()));
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('DXF 已复制到剪贴板（可在 AutoCAD / LibreCAD 中粘贴）')),
      );
    }
  }

  Future<String?> _pickProjectId() async {
    final result = await ApiClient().getList('/projects');
    final projects = result.isSuccess ? result.data as List? : null;
    if (projects == null || projects.isEmpty) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('没有可用项目，请先创建项目')));
      }
      return null;
    }
    if (projects.length == 1) return projects.first['id'] as String;
    String? selected = projects.first['id'] as String;
    return showDialog<String>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          title: const Text('选择项目'),
          content: SizedBox(
            width: double.maxFinite,
            child: ListView.builder(
              shrinkWrap: true,
              itemCount: projects.length,
              itemBuilder: (_, i) {
                final p = projects[i];
                return RadioListTile<String>(
                  value: p['id'] as String,
                  groupValue: selected,
                  title: Text(p['name']?.toString() ?? '未命名项目'),
                  onChanged: (v) => setState(() => selected = v),
                );
              },
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
            TextButton(onPressed: () => Navigator.pop(ctx, selected), child: const Text('确定')),
          ],
        ),
      ),
    );
  }

  Future<void> _savePlan() async {
    if (_elements.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('画布为空，无法保存')));
      return;
    }
    final projectId = await _pickProjectId();
    if (projectId == null) return;

    final nameController = TextEditingController(
      text: '方案 ${DateTime.now().toIso8601String().substring(0, 16)}',
    );
    final name = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('保存方案'),
        content: TextField(
          controller: nameController,
          decoration: const InputDecoration(labelText: '方案名称'),
          autofocus: true,
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(ctx, nameController.text.trim()), child: const Text('保存')),
        ],
      ),
    );
    if (name == null || name.isEmpty) return;

    final data = {
      'type': 'floorplan', 'version': '1.0',
      'elements': _elements.map((e) => e.toJson()).toList(),
    };
    final dataStr = jsonEncode(data);

    double totalArea = 0;
    int roomCount = 0;
    for (final el in _elements) {
      if (el.type == 'rect') {
        totalArea += el.w * el.h;
        if (el.name.isNotEmpty) roomCount++;
      }
    }

    final result = await ApiClient().post('/floorplans', {
      'project_id': projectId,
      'name': name,
      'data': dataStr,
      'wall_height': 2.8,
      'total_area': totalArea,
      'room_count': roomCount,
    });

    if (context.mounted) {
      if (result.isSuccess) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('方案已保存')));
      } else {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('保存失败: ${result.error}')));
      }
    }
  }

  Future<void> _loadPlan() async {
    final projectId = await _pickProjectId();
    if (projectId == null) return;

    final plansResult = await ApiClient().getList('/floorplans/project/$projectId');
    final plans = plansResult.isSuccess ? plansResult.data as List? : null;
    if (plans == null || plans.isEmpty) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('该项目没有保存的方案')));
      }
      return;
    }

    final planId = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('加载方案'),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView.builder(
            shrinkWrap: true,
            itemCount: plans.length,
            itemBuilder: (_, i) {
              final p = plans[i];
              final updated = (p['updated_at']?.toString() ?? '').substring(0, 16);
              return ListTile(
                title: Text(p['name']?.toString() ?? '未命名方案'),
                subtitle: Text('${p['total_area'] ?? 0}㎡ · ${p['room_count'] ?? 0}房间 · $updated'),
                onTap: () => Navigator.pop(ctx, p['id'] as String),
              );
            },
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
        ],
      ),
    );
    if (planId == null) return;

    final planResult = await ApiClient().get('/floorplans/$planId');
    if (!planResult.isSuccess) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('加载失败: ${planResult.error}')));
      }
      return;
    }
    final plan = planResult.data as Map<String, dynamic>;
    final dataStr = plan['data'] as String;
    final decoded = jsonDecode(dataStr);
    final List elementsList = decoded is Map
        ? (decoded['elements'] as List)
        : (decoded as List);

    setState(() {
      _elements
        ..clear()
        ..addAll(elementsList.map((e) => DrawingElement.fromJson(e as Map<String, dynamic>)));
    });

    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('已加载 ${_elements.length} 个元素')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('设计台', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(icon: const Icon(Icons.undo, size: 20), tooltip: '撤销', onPressed: _undoStack.isNotEmpty ? _undo : null, color: const Color(0xFF8A8894)),
          IconButton(icon: const Icon(Icons.redo, size: 20), tooltip: '重做', onPressed: _redoStack.isNotEmpty ? _redo : null, color: const Color(0xFF8A8894)),
          IconButton(icon: const Icon(Icons.layers, size: 20), tooltip: '图层', onPressed: _showLayerPanel, color: const Color(0xFFC9973B)),
          IconButton(icon: const Icon(Icons.save_alt, size: 20), tooltip: '保存项目文件', onPressed: _saveProject, color: const Color(0xFF4A9E6E)),
          IconButton(icon: const Icon(Icons.file_open, size: 20), tooltip: '加载项目文件', onPressed: _loadProject, color: const Color(0xFF5A7EC9)),
          IconButton(icon: const Icon(Icons.folder_open, size: 20), tooltip: '加载方案', onPressed: _loadPlan),
          IconButton(icon: const Icon(Icons.save, size: 20), tooltip: '保存方案', onPressed: _savePlan),
          IconButton(icon: Icon(_orthoLock ? Icons.lock : Icons.lock_open, size: 20), tooltip: '正交锁定 ${_orthoLock ? "ON" : "OFF"}', onPressed: () => setState(() => _orthoLock = !_orthoLock)),
          IconButton(icon: Icon(_snapEnabled ? Icons.grid_on : Icons.grid_off, size: 20), tooltip: '对象捕捉 ${_snapEnabled ? "ON" : "OFF"}', onPressed: () => setState(() => _snapEnabled = !_snapEnabled)),
          IconButton(icon: const Icon(Icons.refresh), tooltip: '重置', onPressed: _reset),
          PopupMenuButton<String>(
            icon: const Icon(Icons.ios_share),
            onSelected: (v) {
              if (v == 'json') _exportJSON();
              if (v == 'dxf') _exportDXF();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'json', child: Text('导出 JSON')),
              PopupMenuItem(value: 'dxf', child: Text('导出 DXF')),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            color: const Color(0xFF12121D),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: _toolNames.entries.map((e) => Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 3),
                  child: ChoiceChip(
                    label: Text(e.value, style: TextStyle(fontSize: 12, color: _tool == e.key ? const Color(0xFFC9973B) : const Color(0xFF8A8894))),
                    selected: _tool == e.key,
                    onSelected: (_) => setState(() => _tool = e.key),
                    selectedColor: const Color(0xFFC9973B).withValues(alpha: 0.2),
                  ),
                )).toList(),
              ),
            ),
          ),
          Expanded(
            child: GestureDetector(
              onScaleStart: _onScaleStart,
              onScaleUpdate: _onScaleUpdate,
              onScaleEnd: _onScaleEnd,
              child: CustomPaint(
                size: Size.infinite,
                painter: CADPainter(
                  elements: _elements,
                  drawing: _drawing,
                  scale: _scale,
                  offset: _offset,
                  pxPerMeter: _pxPerMeter,
                  tool: _tool,
                ),
              ),
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            color: const Color(0xFF12121D),
            child: Row(
              children: [
                Text('${_elements.length} 元素', style: const TextStyle(fontSize: 12, color: Color(0xFF8A8894))),
                const SizedBox(width: 12),
                Text('正交:${_orthoLock ? "ON" : "OFF"}', style: const TextStyle(fontSize: 11, color: Color(0xFF5A5866))),
                const SizedBox(width: 8),
                Text('捕捉:${_snapEnabled ? "ON" : "OFF"}', style: const TextStyle(fontSize: 11, color: Color(0xFF5A5866))),
                const Spacer(),
                Text('缩放 ${(_scale * 100).toInt()}% | ${_toolNames[_tool]}', style: const TextStyle(fontSize: 12, color: Color(0xFF5A5866))),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class CADPainter extends CustomPainter {
  final List<DrawingElement> elements;
  final DrawingElement? drawing;
  final double scale, offsetX = 0, offsetY = 0, pxPerMeter;
  final String tool;
  final Offset offset;

  CADPainter({
    required this.elements, this.drawing, required this.scale,
    required this.offset, required this.pxPerMeter, required this.tool,
  });

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.translate(offset.dx, offset.dy);
    canvas.scale(scale, scale);

    final gs = pxPerMeter;
    final gridPaint = Paint()..color = const Color(0x08FFFFFF)..strokeWidth = 0.5 / scale;
    for (double x = -20 * gs; x < size.width * 3; x += gs) {
      canvas.drawLine(Offset(x, -2000), Offset(x, 10000), gridPaint);
    }
    for (double y = -20 * gs; y < size.height * 3; y += gs) {
      canvas.drawLine(Offset(-2000, y), Offset(10000, y), gridPaint);
    }
    final majorPaint = Paint()..color = const Color(0x15FFFFFF)..strokeWidth = 1.0 / scale;
    for (double x = -20 * gs; x < size.width * 3; x += gs * 5) {
      canvas.drawLine(Offset(x, -2000), Offset(x, 10000), majorPaint);
    }
    for (double y = -20 * gs; y < size.height * 3; y += gs * 5) {
      canvas.drawLine(Offset(-2000, y), Offset(10000, y), majorPaint);
    }

    final axisPaint = Paint()..color = const Color(0x20FFFFFF)..strokeWidth = 1.5 / scale;
    canvas.drawLine(const Offset(-2000, 0), const Offset(10000, 0), axisPaint);
    canvas.drawLine(const Offset(0, -2000), const Offset(0, 10000), axisPaint);

    for (final el in elements) {
      _drawElement(canvas, el);
    }

    if (drawing != null) {
      final previewPaint = Paint()..color = const Color(0x33C9973B)..style = PaintingStyle.fill;
      final previewStroke = Paint()..color = const Color(0x99C9973B)..style = PaintingStyle.stroke..strokeWidth = 2.0 / scale;
      if (drawing!.type == 'rect') {
        final r = Rect.fromLTWH(drawing!.x * pxPerMeter, drawing!.y * pxPerMeter, drawing!.w * pxPerMeter, drawing!.h * pxPerMeter);
        canvas.drawRect(r, previewPaint);
        canvas.drawRect(r, previewStroke);
      }
    }

    canvas.restore();
  }

  void _drawElement(Canvas canvas, DrawingElement el) {
    if (el.type == 'rect') {
      final rect = Rect.fromLTWH(el.x * pxPerMeter, el.y * pxPerMeter, el.w * pxPerMeter, el.h * pxPerMeter);
      canvas.drawRect(rect, Paint()..color = el.color.withValues(alpha: 0.3));
      canvas.drawRect(rect, Paint()..color = el.color..style = PaintingStyle.stroke..strokeWidth = 2.0 / scale);
      if (el.name.isNotEmpty) {
        final tp = _textPainter(el.name, 11 / scale, Colors.white);
        canvas.drawParagraph(tp, Offset(el.x * pxPerMeter + rect.width / 2 - tp.width / 2, el.y * pxPerMeter + rect.height / 2 - tp.height / 2));
      }
      final area = (el.w * el.h).toStringAsFixed(1);
      final ap = _textPainter('${area}㎡', 9 / scale, Colors.white54);
      canvas.drawParagraph(ap, Offset(el.x * pxPerMeter + rect.width / 2 - ap.width / 2, el.y * pxPerMeter + rect.height / 2 + 6 / scale));
      final dimPaint = Paint()..color = Colors.white38..strokeWidth = 0.8 / scale;
      final dimOffset = 8.0 / scale;
      canvas.drawLine(Offset(el.x * pxPerMeter, el.y * pxPerMeter - dimOffset), Offset((el.x + el.w) * pxPerMeter, el.y * pxPerMeter - dimOffset), dimPaint);
      canvas.drawLine(Offset(el.x * pxPerMeter, el.y * pxPerMeter - dimOffset - 3 / scale), Offset(el.x * pxPerMeter, el.y * pxPerMeter - dimOffset + 3 / scale), dimPaint);
      canvas.drawLine(Offset((el.x + el.w) * pxPerMeter, el.y * pxPerMeter - dimOffset - 3 / scale), Offset((el.x + el.w) * pxPerMeter, el.y * pxPerMeter - dimOffset + 3 / scale), dimPaint);
      final wp = _textPainter('${el.w.toStringAsFixed(1)}m', 8 / scale, Colors.white38);
      canvas.drawParagraph(wp, Offset(el.x * pxPerMeter + rect.width / 2 - wp.width / 2, el.y * pxPerMeter - dimOffset - 10 / scale));
    } else if (el.type == 'line') {
      canvas.drawLine(Offset(el.x1 * pxPerMeter, el.y1 * pxPerMeter), Offset(el.x2 * pxPerMeter, el.y2 * pxPerMeter),
          Paint()..color = Colors.white..strokeWidth = 2.5 / scale);
    }
  }

  ui.Paragraph _textPainter(String text, double fontSize, Color color) {
    final builder = ui.ParagraphBuilder(ui.ParagraphStyle(textDirection: TextDirection.ltr, maxLines: 1))
      ..addText(text)
      ..pushStyle(ui.TextStyle(color: color, fontSize: fontSize));
    final p = builder.build()..layout(const ui.ParagraphConstraints(width: 500));
    return p;
  }

  @override
  bool shouldRepaint(covariant CADPainter old) => true;
}
