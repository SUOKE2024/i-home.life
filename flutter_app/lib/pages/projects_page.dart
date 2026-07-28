import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import '../theme/suoke_theme.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';
import '../models/models.dart';
import 'project_detail_page.dart';

/// 面积显示：整数面积不带小数点（126.0 → "126"）
String _fmtArea(double? area) {
  if (area == null) return '-';
  return area == area.roundToDouble() ? '${area.toInt()}' : '$area';
}

class ProjectsPage extends StatefulWidget {
  const ProjectsPage({super.key});

  @override
  State<ProjectsPage> createState() => _ProjectsPageState();
}

class _ProjectsPageState extends State<ProjectsPage> {
  List<Project> _projects = [];
  bool _loading = true;
  String? _error;
  bool _showForm = false;
  bool _submitting = false;

  final _nameCtrl = TextEditingController();
  final _areaCtrl = TextEditingController();

  // 户型选择
  int _floors = 2;
  int _bedrooms = 3;
  int _livingRooms = 2;
  int _kitchens = 1;
  int _bathrooms = 2;

  // 位置搜索
  final _locationCtrl = TextEditingController();
  bool _locating = false;
  String? _locationError;
  List<Map<String, dynamic>> _locationResults = [];
  bool _searchingLocation = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final api = ApiClient();
    final result = await api.getList('/projects');
    if (result.isSuccess) {
      final data = result.data as List;
      setState(() {
        _projects = data.map((e) => Project.fromJson(e as Map<String, dynamic>)).toList();
        _loading = false;
      });
    } else {
      setState(() {
        _loading = false;
        _error = '加载失败，请检查网络后重试';
      });
    }
  }

  Future<void> _create() async {
    if (_submitting) return;
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请输入项目名称')),
      );
      return;
    }
    setState(() => _submitting = true);
    try {
      final api = ApiClient();
      final area = double.tryParse(_areaCtrl.text);
      final result = await api.post('/projects', {
        'name': name,
        'address': _locationCtrl.text.trim(),
        'total_area': area,
        'floors': [
          {
            'name': '1层',
            'floor_number': 1,
            'area': area,
            'rooms': [],
          }
        ],
        'house_type': {
          'floors': _floors,
          'bedrooms': _bedrooms,
          'living_rooms': _livingRooms,
          'kitchens': _kitchens,
          'bathrooms': _bathrooms,
        },
      });
      if (result.isSuccess) {
        _nameCtrl.clear();
        _locationCtrl.clear();
        _areaCtrl.clear();
        _locationResults = [];
        if (mounted) setState(() => _showForm = false);
        _load();
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('创建失败: ${result.error}')),
          );
        }
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  // ── 位置搜索 ──

  Future<void> _autoLocate() async {
    setState(() {
      _locating = true;
      _locationError = null;
    });
    try {
      final bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        setState(() {
          _locating = false;
          _locationError = '请开启定位服务';
        });
        return;
      }
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          setState(() {
            _locating = false;
            _locationError = '定位权限被拒绝';
          });
          return;
        }
      }
      if (permission == LocationPermission.deniedForever) {
        setState(() {
          _locating = false;
          _locationError = '请在系统设置中开启定位权限';
        });
        return;
      }
      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );
      // 反向地理编码获取附近地址
      await _reverseGeocode(position.latitude, position.longitude);
    } catch (e) {
      setState(() {
        _locating = false;
        _locationError = '定位失败: $e';
      });
    }
  }

  Future<void> _reverseGeocode(double lat, double lon) async {
    try {
      final uri = Uri.parse(
        'https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=$lat&lon=$lon&zoom=18&addressdetails=1',
      );
      final response = await http.get(uri, headers: {
        'User-Agent': 'SuokeHomeApp/1.0',
        'Accept-Language': 'zh-CN',
      });
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final displayName = data['display_name'] as String? ?? '';
        final address = data['address'] as Map<String, dynamic>? ?? {};
        final suburb = address['suburb'] ?? address['neighbourhood'] ?? address['hamlet'] ?? '';
        final road = address['road'] ?? address['pedestrian'] ?? '';
        final city = address['city'] ?? address['town'] ?? address['county'] ?? '';
        final district = address['district'] ?? address['state_district'] ?? '';
        final building = address['building'] ?? address['house_number'] ?? '';

        // 构造可读的当前位置名称
        String locationName;
        if (suburb.isNotEmpty) {
          locationName = suburb;
          if (road.isNotEmpty) locationName = '$suburb$road';
        } else if (road.isNotEmpty) {
          locationName = road;
          if (building.isNotEmpty) locationName = '$building($road)';
        } else if (building.isNotEmpty) {
          locationName = building;
        } else {
          locationName = displayName;
        }
        final String fullAddr = [city, district, suburb, road, building]
            .where((s) => s.toString().isNotEmpty)
            .join(' · ');

        final results = <Map<String, dynamic>>[
          {
            'name': locationName,
            'address': fullAddr.isNotEmpty ? fullAddr : displayName,
            'display_name': displayName,
            'lat': lat.toString(),
            'lon': lon.toString(),
            'selected': true,
          },
        ];
        await _searchNearby(lat, lon, results);
      } else {
        _locationError = '地址解析失败';
      }
    } catch (e) {
      _locationError = '地址解析失败: $e';
    } finally {
      setState(() => _locating = false);
    }
  }

  Future<void> _searchNearby(double lat, double lon, List<Map<String, dynamic>> existing) async {
    // 搜索附近的住宅/楼盘 POI
    try {
      final uri = Uri.parse(
        'https://nominatim.openstreetmap.org/search?format=jsonv2&q=小区|住宅|公寓|花园|新城|家园|苑&limit=5&accept-language=zh-CN&bounded=1'
        '&viewbox=${lon - 0.05},${lat - 0.03},${lon + 0.05},${lat + 0.03}',
      );
      final response = await http.get(uri, headers: {
        'User-Agent': 'SuokeHomeApp/1.0',
      });
      if (response.statusCode == 200) {
        final data = json.decode(response.body) as List;
        for (final item in data) {
          final name = _extractName(item);
          final addr = _extractAddress(item);
          existing.add({
            'name': name.isNotEmpty ? name : (item['display_name'] ?? ''),
            'address': addr.isNotEmpty ? addr : (item['display_name'] ?? ''),
            'display_name': item['display_name'] ?? '',
            'lat': item['lat'] ?? '',
            'lon': item['lon'] ?? '',
            'selected': false,
          });
        }
      }
    } catch (_) {}
    setState(() {
      _locationResults = existing;
    });
  }

  Future<void> _searchLocation(String query) async {
    if (query.length < 2) {
      setState(() => _locationResults = []);
      return;
    }
    setState(() => _searchingLocation = true);
    try {
      final uri = Uri.parse(
        'https://nominatim.openstreetmap.org/search?format=jsonv2&q=$query&limit=5&accept-language=zh-CN&countrycodes=cn',
      );
      final response = await http.get(uri, headers: {
        'User-Agent': 'SuokeHomeApp/1.0',
      });
      if (response.statusCode == 200) {
        final data = json.decode(response.body) as List;
        setState(() {
          _locationResults = data.map((item) {
            final name = _extractName(item);
            final addr = _extractAddress(item);
            return {
              'name': name.isNotEmpty ? name : (item['display_name'] ?? ''),
              'address': addr.isNotEmpty ? addr : (item['display_name'] ?? ''),
              'display_name': item['display_name'] ?? '',
              'lat': item['lat'] ?? '',
              'lon': item['lon'] ?? '',
              'selected': false,
            };
          }).toList();
        });
      }
    } catch (_) {
      setState(() => _locationResults = []);
    } finally {
      setState(() => _searchingLocation = false);
    }
  }

  /// 从 Nominatim 结果提取可读名称
  String _extractName(Map<String, dynamic> item) {
    final address = item['address'] as Map<String, dynamic>? ?? {};
    final name = item['name'] as String? ?? '';
    if (name.isNotEmpty) return name;
    // 从 address 提取最具体的部分
    return (address['suburb'] ?? address['neighbourhood'] ?? address['road'] ??
            address['hamlet'] ?? address['village'] ?? address['town'] ?? '')
        .toString();
  }

  /// 从 Nominatim 结果提取完整地址
  String _extractAddress(Map<String, dynamic> item) {
    final address = item['address'] as Map<String, dynamic>? ?? {};
    final parts = <String>[
      if (address['city'] != null) address['city'].toString(),
      if (address['district'] != null) address['district'].toString(),
      if (address['state_district'] != null) address['state_district'].toString(),
      if (address['suburb'] != null) address['suburb'].toString(),
      if (address['neighbourhood'] != null) address['neighbourhood'].toString(),
      if (address['road'] != null) address['road'].toString(),
      if (address['building'] != null) address['building'].toString(),
    ];
    return parts.where((s) => s.isNotEmpty).join(' · ');
  }

  String _statusText(String s) {
    return s == 'draft' ? '草稿' : s == 'in_progress' ? '施工中' : '已完成';
  }

  Color _statusColor(String s) {
    return s == 'draft' ? const Color(0xFF8A8894) : s == 'in_progress' ? const Color(0xFF4A9E6E) : const Color(0xFF5B8EC4);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('我的项目', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: Icon(_showForm ? Icons.close : Icons.add),
            onPressed: () => setState(() => _showForm = !_showForm),
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const LoadingSkeleton(itemHeight: 80);
    }
    if (_error != null) {
      return ErrorRetryWidget(
        message: _error!,
        onRetry: _load,
      );
    }
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final textPrimary = SuokeDesignTokens.text(context);
    final textSub = SuokeDesignTokens.textSub(context);
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_showForm) ...[
            _buildCreateForm(),
            const SizedBox(height: 16),
          ],
          if (_projects.isEmpty && !_showForm)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(48),
                child: Column(
                  children: [
                    const Icon(Icons.home_work_outlined, size: 48, color: SuokeDesignTokens.textMuted),
                    const SizedBox(height: 12),
                    const Text('还没有项目，点击下方按钮创建', style: TextStyle(color: SuokeDesignTokens.textMuted)),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: () => setState(() => _showForm = true),
                      icon: const Icon(Icons.add, size: 18),
                      label: const Text('创建项目'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: SuokeDesignTokens.accent,
                        side: const BorderSide(color: SuokeDesignTokens.accent),
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            ..._projects.map((p) => Card(
              child: InkWell(
                onTap: () async {
                  final deleted = await Navigator.push<bool>(
                    context,
                    MaterialPageRoute(
                      builder: (_) => ProjectDetailPage(
                        projectId: p.id,
                      ),
                    ),
                  );
                  if (deleted == true) _load();
                },
                borderRadius: BorderRadius.circular(12),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              p.name,
                              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: textPrimary),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: _statusColor(p.status.value).withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(100),
                            ),
                            child: Text(
                              _statusText(p.status.value),
                              style: TextStyle(fontSize: 12, color: _statusColor(p.status.value)),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${p.address ?? '未填写地址'} · ${_fmtArea(p.totalArea)}㎡',
                        style: TextStyle(color: textSub, fontSize: 13),
                      ),
                    ],
                  ),
                ),
              ),
            )),
        ],
      ),
    );
  }

  /// 创建项目表单（满宽卡片）
  Widget _buildCreateForm() {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    const accent = Color(0xFFC9973B);
    final cardBg = isDark ? const Color(0xFF12121D) : Colors.white;
    final textPrimary = isDark ? const Color(0xFFE8E6E1) : const Color(0xFF1A1814);
    final textSecondary = isDark ? const Color(0xFF8A8894) : const Color(0xFF6B6760);
    final border = isDark ? const Color(0xFF2A2A3A) : const Color(0xFFE8E5DE);

    Widget stepper(String label, int value, int min, int max, Function(int) onChanged) {
      return Column(
        children: [
          Text(label, style: TextStyle(color: textSecondary, fontSize: 12)),
          const SizedBox(height: 6),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              GestureDetector(
                onTap: value > min ? () => onChanged(value - 1) : null,
                child: Container(
                  width: 32, height: 32,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: value > min ? accent : border),
                    color: value > min ? accent.withValues(alpha: 0.1) : Colors.transparent,
                  ),
                  child: Icon(Icons.remove, size: 18, color: value > min ? accent : textSecondary),
                ),
              ),
              const SizedBox(width: 12),
              SizedBox(
                width: 28,
                child: Text('$value', textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: textPrimary)),
              ),
              const SizedBox(width: 12),
              GestureDetector(
                onTap: value < max ? () => onChanged(value + 1) : null,
                child: Container(
                  width: 32, height: 32,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: value < max ? accent : border),
                    color: value < max ? accent.withValues(alpha: 0.1) : Colors.transparent,
                  ),
                  child: Icon(Icons.add, size: 18, color: value < max ? accent : textSecondary),
                ),
              ),
            ],
          ),
        ],
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── 项目名称 ──
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: cardBg,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('项目名称', style: TextStyle(color: textSecondary, fontSize: 12, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              TextField(
                controller: _nameCtrl,
                style: TextStyle(color: textPrimary, fontSize: 16),
                decoration: InputDecoration(
                  hintText: '例如：朝阳小区 3-1-502',
                  hintStyle: TextStyle(color: textSecondary.withValues(alpha: 0.5)),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide(color: border),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide(color: border),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: const BorderSide(color: accent),
                  ),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),

        // ── 户型选择 ──
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: cardBg,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('户型信息', style: TextStyle(color: textSecondary, fontSize: 12, fontWeight: FontWeight.w600)),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  stepper('楼层', _floors, 1, 5, (v) => setState(() => _floors = v)),
                  stepper('室', _bedrooms, 1, 8, (v) => setState(() => _bedrooms = v)),
                  stepper('厅', _livingRooms, 1, 4, (v) => setState(() => _livingRooms = v)),
                  stepper('厨', _kitchens, 1, 2, (v) => setState(() => _kitchens = v)),
                  stepper('卫', _bathrooms, 1, 6, (v) => setState(() => _bathrooms = v)),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                '$_floors层 · $_bedrooms室$_livingRooms厅$_kitchens厨$_bathrooms卫',
                style: TextStyle(color: textSecondary, fontSize: 13),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _areaCtrl,
                style: TextStyle(color: textPrimary, fontSize: 16),
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: '面积 (㎡)',
                  labelStyle: TextStyle(color: textSecondary, fontSize: 14),
                  hintText: '126',
                  hintStyle: TextStyle(color: textSecondary.withValues(alpha: 0.5)),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide(color: border),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide(color: border),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: const BorderSide(color: accent),
                  ),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),

        // ── 项目位置 ──
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: cardBg,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('项目位置', style: TextStyle(color: textSecondary, fontSize: 12, fontWeight: FontWeight.w600)),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _locationCtrl,
                      style: TextStyle(color: textPrimary, fontSize: 15),
                      onChanged: (v) => _searchLocation(v),
                      decoration: InputDecoration(
                        hintText: '搜索小区/街道/楼盘名称',
                        hintStyle: TextStyle(color: textSecondary.withValues(alpha: 0.5)),
                        prefixIcon: Icon(Icons.search, color: textSecondary, size: 20),
                        suffixIcon: _locationCtrl.text.isNotEmpty
                            ? IconButton(
                                icon: Icon(Icons.clear, color: textSecondary, size: 18),
                                onPressed: () {
                                  _locationCtrl.clear();
                                  setState(() => _locationResults = []);
                                },
                              )
                            : null,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: BorderSide(color: border),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: BorderSide(color: border),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: const BorderSide(color: accent),
                        ),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  // 自动定位按钮
                  GestureDetector(
                    onTap: _locating ? null : _autoLocate,
                    child: Container(
                      width: 44, height: 44,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: accent),
                        color: accent.withValues(alpha: 0.1),
                      ),
                      child: _locating
                          ? const SizedBox(
                              width: 20, height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2, color: accent),
                            )
                          : const Icon(Icons.my_location, color: accent, size: 22),
                    ),
                  ),
                ],
              ),
              if (_locationError != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(_locationError!, style: const TextStyle(color: Color(0xFFE57373), fontSize: 12)),
                ),
              // 搜索结果列表
              if (_locationResults.isNotEmpty) ...[
                const SizedBox(height: 8),
                Container(
                  constraints: const BoxConstraints(maxHeight: 180),
                  decoration: BoxDecoration(
                    border: Border.all(color: border),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: _locationResults.length,
                    separatorBuilder: (_, _) => Divider(height: 1, color: border),
                    itemBuilder: (ctx, i) {
                      final item = _locationResults[i];
                      final name = (item['name'] as String?) ?? '';
                      final addr = (item['address'] as String?) ?? '';
                      final displayFull = name.isNotEmpty && addr.isNotEmpty
                          ? '$name\n$addr'
                          : (item['display_name'] as String?) ?? '';
                      final isSelected = item['selected'] == true;
                      return InkWell(
                        onTap: () {
                          _locationCtrl.text = name.isNotEmpty ? name : displayFull;
                          setState(() {
                            for (final r in _locationResults) {
                              r['selected'] = false;
                            }
                            item['selected'] = true;
                          });
                        },
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Padding(
                                padding: const EdgeInsets.only(top: 2),
                                child: Icon(
                                  isSelected ? Icons.location_on : Icons.location_on_outlined,
                                  color: isSelected ? accent : textSecondary,
                                  size: 18,
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    if (name.isNotEmpty)
                                      Text(
                                        name,
                                        style: TextStyle(
                                          color: isSelected ? accent : textPrimary,
                                          fontSize: 14,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                    if (addr.isNotEmpty)
                                      Text(
                                        addr,
                                        style: TextStyle(
                                          color: isSelected ? accent.withValues(alpha: 0.7) : textSecondary,
                                          fontSize: 12,
                                        ),
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    if (name.isEmpty && addr.isEmpty)
                                      Text(
                                        displayFull,
                                        style: TextStyle(
                                          color: isSelected ? accent : textPrimary,
                                          fontSize: 13,
                                        ),
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                  ],
                                ),
                              ),
                              if (isSelected)
                                const Icon(Icons.check, color: accent, size: 18),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
              if (_searchingLocation)
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: SizedBox(
                    height: 20,
                    child: LinearProgressIndicator(),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // ── 创建按钮 ──
        SizedBox(
          width: double.infinity,
          height: 50,
          child: ElevatedButton(
            onPressed: _submitting ? null : _create,
            style: ElevatedButton.styleFrom(
              backgroundColor: accent,
              foregroundColor: Colors.black,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
            ),
            child: _submitting
                ? const SizedBox(
                    width: 22, height: 22,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black),
                  )
                : const Text('创建项目'),
          ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _locationCtrl.dispose();
    _areaCtrl.dispose();
    super.dispose();
  }
}
