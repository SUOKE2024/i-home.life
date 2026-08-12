import 'package:flutter/material.dart';
import '../theme/suoke_theme.dart';
import '../services/api.dart';

/// 位置服务页：POI 搜索 + 地理编码（后端 /location/* 高德代理）。
///
/// 后端未配置 amap_api_key 时返回 demo 空结果，页面按空态展示。
class LocationPage extends StatefulWidget {
  const LocationPage({super.key});

  @override
  State<LocationPage> createState() => _LocationPageState();
}

class _LocationPageState extends State<LocationPage> {
  final ApiClient _api = ApiClient();

  final TextEditingController _searchCtrl = TextEditingController();
  final TextEditingController _geocodeCtrl = TextEditingController();

  // POI 搜索
  List<Map<String, dynamic>> _pois = [];
  bool _searching = false;
  bool _hasSearched = false;
  String? _searchError;

  // 地理编码
  Map<String, dynamic>? _geocodeResult;
  bool _geocoding = false;
  bool _hasGeocoded = false;
  String? _geocodeError;

  @override
  void dispose() {
    _searchCtrl.dispose();
    _geocodeCtrl.dispose();
    super.dispose();
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  // ── POI 搜索 ──

  Future<void> _doSearch() async {
    final kw = _searchCtrl.text.trim();
    if (kw.isEmpty) {
      _showSnack('请输入搜索关键词');
      return;
    }
    setState(() {
      _searching = true;
      _hasSearched = true;
      _searchError = null;
    });
    final result = await _api.searchLocation({'keywords': kw, 'city': ''});
    if (!mounted) return;
    setState(() {
      _searching = false;
      if (result.isSuccess) {
        _pois = _parsePois(result.data);
      } else {
        _pois = [];
        _searchError = '搜索失败：${result.error ?? '未知错误'}';
      }
    });
  }

  /// 防御性解析 POI 列表：pois 可能是 List，元素可能是任意 Map
  List<Map<String, dynamic>> _parsePois(dynamic data) {
    final list = <Map<String, dynamic>>[];
    if (data is Map) {
      final pois = data['pois'];
      if (pois is List) {
        for (final p in pois) {
          if (p is Map) {
            list.add(Map<String, dynamic>.from(p));
          }
        }
      }
    } else if (data is List) {
      for (final p in data) {
        if (p is Map) {
          list.add(Map<String, dynamic>.from(p));
        }
      }
    }
    return list;
  }

  // ── 地理编码 ──

  Future<void> _doGeocode() async {
    final addr = _geocodeCtrl.text.trim();
    if (addr.isEmpty) {
      _showSnack('请输入地址');
      return;
    }
    setState(() {
      _geocoding = true;
      _hasGeocoded = true;
      _geocodeError = null;
      _geocodeResult = null;
    });
    final result = await _api.geocodeLocation({'address': addr});
    if (!mounted) return;
    setState(() {
      _geocoding = false;
      if (result.isSuccess) {
        final data = result.data;
        if (data is Map && data['result'] is Map) {
          _geocodeResult = Map<String, dynamic>.from(data['result'] as Map);
        } else if (data is Map) {
          _geocodeResult = Map<String, dynamic>.from(data);
        } else {
          _geocodeResult = null;
        }
      } else {
        _geocodeResult = null;
        _geocodeError = '地理编码失败：${result.error ?? '未知错误'}';
      }
    });
  }

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.bg(context),
        title: Text('位置服务',
            style: TextStyle(color: SuokeDesignTokens.text(context))),
        iconTheme: IconThemeData(color: SuokeDesignTokens.text(context)),
      ),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          _buildSectionTitle('POI 搜索'),
          _buildSearchInput(),
          const SizedBox(height: 12),
          _buildSearchResult(),
          const SizedBox(height: 20),
          _buildSectionTitle('地理编码'),
          _buildGeocodeInput(),
          const SizedBox(height: 12),
          _buildGeocodeResult(),
          const SizedBox(height: 16),
          _buildDemoNotice(),
        ],
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: const TextStyle(
          color: SuokeDesignTokens.accent,
          fontSize: 13,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildSearchInput() {
    return Row(
      children: [
        Expanded(
          child: TextField(
            controller: _searchCtrl,
            style: TextStyle(color: SuokeDesignTokens.text(context)),
            decoration: InputDecoration(
              hintText: '搜索地点，如：杭州东站',
              hintStyle: TextStyle(color: SuokeDesignTokens.textSub(context)),
              prefixIcon:
                  Icon(Icons.search, color: SuokeDesignTokens.textSub(context)),
              filled: true,
              fillColor: SuokeDesignTokens.card(context),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide:
                    BorderSide(color: SuokeDesignTokens.borderClr(context)),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: SuokeDesignTokens.accent),
              ),
            ),
            onSubmitted: (_) => _doSearch(),
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          height: 48,
          child: ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: SuokeDesignTokens.accent,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            onPressed: _searching ? null : _doSearch,
            child: Text('搜索',
                style: TextStyle(color: SuokeDesignTokens.bg(context))),
          ),
        ),
      ],
    );
  }

  Widget _buildSearchResult() {
    if (_searching) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 32),
        child: Center(
          child: CircularProgressIndicator(color: SuokeDesignTokens.accent),
        ),
      );
    }
    if (!_hasSearched) {
      return _buildInlineEmpty('输入关键词搜索周边地点', Icons.search);
    }
    if (_searchError != null) {
      return _buildInlineError(_searchError!);
    }
    if (_pois.isEmpty) {
      return _buildInlineEmpty('未找到相关地点', Icons.location_off_outlined);
    }
    return Column(
      children: [
        for (final poi in _pois) _buildPoiCard(poi),
      ],
    );
  }

  Widget _buildPoiCard(Map<String, dynamic> poi) {
    final name = poi['name']?.toString() ?? '未命名地点';
    final address = poi['address']?.toString() ?? '';
    final location = poi['location']?.toString() ?? '';
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.location_on_outlined,
                  color: SuokeDesignTokens.accent, size: 16),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: SuokeDesignTokens.text(context),
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          if (address.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              address,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                  color: SuokeDesignTokens.textSub(context), fontSize: 12),
            ),
          ],
          if (location.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              '坐标：$location',
              style: TextStyle(
                  color: SuokeDesignTokens.textSub(context), fontSize: 11),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildGeocodeInput() {
    return Row(
      children: [
        Expanded(
          child: TextField(
            controller: _geocodeCtrl,
            style: TextStyle(color: SuokeDesignTokens.text(context)),
            decoration: InputDecoration(
              hintText: '输入结构化地址，如：杭州市西湖区文三路 138 号',
              hintStyle: TextStyle(color: SuokeDesignTokens.textSub(context)),
              prefixIcon: Icon(Icons.place_outlined,
                  color: SuokeDesignTokens.textSub(context)),
              filled: true,
              fillColor: SuokeDesignTokens.card(context),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide:
                    BorderSide(color: SuokeDesignTokens.borderClr(context)),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: SuokeDesignTokens.accent),
              ),
            ),
            onSubmitted: (_) => _doGeocode(),
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          height: 48,
          child: ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: SuokeDesignTokens.accent,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            onPressed: _geocoding ? null : _doGeocode,
            child: Text('解析',
                style: TextStyle(color: SuokeDesignTokens.bg(context))),
          ),
        ),
      ],
    );
  }

  Widget _buildGeocodeResult() {
    if (_geocoding) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 32),
        child: Center(
          child: CircularProgressIndicator(color: SuokeDesignTokens.accent),
        ),
      );
    }
    if (!_hasGeocoded) {
      return _buildInlineEmpty('输入地址解析为坐标', Icons.map_outlined);
    }
    if (_geocodeError != null) {
      return _buildInlineError(_geocodeError!);
    }
    final r = _geocodeResult;
    if (r == null || r.isEmpty) {
      return _buildInlineEmpty('未解析到结果', Icons.map_outlined);
    }
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _detailRow('地址', r['formatted_address']?.toString() ?? '—'),
          _detailRow('城市', r['city']?.toString() ?? '—'),
          _detailRow('区县', r['district']?.toString() ?? '—'),
          _detailRow('坐标', r['location']?.toString() ?? '—'),
        ],
      ),
    );
  }

  Widget _detailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 64,
            child: Text(label,
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 13)),
          ),
          Expanded(
            child: Text(value,
                style: TextStyle(
                    color: SuokeDesignTokens.text(context), fontSize: 13)),
          ),
        ],
      ),
    );
  }

  Widget _buildInlineEmpty(String message, IconData icon) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 24),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 40, color: SuokeDesignTokens.textSub(context)),
            const SizedBox(height: 8),
            Text(message,
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 13)),
          ],
        ),
      ),
    );
  }

  Widget _buildInlineError(String message) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.danger.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border:
            Border.all(color: SuokeDesignTokens.danger.withValues(alpha: 0.4)),
      ),
      child: Text(message,
          style: const TextStyle(color: SuokeDesignTokens.danger, fontSize: 13)),
    );
  }

  Widget _buildDemoNotice() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.bg(context),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline,
              size: 16, color: SuokeDesignTokens.textSub(context)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '说明：后端未配置高德 amap_api_key 时，位置接口返回演示空结果，页面按空态展示。',
              style: TextStyle(
                  color: SuokeDesignTokens.textSub(context), fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }
}
