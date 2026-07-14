// 索克家居
import 'package:flutter/material.dart';

/// 设计深化页面 - 方案迭代历史
class DesignDeepeningPage extends StatefulWidget {
  final String projectId;
  const DesignDeepeningPage({super.key, required this.projectId});
  @override
  State<DesignDeepeningPage> createState() => _DesignDeepeningPageState();
}

class _DesignDeepeningPageState extends State<DesignDeepeningPage> {
  int? _expandedIndex;

  final List<Map<String, dynamic>> _plans = [
    {
      'name': '现代简约 · 方案 A',
      'style': '现代简约',
      'created': '2026-07-10',
      'status': '深化中',
      'space': '客餐厅一体化 · 主卧套房 · 干湿分离卫生间',
      'materials': '750×1500 大板砖 · 实木复合地板 · 艺术漆墙面',
      'budget': '18.5 万',
    },
    {
      'name': '轻奢风格 · 方案 B',
      'style': '轻奢风',
      'created': '2026-07-08',
      'status': '已完成',
      'space': '双厅分离 · 独立书房 · 步入式衣帽间',
      'materials': '大理石纹瓷砖 · 定制护墙板 · 黄铜五金',
      'budget': '28.0 万',
    },
    {
      'name': '北欧原木 · 方案 C',
      'style': '北欧风',
      'created': '2026-07-05',
      'status': '等待审批',
      'space': '开放式厨房 · 多功能次卧 · 阳台花园',
      'materials': '橡木地板 · 小白砖 · 原木家具',
      'budget': '15.2 万',
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('设计深化'),
        backgroundColor: const Color(0xFF12121D),
        foregroundColor: Colors.white,
      ),
      body: Container(
        color: const Color(0xFF0E0E1A),
        child: ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: _plans.length,
          itemBuilder: (ctx, i) {
            final plan = _plans[i];
            final expanded = _expandedIndex == i;
            final statusColor = plan['status'] == '已完成'
                ? const Color(0xFF4A9E6E)
                : plan['status'] == '深化中'
                    ? const Color(0xFFC9973B)
                    : const Color(0xFF8A8894);
            return Card(
              color: const Color(0xFF1A1A2E),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              child: InkWell(
                borderRadius: BorderRadius.circular(12),
                onTap: () =>
                    setState(() => _expandedIndex = expanded ? null : i),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(children: [
                        Expanded(
                          child: Text(plan['name'],
                              style: const TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 15)),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: statusColor.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(plan['status'],
                              style:
                                  TextStyle(color: statusColor, fontSize: 11)),
                        ),
                      ]),
                      const SizedBox(height: 6),
                      Row(children: [
                        _tag(plan['style']),
                        const SizedBox(width: 8),
                        Text(plan['created'],
                            style: const TextStyle(
                                color: Color(0xFF8A8894), fontSize: 11)),
                      ]),
                      if (expanded) ...[
                        const Divider(
                            color: Color(0xFF2A2A3E), height: 24),
                        _detailRow('📍 空间规划', plan['space']),
                        _detailRow('🧱 材料清单', plan['materials']),
                        _detailRow('💰 预算预估', plan['budget']),
                        const SizedBox(height: 12),
                        Row(
                            mainAxisAlignment: MainAxisAlignment.end,
                            children: [
                              TextButton.icon(
                                onPressed: () {},
                                icon: const Icon(Icons.edit, size: 16),
                                label: const Text('编辑方案'),
                                style: TextButton.styleFrom(
                                    foregroundColor:
                                        const Color(0xFFC9973B)),
                              ),
                              TextButton.icon(
                                onPressed: () {},
                                icon:
                                    const Icon(Icons.compare_arrows, size: 16),
                                label: const Text('对比方案'),
                                style: TextButton.styleFrom(
                                    foregroundColor:
                                        const Color(0xFF5A7EC9)),
                              ),
                            ]),
                      ],
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {},
        backgroundColor: const Color(0xFFC9973B),
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }

  Widget _tag(String text) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
        decoration: BoxDecoration(
          color: const Color(0xFFC9973B).withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(text,
            style:
                const TextStyle(color: Color(0xFFC9973B), fontSize: 10)),
      );

  Widget _detailRow(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
                width: 100,
                child: Text(label,
                    style: const TextStyle(
                        color: Color(0xFF8A8894), fontSize: 12))),
            Expanded(
                child: Text(value,
                    style:
                        const TextStyle(color: Colors.white, fontSize: 12))),
          ],
        ),
      );
}
