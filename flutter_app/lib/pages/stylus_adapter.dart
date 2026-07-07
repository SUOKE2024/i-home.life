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
