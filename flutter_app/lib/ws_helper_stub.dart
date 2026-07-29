/// Web 平台 WebSocket wrapper。
/// dart:io WebSocket 在 Web 不可用，用 dart:html 替代。
// ignore_for_file: deprecated_member_use, avoid_web_libraries_in_flutter
// TODO(web-migration): 迁移到 package:web + dart:js_interop（独立任务）
library;
import 'dart:async';
import 'dart:html' as html;

typedef WsSocket = html.WebSocket;

Future<html.WebSocket> wsConnect(String url) {
  final ws = html.WebSocket(url);
  final completer = Completer<html.WebSocket>();
  ws.onOpen.first.then((_) => completer.complete(ws));
  ws.onError.first.then((_) => completer.completeError('WebSocket connection failed'));
  return completer.future;
}

abstract class WsState {
  static const int open = html.WebSocket.OPEN;
}

/// 监听 WebSocket 消息
StreamSubscription<dynamic> wsListen(
  html.WebSocket ws, {
  required void Function(dynamic data) onData,
  void Function(Object error)? onError,
  void Function()? onDone,
  bool cancelOnError = false,
}) {
  final sub = ws.onMessage.listen(
    (html.MessageEvent event) => onData(event.data),
  );
  if (onError != null) {
    ws.onError.listen((_) => onError('WebSocket error'));
  }
  if (onDone != null) {
    ws.onClose.listen((_) => onDone());
  }
  return sub;
}

/// 发送数据
void wsSend(html.WebSocket ws, dynamic data) => ws.send(data.toString());

/// 关闭连接
Future<void> wsClose(html.WebSocket ws) async => ws.close();
