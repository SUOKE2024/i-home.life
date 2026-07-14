import 'dart:ui' as dart_ui;
import 'package:flutter/material.dart';

enum StylusPlatform { applePencil, harmonyMPencil, unknown }

class StylusAdapter extends StatefulWidget {
  final Widget child;
  final bool enablePressure;
  final bool enableHover;
  final bool enableDoubleTap;
  final ValueChanged<double>? onPressureChanged;
  final ValueChanged<Offset>? onHoverChanged;
  final ValueChanged<String>? onDoubleTapToolChanged;

  const StylusAdapter({
    super.key,
    required this.child,
    this.enablePressure = true,
    this.enableHover = true,
    this.enableDoubleTap = true,
    this.onPressureChanged,
    this.onHoverChanged,
    this.onDoubleTapToolChanged,
  });

  @override
  State<StylusAdapter> createState() => _StylusAdapterState();
}

class _StylusAdapterState extends State<StylusAdapter> {
  double _currentPressure = 0.0;
  double _currentTilt = 0.0;
  Offset _hoverPosition = Offset.zero;
  bool _isHovering = false;
  int _toolIndex = 0;
  final _tools = ['select', 'rect', 'line', 'delete', 'move'];
  double _lastTapTime = 0;

  double get pressure => _enablePressure ? _currentPressure : 1.0;
  double get tilt => _currentTilt;
  double get strokeWidth => 1.0 + _currentPressure * 8.0 + _currentTilt * 3.0;
  bool get isHovering => _isHovering && _enableHover;
  int get toolIndex => _toolIndex;
  StylusPlatform get _platform => _detectPlatform();

  bool get _enablePressure => widget.enablePressure;
  bool get _enableHover => widget.enableHover;
  bool get _enableDoubleTap => widget.enableDoubleTap;

  StylusPlatform _detectPlatform() {
    try {
      if (dart_ui.PlatformDispatcher.instance.defaultRouteName.contains('ohos')) {
        return StylusPlatform.harmonyMPencil;
      }
    } catch (_) {}
    return StylusPlatform.applePencil;
  }

  void _handleDoubleTap() {
    if (!_enableDoubleTap) return;
    _toolIndex = (_toolIndex + 1) % _tools.length;
    widget.onDoubleTapToolChanged?.call(_tools[_toolIndex]);
  }

  @override
  Widget build(BuildContext context) {
    return Listener(
      onPointerDown: (event) {
        if (event.kind == dart_ui.PointerDeviceKind.stylus) {
          if (_enablePressure) {
            _currentPressure = event.pressure.clamp(0.0, 1.0);
            _currentTilt = (event.tilt).clamp(0.0, 1.0);
            widget.onPressureChanged?.call(_currentPressure);
          }
          if (_enableDoubleTap) {
            final dt = DateTime.now().millisecondsSinceEpoch.toDouble();
            if (dt - _lastTapTime < 400) {
              _handleDoubleTap();
              _lastTapTime = 0;
            } else {
              _lastTapTime = dt;
            }
          }
        }
      },
      onPointerMove: (event) {
        if (event.kind == dart_ui.PointerDeviceKind.stylus && _enablePressure) {
          _currentPressure = event.pressure.clamp(0.0, 1.0);
          _currentTilt = (event.tilt).clamp(0.0, 1.0);
          widget.onPressureChanged?.call(_currentPressure);
        }
      },
      onPointerUp: (event) {
        if (event.kind == dart_ui.PointerDeviceKind.stylus) {
          _currentPressure = 0.0;
          _currentTilt = 0.0;
          widget.onPressureChanged?.call(0.0);
        }
      },
      onPointerHover: (event) {
        if (event.kind == dart_ui.PointerDeviceKind.stylus && _enableHover) {
          _hoverPosition = event.position;
          _isHovering = true;
          widget.onHoverChanged?.call(_hoverPosition);
        } else {
          _isHovering = false;
        }
      },
      child: widget.child,
    );
  }
}

class StylusCursorPainter extends CustomPainter {
  final Offset position;
  final double radius;
  final double pressure;
  final StylusPlatform platform;

