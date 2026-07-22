import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/services.dart';

/// 轻量级 Markdown 渲染器
///
/// v1.1.29: 为 Agent 聊天气泡提供基础 Markdown 渲染能力。
/// 支持: **粗体**、*斜体*、`行内代码`、代码块、无序/有序列表、链接、标题。
/// 避免引入 flutter_markdown 以保持鸿蒙兼容性和包体积。

class MarkdownRenderer extends StatelessWidget {
  final String text;
  final TextStyle baseStyle;
  final Color codeBgColor;
  final Color linkColor;

  const MarkdownRenderer({
    super.key,
    required this.text,
    this.baseStyle = const TextStyle(fontSize: 14, height: 1.5),
    this.codeBgColor = const Color(0xFF2D2D2D),
    this.linkColor = const Color(0xFF6A9BC9),
  });

  @override
  Widget build(BuildContext context) {
    return RichText(
      text: _buildTextSpan(text, baseStyle),
    );
  }

  TextSpan _buildTextSpan(String source, TextStyle style) {
    // 代码块优先处理（跨行）
    if (source.contains('```')) {
      return _parseCodeBlocks(source, style);
    }

    final spans = <InlineSpan>[];
    final lines = source.split('\n');
    for (int i = 0; i < lines.length; i++) {
      if (i > 0) spans.add(const TextSpan(text: '\n'));

      final line = lines[i];
      // 无序列表
      if (RegExp(r'^\s*[-*+]\s').hasMatch(line)) {
        spans.add(_parseLineWithPrefix(line, '• ', style));
      }
      // 有序列表
      else if (RegExp(r'^\s*\d+[.)]\s').hasMatch(line)) {
        final match = RegExp(r'^(\s*\d+[.)]\s)').firstMatch(line)!;
        final prefix = match.group(0)!;
        spans.add(_parseLineWithPrefix(line, prefix, style));
      }
      // 标题
      else if (line.startsWith('### ')) {
        spans.add(_parseLine(line.substring(4), style.copyWith(
          fontSize: (style.fontSize ?? 14) + 2,
          fontWeight: FontWeight.w700,
        )));
      } else if (line.startsWith('## ')) {
        spans.add(_parseLine(line.substring(3), style.copyWith(
          fontSize: (style.fontSize ?? 14) + 4,
          fontWeight: FontWeight.w700,
        )));
      } else if (line.startsWith('# ')) {
        spans.add(_parseLine(line.substring(2), style.copyWith(
          fontSize: (style.fontSize ?? 14) + 6,
          fontWeight: FontWeight.w800,
        )));
      }
      // 普通文本行
      else {
        spans.add(_parseLine(line, style));
      }
    }
    return TextSpan(children: spans);
  }

  /// 解析带前缀的行（列表项）
  TextSpan _parseLineWithPrefix(String line, String prefix, TextStyle style) {
    final content = line.substring(line.indexOf(prefix) + prefix.length);
    return TextSpan(children: [
      TextSpan(text: prefix, style: style.copyWith(fontWeight: FontWeight.w600)),
      _parseInline(content, style),
    ]);
  }

  /// 解析单行内联格式
  TextSpan _parseLine(String line, TextStyle style) {
    if (line.isEmpty) return const TextSpan(text: '');
    return _parseInline(line, style);
  }

  /// 解析内联格式: **bold**, *italic*, `code`, [link](url)
  TextSpan _parseInline(String input, TextStyle style) {
    final children = <InlineSpan>[];
    int pos = 0;

    while (pos < input.length) {
      // 检查行内代码
      final codeMatch = _matchAt(input, pos, '`');
      if (codeMatch != null && codeMatch > pos) {
        final endTick = input.indexOf('`', codeMatch);
        if (endTick > codeMatch) {
          if (codeMatch > pos) {
            children.add(TextSpan(
              text: input.substring(pos, codeMatch),
              style: style,
            ));
          }
          children.add(WidgetSpan(
            alignment: PlaceholderAlignment.middle,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
              decoration: BoxDecoration(
                color: codeBgColor,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                input.substring(codeMatch + 1, endTick),
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: (style.fontSize ?? 14) - 1,
                  color: const Color(0xFFE6DB74),
                ),
              ),
            ),
          ));
          pos = endTick + 1;
          continue;
        }
      }

