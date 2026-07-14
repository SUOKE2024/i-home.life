import 'dart:math' as math;
import 'package:flutter/material.dart';

class DrawingElement {
  String type;
  double x, y, w, h;
  double x1, y1, x2, y2;
  double r, startAngle, sweepAngle;
  String name;
  Color color;
  int layer;
  bool selected;
  bool isWall;

  DrawingElement.rect(this.x, this.y, this.w, this.h,
      {this.name = '', this.color = Colors.grey, this.layer = 0, this.isWall = false})
      : type = 'rect',
        x1 = x,
        y1 = y,
        x2 = x + w,
        y2 = y + h,
        r = 0,
        startAngle = 0,
        sweepAngle = 0,
        selected = false;

  DrawingElement.line(this.x1, this.y1, this.x2, this.y2,
      {this.name = '', this.color = Colors.white, this.layer = 0, this.isWall = false})
      : type = 'line',
        x = math.min(x1, x2),
        y = math.min(y1, y2),
        w = (x2 - x1).abs(),
        h = (y2 - y1).abs(),
        r = 0,
        startAngle = 0,
        sweepAngle = 0,
        selected = false;

  DrawingElement.arc(this.x, this.y, this.r, this.startAngle, this.sweepAngle,
      {this.name = '', this.color = Colors.cyan, this.layer = 0})
      : type = 'arc',
        x1 = 0,
        y1 = 0,
        x2 = 0,
        y2 = 0,
        w = 0,
        h = 0,
        isWall = false,
        selected = false;

  Offset get centerRect => Offset(x + w / 2, y + h / 2);
  Offset get endPoint => type == 'line' ? Offset(x2, y2) : Offset(x + w, y + h);
  Offset get startPoint => type == 'line' ? Offset(x1, y1) : Offset(x, y);

  List<Offset> get snapPoints => [
        Offset(x, y),
        Offset(x + w, y),
        Offset(x + w, y + h),
        Offset(x, y + h),
        if (type == 'line') Offset(x1, y1),
        if (type == 'line') Offset(x2, y2),
        if (type == 'line') Offset((x1 + x2) / 2, (y1 + y2) / 2),
        Offset(x + w / 2, y + h / 2),
      ].where((p) => p.dx.isFinite && p.dy.isFinite).toList();

  bool hitTest(double px, double py) {
    if (type == 'rect') {
      return px >= x && px <= x + w && py >= y && py <= y + h;
    }
    if (type == 'line') {
      final d = _distToSegment(px, py, x1, y1, x2, y2);
      return d < 0.3;
    }
    return false;
  }

  Offset? nearestSnap(double px, double py, double threshold) {
    for (final p in snapPoints) {
      final d = math.sqrt((p.dx - px) * (p.dx - px) + (p.dy - py) * (p.dy - py));
      if (d < threshold) return p;
    }
    return null;
  }

  double _distToSegment(double px, double py, double ax, double ay, double bx, double by) {
    final dx = bx - ax, dy = by - ay;
    final len2 = dx * dx + dy * dy;
    if (len2 == 0) return math.sqrt((px - ax) * (px - ax) + (py - ay) * (py - ay));
    var t = ((px - ax) * dx + (py - ay) * dy) / len2;
    t = t.clamp(0.0, 1.0);
    final cx = ax + t * dx, cy = ay + t * dy;
    return math.sqrt((px - cx) * (px - cx) + (py - cy) * (py - cy));
  }

  Map<String, dynamic> toJson() => {
        'type': type,
        'x': x,
        'y': y,
        'w': w,
        'h': h,
        'x1': x1,
        'y1': y1,
        'x2': x2,
        'y2': y2,
        'r': r,
        'startAngle': startAngle,
        'sweepAngle': sweepAngle,
        'name': name,
        'layer': layer,
        'is_wall': isWall,
        'color': color.value,
      };

  factory DrawingElement.fromJson(Map<String, dynamic> json) {
    final type = json['type'] as String? ?? 'rect';
    final name = json['name'] as String? ?? '';
    final layer = (json['layer'] as num?)?.toInt() ?? 0;
    final isWall = json['is_wall'] as bool? ?? false;

    double n(String k) => (json[k] as num?)?.toDouble() ?? 0.0;

    DrawingElement el;
    if (type == 'rect') {
      el = DrawingElement.rect(n('x'), n('y'), n('w'), n('h'),
          name: name, layer: layer, isWall: isWall);
    } else if (type == 'line') {
      el = DrawingElement.line(n('x1'), n('y1'), n('x2'), n('y2'),
          name: name, layer: layer, isWall: isWall);
    } else if (type == 'arc') {
      el = DrawingElement.arc(n('x'), n('y'), n('r'), n('startAngle'), n('sweepAngle'),
          name: name, layer: layer);
    } else {
      el = DrawingElement.rect(n('x'), n('y'), n('w'), n('h'),
          name: name, layer: layer, isWall: isWall);
    }
    if (json['color'] != null) {
      el.color = Color((json['color'] as num).toInt());
    }
    return el;
  }

  String toDxf() {
    if (type == 'rect') {
      final x0 = (x * 1000).toStringAsFixed(0);
      final y0 = (y * 1000).toStringAsFixed(0);
      return [
        '  0\nPOLYLINE\n  8\n${name.isNotEmpty ? "ROOM_$name" : "LAYER_$layer"}\n 66\n1\n 70\n1',
        '  0\nVERTEX\n  8\n${name.isNotEmpty ? "ROOM_$name" : "LAYER_$layer"}\n 10\n$x0\n 20\n$y0',
        '  0\nVERTEX\n  8\n${name.isNotEmpty ? "ROOM_$name" : "LAYER_$layer"}\n 10\n${(x + w) * 1000}\n 20\n$y0',
        '  0\nVERTEX\n  8\n${name.isNotEmpty ? "ROOM_$name" : "LAYER_$layer"}\n 10\n${(x + w) * 1000}\n 20\n${(y + h) * 1000}',
        '  0\nVERTEX\n  8\n${name.isNotEmpty ? "ROOM_$name" : "LAYER_$layer"}\n 10\n$x0\n 20\n${(y + h) * 1000}',
        '  0\nSEQEND',
      ].join('\n');
    }
    if (type == 'line') {
      return [
        '  0\nLINE\n  8\nWALLS',
        ' 10\n${(x1 * 1000).toStringAsFixed(0)}',
        ' 20\n${(y1 * 1000).toStringAsFixed(0)}',
        ' 11\n${(x2 * 1000).toStringAsFixed(0)}',
        ' 21\n${(y2 * 1000).toStringAsFixed(0)}',
      ].join('\n');
    }
    return '';
  }
}
