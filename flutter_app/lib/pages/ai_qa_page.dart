import 'dart:async';
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// F47 AI 装修问答页面（v1.5.0）
class AIQAPage extends StatefulWidget {
  final String projectId;
  const AIQAPage({super.key, required this.projectId});

  @override
  State<AIQAPage> createState() => _AIQAPageState();
}

class _AIQAPageState extends State<AIQAPage> {
  final ApiClient _api = ApiClient();
  final TextEditingController _queryCtrl = TextEditingController();

  bool _faqLoading = true;
  String? _faqError;
  List<dynamic> _topics = [];

  bool _searching = false;
  Map<String, dynamic>? _result;
  String? _searchError;

  @override
  void initState() {
    super.initState();
    _loadFaq();
  }

  @override
  void dispose() {
    _queryCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadFaq() async {
    setState(() {
      _faqLoading = true;
      _faqError = null;
    });
    final result = await _api.aiQaFaq();
    if (!mounted) return;
    if (result.isSuccess && result.data is Map) {
      final data = result.data as Map<String, dynamic>;
      final topics = data['topics'];
      setState(() {
        _topics = topics is List ? topics : [];
        _faqLoading = false;
      });
    } else {
      setState(() {
        _faqError = result.error ?? 'FAQ 加载失败';
        _faqLoading = false;
      });
    }
  }

  Future<void> _search() async {
    final query = _queryCtrl.text.trim();
    if (query.isEmpty) {
      _toast('请输入搜索内容');
      return;
    }
    if (_searching) return;
    setState(() {
      _searching = true;
      _searchError = null;
    });
    final result = await _api.aiQaSearch(query);
    if (!mounted) return;
    setState(() => _searching = false);
    if (result.isSuccess && result.data is Map) {
      setState(() => _result = result.data as Map<String, dynamic>);
    } else {
      setState(() => _searchError = result.error ?? '搜索失败，请稍后重试');
    }
  }

  List<dynamic> _sources() {
    if (_result == null) return [];
    final sources = _result!['sources'];
    return sources is List ? sources : [];
  }

  String _matchTypeLabel(String? type) {
    switch (type) {
      case 'knowledge_base':
        return '知识库命中';
      case 'no_match':
        return '未命中';
      default:
        return type ?? '-';
    }
  }

  Color _matchTypeColor(String? type) {
    switch (type) {
      case 'knowledge_base':
        return SuokeDesignTokens.success;
      case 'no_match':
        return SuokeDesignTokens.warning;
      default:
        return SuokeDesignTokens.info;
    }
  }

  void _toast(String msg) {
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.card(context),
        foregroundColor: SuokeDesignTokens.text(context),
        title: const Text('AI 装修问答'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          _buildSearchBar(),
          const SizedBox(height: 12),
          if (_searching)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Center(
                child: CircularProgressIndicator(
                    color: SuokeDesignTokens.accent),
              ),
            ),
          if (_searchError != null && !_searching)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(_searchError!,
                  textAlign: TextAlign.center,
                  style:
                      TextStyle(color: SuokeDesignTokens.textSub(context))),
            ),
          if (_result != null && !_searching) _buildResultCard(),
          const SizedBox(height: 16),
          _sectionTitle('常见问题 FAQ'),
          if (_faqLoading)
            const LoadingSkeleton(itemHeight: 80, itemCount: 3)
          else if (_faqError != null)
            ErrorRetryWidget(message: _faqError!, onRetry: _loadFaq)
          else if (_topics.isEmpty)
            _buildEmpty('暂无 FAQ')
          else
            for (final topic in _topics)
              _buildFaqCard(topic as Map<String, dynamic>),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Row(
      children: [
        Expanded(
          child: TextField(
            controller: _queryCtrl,
            style: TextStyle(color: SuokeDesignTokens.text(context)),
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _search(),
            decoration: InputDecoration(
              hintText: '输入装修问题，如：防水怎么做',
              hintStyle:
                  TextStyle(color: SuokeDesignTokens.textSub(context)),
              prefixIcon: Icon(Icons.search,
                  color: SuokeDesignTokens.textSub(context), size: 20),
            ),
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          height: 48,
          child: ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: SuokeDesignTokens.accent,
              foregroundColor: SuokeDesignTokens.bg(context),
            ),
            onPressed: _searching ? null : _search,
            icon: const Icon(Icons.send, size: 16),
            label: const Text('搜索'),
          ),
        ),
      ],
    );
  }

  Widget _buildResultCard() {
    final matchType = (_result!['match_type'] ?? '').toString();
    final sources = _sources();
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.smart_toy_outlined,
                    color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text('问答结果',
                      style: TextStyle(
                          color: SuokeDesignTokens.text(context),
                          fontSize: 15,
                          fontWeight: FontWeight.w600)),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: _matchTypeColor(matchType)
                        .withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _matchTypeLabel(matchType),
                    style: TextStyle(
                        color: _matchTypeColor(matchType), fontSize: 12),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(_result!['answer']?.toString() ?? '',
                style: TextStyle(
                    color: SuokeDesignTokens.text(context), fontSize: 14)),
            if (_result!['honest_note'] != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(_result!['honest_note'].toString(),
                    style: TextStyle(
                        color: SuokeDesignTokens.textSub(context),
                        fontSize: 12)),
              ),
            if (sources.isNotEmpty) ...[
              const SizedBox(height: 10),
              for (final source in sources)
                _buildSourceCard(source as Map<String, dynamic>),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSourceCard(Map<String, dynamic> source) {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.bg(context),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(source['title']?.toString() ?? '',
              style: TextStyle(
                  color: SuokeDesignTokens.text(context),
                  fontSize: 13,
                  fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Wrap(
            spacing: 12,
            runSpacing: 4,
            children: [
              Text('来源：${source['domain']?.toString() ?? '-'}',
                  style: TextStyle(
                      color: SuokeDesignTokens.textSub(context),
                      fontSize: 11)),
              if (source['citation'] != null &&
                  source['citation'].toString().isNotEmpty)
                Text('引用：${source['citation']}',
                    style: const TextStyle(
                        color: SuokeDesignTokens.accent, fontSize: 11)),
            ],
          ),
          const SizedBox(height: 4),
          Text(source['snippet']?.toString() ?? '',
              style: TextStyle(
                  color: SuokeDesignTokens.textSub(context),
                  fontSize: 12)),
        ],
      ),
    );
  }

  Widget _buildFaqCard(Map<String, dynamic> topic) {
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 14),
        childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
        leading: const Icon(Icons.help_outline,
            color: SuokeDesignTokens.accent, size: 20),
        title: Text(
          topic['name']?.toString() ?? '未命名话题',
          style: TextStyle(
              color: SuokeDesignTokens.text(context),
              fontSize: 14,
              fontWeight: FontWeight.w600),
        ),
        iconColor: SuokeDesignTokens.textSub(context),
        collapsedIconColor: SuokeDesignTokens.textSub(context),
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: Text(topic['content']?.toString() ?? '',
                style: TextStyle(
                    color: SuokeDesignTokens.text(context), fontSize: 13)),
          ),
          if (topic['citation'] != null &&
              topic['citation'].toString().isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text('引用：${topic['citation']}',
                    style: const TextStyle(
                        color: SuokeDesignTokens.accent, fontSize: 12)),
              ),
            ),
        ],
      ),
    );
  }

  Widget _sectionTitle(String text) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 10),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w600,
          color: SuokeDesignTokens.text(context),
        ),
      ),
    );
  }

  Widget _buildEmpty(String message) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 24),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Center(
        child: Text(message,
            style: TextStyle(
                color: SuokeDesignTokens.textSub(context), fontSize: 13)),
      ),
    );
  }
}
