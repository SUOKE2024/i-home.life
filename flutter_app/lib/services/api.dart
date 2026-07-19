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