      // 检查粗体
      final boldMatch = _matchAt(input, pos, '**');
      if (boldMatch != null && boldMatch > pos) {
        final endBold = input.indexOf('**', boldMatch);
        if (endBold > boldMatch) {
          if (boldMatch > pos) {
            children.add(TextSpan(
              text: input.substring(pos, boldMatch),
              style: style,
            ));
          }
          children.add(TextSpan(
            text: input.substring(boldMatch + 2, endBold),
            style: style.copyWith(fontWeight: FontWeight.w700),
          ));
          pos = endBold + 2;
          continue;
        }
      }

      // 检查斜体
      final italicMatch = _matchAt(input, pos, '*');
      if (italicMatch != null && italicMatch > pos &&
          input.substring(italicMatch, italicMatch + 2) != '**') {
        final endItalic = input.indexOf('*', italicMatch);
        if (endItalic > italicMatch) {
          if (italicMatch > pos) {
            children.add(TextSpan(
              text: input.substring(pos, italicMatch),
              style: style,
            ));
          }
          children.add(TextSpan(
            text: input.substring(italicMatch + 1, endItalic),
            style: style.copyWith(fontStyle: FontStyle.italic),
          ));
          pos = endItalic + 1;
          continue;
        }
      }

      // 检查链接 [text](url)
      final linkMatch = _matchAt(input, pos, '[');
      if (linkMatch != null && linkMatch > pos) {
        final closeBracket = input.indexOf(']', linkMatch);
        if (closeBracket > linkMatch) {
          final openParen = closeBracket + 1 < input.length
              ? input[closeBracket + 1]
              : null;
          if (openParen == '(') {
            final closeParen = input.indexOf(')', closeBracket + 2);
            if (closeParen > closeBracket + 2) {
              if (linkMatch > pos) {
                children.add(TextSpan(
                  text: input.substring(pos, linkMatch),
                  style: style,
                ));
              }
              final linkText = input.substring(linkMatch + 1, closeBracket);
              final url = input.substring(closeBracket + 2, closeParen);
              children.add(TextSpan(
                text: linkText,
                style: style.copyWith(
                  color: linkColor,
                  decoration: TextDecoration.underline,
                ),
                recognizer: TapGestureRecognizer()
                  ..onTap = () => _openUrl(url),
              ));
              pos = closeParen + 1;
              continue;
            }
          }
        }
      }

      // 未匹配特殊格式，普通文本
      int nextSpecial = input.length;
      for (final char in ['`', '*', '[']) {
        final idx = input.indexOf(char, pos + 1);
        if (idx > pos && idx < nextSpecial) nextSpecial = idx;
      }
      children.add(TextSpan(
        text: input.substring(pos, nextSpecial),
        style: style,
      ));
      pos = nextSpecial;
    }

    if (children.isEmpty) {
      return TextSpan(text: input, style: style);
    }
    return TextSpan(children: children);
  }

  /// 解析代码块
  TextSpan _parseCodeBlocks(String source, TextStyle style) {
    final spans = <InlineSpan>[];
    int pos = 0;

    while (true) {
      final start = source.indexOf('```', pos);
      if (start == -1) {
        if (pos < source.length) {
          spans.add(_buildTextSpan(source.substring(pos), style));
        }
        break;
      }

      // 代码块之前的文本
      if (start > pos) {
        spans.add(_buildTextSpan(source.substring(pos, start), style));
      }

      // 跳过语言标识（如 ```python）
      final langEnd = source.indexOf('\n', start + 3);
      final codeStart = langEnd != -1 && langEnd < source.length ? langEnd + 1 : start + 3;

      final end = source.indexOf('```', codeStart);
      if (end == -1) {
        spans.add(TextSpan(text: source.substring(start), style: style));
        break;
      }

      // 渲染代码块
      final code = source.substring(codeStart, end);
      spans.add(WidgetSpan(
        alignment: PlaceholderAlignment.middle,
        child: Container(
          width: double.infinity,
          margin: const EdgeInsets.symmetric(vertical: 6),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: codeBgColor,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: const Color(0xFF444444),
              width: 0.5,
            ),
          ),
          child: SelectableText(
            code.trimRight(),
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: (style.fontSize ?? 14) - 1,
              color: const Color(0xFFE6DB74),
              height: 1.4,
            ),
          ),
        ),
      ));
      pos = end + 3;
    }

    if (spans.isEmpty) {
      return TextSpan(text: source, style: style);
    }
    return TextSpan(children: spans);
  }

  /// 查找字符位置，跳过前导空格
  int? _matchAt(String input, int pos, String char) {
    for (int i = pos; i < input.length; i++) {
      if (input[i] != ' ') {
        if (input.substring(i).startsWith(char)) return i;
        return null;
      }
    }
    return null;
  }

  void _openUrl(String url) {
    Clipboard.setData(ClipboardData(text: url));
  }
}
