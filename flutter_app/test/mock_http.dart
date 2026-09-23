import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

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

  /// 记录最后一次请求的 HTTP 方法（GET/POST/PATCH...）
  String? lastRequestMethod;

  /// 记录最后一次请求体（UTF-8 解码；无请求体时为 null）
  String? lastRequestBody;

  /// 全部请求记录（按发出顺序），用于断言「某次」请求的 URL 与请求体
  final List<MockRequestRecord> requests = [];

  MockHttpOverrides(this.responses);

  /// 最后一次请求体的 JSON 解析结果（非 JSON/空体时为 null）
  Map<String, dynamic>? get lastRequestJson =>
      _parseJsonBody(lastRequestBody);

  /// 指定方法的首次请求记录（未找到返回 null）
  MockRequestRecord? requestByMethod(String method) {
    for (final record in requests) {
      if (record.method == method) return record;
    }
    return null;
  }

  @override
  HttpClient createHttpClient(SecurityContext? context) {
    return _MockHttpClient(responses, this);
  }
}

/// 单次请求记录（method + path + body）——供契约断言使用
class MockRequestRecord {
  final String method;
  final String path;
  String? body;

  MockRequestRecord(this.method, this.path, [this.body]);

  /// 请求体的 JSON 解析结果（非 JSON/空体时为 null）
  Map<String, dynamic>? get json => _parseJsonBody(body);
}

Map<String, dynamic>? _parseJsonBody(String? body) {
  if (body == null || body.isEmpty) return null;
  try {
    final decoded = jsonDecode(body);
    return decoded is Map<String, dynamic> ? decoded : null;
  } catch (_) {
    return null;
  }
}

class _MockHttpClient implements HttpClient {
  final Map<String, http.Response> responses;
  final MockHttpOverrides _overrides;

  _MockHttpClient(this.responses, this._overrides);

  @override
  Future<HttpClientRequest> openUrl(String method, Uri url) async {
    final record = MockRequestRecord(method, url.path);
    _overrides.requests.add(record);
    _overrides.lastRequestUrl = url;
    _overrides.lastRequestMethod = method;
    _overrides.lastRequestBody = null;
    return _MockHttpClientRequest(url, responses, _overrides, record);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) {}
}

class _MockHttpClientRequest implements HttpClientRequest {
  final Uri url;
  final Map<String, http.Response> responses;
  final MockHttpOverrides _overrides;
  final MockRequestRecord _record;
  final BytesBuilder _body = BytesBuilder();
  final _MockHttpHeaders _headers = _MockHttpHeaders();

  _MockHttpClientRequest(this.url, this.responses, this._overrides, this._record);

  @override
  HttpHeaders get headers => _headers;

  @override
  void write(Object? obj) {
    if (obj != null) _body.add(utf8.encode(obj.toString()));
  }

  @override
  Future<void> addStream(Stream<List<int>> stream) async {
    // 收集请求体（供契约断言），不发送真实请求
    await for (final chunk in stream) {
      _body.add(chunk);
    }
  }

  @override
  Future<HttpClientResponse> close() async {
    final bytes = _body.toBytes();
    final body = bytes.isEmpty ? null : utf8.decode(bytes);
    _overrides.lastRequestBody = body;
    _record.body = body;
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
