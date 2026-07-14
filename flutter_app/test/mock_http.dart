import 'dart:async';
import 'dart:io';

import 'package:http/http.dart' as http;

/// 基于 [HttpOverrides] 的 HTTP mock，用于拦截 ApiClient 中通过
/// `http.get`/`http.post` 等顶层函数发出的请求。
///
/// [responses] 的 key 是 URL path 子串，value 是对应的 [http.Response]。
/// 未匹配的请求返回默认响应 `http.Response('[]', 200)`。
///
/// 用法：
/// ```dart
/// HttpOverrides.global = MockHttpOverrides({
///   'budgets/project': jsonResponse({}, status: 404),
/// });
/// // ... 测试代码 ...
/// HttpOverrides.global = null; // 清除
/// ```
class MockHttpOverrides extends HttpOverrides {
  final Map<String, http.Response> responses;

  /// 记录最后一次请求的 URL（可用于验证 URL 构造是否正确）
  Uri? lastRequestUrl;

  MockHttpOverrides(this.responses);

  @override
  HttpClient createHttpClient(SecurityContext? context) {
    return _MockHttpClient(responses, this);
  }
}

class _MockHttpClient implements HttpClient {
  final Map<String, http.Response> responses;
  final MockHttpOverrides _overrides;

  _MockHttpClient(this.responses, this._overrides);

  @override
  Future<HttpClientRequest> openUrl(String method, Uri url) async {
    _overrides.lastRequestUrl = url;
    return _MockHttpClientRequest(url, responses);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) {}
}

class _MockHttpClientRequest implements HttpClientRequest {
  final Uri url;
  final Map<String, http.Response> responses;
  final _MockHttpHeaders _headers = _MockHttpHeaders();

  _MockHttpClientRequest(this.url, this.responses);

  @override
  HttpHeaders get headers => _headers;

  @override
  void write(Object? obj) {
    // 忽略请求体
  }

  @override
  Future<void> addStream(Stream<List<int>> stream) {
    // 消费请求体流但不处理
    return stream.drain<void>();
  }

  @override
  Future<HttpClientResponse> close() async {
    final path = url.path;
    for (final entry in responses.entries) {
      if (path.contains(entry.key)) {
        return _MockHttpClientResponse(entry.value);
      }
    }
    return _MockHttpClientResponse(http.Response('[]', 200));
  }

  @override
  dynamic noSuchMethod(Invocation invocation) {}
}

class _MockHttpHeaders implements HttpHeaders {
  final Map<String, List<String>> _headers = {};

  @override
  void set(String name, Object value, {bool preserveHeaderCase = false}) {
    _headers[name] = [value.toString()];
  }

  @override
  void forEach(void Function(String name, List<String> values) action) {
    _headers.forEach(action);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) {}
}

class _MockHttpClientResponse extends StreamView<List<int>>
    implements HttpClientResponse {
  final http.Response response;

  _MockHttpClientResponse(this.response)
      : super(Stream.value(response.bodyBytes));

  @override
  int get statusCode => response.statusCode;

  @override
  int get contentLength => response.bodyBytes.length;

  @override
  bool get isRedirect => false;

  @override
  List<RedirectInfo> get redirects => [];

  @override
  bool get persistentConnection => true;

  @override
  String get reasonPhrase => '';

  @override
  HttpClientResponseCompressionState get compressionState =>
      HttpClientResponseCompressionState.notCompressed;

  @override
  HttpHeaders get headers {
    final h = _MockHttpHeaders();
    response.headers.forEach((name, value) {
      h.set(name, value);
    });
    return h;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) {}
}
