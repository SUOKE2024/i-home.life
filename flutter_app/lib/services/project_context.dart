import 'package:flutter/foundation.dart';

import 'api.dart';

/// 项目上下文状态管理者
///
/// 通过 [ChangeNotifier] 向 UI 层提供项目列表和当前活动项目的响应式状态。
/// 配合 Provider 使用时，监听此对象即可在项目切换时自动重建 UI。
class ProjectContext extends ChangeNotifier {
  final ApiClient _api = ApiClient();

  /// 当前活动项目 ID
  String? _currentProjectId;
  String? get currentProjectId => _currentProjectId;

  /// 当前活动项目详情
  Map<String, dynamic>? _currentProject;
  Map<String, dynamic>? get currentProject => _currentProject;

  /// 项目列表
  List<Map<String, dynamic>> _projects = [];
  List<Map<String, dynamic>> get projects => _projects;

  /// 是否正在加载
  bool _loading = false;
  bool get loading => _loading;

  /// 加载项目列表
  Future<void> loadProjects() async {
    _loading = true;
    notifyListeners();

    final result = await _api.getProjects();
    if (result.isSuccess) {
      final raw = result.data as List;
      _projects = raw.map((e) => Map<String, dynamic>.from(e as Map)).toList();

      // 如果当前没有选中项目且有项目列表，自动选第一个
      if (_currentProjectId == null && _projects.isNotEmpty) {
        _currentProjectId = _projects.first['id'] as String?;
        _currentProject = _projects.first;
      } else if (_currentProjectId != null) {
        // 刷新当前项目详情
        _currentProject = _projects.cast<Map<String, dynamic>?>().firstWhere(
          (p) => p?['id'] == _currentProjectId,
          orElse: () => null,
        );
      }
    }
    _loading = false;
    notifyListeners();
  }

  /// 切换活动项目
  ///
  /// 如果 [projectId] 在当前项目列表中，则切换并拉取最新详情；
  /// 否则尝试通过 API 获取项目详情再切换。
  Future<void> switchProject(String projectId) async {
    if (projectId == _currentProjectId) return;

    _loading = true;
    notifyListeners();

    // 先从本地列表查找
    final local = _projects.cast<Map<String, dynamic>?>().firstWhere(
      (p) => p?['id'] == projectId,
      orElse: () => null,
    );

    if (local != null) {
      _currentProjectId = projectId;
      _currentProject = local;
    } else {
      // 本地列表没有，从 API 获取详情
      final result = await _api.getProject(projectId);
      if (result.isSuccess) {
        final detail = result.data as Map<String, dynamic>;
        _currentProjectId = projectId;
        _currentProject = detail;
        _projects.add(detail);
      }
    }
    _loading = false;
    notifyListeners();
  }
}
