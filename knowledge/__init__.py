"""装修知识库 — 结构化装修知识管理与来源引用

提供知识库加载、检索和来源引用能力，供 AgenticRAG 和 QA/Design Agent 使用。

知识域（8 个）：
1. materials      材质库（板材/瓷砖/涂料/石材/五金等）
2. techniques     施工工艺（水电/泥瓦/木工/油漆等工序标准）
3. standards      验收标准（GB 50210/GB 50327/GB 50300 等国标引用）
4. eco_ratings    环保等级（E0/E1/ENF 标准解读及适用范围）
5. safety         安全规范（承重结构/消防/燃气/电气安全）
6. design_rules   设计规范（空间尺寸/动线/采光/无障碍）
7. cost_reference 造价参考（各工种市场价区间/地区差异系数）
8. faq            常见问题（装修流程/避坑指南/选材建议）
"""

from knowledge.loader import KnowledgeLoader, load_knowledge_base

__all__ = ["KnowledgeLoader", "load_knowledge_base"]
