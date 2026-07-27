/// 原生平台 WebSocket 连接。
import 'dart:async';
import 'dart:io';

typedef WsSocket = WebSocket;

Future<WebSocket> wsConnect(String url) => WebSocket.connect(url);

abstract class WsState {
  static const int open = WebSocket.open;
}

/// 监听 WebSocket 消息
StreamSubscription<dynamic> wsListen(
  WebSocket ws, {
  required void Function(dynamic data) onData,
  void Function(Object error)? onError,
  void Function()? onDone,
  bool cancelOnError = false,
}) {
  return ws.listen(
    onData,
    onError: onError,
    onDone: onDone,
    cancelOnError: cancelOnError,
  );
}

/// 发送数据
void wsSend(WebSocket ws, dynamic data) => ws.add(data);

/// 关闭连接
Future<void> wsClose(WebSocket ws) => ws.close();
