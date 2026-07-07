import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../config.dart';

/// 统一 API 响应
class ApiResponse<T> {
  final T? data;
  final String? error;
  final int statusCode;
  final bool isNetworkError;
  bool get isSuccess => statusCode >= 200 && statusCode < 300;
  ApiResponse({this.data, this.error, this.statusCode = 0, this.isNetworkError = false});
}

class ApiClient {
  String? _token;
  int _retryCount = 0;
  static const int _maxRetries = 3;
  static const Duration _retryBaseDelay = Duration(milliseconds: 500);

  static final ApiClient _instance = ApiClient._();
  factory ApiClient() => _instance;
  ApiClient._();

  /// 外部可设置的未授权回调，收到 401 时触发。
  void Function()? onUnauthorized;

  Future<void> loadToken() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('auth_token');
  }

  Future<void> saveToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('auth_token', token);
  }

  Future<void> clearToken() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
  }

  bool get isLoggedIn => _token != null;

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    if (_token != null) 'Authorization': 'Bearer $_token',
  };

  Uri _uri(String path) => Uri.parse('${AppConfig.apiBaseUrl}$path');

  // ── 核心请求（带重试） ──

  Future<http.Response> _send(Future<http.Response> Function() request) async {
    _retryCount = 0;
    while (true) {
      try {
        return await request().timeout(AppConfig.requestTimeout);
      } on SocketException catch (e) {
        if (_retryCount >= _maxRetries) {
          throw ApiException('网络连接失败', isNetwork: true, cause: e);
        }
        _retryCount++;
        await Future.delayed(_retryBaseDelay * (1 << (_retryCount - 1)));
      } on TimeoutException {
        if (_retryCount >= _maxRetries) {
          throw ApiException('请求超时', isNetwork: true);
        }
        _retryCount++;
        await Future.delayed(_retryBaseDelay * (1 << (_retryCount - 1)));
      } on http.ClientException catch (e) {
        if (_retryCount >= _maxRetries) {
          throw ApiException('网络错误: ${e.message}', isNetwork: true, cause: e);
        }
        _retryCount++;
        await Future.delayed(_retryBaseDelay * (1 << (_retryCount - 1)));
      }
    }
  }

  // ── HTTP 方法 ──

  Future<dynamic> get(String path) async {
    final res = await _send(() => http.get(_uri(path), headers: _headers));
    return _handleResponse(res);
  }

  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    final res = await _send(() => http.post(_uri(path), headers: _headers, body: jsonEncode(body)));
    return _handleResponse(res);
  }

  Future<dynamic> put(String path, Map<String, dynamic> body) async {
    final res = await _send(() => http.put(_uri(path), headers: _headers, body: jsonEncode(body)));
    return _handleResponse(res);
  }

  Future<dynamic> patch(String path, Map<String, dynamic> body) async {
    final res = await _send(() => http.patch(_uri(path), headers: _headers, body: jsonEncode(body)));
    return _handleResponse(res);
  }

  Future<dynamic> delete(String path) async {
    final res = await _send(() => http.delete(_uri(path), headers: _headers));
    return _handleResponse(res);
  }

  Future<dynamic> getList(String path) async {
    final res = await _send(() => http.get(_uri(path), headers: _headers));
    if (res.statusCode == 204) return [];
    if (res.statusCode == 401) {
      await _onUnauthorized();
      throw Exception('未授权，请重新登录');
    }
    final decoded = jsonDecode(res.body);
    if (res.statusCode >= 400) {
      throw Exception(decoded['detail'] ?? '请求失败 (${res.statusCode})');
    }
    if (decoded is List) return decoded;
    return decoded;
  }

  // ── 文件上传 ──

  Future<dynamic> uploadFile(String path, {required String filePath, String? projectId}) async {
    final uri = _uri(path);
    final request = http.MultipartRequest('POST', uri);
    if (_token != null) {
      request.headers['Authorization'] = 'Bearer $_token';
    }
    request.files.add(await http.MultipartFile.fromPath('file', filePath));
    if (projectId != null) {
      request.fields['project_id'] = projectId;
    }
    final streamed = await _send(() => request.send());
    final res = await http.Response.fromStream(streamed);
    return _handleResponse(res);
  }

  // ── 安全 API 调用（非抛异常，返回 ApiResponse） ──

  Future<ApiResponse<dynamic>> safeGet(String path) => _safeCall(() => get(path));
  Future<ApiResponse<dynamic>> safePost(String path, Map<String, dynamic> body) => _safeCall(() => post(path, body));
  Future<ApiResponse<dynamic>> safePut(String path, Map<String, dynamic> body) => _safeCall(() => put(path, body));
  Future<ApiResponse<dynamic>> safeDelete(String path) => _safeCall(() => delete(path));

  Future<ApiResponse<dynamic>> _safeCall(Future<dynamic> Function() call) async {
    try {
      final data = await call();
      return ApiResponse(data: data, statusCode: 200);
    } on ApiException catch (e) {
      return ApiResponse(error: e.message, statusCode: e.statusCode, isNetworkError: e.isNetwork);
    } on Exception catch (e) {
      return ApiResponse(error: e.toString(), statusCode: 500);
    }
  }

  // ── 响应处理 ──

  dynamic _handleResponse(http.Response res) {
    if (res.statusCode == 204) return {};
    if (res.statusCode == 401) {
      _onUnauthorized();
      throw ApiException('未授权，请重新登录', statusCode: 401);
    }
    final data = jsonDecode(res.body);
    if (res.statusCode >= 500) {
      throw ApiException(
        data['detail'] ?? '服务器错误 (${res.statusCode})',
        statusCode: res.statusCode,
      );
    }
    if (res.statusCode >= 400) {
      throw ApiException(
        data['detail'] ?? '请求失败 (${res.statusCode})',
        statusCode: res.statusCode,
      );
    }
    return data;
  }

  Future<void> _onUnauthorized() async {
    await clearToken();
    final cb = onUnauthorized;
    if (cb != null) cb();
  }
}

/// 统一异常类
class ApiException implements Exception {
  final String message;
  final int statusCode;
  final bool isNetwork;
  final Object? cause;
  ApiException(this.message, {this.statusCode = 0, this.isNetwork = false, this.cause});
  @override
  String toString() => 'ApiException($statusCode): $message';
}
