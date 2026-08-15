"""家装领域本体基座（P0 本体/领域知识基座）

对齐 Brick Schema / BOT（Building Topology Ontology）/ IFC（ISO 16739）的术语与关系，
输出确定性 JSON 本体，供：
- ``spatial_semantics_service``（空间语义对齐开放本体）
- ``agent_identity_card``（Agent 能力描述对齐 GB/Z 185 ACDL 思路）
- ``agent_governance_audit`` / 控制台「标准对齐」页 / 论文引用

三个本体文件（确定性知识基座，非 RDF/OWL 推理引擎，模块化单体红线）：
- ``renovation_ontology.json``：空间 / 构件 / 关系本体
- ``agent_ontology.json``：25 Agent + 1 Orchestrator 能力 / 审批边界
- ``material_ontology.json``：材质 / 环保等级 / 工艺（对齐 GB 18580 ENF/E0、HC-003）

诚实边界：本包为「对齐开放本体的确定性 JSON 知识基座」，不引入 RDF/OWL 推理、
不依赖外部本体服务，仅以 JSON 表达术语与关系供检索 / 映射 / 引用。
"""

# 可用本体领域（与 app/ontology/*_ontology.json 文件名前缀一一对应）
ONTOLOGY_DOMAINS: tuple[str, ...] = ("renovation", "agent", "material")

__all__ = ["ONTOLOGY_DOMAINS"]
