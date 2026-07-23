"""行业标准库 —— 装修验收清单 / 定额 / 规范引用

v1.1.31 FP-5 修复（S4）：原 QUALITY_CHECKLISTS 仅存在于 ConstructionAgent 内部，
quality_service 无法引用，导致"验收清单"与"质量问题"两套数据割裂。
现提取为共享标准库，供 ConstructionAgent + quality_service 共同使用。
"""