  StylusCursorPainter({
    required this.position,
    required this.radius,
    this.pressure = 0.0,
    this.platform = StylusPlatform.applePencil,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final baseRadius = radius + pressure * 8.0;

    final outerPaint = Paint()
      ..color = const Color(0x30C9973B)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;
    canvas.drawCircle(position, baseRadius, outerPaint);

    final innerPaint = Paint()
      ..color = const Color(0x60C9973B)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(position, baseRadius * 0.4, innerPaint);

    final dotPaint = Paint()
      ..color = const Color(0xA0C9973B)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(position, 2.5, dotPaint);
  }

  @override
  bool shouldRepaint(covariant StylusCursorPainter old) =>
      old.position != position ||
      old.radius != radius ||
      old.pressure != pressure;
}

// 索克家居
/// 笔触适配器演示页面
class StylusAdapterPage extends StatefulWidget {
  const StylusAdapterPage({super.key});
  @override
  State<StylusAdapterPage> createState() => _StylusAdapterPageState();
}

class _StylusAdapterPageState extends State<StylusAdapterPage> {
  bool _palmRejection = true;
  String _stylusType = '未检测';
  double _pressure = 0;
  double _tilt = 0;
  final List<Map<String, dynamic>> _strokes = [];
  Offset? _lastPoint;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('笔触适配器'),
        backgroundColor: const Color(0xFF12121D),
        foregroundColor: Colors.white,
      ),
      body: Container(
        color: const Color(0xFF0E0E1A),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              margin: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF1A1A2E),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFF2A2A3E)),
              ),
              child: Column(
                children: [
                  Row(mainAxisAlignment: MainAxisAlignment.spaceAround, children: [
                    _infoChip('笔类型', _stylusType, const Color(0xFFC9973B)),
                    _infoChip('压感', '${(_pressure * 4096).round()}/4096', const Color(0xFF4A9E6E)),
                    _infoChip('倾斜角', '${(_tilt * 90).round()}°', const Color(0xFF5A7EC9)),
                  ]),
                  const SizedBox(height: 12),
                  Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    const Text('防手掌误触', style: TextStyle(color: Color(0xFF8A8894), fontSize: 13)),
                    Switch(
                      value: _palmRejection,
                      onChanged: (v) => setState(() => _palmRejection = v),
                      activeTrackColor: const Color(0xFFC9973B),
                    ),
                  ]),
                ],
              ),
            ),
            Expanded(
              child: Container(
                margin: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFF1A1A2E),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFF2A2A3E)),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Listener(
                    onPointerDown: (event) {
                      setState(() {
                        _stylusType = event.kind == dart_ui.PointerDeviceKind.stylus ? '触控笔' : '手指';
                        _pressure = event.pressure.clamp(0.0, 1.0);
                        _strokes.add({
                          'points': [event.localPosition],
                          'pressure': _pressure,
                          'color': Colors.white,
                        });
                        _lastPoint = event.localPosition;
                      });
                    },
                    onPointerMove: (event) {
                      if (_palmRejection && event.kind != dart_ui.PointerDeviceKind.stylus) return;
                      setState(() {
                        _pressure = event.pressure.clamp(0.0, 1.0);
                        _tilt = event.pressure;
                        if (_strokes.isNotEmpty) {
                          _strokes.last['points'].add(event.localPosition);
                        }
                      });
                    },
                    child: CustomPaint(
                      painter: _StylusPainter(_strokes),
                      size: Size.infinite,
                    ),
                  ),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(12),
              child: Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
                ElevatedButton.icon(
                  onPressed: () => setState(() => _strokes.clear()),
                  icon: const Icon(Icons.delete_outline, size: 18),
                  label: const Text('清除'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1A1A2E),
                    foregroundColor: Colors.white,
                  ),
                ),
                ElevatedButton.icon(
                  onPressed: () {
                    setState(() {
                      _stylusType = 'Apple Pencil (模拟)';
                    });
                  },
                  icon: const Icon(Icons.apple, size: 18),
                  label: const Text('Apple Pencil'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1A1A2E),
                    foregroundColor: Colors.white,
                  ),
                ),
                ElevatedButton.icon(
                  onPressed: () {
                    setState(() {
                      _stylusType = 'M-Pencil (模拟)';
                    });
                  },
                  icon: const Icon(Icons.edit, size: 18),
                  label: const Text('M-Pencil'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1A1A2E),
                    foregroundColor: Colors.white,
                  ),
                ),
              ]),
            ),
          ],
        ),
      ),
    );
  }

  Widget _infoChip(String label, String value, Color color) {
    return Column(children: [
      Text(label, style: const TextStyle(color: Color(0xFF8A8894), fontSize: 11)),
      const SizedBox(height: 4),
      Text(value, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 14)),
    ]);
  }
}

class _StylusPainter extends CustomPainter {
  final List<Map<String, dynamic>> strokes;
  _StylusPainter(this.strokes);

  @override
  void paint(Canvas canvas, Size size) {
    for (final stroke in strokes) {
      final points = stroke['points'] as List<Offset>;
      final pressure = stroke['pressure'] as double;
      final color = stroke['color'] as Color;
      final paint = Paint()
        ..color = color
        ..strokeWidth = 2 + pressure * 6
        ..strokeCap = StrokeCap.round
        ..style = PaintingStyle.stroke;
      for (int i = 1; i < points.length; i++) {
        canvas.drawLine(points[i - 1], points[i], paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _StylusPainter old) => true;
}
