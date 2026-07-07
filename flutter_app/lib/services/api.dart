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

  // ── F18 厨卫水电 (MEP-KB) ──

  Future<dynamic> mepListPlans(String projectId) =>
      get('/mep-kb/plans?project_id=$projectId');
  Future<dynamic> mepCreatePlan(Map<String, dynamic> body) =>
      post('/mep-kb/plans', body);
  Future<dynamic> mepGetPlan(String planId) =>
      get('/mep-kb/plans/$planId');
  Future<dynamic> mepUpdatePlan(String planId, Map<String, dynamic> body) =>
      put('/mep-kb/plans/$planId', body);
  Future<dynamic> mepDeletePlan(String planId) =>
      delete('/mep-kb/plans/$planId');
  Future<dynamic> mepListPoints(String planId) =>
      get('/mep-kb/plans/$planId/points');
  Future<dynamic> mepListGas(String planId) =>
      get('/mep-kb/plans/$planId/gas');
  Future<dynamic> mepListCircuits(String planId) =>
      get('/mep-kb/plans/$planId/circuits');
  Future<dynamic> mepListEquipotential(String planId) =>
      get('/mep-kb/plans/$planId/equipotential');
  Future<dynamic> mepAddPoint(String planId, Map<String, dynamic> body) =>
      post('/mep-kb/plans/$planId/points', body);
  Future<dynamic> mepAddCircuit(String planId, Map<String, dynamic> body) =>
      post('/mep-kb/plans/$planId/circuits', body);

  // ── F21 硬装 ──

  Future<dynamic> hardDecoListSchemes(String projectId) =>
      get('/hard-decoration/schemes?project_id=$projectId');
  Future<dynamic> hardDecoCreateScheme(Map<String, dynamic> body) =>
      post('/hard-decoration/schemes', body);
  Future<dynamic> hardDecoGetScheme(String schemeId) =>
      get('/hard-decoration/schemes/$schemeId');
  Future<dynamic> hardDecoUpdateScheme(String schemeId, Map<String, dynamic> body) =>
      put('/hard-decoration/schemes/$schemeId', body);
  Future<dynamic> hardDecoDeleteScheme(String schemeId) =>
      delete('/hard-decoration/schemes/$schemeId');
  Future<dynamic> hardDecoListFloors(String schemeId) =>
      get('/hard-decoration/schemes/$schemeId/floor');
  Future<dynamic> hardDecoListWalls(String schemeId) =>
      get('/hard-decoration/schemes/$schemeId/wall');
  Future<dynamic> hardDecoListCeilings(String schemeId) =>
      get('/hard-decoration/schemes/$schemeId/ceiling');
  Future<dynamic> hardDecoListTileLayout(String schemeId) =>
      get('/hard-decoration/schemes/$schemeId/tile-layout');
  Future<dynamic> hardDecoAddFloor(String schemeId, Map<String, dynamic> body) =>
      post('/hard-decoration/schemes/$schemeId/floor', body);
  Future<dynamic> hardDecoAddWall(String schemeId, Map<String, dynamic> body) =>
      post('/hard-decoration/schemes/$schemeId/wall', body);

  // ── F23 门窗防水 ──

  Future<dynamic> doorWinListSpecs(String projectId) =>
      get('/door-window-waterproof/specs?project_id=$projectId');
  Future<dynamic> doorWinCreateSpec(Map<String, dynamic> body) =>
      post('/door-window-waterproof/specs', body);
  Future<dynamic> doorWinGetSpec(String specId) =>
      get('/door-window-waterproof/specs/$specId');
  Future<dynamic> doorWinUpdateSpec(String specId, Map<String, dynamic> body) =>
      put('/door-window-waterproof/specs/$specId', body);
  Future<dynamic> doorWinDeleteSpec(String specId) =>
      delete('/door-window-waterproof/specs/$specId');
  Future<dynamic> doorWinListWaterproof(String specId) =>
      get('/door-window-waterproof/specs/$specId/waterproof');
  Future<dynamic> doorWinValidate(String specId) =>
      post('/door-window-waterproof/specs/$specId/validate', {});
  Future<dynamic> doorWinAddWaterproof(String specId, Map<String, dynamic> body) =>
      post('/door-window-waterproof/specs/$specId/waterproof', body);

  // ── F26 家具品类库 ──

  Future<dynamic> furnitureListItems({int limit = 100, String? category}) =>
      get('/furniture-catalog/items?limit=$limit${category != null ? '&category=$category' : ''}');
  Future<dynamic> furnitureGetItem(String itemId) =>
      get('/furniture-catalog/items/$itemId');
  Future<dynamic> furnitureCreateItem(Map<String, dynamic> body) =>
      post('/furniture-catalog/items', body);
  Future<dynamic> furnitureUpdateItem(String itemId, Map<String, dynamic> body) =>
      put('/furniture-catalog/items/$itemId', body);
  Future<dynamic> furnitureDeleteItem(String itemId) =>
      delete('/furniture-catalog/items/$itemId');
  Future<dynamic> furnitureSearch(String keyword) =>
      post('/furniture-catalog/items/search', {'keyword': keyword});
  Future<dynamic> furnitureRecommend(String itemId) =>
      get('/furniture-catalog/items/$itemId/recommend');
  Future<dynamic> furnitureArPlace(String itemId, Map<String, dynamic> body) =>
      post('/furniture-catalog/items/$itemId/ar-place', body);

  // ── F31 智能家居 ──

  Future<dynamic> smartHomeListSchemes(String projectId) =>
      get('/smart-home/schemes?project_id=$projectId');
  Future<dynamic> smartHomeCreateScheme(Map<String, dynamic> body) =>
      post('/smart-home/schemes', body);
  Future<dynamic> smartHomeGetScheme(String schemeId) =>
      get('/smart-home/schemes/$schemeId');
  Future<dynamic> smartHomeUpdateScheme(String schemeId, Map<String, dynamic> body) =>
      put('/smart-home/schemes/$schemeId', body);
  Future<dynamic> smartHomeDeleteScheme(String schemeId) =>
      delete('/smart-home/schemes/$schemeId');
  Future<dynamic> smartHomeListDevices(String schemeId) =>
      get('/smart-home/schemes/$schemeId/devices');
  Future<dynamic> smartHomeAutoRecommend(String schemeId) =>
      post('/smart-home/schemes/$schemeId/auto-recommend', {});
  Future<dynamic> smartHomeWiring(String schemeId) =>
      get('/smart-home/schemes/$schemeId/wiring');
  Future<dynamic> smartHomeProtocol(String schemeId) =>
      get('/smart-home/schemes/$schemeId/protocol');
  Future<dynamic> smartHomeAddDevice(String schemeId, Map<String, dynamic> body) =>
      post('/smart-home/schemes/$schemeId/devices', body);

  // ── F32 场景编辑 ──

  Future<dynamic> sceneListScenes(String schemeId) =>
      get('/scene-automation/scenes?scheme_id=$schemeId');
  Future<dynamic> sceneCreateScene(Map<String, dynamic> body) =>
      post('/scene-automation/scenes', body);
  Future<dynamic> sceneGetScene(String sceneId) =>
      get('/scene-automation/scenes/$sceneId');
  Future<dynamic> sceneUpdateScene(String sceneId, Map<String, dynamic> body) =>
      put('/scene-automation/scenes/$sceneId', body);
  Future<dynamic> sceneDeleteScene(String sceneId) =>
      delete('/scene-automation/scenes/$sceneId');
  Future<dynamic> sceneSimulate(String sceneId) =>
      post('/scene-automation/scenes/$sceneId/simulate', {});
  Future<dynamic> sceneParseNl(String text) =>
      post('/scene-automation/scenes/parse-nl', {'text': text});
  Future<dynamic> sceneValidate(String sceneId) =>
      post('/scene-automation/scenes/$sceneId/validate', {});
  Future<dynamic> sceneListEcosystems() =>
      get('/scene-automation/ecosystems');

  // ── F33/F34 采购增强 ──

  Future<dynamic> procPriceComparisons({String? projectId}) =>
      get('/procurement-enhanced/price-comparisons${projectId != null ? '?project_id=$projectId' : ''}');
  Future<dynamic> procCreatePriceComparison(Map<String, dynamic> body) =>
      post('/procurement-enhanced/price-comparisons', body);
  Future<dynamic> procGetPriceComparison(String id) =>
      get('/procurement-enhanced/price-comparisons/$id');
  Future<dynamic> procEscrowPayments({String? projectId}) =>
      get('/procurement-enhanced/escrow-payments${projectId != null ? '?project_id=$projectId' : ''}');
  Future<dynamic> procCreateEscrowPayment(Map<String, dynamic> body) =>
      post('/procurement-enhanced/escrow-payments', body);
  Future<dynamic> procGetEscrowPayment(String id) =>
      get('/procurement-enhanced/escrow-payments/$id');
  Future<dynamic> procConfirmEscrow(String id) =>
      post('/procurement-enhanced/escrow-payments/$id/confirm', {});
  Future<dynamic> procLogistics({String? projectId}) =>
      get('/procurement-enhanced/logistics${projectId != null ? '?project_id=$projectId' : ''}');
  Future<dynamic> procCreateLogistics(Map<String, dynamic> body) =>
      post('/procurement-enhanced/logistics', body);
  Future<dynamic> procGetLogistics(String id) =>
      get('/procurement-enhanced/logistics/$id');
  Future<dynamic> procTrackLogistics(String id) =>
      get('/procurement-enhanced/logistics/$id/track');
  Future<dynamic> procSampleRequests({String? projectId}) =>
      get('/procurement-enhanced/sample-requests${projectId != null ? '?project_id=$projectId' : ''}');
  Future<dynamic> procCreateSampleRequest(Map<String, dynamic> body) =>
      post('/procurement-enhanced/sample-requests', body);
  Future<dynamic> procGetSampleRequest(String id) =>
      get('/procurement-enhanced/sample-requests/$id');
  Future<dynamic> procApproveSample(String id) =>
      post('/procurement-enhanced/sample-requests/$id/approve', {});

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
