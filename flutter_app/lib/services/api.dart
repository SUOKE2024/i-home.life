import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../config.dart';
import 'offline_cache_service.dart';

/// 统一 API 结果（Result 模式）
///
/// 所有 API 方法返回 [Result] 而非抛异常，调用方通过 [isSuccess] 判断
/// 成功与否，避免 try-catch 散落各处。
class Result<T> {
  final T? data;
  final String? error;
  final int statusCode;
  final bool isNetworkError;

  bool get isSuccess => statusCode >= 200 && statusCode < 300;

  Result.success(this.data, {this.statusCode = 200})
      : error = null,
        isNetworkError = false;

  Result.failure(this.error, {this.statusCode = 0, this.isNetworkError = false})
      : data = null;
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
    _token = prefs.getString('paseto_token');
  }

  Future<void> saveToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('paseto_token', token);
  }

  Future<void> clearToken() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('paseto_token');
  }

  bool get isLoggedIn => _token != null;
  String? get token => _token;

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    if (_token != null) 'Authorization': 'Bearer $_token',
  };

  Uri _uri(String path) => Uri.parse('${AppConfig.apiBaseUrl}$path');

  // ── 核心请求（带重试） ──

  Future<T> _send<T>(Future<T> Function() request) async {
    _retryCount = 0;
    while (true) {
      try {
        return await request().timeout(AppConfig.requestTimeout);
      } on SocketException catch (e) {
        // 连接被拒绝不重试（后端未启动或端口未开放）
        if (e.message.contains('Connection refused') || e.osError?.errorCode == 61) {
          throw ApiException('无法连接到服务器', isNetwork: true, cause: e);
        }
        if (_retryCount >= _maxRetries) {
          throw ApiException('网络连接失败: ${e.message}', isNetwork: true, cause: e);
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

  // ── HTTP 方法（统一返回 Result） ──

  Future<Result<dynamic>> get(String path) async {
    try {
      final res = await _send(() => http.get(_uri(path), headers: _headers));
      return _handleResponse(res);
    } on ApiException catch (e) {
      return Result.failure(e.message, statusCode: e.statusCode, isNetworkError: e.isNetwork);
    }
  }

  Future<Result<dynamic>> post(String path, Map<String, dynamic> body) async {
    try {
      final res = await _send(() => http.post(_uri(path), headers: _headers, body: jsonEncode(body)));
      return _handleResponse(res);
    } on ApiException catch (e) {
      return Result.failure(e.message, statusCode: e.statusCode, isNetworkError: e.isNetwork);
    }
  }

  Future<Result<dynamic>> put(String path, Map<String, dynamic> body) async {
    try {
      final res = await _send(() => http.put(_uri(path), headers: _headers, body: jsonEncode(body)));
      return _handleResponse(res);
    } on ApiException catch (e) {
      return Result.failure(e.message, statusCode: e.statusCode, isNetworkError: e.isNetwork);
    }
  }

  Future<Result<dynamic>> patch(String path, Map<String, dynamic> body) async {
    try {
      final res = await _send(() => http.patch(_uri(path), headers: _headers, body: jsonEncode(body)));
      return _handleResponse(res);
    } on ApiException catch (e) {
      return Result.failure(e.message, statusCode: e.statusCode, isNetworkError: e.isNetwork);
    }
  }

  Future<Result<dynamic>> delete(String path) async {
    try {
      final res = await _send(() => http.delete(_uri(path), headers: _headers));
      return _handleResponse(res);
    } on ApiException catch (e) {
      return Result.failure(e.message, statusCode: e.statusCode, isNetworkError: e.isNetwork);
    }
  }

  Future<Result<dynamic>> getList(String path, {bool enableCache = true}) async {
    try {
      final res = await _send(() => http.get(_uri(path), headers: _headers));
      if (res.statusCode == 204) return Result.success([]);
      if (res.statusCode == 401) {
        await _onUnauthorized();
        return Result.failure('未授权，请重新登录', statusCode: 401);
      }
      final decoded = jsonDecode(res.body);
      if (res.statusCode >= 400) {
        return Result.failure(
          decoded['detail'] ?? '请求失败 (${res.statusCode})',
          statusCode: res.statusCode,
        );
      }
      // 请求成功，更新离线缓存
      if (enableCache) {
        await OfflineCacheService().cacheData('list:$path', decoded);
      }
      return Result.success(decoded);
    } on ApiException catch (e) {
      // 网络超时/断连时降级到缓存，保证离线可浏览
      if (enableCache && e.isNetwork) {
        final cached = await OfflineCacheService().getCachedData('list:$path');
        if (cached != null) return Result.success(cached);
      }
      return Result.failure(e.message, statusCode: e.statusCode, isNetworkError: e.isNetwork);
    }
  }

  // ── 文件上传 ──

  Future<Result<dynamic>> uploadFile(String path, {required String filePath, String? projectId}) async {
    try {
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
    } on ApiException catch (e) {
      return Result.failure(e.message, statusCode: e.statusCode, isNetworkError: e.isNetwork);
    }
  }

  // ── F18 厨卫水电 (MEP-KB) ──

  Future<Result<dynamic>> mepListPlans(String projectId) =>
      get('/mep-kb/plans/project/$projectId');
  Future<Result<dynamic>> mepCreatePlan(Map<String, dynamic> body) =>
      post('/mep-kb/plans', body);
  Future<Result<dynamic>> mepGetPlan(String planId) =>
      get('/mep-kb/plans/$planId');
  Future<Result<dynamic>> mepUpdatePlan(String planId, Map<String, dynamic> body) =>
      put('/mep-kb/plans/$planId', body);
  Future<Result<dynamic>> mepDeletePlan(String planId) =>
      delete('/mep-kb/plans/$planId');
  Future<Result<dynamic>> mepListPoints(String planId) =>
      get('/mep-kb/plans/$planId/points');
  Future<Result<dynamic>> mepListGas(String planId) =>
      get('/mep-kb/plans/$planId/gas');
  Future<Result<dynamic>> mepListCircuits(String planId) =>
      get('/mep-kb/plans/$planId/circuits');
  Future<Result<dynamic>> mepListEquipotential(String planId) =>
      get('/mep-kb/plans/$planId/equipotential');
  Future<Result<dynamic>> mepAddPoint(String planId, Map<String, dynamic> body) =>
      post('/mep-kb/plans/$planId/points', body);
  Future<Result<dynamic>> mepAddCircuit(String planId, Map<String, dynamic> body) =>
      post('/mep-kb/plans/$planId/circuits', body);
  Future<Result<dynamic>> mepAutoGenerate(String planId) =>
      post('/mep-kb/plans/$planId/auto-generate', {});
  Future<Result<dynamic>> mepDeletePoint(String pointId) =>
      delete('/mep-kb/points/$pointId');

  // ── F17 卫浴设计 ──

  Future<Result<dynamic>> bathroomListDesigns(String projectId) =>
      get('/bathroom/designs/project/$projectId');
  Future<Result<dynamic>> bathroomCreateDesign(Map<String, dynamic> body) =>
      post('/bathroom/designs', body);
  Future<Result<dynamic>> bathroomGetDesign(String designId) =>
      get('/bathroom/designs/$designId');
  Future<Result<dynamic>> bathroomDeleteDesign(String designId) =>
      delete('/bathroom/designs/$designId');
  Future<Result<dynamic>> bathroomAutoLayout(String designId) =>
      post('/bathroom/designs/$designId/auto-layout', {});
  Future<Result<dynamic>> bathroomDrain(String designId) =>
      get('/bathroom/designs/$designId/drain');
  Future<Result<dynamic>> bathroomWaterproof(String designId) =>
      get('/bathroom/designs/$designId/waterproof');
  Future<Result<dynamic>> bathroomVentilation(String designId) =>
      get('/bathroom/designs/$designId/ventilation');
  Future<Result<dynamic>> bathroomListFixtures(String designId) =>
      get('/bathroom/designs/$designId/fixtures');
  Future<Result<dynamic>> bathroomAddFixture(String designId, Map<String, dynamic> body) =>
      post('/bathroom/designs/$designId/fixtures', body);
  Future<Result<dynamic>> bathroomDeleteFixture(String fixtureId) =>
      delete('/bathroom/fixtures/$fixtureId');

  // ── F21 硬装 ──

  Future<Result<dynamic>> hardDecoListSchemes(String projectId) =>
      get('/hard-decoration/schemes/project/$projectId');
  Future<Result<dynamic>> hardDecoCreateScheme(Map<String, dynamic> body) =>
      post('/hard-decoration/schemes', body);
  Future<Result<dynamic>> hardDecoGetScheme(String schemeId) =>
      get('/hard-decoration/schemes/$schemeId');
  Future<Result<dynamic>> hardDecoDeleteScheme(String schemeId) =>
      delete('/hard-decoration/schemes/$schemeId');
  Future<Result<dynamic>> hardDecoListFloors(String schemeId) =>
      get('/hard-decoration/schemes/$schemeId/floors');
  Future<Result<dynamic>> hardDecoListWalls(String schemeId) =>
      get('/hard-decoration/schemes/$schemeId/walls');
  Future<Result<dynamic>> hardDecoListCeilings(String schemeId) =>
      get('/hard-decoration/schemes/$schemeId/ceilings');
  Future<Result<dynamic>> hardDecoTileLayout(String schemeId, Map<String, dynamic> body) =>
      post('/hard-decoration/schemes/$schemeId/tile-layout', body);
  Future<Result<dynamic>> hardDecoAddFloor(String schemeId, Map<String, dynamic> body) =>
      post('/hard-decoration/schemes/$schemeId/floors', body);
  Future<Result<dynamic>> hardDecoAddWall(String schemeId, Map<String, dynamic> body) =>
      post('/hard-decoration/schemes/$schemeId/walls', body);
  Future<Result<dynamic>> hardDecoAddCeiling(String schemeId, Map<String, dynamic> body) =>
      post('/hard-decoration/schemes/$schemeId/ceilings', body);
  Future<Result<dynamic>> hardDecoPaintUsage(String schemeId, Map<String, dynamic> body) =>
      post('/hard-decoration/schemes/$schemeId/paint-usage', body);
  Future<Result<dynamic>> hardDecoCeilingDesign(String schemeId, Map<String, dynamic> body) =>
      post('/hard-decoration/schemes/$schemeId/ceiling-design', body);
  Future<Result<dynamic>> hardDecoGetBudget(String schemeId) =>
      get('/hard-decoration/schemes/$schemeId/budget');

  // ── F23 门窗防水 ──

  Future<Result<dynamic>> doorWinListSpecs(String projectId) =>
      get('/door-window-waterproof/door-windows/project/$projectId');
  Future<Result<dynamic>> doorWinCreateSpec(Map<String, dynamic> body) =>
      post('/door-window-waterproof/door-windows', body);
  Future<Result<dynamic>> doorWinGetSpec(String specId) =>
      get('/door-window-waterproof/door-windows/$specId');
  Future<Result<dynamic>> doorWinDeleteSpec(String specId) =>
      delete('/door-window-waterproof/door-windows/$specId');
  Future<Result<dynamic>> doorWinListWaterproof(String projectId) =>
      get('/door-window-waterproof/waterproof/project/$projectId');
  Future<Result<dynamic>> doorWinGetWaterproof(String planId) =>
      get('/door-window-waterproof/waterproof/$planId');
  Future<Result<dynamic>> doorWinValidateWaterproof(String planId) =>
      get('/door-window-waterproof/waterproof/$planId/validation');
  Future<Result<dynamic>> doorWinAddWaterproof(Map<String, dynamic> body) =>
      post('/door-window-waterproof/waterproof', body);
  Future<Result<dynamic>> doorWinRecommend(String projectId, Map<String, dynamic> body) =>
      post('/door-window-waterproof/door-windows/recommend', body..['project_id'] = projectId);
  Future<Result<dynamic>> doorWinComputeWaterproofArea(String planId, Map<String, dynamic> body) =>
      post('/door-window-waterproof/waterproof/$planId/compute-area', body);
  Future<Result<dynamic>> doorWinDeleteWaterproof(String planId) =>
      delete('/door-window-waterproof/waterproof/$planId');

  // ── F26 家具品类库 ──

  Future<Result<dynamic>> furnitureListItems({int limit = 100, String? category}) =>
      get('/furniture-catalog/items?limit=$limit${category != null ? '&category=$category' : ''}');
  Future<Result<dynamic>> furnitureGetItem(String itemId) =>
      get('/furniture-catalog/items/$itemId');
  Future<Result<dynamic>> furnitureCreateItem(Map<String, dynamic> body) =>
      post('/furniture-catalog/items', body);
  Future<Result<dynamic>> furnitureUpdateItem(String itemId, Map<String, dynamic> body) =>
      put('/furniture-catalog/items/$itemId', body);
  Future<Result<dynamic>> furnitureDeleteItem(String itemId) =>
      delete('/furniture-catalog/items/$itemId');
  Future<Result<dynamic>> furnitureSearch(String keyword) =>
      post('/furniture-catalog/items/search', {'keyword': keyword});
  Future<Result<dynamic>> furnitureRecommend(String itemId) =>
      get('/furniture-catalog/items/$itemId/recommend');
  Future<Result<dynamic>> furnitureArPlace(String itemId, Map<String, dynamic> body) =>
      post('/furniture-catalog/items/$itemId/ar-place', body);
  Future<Result<dynamic>> furnitureGetSimilar(String itemId) =>
      get('/furniture-catalog/items/$itemId/similar');

  // ── F19/F20 电器品类与点位 ──

  // 电器品类
  Future<Result<dynamic>> applianceListCategories() =>
      get('/appliances/categories');
  Future<Result<dynamic>> applianceCreateCategory(Map<String, dynamic> body) =>
      post('/appliances/categories', body);
  Future<Result<dynamic>> applianceGetCategory(String catId) =>
      get('/appliances/categories/$catId');
  Future<Result<dynamic>> applianceUpdateCategory(String catId, Map<String, dynamic> body) =>
      put('/appliances/categories/$catId', body);
  Future<Result<dynamic>> applianceDeleteCategory(String catId) =>
      delete('/appliances/categories/$catId');

  // 电器实例
  Future<Result<dynamic>> applianceCreate(Map<String, dynamic> body) =>
      post('/appliances', body);
  Future<Result<dynamic>> applianceSearch({
    String? categoryId,
    String? subcategory,
    String? brand,
    String? energyLabel,
    String? keyword,
    double? priceMin,
    double? priceMax,
    String sortBy = 'price',
    String sortOrder = 'asc',
  }) {
    final params = <String>[];
    if (categoryId != null) params.add('category_id=$categoryId');
    if (subcategory != null) params.add('subcategory=$subcategory');
    if (brand != null) params.add('brand=$brand');
    if (energyLabel != null) params.add('energy_label=$energyLabel');
    if (keyword != null) {
      params.add('keyword=${Uri.encodeQueryComponent(keyword)}');
    }
    if (priceMin != null) params.add('price_min=$priceMin');
    if (priceMax != null) params.add('price_max=$priceMax');
    params.add('sort_by=$sortBy');
    params.add('sort_order=$sortOrder');
    return get('/appliances/search?${params.join('&')}');
  }

  Future<Result<dynamic>> applianceGet(String applianceId) =>
      get('/appliances/$applianceId');
  Future<Result<dynamic>> applianceUpdate(String applianceId, Map<String, dynamic> body) =>
      put('/appliances/$applianceId', body);
  Future<Result<dynamic>> applianceDelete(String applianceId) =>
      delete('/appliances/$applianceId');

  // 电器点位
  Future<Result<dynamic>> applianceListPoints(String projectId) =>
      get('/appliances/projects/$projectId/points');
  Future<Result<dynamic>> applianceCreatePoint(Map<String, dynamic> body) =>
      post('/appliances/points', body);
  Future<Result<dynamic>> applianceGetPoint(String pointId) =>
      get('/appliances/points/$pointId');
  Future<Result<dynamic>> applianceUpdatePoint(String pointId, Map<String, dynamic> body) =>
      put('/appliances/points/$pointId', body);
  Future<Result<dynamic>> applianceDeletePoint(String pointId) =>
      delete('/appliances/points/$pointId');

  // 负载计算
  Future<Result<dynamic>> applianceComputeLoadCalc(String projectId) =>
      post('/appliances/projects/$projectId/load-calc', {});
  Future<Result<dynamic>> applianceGetLoadCalcs(String projectId) =>
      get('/appliances/projects/$projectId/load-calcs');

  // 嵌入式匹配
  Future<Result<dynamic>> applianceCabinetMatch(Map<String, dynamic> body) =>
      post('/appliances/cabinet-match', body);

  // 预埋规划
  Future<Result<dynamic>> applianceGetEmbeddingPlan(String projectId) =>
      get('/appliances/projects/$projectId/embedding-plan');

  // 房间推荐
  Future<Result<dynamic>> applianceRecommendForRoom(String roomId) =>
      get('/appliances/rooms/$roomId/recommend');

  // ── F31 智能家居 ──

  Future<Result<dynamic>> smartHomeListSchemes(String projectId) =>
      get('/smart-home/schemes/project/$projectId');
  Future<Result<dynamic>> smartHomeCreateScheme(Map<String, dynamic> body) =>
      post('/smart-home/schemes', body);
  Future<Result<dynamic>> smartHomeGetScheme(String schemeId) =>
      get('/smart-home/schemes/$schemeId');
  Future<Result<dynamic>> smartHomeDeleteScheme(String schemeId) =>
      delete('/smart-home/schemes/$schemeId');
  Future<Result<dynamic>> smartHomeListDevices(String schemeId) =>
      get('/smart-home/schemes/$schemeId/devices');
  Future<Result<dynamic>> smartHomeAutoRecommend(String schemeId) =>
      post('/smart-home/schemes/$schemeId/auto-recommend', {});
  Future<Result<dynamic>> smartHomeWiring(String schemeId) =>
      get('/smart-home/schemes/$schemeId/wiring');
  Future<Result<dynamic>> smartHomeProtocol(String schemeId) =>
      get('/smart-home/schemes/$schemeId/protocol-advice');
  Future<Result<dynamic>> smartHomeAddDevice(String schemeId, Map<String, dynamic> body) =>
      post('/smart-home/schemes/$schemeId/devices', body);
  Future<Result<dynamic>> smartHomeGetPrice(String schemeId) =>
      get('/smart-home/schemes/$schemeId/price');
  Future<Result<dynamic>> smartHomeDeleteDevice(String deviceId) =>
      delete('/smart-home/devices/$deviceId');

  // ── F32 场景编辑 ──

  Future<Result<dynamic>> sceneListScenes(String projectId) =>
      get('/scene-automation/scenes/project/$projectId');
  Future<Result<dynamic>> sceneCreateScene(Map<String, dynamic> body) =>
      post('/scene-automation/scenes', body);
  Future<Result<dynamic>> sceneGetScene(String sceneId) =>
      get('/scene-automation/scenes/$sceneId');
  Future<Result<dynamic>> sceneUpdateScene(String sceneId, Map<String, dynamic> body) =>
      patch('/scene-automation/scenes/$sceneId', body);
  Future<Result<dynamic>> sceneDeleteScene(String sceneId) =>
      delete('/scene-automation/scenes/$sceneId');
  Future<Result<dynamic>> sceneSimulate(String sceneId) =>
      post('/scene-automation/scenes/$sceneId/simulate', {});
  Future<Result<dynamic>> sceneParseNl(String text) =>
      post('/scene-automation/scenes/parse', {'text': text});
  Future<Result<dynamic>> sceneValidate(String sceneId) =>
      post('/scene-automation/scenes/$sceneId/validate', {});
  Future<Result<dynamic>> sceneListEcosystems(String projectId) =>
      get('/scene-automation/ecosystems/project/$projectId');
  Future<Result<dynamic>> sceneRecommend(Map<String, dynamic> query) =>
      get('/scene-automation/scenes/recommend?${query.entries.map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value.toString())}').join('&')}');
  Future<Result<dynamic>> sceneSync(String sceneId) =>
      post('/scene-automation/scenes/$sceneId/sync', {});
  Future<Result<dynamic>> sceneCreateEcosystem(Map<String, dynamic> body) =>
      post('/scene-automation/ecosystems', body);
  Future<Result<dynamic>> sceneDeleteEcosystem(String ecosystemId) =>
      delete('/scene-automation/ecosystems/$ecosystemId');

  // ── F33/F34 采购增强 ──

  Future<Result<dynamic>> procPriceComparisons(String projectId) =>
      get('/procurement-enhanced/comparisons/project/$projectId');
  Future<Result<dynamic>> procCreatePriceComparison(Map<String, dynamic> body) =>
      post('/procurement-enhanced/comparisons', body);
  Future<Result<dynamic>> procGetPriceComparison(String id) =>
      get('/procurement-enhanced/comparisons/$id');
  Future<Result<dynamic>> procDeletePriceComparison(String id) =>
      delete('/procurement-enhanced/comparisons/$id');
  Future<Result<dynamic>> procEscrowPayments(String projectId) =>
      get('/procurement-enhanced/escrow/project/$projectId');
  Future<Result<dynamic>> procCreateEscrowPayment(Map<String, dynamic> body) =>
      post('/procurement-enhanced/escrow', body);
  Future<Result<dynamic>> procGetEscrowPayment(String id) =>
      get('/procurement-enhanced/escrow/$id');
  Future<Result<dynamic>> procConfirmEscrow(String id) =>
      post('/procurement-enhanced/escrow/$id/release', {});
  Future<Result<dynamic>> procEscrowPay(String id) =>
      post('/procurement-enhanced/escrow/$id/pay', {});
  Future<Result<dynamic>> procEscrowRefund(String id, Map<String, dynamic> body) =>
      post('/procurement-enhanced/escrow/$id/refund', body);
  Future<Result<dynamic>> procLogistics(String projectId) =>
      get('/procurement-enhanced/logistics/project/$projectId');
  Future<Result<dynamic>> procCreateLogistics(Map<String, dynamic> body) =>
      post('/procurement-enhanced/logistics', body);
  Future<Result<dynamic>> procGetLogistics(String id) =>
      get('/procurement-enhanced/logistics/$id');
  Future<Result<dynamic>> procSampleRequests(String projectId) =>
      get('/procurement-enhanced/samples/project/$projectId');
  Future<Result<dynamic>> procCreateSampleRequest(Map<String, dynamic> body) =>
      post('/procurement-enhanced/samples', body);
  Future<Result<dynamic>> procApproveSample(String id) =>
      patch('/procurement-enhanced/samples/$id', {'status': 'approved'});
  Future<Result<dynamic>> procUpdateSample(String id, Map<String, dynamic> body) =>
      patch('/procurement-enhanced/samples/$id', body);
  Future<Result<dynamic>> procAiMatchSuppliers(String bomItemId, {String? location}) =>
      post('/procurement-enhanced/ai-match', {
        'bom_item_id': bomItemId,
        if (location != null) 'location': location,
      });
  Future<Result<dynamic>> procGetOrderEscrow(String orderId) =>
      get('/procurement-enhanced/escrow/order/$orderId');
  Future<Result<dynamic>> procDisputeEscrow(String id, String reason) =>
      post('/procurement-enhanced/escrow/$id/dispute', {'reason': reason});
  Future<Result<dynamic>> procResolveEscrow(String id, String resolution) =>
      post('/procurement-enhanced/escrow/$id/resolve', {'resolution': resolution});
  Future<Result<dynamic>> procGetOrderLogistics(String orderId) =>
      get('/procurement-enhanced/logistics/order/$orderId');
  Future<Result<dynamic>> procUpdateLogistics(String id, Map<String, dynamic> body) =>
      patch('/procurement-enhanced/logistics/$id', body);

  // ── 用户 & 项目 ──

  Future<Result<dynamic>> getCurrentUser() => get('/auth/me');

  // L4 自适应学习：Agent 反馈
  Future<Result<dynamic>> submitAgentFeedback(Map<String, dynamic> data) =>
      post('/agents/feedback', data);

  // ── WebAuthn / FIDO2 / Passkey ──

  /// 注册：开始（需已登录）
  Future<Result<dynamic>> webauthnRegisterBegin({String? deviceName}) =>
      post('/auth/webauthn/register/begin', {
        if (deviceName != null) 'device_name': deviceName,
      });

  /// 注册：完成
  Future<Result<dynamic>> webauthnRegisterComplete(Map<String, dynamic> params) =>
      post('/auth/webauthn/register/complete', params);

  /// 登录：开始（获取挑战）
  Future<Result<dynamic>> webauthnLoginBegin({String? phone}) =>
      post('/auth/webauthn/login/begin', {
        if (phone != null) 'phone': phone,
      });

  /// 登录：完成（验证断言，返回 PASETO Token）
  Future<Result<dynamic>> webauthnLoginComplete(Map<String, dynamic> credential) async {
    final result = await post('/auth/webauthn/login/complete', {
      'credential': credential,
    });
    if (result.isSuccess && result.data != null) {
      final data = result.data as Map<String, dynamic>;
      if (data['access_token'] != null) {
        await saveToken(data['access_token'] as String);
      }
    }
    return result;
  }

  /// 列出当前用户的 Passkey
  Future<Result<dynamic>> listPasskeys() =>
      get('/auth/webauthn/credentials');

  /// 删除 Passkey
  Future<Result<dynamic>> deletePasskey(String credentialId) =>
      delete('/auth/webauthn/credentials/$credentialId');

  // ── 项目 ──

  Future<Result<dynamic>> getProjects() => get('/projects');
  Future<Result<dynamic>> getProject(String id) => get('/projects/$id');
  Future<Result<dynamic>> createProject(Map<String, dynamic> data) => post('/projects', data);

  // ── 业务操作 API ──

  /// 审批变更单
  Future<Result<dynamic>> approveChangeOrder(String changeId, String decision) {
    final action = decision == 'approve' ? 'approve' : 'cancel';
    return post('/change-orders/$changeId/$action', {});
  }

  /// 确认结算
  Future<Result<dynamic>> confirmSettlement(String projectId) =>
      post('/settlements/confirm/$projectId', {});

  /// 通过结算复核
  Future<Result<dynamic>> approveSettlementReview(String projectId) =>
      post('/settlements/approve-review/$projectId', {});

  /// 导出 BOM
  Future<Result<dynamic>> exportBOM(String projectId) =>
      get('/materials/bom/$projectId/export');

  // ── AI 图片生成 ──

  Future<Result<dynamic>> aiImageListJobs(String projectId) =>
      get('/ai-image/jobs/project/$projectId');
  Future<Result<dynamic>> aiImageCreateJob(Map<String, dynamic> body) =>
      post('/ai-image/jobs', body);
  Future<Result<dynamic>> aiImageGetJob(String jobId) =>
      get('/ai-image/jobs/$jobId');
  Future<Result<dynamic>> aiImageDeleteJob(String jobId) =>
      delete('/ai-image/jobs/$jobId');
  Future<Result<dynamic>> aiImageListPresets() =>
      get('/ai-image/presets');
  Future<Result<dynamic>> aiImageProcessJob(String jobId) =>
      post('/ai-image/jobs/$jobId/process', {});
  Future<Result<dynamic>> aiImageGetJobStatus(String jobId) =>
      get('/ai-image/jobs/$jobId/status');
  Future<Result<dynamic>> aiImageApplyPreset(
          String presetId, String projectId, String inputImageUrl,
          [Map<String, dynamic>? customizations, String? floorplanId]) =>
      post('/ai-image/jobs/apply-preset', {
        'preset_id': presetId,
        'project_id': projectId,
        if (floorplanId != null) 'floorplan_id': floorplanId,
        'input_image_url': inputImageUrl,
        'customizations': customizations ?? {},
      });
  Future<Result<dynamic>> aiImageCreatePreset(Map<String, dynamic> body) =>
      post('/ai-image/presets', body);
  Future<Result<dynamic>> aiImageGetPreset(String presetId) =>
      get('/ai-image/presets/$presetId');
  Future<Result<dynamic>> aiImageBatchJobs(Map<String, dynamic> body) =>
      post('/ai-image/jobs/batch', body);

  // ── VR 全景 ──

  Future<Result<dynamic>> vrListPanoramas(String projectId) =>
      get('/vr/panoramas/project/$projectId');
  Future<Result<dynamic>> vrCreatePanorama(Map<String, dynamic> body) =>
      post('/vr/panoramas', body);
  Future<Result<dynamic>> vrGetPanorama(String panoId) =>
      get('/vr/panoramas/$panoId');
  Future<Result<dynamic>> vrRenderPanorama(String panoId, Map<String, dynamic> body) =>
      post('/vr/panoramas/$panoId/render', body);
  Future<Result<dynamic>> vrDeletePanorama(String panoId) =>
      delete('/vr/panoramas/$panoId');
  Future<Result<dynamic>> vrListHotspots(String panoId) =>
      get('/vr/panoramas/$panoId/hotspots');
  Future<Result<dynamic>> vrAddHotspot(String panoId, Map<String, dynamic> body) =>
      post('/vr/panoramas/$panoId/hotspots', body);
  Future<Result<dynamic>> vrDeleteHotspot(String panoId, int hotspotIndex) =>
      delete('/vr/hotspots/$panoId/$hotspotIndex');
  Future<Result<dynamic>> vrListScenes(String projectId) =>
      get('/vr/scenes/project/$projectId');
  Future<Result<dynamic>> vrCreateScene(Map<String, dynamic> body) =>
      post('/vr/scenes', body);
  Future<Result<dynamic>> vrGetScene(String sceneId) =>
      get('/vr/scenes/$sceneId');
  Future<Result<dynamic>> vrUpdateScene(String sceneId, Map<String, dynamic> body) =>
      patch('/vr/scenes/$sceneId', body);
  Future<Result<dynamic>> vrDeleteScene(String sceneId) =>
      delete('/vr/scenes/$sceneId');

  // ── 积分系统 ──

  Future<Result<dynamic>> pointsGetAccount() =>
      get('/points/account');
  Future<Result<dynamic>> pointsListTransactions({int limit = 50, int offset = 0}) =>
      get('/points/transactions?limit=$limit&offset=$offset');
  Future<Result<dynamic>> pointsListRules() =>
      get('/points/rules');
  Future<Result<dynamic>> pointsListMallItems({String? category}) =>
      get('/points/mall${category != null ? '?category=$category' : ''}');
  Future<Result<dynamic>> pointsRedeem(String itemId) =>
      post('/points/redeem', {'item_id': itemId});
  Future<Result<dynamic>> pointsListRedemptions() =>
      get('/points/redemptions');
  Future<Result<dynamic>> pointsGetRanking({String category = 'overall'}) =>
      get('/points/ranking?category=$category');
  Future<Result<dynamic>> pointsEarn(Map<String, dynamic> body) =>
      post('/points/earn', body);
  Future<Result<dynamic>> pointsRecomputeRanking() =>
      post('/points/ranking/recompute', {});

  // ── 身份认证 ──

  /// 提交实名认证申请
  Future<Result<dynamic>> identitySubmit({
    required String realName,
    required String idCard,
    String? idCardFront,
    String? idCardBack,
    String? selfieWithId,
    Map<String, dynamic>? roleAttributes,
  }) =>
      post('/identity/submit', {
        'real_name': realName,
        'id_card': idCard,
        'id_card_front': ?idCardFront,
        'id_card_back': ?idCardBack,
        'selfie_with_id': ?selfieWithId,
        'role_attributes': ?roleAttributes,
      });

  /// 查询当前用户的认证状态
  Future<Result<dynamic>> identityGetStatus() => get('/identity/status');

  /// 管理员查看待审核列表
  Future<Result<dynamic>> identityListPending() => get('/identity/pending');

  /// 管理员审核通过/拒绝认证
  Future<Result<dynamic>> identityReview(
    String verificationId, {
    required String reviewStatus,
    String? reviewNote,
  }) =>
      post('/identity/$verificationId/review', {
        'status': reviewStatus,
        'review_note': ?reviewNote,
      });

  // ── F16 厨房设计 ──

  Future<Result<dynamic>> kitchenCreateDesign(Map<String, dynamic> body) =>
      post('/kitchen/designs', body);
  Future<Result<dynamic>> kitchenListDesigns(String projectId) =>
      get('/kitchen/designs/project/$projectId');
  Future<Result<dynamic>> kitchenGetDesign(String designId) =>
      get('/kitchen/designs/$designId');
  Future<Result<dynamic>> kitchenDeleteDesign(String designId) =>
      delete('/kitchen/designs/$designId');
  Future<Result<dynamic>> kitchenAutoLayout(String designId) =>
      post('/kitchen/designs/$designId/auto-layout', {});
  Future<Result<dynamic>> kitchenAnalyzeWorkflow(String designId) =>
      get('/kitchen/designs/$designId/workflow');
  Future<Result<dynamic>> kitchenValidateCompliance(String designId) =>
      get('/kitchen/designs/$designId/compliance');
  Future<Result<dynamic>> kitchenListComponents(String designId) =>
      get('/kitchen/designs/$designId/components');
  Future<Result<dynamic>> kitchenAddComponent(String designId, Map<String, dynamic> body) =>
      post('/kitchen/designs/$designId/components', body);
  Future<Result<dynamic>> kitchenDeleteComponent(String componentId) =>
      delete('/kitchen/components/$componentId');

  // ── F29/F30 灯光设计器 ──

  Future<Result<dynamic>> lightingListSchemes(String projectId) =>
      get('/lighting/schemes/project/$projectId');
  Future<Result<dynamic>> lightingCreateScheme(Map<String, dynamic> body) =>
      post('/lighting/schemes', body);
  Future<Result<dynamic>> lightingGetScheme(String schemeId) =>
      get('/lighting/schemes/$schemeId');
  Future<Result<dynamic>> lightingDeleteScheme(String schemeId) =>
      delete('/lighting/schemes/$schemeId');
  Future<Result<dynamic>> lightingAiDesign(String schemeId, Map<String, dynamic> body) =>
      post('/lighting/schemes/$schemeId/ai-design', body);
  Future<Result<dynamic>> lightingListFixtures(String schemeId) =>
      get('/lighting/schemes/$schemeId/fixtures');
  Future<Result<dynamic>> lightingAddFixture(String schemeId, Map<String, dynamic> body) =>
      post('/lighting/schemes/$schemeId/fixtures', body);
  Future<Result<dynamic>> lightingDeleteFixture(String fixtureId) =>
      delete('/lighting/fixtures/$fixtureId');
  Future<Result<dynamic>> lightingComputeIlluminance(String schemeId) =>
      get('/lighting/schemes/$schemeId/illuminance');

  // ── F24/F25 软装搭配 + 收纳系统 ──

  Future<Result<dynamic>> softListSchemes(String projectId) =>
      get('/soft-furnishing/schemes/project/$projectId');
  Future<Result<dynamic>> softCreateScheme(Map<String, dynamic> body) =>
      post('/soft-furnishing/schemes', body);
  Future<Result<dynamic>> softGetScheme(String schemeId) =>
      get('/soft-furnishing/schemes/$schemeId');
  Future<Result<dynamic>> softDeleteScheme(String schemeId) =>
      delete('/soft-furnishing/schemes/$schemeId');
  Future<Result<dynamic>> softAiMatch(String schemeId) =>
      post('/soft-furnishing/schemes/$schemeId/ai-match', {});
  Future<Result<dynamic>> softColorHarmony(String schemeId) =>
      get('/soft-furnishing/schemes/$schemeId/color-harmony');
  Future<Result<dynamic>> softBudgetUsage(String schemeId) =>
      get('/soft-furnishing/schemes/$schemeId/budget');
  Future<Result<dynamic>> softListItems(String schemeId) =>
      get('/soft-furnishing/schemes/$schemeId/items');
  Future<Result<dynamic>> softAddItem(String schemeId, Map<String, dynamic> body) =>
      post('/soft-furnishing/schemes/$schemeId/items', body);
  Future<Result<dynamic>> softDeleteItem(String itemId) =>
      delete('/soft-furnishing/items/$itemId');
  Future<Result<dynamic>> softUpdateItemStatus(String itemId, String status) =>
      patch('/soft-furnishing/items/$itemId/status', {'status': status});
  Future<Result<dynamic>> softListStorages(String schemeId) =>
      get('/soft-furnishing/schemes/$schemeId/storage');
  Future<Result<dynamic>> softAddStorage(String schemeId, Map<String, dynamic> body) =>
      post('/soft-furnishing/schemes/$schemeId/storage', body);
  Future<Result<dynamic>> softStorageCapacity(String storageId) =>
      get('/soft-furnishing/storage/$storageId/capacity');
  Future<Result<dynamic>> softRecommendStorage(String roomName, double roomArea, int familySize) =>
      post('/soft-furnishing/storage/recommend', {
        'room_name': roomName,
        'room_area': roomArea,
        'family_size': familySize,
      });

  // ── 任务管理 ──

  /// 获取项目下所有任务
  Future<Result<dynamic>> taskListByProject(String projectId) =>
      get('/tasks/project/$projectId');

  /// 创建任务
  Future<Result<dynamic>> taskCreate(Map<String, dynamic> body) =>
      post('/tasks', body);

  /// 获取可申领任务池
  Future<Result<dynamic>> taskPool({String? claimRole, int limit = 50}) =>
      get('/tasks/pool?limit=$limit${claimRole != null ? '&claim_role=$claimRole' : ''}');

  /// 获取我的任务
  Future<Result<dynamic>> taskMine() => get('/tasks/mine');

  /// 申领任务
  Future<Result<dynamic>> taskClaim(String taskId) =>
      post('/tasks/claim', {'task_id': taskId});

  /// 查看任务候选人
  Future<Result<dynamic>> taskCandidates(String taskId) =>
      get('/tasks/$taskId/candidates');

  /// 分配任务给指定用户
  Future<Result<dynamic>> taskAssign(String taskId, String userId) =>
      post('/tasks/assign', {'task_id': taskId, 'user_id': userId});

  /// 完成任务
  Future<Result<dynamic>> taskComplete(String taskId, [Map<String, dynamic>? result]) =>
      post('/tasks/$taskId/complete', result ?? {});

  // ── F39 变更管理 ──

  Future<Result<dynamic>> changeOrderList(String projectId) =>
      get('/change-orders/project/$projectId');
  Future<Result<dynamic>> changeOrderCreate(Map<String, dynamic> body) =>
      post('/change-orders', body);
  Future<Result<dynamic>> changeOrderGet(String changeId) =>
      get('/change-orders/$changeId');
  Future<Result<dynamic>> changeOrderReview(String changeId, Map<String, dynamic> body) =>
      post('/change-orders/$changeId/review', body);
  Future<Result<dynamic>> changeOrderApprove(String changeId) =>
      post('/change-orders/$changeId/approve', {});
  Future<Result<dynamic>> changeOrderCancel(String changeId) =>
      post('/change-orders/$changeId/cancel', {});

  // ── 施工任务 & 质检 & 进度（对齐 Web 端） ──

  /// F37 施工任务列表
  Future<Result<dynamic>> constructionTasks(String projectId) =>
      get('/construction/tasks/$projectId');

  /// F37 施工日志
  Future<Result<dynamic>> constructionLogs(String taskId) =>
      get('/construction/logs/$taskId');

  /// F38 质检记录
  Future<Result<dynamic>> inspections(String taskId) =>
      get('/construction/inspections/$taskId');

  /// F38 获取项目所有质检记录（按任务聚合）
  Future<Result<dynamic>> projectInspections(String projectId) async {
    final tasksRes = await constructionTasks(projectId);
    if (!tasksRes.isSuccess) return tasksRes;
    final tasks = tasksRes.data is List ? tasksRes.data as List : (tasksRes.data['items'] as List? ?? []);
    final allInspections = <Map<String, dynamic>>[];
    for (final task in tasks) {
      final taskId = (task as Map<String, dynamic>)['id']?.toString() ?? '';
      if (taskId.isEmpty) continue;
      try {
        final invRes = await inspections(taskId);
        if (invRes.isSuccess) {
          final list = invRes.data is List ? invRes.data as List : [];
          for (final inv in list) {
            final m = Map<String, dynamic>.from(inv as Map);
            m['_task_id'] = taskId;
            m['_task_name'] = task['title'] ?? task['name'] ?? '';
            allInspections.add(m);
          }
        }
      } catch (_) {}
    }
    return Result.success(allInspections);
  }

  /// F38 AI 图像质检分析
  Future<Result<dynamic>> analyzeInspectionImages(Map<String, dynamic> data) =>
      post('/construction/inspections/analyze', data);

  /// F38 创建质检记录
  Future<Result<dynamic>> createInspection(Map<String, dynamic> data) =>
      post('/construction/inspections', data);

  /// F38 质量问题列表
  Future<Result<dynamic>> qualityIssues(String projectId) =>
      get('/construction/quality-issues/$projectId');

  /// F37 进度预警
  Future<Result<dynamic>> progressAlerts(String projectId) =>
      get('/construction/progress-alerts/$projectId');

  /// F37 里程碑
  Future<Result<dynamic>> milestones(String projectId) =>
      get('/construction/milestones/$projectId');

  // ── F9 工程量计算 ──

  /// 墙体工程量计算（砖数/砂浆/涂料面积）
  Future<Result<dynamic>> takeoffCalcWall(Map<String, dynamic> body) =>
      post('/takeoff/wall', body);

  /// 楼板工程量计算（混凝土/钢筋/模板）
  Future<Result<dynamic>> takeoffCalcSlab(Map<String, dynamic> body) =>
      post('/takeoff/slab', body);

  /// 地面工程量计算（瓷砖数/砂浆/砖缝）
  Future<Result<dynamic>> takeoffCalcFloor(Map<String, dynamic> body) =>
      post('/takeoff/floor', body);

  /// 涂料工程量计算（漆量/桶数）
  Future<Result<dynamic>> takeoffCalcPaint(Map<String, dynamic> body) =>
      post('/takeoff/paint', body);

  /// 项目级工程量汇总（墙体/楼板/地面）
  Future<Result<dynamic>> takeoffCalcProject(Map<String, dynamic> body) =>
      post('/takeoff/project', body);

  // ── F8/F9 土建结构 ──

  // 承重墙
  Future<Result<dynamic>> structuralListWalls(String projectId) =>
      get('/structural/projects/$projectId/walls');
  Future<Result<dynamic>> structuralCreateWall(Map<String, dynamic> body) =>
      post('/structural/walls', body);
  Future<Result<dynamic>> structuralGetWall(String wallId) =>
      get('/structural/walls/$wallId');
  Future<Result<dynamic>> structuralUpdateWall(String wallId, Map<String, dynamic> body) =>
      put('/structural/walls/$wallId', body);
  Future<Result<dynamic>> structuralDeleteWall(String wallId) =>
      delete('/structural/walls/$wallId');

  // 梁
  Future<Result<dynamic>> structuralListBeams(String projectId) =>
      get('/structural/projects/$projectId/beams');
  Future<Result<dynamic>> structuralCreateBeam(Map<String, dynamic> body) =>
      post('/structural/beams', body);
  Future<Result<dynamic>> structuralGetBeam(String beamId) =>
      get('/structural/beams/$beamId');
  Future<Result<dynamic>> structuralUpdateBeam(String beamId, Map<String, dynamic> body) =>
      put('/structural/beams/$beamId', body);
  Future<Result<dynamic>> structuralDeleteBeam(String beamId) =>
      delete('/structural/beams/$beamId');

  // 柱
  Future<Result<dynamic>> structuralListColumns(String projectId) =>
      get('/structural/projects/$projectId/columns');
  Future<Result<dynamic>> structuralCreateColumn(Map<String, dynamic> body) =>
      post('/structural/columns', body);
  Future<Result<dynamic>> structuralGetColumn(String columnId) =>
      get('/structural/columns/$columnId');
  Future<Result<dynamic>> structuralUpdateColumn(String columnId, Map<String, dynamic> body) =>
      put('/structural/columns/$columnId', body);
  Future<Result<dynamic>> structuralDeleteColumn(String columnId) =>
      delete('/structural/columns/$columnId');

  // 楼板
  Future<Result<dynamic>> structuralListSlabs(String projectId) =>
      get('/structural/projects/$projectId/slabs');
  Future<Result<dynamic>> structuralCreateSlab(Map<String, dynamic> body) =>
      post('/structural/slabs', body);
  Future<Result<dynamic>> structuralGetSlab(String slabId) =>
      get('/structural/slabs/$slabId');
  Future<Result<dynamic>> structuralUpdateSlab(String slabId, Map<String, dynamic> body) =>
      put('/structural/slabs/$slabId', body);
  Future<Result<dynamic>> structuralDeleteSlab(String slabId) =>
      delete('/structural/slabs/$slabId');

  // 工程量计算
  Future<Result<dynamic>> structuralListQuantityCalcs(String projectId) =>
      get('/structural/projects/$projectId/quantity-calcs');
  Future<Result<dynamic>> structuralCreateQuantityCalc(Map<String, dynamic> body) =>
      post('/structural/quantity-calcs', body);
  Future<Result<dynamic>> structuralGetQuantityCalc(String calcId) =>
      get('/structural/quantity-calcs/$calcId');
  Future<Result<dynamic>> structuralDeleteQuantityCalc(String calcId) =>
      delete('/structural/quantity-calcs/$calcId');
  Future<Result<dynamic>> structuralAutoCalcQuantity(Map<String, dynamic> body) =>
      post('/structural/quantity-calcs/auto-calc', body);
  Future<Result<dynamic>> structuralAddQuantityLineItem(String calcId, Map<String, dynamic> body) =>
      post('/structural/quantity-calcs/$calcId/line-items', body);
  Future<Result<dynamic>> structuralDeleteQuantityLineItem(String itemId) =>
      delete('/structural/quantity-calcs/line-items/$itemId');

  // 基础
  Future<Result<dynamic>> structuralListFoundations(String projectId) =>
      get('/structural/projects/$projectId/foundations');
  Future<Result<dynamic>> structuralCreateFoundation(Map<String, dynamic> body) =>
      post('/structural/foundations', body);
  Future<Result<dynamic>> structuralGetFoundation(String foundationId) =>
      get('/structural/foundations/$foundationId');
  Future<Result<dynamic>> structuralDeleteFoundation(String foundationId) =>
      delete('/structural/foundations/$foundationId');
  Future<Result<dynamic>> structuralSelectFoundation(String foundationId) =>
      post('/structural/foundations/$foundationId/select', {});
  Future<Result<dynamic>> structuralRecommendFoundation(Map<String, dynamic> body) =>
      post('/structural/foundations/recommend', body);

  // 荷载估算
  Future<Result<dynamic>> structuralListLoadEstimates(String projectId) =>
      get('/structural/projects/$projectId/load-estimates');
  Future<Result<dynamic>> structuralCreateLoadEstimate(Map<String, dynamic> body) =>
      post('/structural/load-estimates', body);
  Future<Result<dynamic>> structuralGetLoadEstimate(String estimateId) =>
      get('/structural/load-estimates/$estimateId');
  Future<Result<dynamic>> structuralDeleteLoadEstimate(String estimateId) =>
      delete('/structural/load-estimates/$estimateId');
  Future<Result<dynamic>> structuralComputeLoad(Map<String, dynamic> body) =>
      post('/structural/load-estimates/compute', body);

  // 合规检查
  Future<Result<dynamic>> structuralListCompliance(String projectId) =>
      get('/structural/projects/$projectId/compliance');
  Future<Result<dynamic>> structuralCreateCompliance(Map<String, dynamic> body) =>
      post('/structural/compliance', body);
  Future<Result<dynamic>> structuralGetCompliance(String complianceId) =>
      get('/structural/compliance/$complianceId');
  Future<Result<dynamic>> structuralDeleteCompliance(String complianceId) =>
      delete('/structural/compliance/$complianceId');

  // ── 产品/服务管理 ──

  /// 查询产品列表（全局产品库）
  Future<Result<dynamic>> productList({
    String? category,
    String status = 'published',
    int offset = 0,
    int limit = 20,
  }) {
    final params = <String>[];
    if (category != null) {
      params.add('category=${Uri.encodeQueryComponent(category)}');
    }
    params.add('status=$status');
    params.add('offset=$offset');
    params.add('limit=$limit');
    return get('/products?${params.join('&')}');
  }

  /// 获取产品详情
  Future<Result<dynamic>> productGet(String productId) =>
      get('/products/$productId');

  /// 创建产品（支持 AI 辅助生成文案）
  Future<Result<dynamic>> productCreate(Map<String, dynamic> body) =>
      post('/products', body);

  /// 更新产品
  Future<Result<dynamic>> productUpdate(String productId, Map<String, dynamic> body) =>
      put('/products/$productId', body);

  /// 发布产品到市场（可选推送到项目聊天室）
  Future<Result<dynamic>> productPublish(String productId, {String? projectId}) =>
      post('/products/$productId/publish${projectId != null ? '?project_id=$projectId' : ''}', {});

  /// 查询当前供应商的产品
  Future<Result<dynamic>> productMine({int offset = 0, int limit = 20}) =>
      get('/products/mine?offset=$offset&limit=$limit');

  // ── 拍照上架 camera_scan ──

  /// 拍照识别产品（需已认证供应商）
  Future<Result<dynamic>> cameraScan(Uint8List imageBytes, String filename, {String? context}) async {
    try {
      final request = http.MultipartRequest('POST', _uri('/products/camera/scan'));
      if (_token != null) request.headers['Authorization'] = 'Bearer $_token';
      request.files.add(http.MultipartFile.fromBytes('image', imageBytes, filename: filename));
      if (context != null) request.fields['context'] = context;
      final streamed = await _send(() => request.send());
      final res = await http.Response.fromStream(streamed);
      return _handleResponse(res);
    } on ApiException catch (e) {
      return Result.failure(e.message, statusCode: e.statusCode, isNetworkError: e.isNetwork);
    }
  }

  /// 确认拍照识别结果并创建产品
  Future<Result<dynamic>> cameraConfirm(Map<String, dynamic> body) =>
      post('/products/camera/confirm', body);

  /// 获取批量上传模板下载链接
  Future<Result<dynamic>> productBatchTemplate() =>
      get('/products/batch/template');

  /// 查询 AI 文案生成任务状态
  Future<Result<dynamic>> productBatchAiCopyStatus(String batchId) =>
      get('/products/batch/ai-jobs/$batchId');

  // ── AR 空间测量 ar_scan ──

  Future<Result<dynamic>> arDeviceCapability(Map<String, dynamic> body) =>
      post('/surveys/ar/device-capability', body);
  Future<Result<dynamic>> arCreateSession(Map<String, dynamic> body) =>
      post('/surveys/ar/sessions', body);
  Future<Result<dynamic>> arListSessions(String projectId) =>
      get('/surveys/ar/sessions/project/$projectId');
  Future<Result<dynamic>> arGetSession(String sessionId) =>
      get('/surveys/ar/sessions/$sessionId');
  Future<Result<dynamic>> arUpdateSession(String sessionId, Map<String, dynamic> body) =>
      patch('/surveys/ar/sessions/$sessionId', body);
  Future<Result<dynamic>> arStartScan(String sessionId) =>
      post('/surveys/ar/sessions/$sessionId/start', {});
  Future<Result<dynamic>> arProcessScan(String sessionId, Map<String, dynamic> body) =>
      post('/surveys/ar/sessions/$sessionId/process', body);
  Future<Result<dynamic>> arGetAccuracy(String sessionId) =>
      get('/surveys/ar/sessions/$sessionId/accuracy');
  Future<Result<dynamic>> arApplySession(String sessionId) =>
      post('/surveys/ar/sessions/$sessionId/apply', {});
  Future<Result<dynamic>> arDeleteSession(String sessionId) =>
      delete('/surveys/ar/sessions/$sessionId');
  Future<Result<dynamic>> arAddFeature(Map<String, dynamic> body) =>
      post('/surveys/ar/features', body);
  Future<Result<dynamic>> arListFeatures(String sessionId) =>
      get('/surveys/ar/features/$sessionId');
  Future<Result<dynamic>> arDeleteFeature(String featureId) =>
      delete('/surveys/ar/features/$featureId');
  Future<Result<dynamic>> arAddPoint(Map<String, dynamic> body) =>
      post('/surveys/ar/points', body);
  Future<Result<dynamic>> arListPoints(String sessionId) =>
      get('/surveys/ar/points/$sessionId');
  Future<Result<dynamic>> arDeviceCheck() =>
      get('/surveys/device-check');
  Future<Result<dynamic>> arUploadModel(String sessionId, {required String filePath}) =>
      uploadFile('/surveys/ar/sessions/$sessionId/upload-model', filePath: filePath);

  // ── 位置服务 ──

  Future<Result<dynamic>> searchLocation(Map<String, dynamic> query) {
    final qs = query.entries.map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value.toString())}').join('&');
    return get('/location/search?$qs');
  }
  Future<Result<dynamic>> geocodeLocation(Map<String, dynamic> query) {
    final qs = query.entries.map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value.toString())}').join('&');
    return get('/location/geocode?$qs');
  }
  Future<Result<dynamic>> autocompleteLocation(Map<String, dynamic> query) {
    final qs = query.entries.map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value.toString())}').join('&');
    return get('/location/autocomplete?$qs');
  }

  // ── 户型管理 ──

  Future<Result<dynamic>> getFloorplans(String projectId) =>
      getList('/floorplans/$projectId');
  Future<Result<dynamic>> getFloorplan(String floorplanId) =>
      get('/floorplans/$floorplanId');
  Future<Result<dynamic>> createFloorplan(Map<String, dynamic> body) =>
      post('/floorplans', body);
  Future<Result<dynamic>> updateFloorplan(String floorplanId, Map<String, dynamic> body) =>
      put('/floorplans/$floorplanId', body);
  Future<Result<dynamic>> deleteFloorplan(String floorplanId) =>
      delete('/floorplans/$floorplanId');

  // ── 水电点位 MEP ──

  Future<Result<dynamic>> mepPlan(String projectId, Map<String, dynamic> body) =>
      post('/mep/plan', body..['project_id'] = projectId);
  Future<Result<dynamic>> mepAppliances(String projectId) =>
      get('/mep/appliances/$projectId');
  Future<Result<dynamic>> mepComplianceCheck(String projectId) =>
      post('/mep/compliance/check', {'project_id': projectId});
  Future<Result<dynamic>> mepRoomStandards() =>
      get('/mep/room-standards');

  // ── 定制家具 ──

  Future<Result<dynamic>> createCustomFurnitureDesign(Map<String, dynamic> body) =>
      post('/custom-furniture/designs', body);
  Future<Result<dynamic>> getCustomFurnitureDesigns(String projectId) =>
      getList('/custom-furniture/designs/$projectId');
  Future<Result<dynamic>> getCustomFurnitureDesign(String designId) =>
      get('/custom-furniture/designs/$designId');
  Future<Result<dynamic>> updateCustomFurnitureDesign(String designId, Map<String, dynamic> body) =>
      put('/custom-furniture/designs/$designId', body);
  Future<Result<dynamic>> deleteCustomFurnitureDesign(String designId) =>
      delete('/custom-furniture/designs/$designId');
  Future<Result<dynamic>> customFurnitureGenerateBom(String designId) =>
      post('/custom-furniture/designs/$designId/bom', {});
  Future<Result<dynamic>> customFurnitureGetBom(String designId) =>
      get('/custom-furniture/designs/$designId/bom');
  Future<Result<dynamic>> customFurniturePriceEstimate(String designId, Map<String, dynamic> body) =>
      get('/custom-furniture/designs/$designId/price');
  Future<Result<dynamic>> customFurnitureValidate(String designId) =>
      post('/custom-furniture/designs/$designId/validate', {});
  Future<Result<dynamic>> customFurnitureParametric(String designId, Map<String, dynamic> body) =>
      post('/custom-furniture/designs/$designId/parametric', body);
  Future<Result<dynamic>> customFurnitureAddModule(String designId, Map<String, dynamic> body) =>
      post('/custom-furniture/designs/$designId/modules', body);
  Future<Result<dynamic>> customFurnitureListModules(String designId) =>
      get('/custom-furniture/designs/$designId/modules');
  Future<Result<dynamic>> customFurnitureDeleteModule(String moduleId) =>
      delete('/custom-furniture/modules/$moduleId');
  Future<Result<dynamic>> customFurnitureListPanels(String designId) =>
      get('/custom-furniture/designs/$designId/panels');

  // ── 工程队匹配 ──

  Future<Result<dynamic>> getCrews(Map<String, dynamic>? query) {
    final path = query != null && query.isNotEmpty
        ? '/crews?${query.entries.map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value.toString())}').join('&')}'
        : '/crews';
    return getList(path);
  }
  Future<Result<dynamic>> createCrew(Map<String, dynamic> body) =>
      post('/crews', body);
  Future<Result<dynamic>> getCrew(String crewId) =>
      get('/crews/$crewId');
  Future<Result<dynamic>> updateCrew(String crewId, Map<String, dynamic> body) =>
      put('/crews/$crewId', body);
  Future<Result<dynamic>> matchCrews(Map<String, dynamic> body) =>
      post('/crews/match', body);
  Future<Result<dynamic>> getCrewMatches(String projectId) =>
      getList('/crews/matches/$projectId');
  Future<Result<dynamic>> updateCrewMatchStatus(String matchId, Map<String, dynamic> body) =>
      patch('/crews/matches/$matchId/status', body);

  // ── 工人匹配 ──

  Future<Result<dynamic>> getWorkers(Map<String, dynamic>? query) {
    final path = query != null && query.isNotEmpty
        ? '/workers?${query.entries.map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value.toString())}').join('&')}'
        : '/workers';
    return getList(path);
  }
  Future<Result<dynamic>> createWorker(Map<String, dynamic> body) =>
      post('/workers', body);
  Future<Result<dynamic>> getWorker(String workerId) =>
      get('/workers/$workerId');
  Future<Result<dynamic>> updateWorker(String workerId, Map<String, dynamic> body) =>
      put('/workers/$workerId', body);
  Future<Result<dynamic>> matchWorkers(Map<String, dynamic> body) =>
      post('/workers/match', body);
  Future<Result<dynamic>> getWorkerMatches(String projectId) =>
      getList('/workers/matches/$projectId');
  Future<Result<dynamic>> updateWorkerMatchStatus(String matchId, Map<String, dynamic> body) =>
      patch('/workers/matches/$matchId/status', body);

  // ── 通知 / 设备推送 ──

  Future<Result<dynamic>> registerDevice(Map<String, dynamic> body) =>
      post('/notifications/devices', body);
  Future<Result<dynamic>> listMyDevices() =>
      get('/notifications/devices');
  Future<Result<dynamic>> unregisterDevice(String deviceId) =>
      delete('/notifications/devices/$deviceId');

  // ── 健康检查 ──

  Future<Result<dynamic>> healthCheck() =>
      get('/health');

  // ── 功能开关 ──

  Future<Result<dynamic>> getFeatureFlags() =>
      get('/config/feature-flags');

  // ── BIM IFC 导出 ──

  /// 导出项目结构数据为 IFC 文件
  Future<Result<dynamic>> exportStructuralIFC(String projectId) =>
      post('/bim/export/structural/$projectId', {});

  /// 导出设计方案数据为 IFC 文件
  Future<Result<dynamic>> exportDesignIFC(String planId) =>
      post('/bim/export/design/$planId', {});

  // ══════════════════════════════════════════════════════
  // v1.1.16 补齐：Web 端已有但 Flutter 缺失的 API 模块
  // ══════════════════════════════════════════════════════

  // ── Agent 聊天 (P0) ──

  /// 通用 Agent 聊天（自然语言路由）
  Future<Result<dynamic>> agentChat(String message,
          {String agentType = 'orchestrator', String? projectId,
           String? sessionId}) =>
      post('/agents/chat', {
        'message': message,
        'agent_type': agentType,
        if (projectId != null) 'project_id': projectId,
        if (sessionId != null) 'session_id': sessionId,
      });

  /// 支持多轮对话历史的 Agent 聊天
  Future<Result<dynamic>> agentChatWithHistory(String message,
          {String agentType = 'orchestrator', String? projectId,
           List<Map<String, dynamic>>? history, String? sessionId}) =>
      post('/agents/chat', {
        'message': message,
        'agent_type': agentType,
        if (projectId != null) 'project_id': projectId,
        if (history != null) 'history': history,
        if (sessionId != null) 'session_id': sessionId,
      });

  /// 设计 Agent 专用端点
  Future<Result<dynamic>> agentDesignChat(String message, {String? projectId}) =>
      post('/agents/design', {
        'message': message,
        if (projectId != null) 'project_id': projectId,
      });

  /// 预算 Agent 专用端点
  Future<Result<dynamic>> agentBudgetChat(String message, {String? projectId}) =>
      post('/agents/budget', {
        'message': message,
        if (projectId != null) 'project_id': projectId,
      });

  /// 采购 Agent 专用端点
  Future<Result<dynamic>> agentProcurementChat(String message, {String? projectId}) =>
      post('/agents/procurement', {
        'message': message,
        if (projectId != null) 'project_id': projectId,
      });

  /// 施工 Agent 专用端点
  Future<Result<dynamic>> agentConstructionChat(String message, {String? projectId}) =>
      post('/agents/construction', {
        'message': message,
        if (projectId != null) 'project_id': projectId,
      });

  // ── Agent 会话管理 ──

  Future<Result<dynamic>> listAgentSessions({String? projectId, int skip = 0, int limit = 20}) {
    final params = <String, String>{};
    if (projectId != null) params['project_id'] = projectId;
    params['skip'] = skip.toString();
    params['limit'] = limit.toString();
    final qs = params.entries.map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value)}').join('&');
    return get('/agents/sessions?$qs');
  }

  Future<Result<dynamic>> getAgentSession(String sessionId) {
    return get('/agents/sessions/$sessionId');
  }

  Future<Result<dynamic>> deleteAgentSession(String sessionId) {
    return delete('/agents/sessions/$sessionId');
  }

  // ── 预算模块 (P1) ──

  Future<Result<dynamic>> getBudget(String projectId) =>
      get('/budgets/project/$projectId');

  Future<Result<dynamic>> createBudget(Map<String, dynamic> body) =>
      post('/budgets', body);

  Future<Result<dynamic>> generateBudgetFromBom(String projectId) =>
      post('/budgets/generate-from-bom/$projectId', {});

  Future<Result<dynamic>> generateBudgetPlan(String message) =>
      post('/budgets/generate-plan', {'message': message});

  Future<Result<dynamic>> compareBudgetPlans(String message) =>
      post('/budgets/compare-plans', {'message': message});

  Future<Result<dynamic>> budgetVarianceCheck(Map<String, dynamic> body) =>
      post('/budgets/variance-check', body);

  Future<Result<dynamic>> listBudgetTemplates() =>
      get('/budgets/templates');

  Future<Result<dynamic>> applyBudgetTemplate(String templateCode, double area) =>
      post('/budgets/templates/apply', {'template_code': templateCode, 'area': area});

  Future<Result<dynamic>> updateBudgetLine(String lineId, Map<String, dynamic> body) =>
      patch('/budgets/lines/$lineId', body);

  // ── 物料/BOM 模块 (P1) ──

  Future<Result<dynamic>> getMaterialCategories() =>
      get('/materials/categories');

  Future<Result<dynamic>> getMaterials(Map<String, String> params) =>
      get('/materials${_queryParams(params)}');

  Future<Result<dynamic>> getMaterial(String materialId) =>
      get('/materials/$materialId');

  Future<Result<dynamic>> addBOMItem(Map<String, dynamic> body) =>
      post('/materials/bom', body);

  Future<Result<dynamic>> generateBOM(String projectId) =>
      post('/materials/bom/generate/$projectId', {});

  Future<Result<dynamic>> getProjectBOM(String projectId) =>
      get('/materials/bom/$projectId');

  Future<Result<dynamic>> getBOMSummary(String projectId) =>
      get('/materials/bom/$projectId/summary');

  Future<Result<dynamic>> deleteBOMItem(String bomId) =>
      delete('/materials/bom/$bomId');

  // ── 结算/支付模块 (P1) ──

  Future<Result<dynamic>> getSettlement(String projectId) =>
      get('/settlements/project/$projectId');

  Future<Result<dynamic>> createSettlement(Map<String, dynamic> body) =>
      post('/settlements', body);

  Future<Result<dynamic>> generateSettlementFromBudget(String projectId) =>
      post('/settlements/generate-from-budget/$projectId', {});

  Future<Result<dynamic>> generateMilestoneSettlement(Map<String, dynamic> body) =>
      post('/settlements/milestone', body);

  Future<Result<dynamic>> listSettlementMilestones() =>
      get('/settlements/milestones');

  Future<Result<dynamic>> checkSettlementAnomalies(Map<String, dynamic> body) =>
      post('/settlements/anomaly-check', body);

  Future<Result<dynamic>> attachSettlementAnomalies(
          String projectId, List<Map<String, dynamic>> anomalies, {bool autoMarkLines = true}) =>
      post('/settlements/anomaly-attach/$projectId', {
        'anomalies': anomalies,
        'auto_mark_lines': autoMarkLines,
      });

  Future<Result<dynamic>> requestSettlementReview(
          String projectId, String reason, {String? reviewerId}) =>
      post('/settlements/request-review/$projectId', {
        'reason': reason,
        if (reviewerId != null) 'reviewer_id': reviewerId,
      });

  Future<Result<dynamic>> generateReconciliation(Map<String, dynamic> body) =>
      post('/settlements/reconciliation', body);

  Future<Result<dynamic>> autoSettlement(Map<String, dynamic> body) =>
      post('/settlements/auto-settlement', body);

  Future<Result<dynamic>> exportSettlement(String projectId) =>
      get('/settlements/export/$projectId');

  // 支付管理
  Future<Result<dynamic>> getPayments(String projectId) =>
      get('/payments/project/$projectId');

  Future<Result<dynamic>> createPayment(Map<String, dynamic> body) =>
      post('/payments', body);

  Future<Result<dynamic>> getPayment(String paymentId) =>
      get('/payments/$paymentId');

  Future<Result<dynamic>> confirmPayment(String paymentId, Map<String, dynamic> body) =>
      post('/payments/$paymentId/confirm', body);

  Future<Result<dynamic>> refundPayment(String paymentId, Map<String, dynamic> body) =>
      post('/payments/$paymentId/refund', body);

  Future<Result<dynamic>> failPayment(String paymentId, Map<String, dynamic> body) =>
      post('/payments/$paymentId/fail', body);

  Future<Result<dynamic>> generateInvoice(String paymentId, Map<String, dynamic> body) =>
      post('/payments/$paymentId/invoice', body);

  Future<Result<dynamic>> getPaymentMilestones(String projectId) =>
      get('/payments/milestones/$projectId');

  Future<Result<dynamic>> getPaymentSchedule(String projectId) =>
      get('/payments/schedule/$projectId');

  Future<Result<dynamic>> getFinalSettlement(String projectId) =>
      get('/payments/final-settlement/$projectId');

  // ── 项目管理 (P2) ──

  Future<Result<dynamic>> updateProject(String projectId, Map<String, dynamic> data) =>
      patch('/projects/$projectId', data);

  Future<Result<dynamic>> deleteProject(String projectId) =>
      delete('/projects/$projectId');

  // ── 基础采购订单管理 (P2) ──

  Future<Result<dynamic>> getProcurementOrders(String projectId) =>
      get('/procurement/orders/$projectId');

  Future<Result<dynamic>> getProcurementOrder(String orderId) =>
      get('/procurement/orders/detail/$orderId');

  Future<Result<dynamic>> createProcurementOrder(Map<String, dynamic> body) =>
      post('/procurement/orders', body);

  Future<Result<dynamic>> updateProcurementOrder(String orderId, Map<String, dynamic> body) =>
      patch('/procurement/orders/$orderId', body);

  Future<Result<dynamic>> updateOrderStatus(String orderId, String status) =>
      patch('/procurement/orders/$orderId/status', {'status': status});

  Future<Result<dynamic>> deleteProcurementOrder(String orderId) =>
      delete('/procurement/orders/$orderId');

  Future<Result<dynamic>> getQuotations(String projectId) =>
      get('/procurement/quotations/$projectId');

  Future<Result<dynamic>> createQuotation(Map<String, dynamic> body) =>
      post('/procurement/quotations', body);

  Future<Result<dynamic>> getSuppliers() =>
      get('/procurement/suppliers');

  Future<Result<dynamic>> createSupplier(Map<String, dynamic> body) =>
      post('/procurement/suppliers', body);

  Future<Result<dynamic>> compareQuotes(Map<String, dynamic> body) =>
      post('/procurement/compare', body);

  // ── 文件管理 (P2) ──

  Future<Result<dynamic>> getFiles(String projectId) =>
      get('/files/project/$projectId');

  Future<Result<dynamic>> downloadFile(String attachmentId) =>
      get('/files/download/$attachmentId');

  Future<Result<dynamic>> deleteFileAttachment(String attachmentId) =>
      delete('/files/$attachmentId');

  // ── IM 聊天 (P2) ──

  Future<Result<dynamic>> getChatRoom(String projectId) =>
      get('/chat/rooms/$projectId');

  Future<Result<dynamic>> getChatMessages(String projectId, {int? limit}) =>
      get('/chat/messages/$projectId${limit != null ? '?limit=$limit' : ''}');

  Future<Result<dynamic>> sendChatMessage(Map<String, dynamic> body) =>
      post('/chat/messages', body);

  Future<Result<dynamic>> markMessageRead(String messageId) =>
      post('/chat/messages/$messageId/read', {});

  Future<Result<dynamic>> getUnreadCount(String projectId) =>
      get('/chat/unread/$projectId');

  // ── 现场测量 Survey (P2) ──

  Future<Result<dynamic>> createSurvey(Map<String, dynamic> body) =>
      post('/surveys', body);

  Future<Result<dynamic>> getSurveys(String projectId) =>
      get('/surveys/project/$projectId');

  Future<Result<dynamic>> getSurvey(String surveyId) =>
      get('/surveys/$surveyId');

  Future<Result<dynamic>> updateSurvey(String surveyId, Map<String, dynamic> body) =>
      patch('/surveys/$surveyId', body);

  Future<Result<dynamic>> deleteSurvey(String surveyId) =>
      delete('/surveys/$surveyId');

  // ── 语音处理 (P2) ──

  Future<Result<dynamic>> processVoice(String text, {String? projectId}) =>
      post('/voice/process', {
        'text': text,
        if (projectId != null) 'project_id': projectId,
      });

  // ── 管理后台 (P2) ──

  Future<Result<dynamic>> getAdminUsers() =>
      get('/admin/users');

  Future<Result<dynamic>> getAdminUserDetail(String userId) =>
      get('/admin/users/$userId');

  Future<Result<dynamic>> toggleAdminUserStatus(String userId, bool isActive) =>
      patch('/admin/users/$userId/status', {'is_active': isActive});

  // ── 查询参数辅助 ──
  String _queryParams(Map<String, String> params) {
    if (params.isEmpty) return '';
    final entries = params.entries
        .where((e) => e.value.isNotEmpty)
        .map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value)}')
        .join('&');
    return entries.isEmpty ? '' : '?$entries';
  }

  // ── 响应处理 ──

  Result<dynamic> _handleResponse(http.Response res) {
    if (res.statusCode == 204) return Result.success({});
    if (res.statusCode == 401) {
      _onUnauthorized();
      return Result.failure('未授权，请重新登录', statusCode: 401);
    }
    final data = jsonDecode(res.body);
    if (res.statusCode >= 400) {
      return Result.failure(
        data['detail'] ?? '请求失败 (${res.statusCode})',
        statusCode: res.statusCode,
      );
    }
    return Result.success(data);
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
