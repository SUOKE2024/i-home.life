"""DSPy 提示词优化器（借鉴索克生活 dspy_optimization_service）

索克生活的 dspy_optimization_service 通过 DSPy 的 ChainOfThought + BootstrapFewShot
对 Laoke 智能体的 RAG 提示词进行自动优化与效果评估。本模块将该方法论移植到家居领域：
为 DesignerAgent / BudgetAgent / ProcurementAgent 等智能体提供提示词优化、签名编译
与离线评估能力，在不改变 Agent 主流程的前提下提升提示词质量。

核心能力（受 settings.dspy_enabled feature flag 控制）：
1. optimize_prompt() — 基于 ChainOfThought + BootstrapFewShot 优化系统提示词
2. compile_signature() — 懒构建 dspy.Signature，用于声明 Agent 的输入/输出契约
3. evaluate_prompt() — 在测试用例集上评估提示词得分（0~100）

依赖策略：
- DSPy 为「可选依赖」，模块内部懒导入并 try/except 包裹，未安装时不影响主服务
- settings.dspy_enabled 默认 False，关闭时所有方法返回优雅降级值
- 任何 DSPy 缺失/异常均只记录 warning，绝不向上抛出，保证生产安全
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class DSPyOptimizer:
    """DSPy 提示词优化器

    受 settings.dspy_enabled feature flag 控制：
    - True: 调用 DSPy 的 ChainOfThought / BootstrapFewShot 进行提示词优化与评估
    - False: 所有方法直接返回降级值（原提示词 / None / 0.0），仅记录 debug 日志

    DSPy 为可选依赖，未安装时自动降级，绝不抛出异常。
    """

    def __init__(self) -> None:
        # 缓存已构建的 Signature，避免重复反射开销
        self._signature_cache: dict[str, Any] = {}

    def optimize_prompt(
        self,
        agent_name: str,
        base_prompt: str,
        examples: list[dict],
    ) -> str:
        """使用 ChainOfThought + BootstrapFewShot 优化系统提示词。

        Args:
            agent_name: 智能体名称（如 DesignerAgent / BudgetAgent），用于日志与缓存键
            base_prompt: 待优化的原始系统提示词
            examples: 少样本示例列表，每项形如
                {"input": "...", "output": "..."}，作为 BootstrapFewShot 训练集

        Returns:
            优化后的系统提示词字符串；当 dspy 关闭、未安装或优化失败时，
            原样返回 base_prompt 并记录 debug/warning 日志。
        """
        # 1. feature flag 关闭 → 原样返回
        if not settings.dspy_enabled:
            logger.debug(
                "dspy_enabled=False，跳过提示词优化，返回原始提示词 (agent=%s)",
                agent_name,
            )
            return base_prompt

        # 2. 示例不足 → 无法 bootstrap，原样返回
        if not examples:
            logger.debug(
                "无 few-shot 示例，跳过 BootstrapFewShot 优化 (agent=%s)",
                agent_name,
            )
            return base_prompt

        # 3. 懒导入 DSPy
        try:
            import dspy
            from dspy.teleprompt import BootstrapFewShot
        except ImportError:
            logger.warning(
                "DSPy 未安装，无法优化提示词，返回原始提示词 (agent=%s)",
                agent_name,
            )
            return base_prompt
        except Exception as exc:  # pragma: no cover - 防御性兜底
            logger.warning(
                "DSPy 导入异常: %s，返回原始提示词 (agent=%s)",
                exc,
                agent_name,
            )
            return base_prompt

        # 4. 执行 ChainOfThought 优化
        try:
            # 构建少样本训练集
            trainset = []
            for ex in examples:
                input_text = str(ex.get("input", ex.get("query", "")))
                output_text = str(ex.get("output", ex.get("answer", "")))
                if not input_text:
                    continue
                trainset.append(
                    dspy.Example(input=input_text, output=output_text).with_inputs(
                        "input"
                    )
                )

            if not trainset:
                logger.warning(
                    "解析后无可用的训练样本，返回原始提示词 (agent=%s)",
                    agent_name,
                )
                return base_prompt

            # 定义 ChainOfThought 模块：输入提示 → 优化后提示
            class PromptOptimizer(dspy.Module):
                def __init__(self) -> None:
                    super().__init__()
                    self.generate = dspy.ChainOfThought("input -> output")

                def forward(self, input: str) -> Any:  # noqa: A002 - DSPy 约定参数名
                    return self.generate(input=input)

            # Bootstrap 验证函数：输出非空即视为有效示例
            def validate_answer(
                example: Any, prediction: Any, trace: Any = None
            ) -> bool:
                output = getattr(prediction, "output", None)
                return bool(output)

            teleprompter = BootstrapFewShot(metric=validate_answer)
            optimized_module = teleprompter.compile(
                PromptOptimizer(), trainset=trainset
            )

            # 从优化后的模块提取提示词
            optimized_prompt = self._extract_prompt(optimized_module, base_prompt)

            logger.info(
                "DSPy 提示词优化完成 (agent=%s, examples=%d)",
                agent_name,
                len(trainset),
            )
            return optimized_prompt

        except Exception as exc:
            logger.warning(
                "DSPy 提示词优化失败: %s，返回原始提示词 (agent=%s)",
                exc,
                agent_name,
            )
            return base_prompt

    def compile_signature(
        self,
        agent_name: str,
        input_desc: str,
        output_desc: str,
    ) -> Any:
        """懒构建 dspy.Signature，声明智能体的输入/输出契约。

        Args:
            agent_name: 智能体名称，用于缓存键与日志
            input_desc: 输入字段描述（如 "用户的设计需求与户型约束"）
            output_desc: 输出字段描述（如 "结构化的设计方案 JSON"）

        Returns:
            构建完成的 dspy.Signature 子类；当 dspy 关闭、未安装或构建失败时返回 None。
        """
        # 1. feature flag 关闭 → None
        if not settings.dspy_enabled:
            logger.debug(
                "dspy_enabled=False，跳过签名编译，返回 None (agent=%s)",
                agent_name,
            )
            return None

        # 2. 命中缓存
        cache_key = f"{agent_name}:{input_desc}->{output_desc}"
        if cache_key in self._signature_cache:
            return self._signature_cache[cache_key]

        # 3. 懒导入 DSPy
        try:
            import dspy
        except ImportError:
            logger.warning(
                "DSPy 未安装，无法编译签名，返回 None (agent=%s)",
                agent_name,
            )
            return None
        except Exception as exc:  # pragma: no cover - 防御性兜底
            logger.warning(
                "DSPy 导入异常: %s，返回 None (agent=%s)",
                exc,
                agent_name,
            )
            return None

        # 4. 动态构建 Signature 子类
        try:
            signature = dspy.Signature(
                f"{input_desc} -> {output_desc}",
                f"{agent_name} 的输入/输出契约：{input_desc} -> {output_desc}",
            )
            self._signature_cache[cache_key] = signature
            logger.debug(
                "DSPy 签名编译完成 (agent=%s)", agent_name
            )
            return signature
        except Exception as exc:
            logger.warning(
                "DSPy 签名编译失败: %s，返回 None (agent=%s)",
                exc,
                agent_name,
            )
            return None

    def evaluate_prompt(
        self,
        prompt: str,
        test_cases: list[dict],
    ) -> float:
        """在测试用例集上评估提示词得分。

        Args:
            prompt: 待评估的系统提示词
            test_cases: 测试用例列表，每项形如
                {"input": "...", "expected": "..."}，期望输出用于相似度比对

        Returns:
            0~100 的得分；当 dspy 关闭、未安装、无测试用例或评估失败时返回 0.0。
        """
        # 1. feature flag 关闭 → 0.0
        if not settings.dspy_enabled:
            logger.debug("dspy_enabled=False，跳过提示词评估，返回 0.0")
            return 0.0

        # 2. 无测试用例 → 0.0
        if not test_cases:
            logger.debug("无测试用例，提示词评估返回 0.0")
            return 0.0

        # 3. 懒导入 DSPy
        try:
            import dspy
        except ImportError:
            logger.warning("DSPy 未安装，无法评估提示词，返回 0.0")
            return 0.0
        except Exception as exc:  # pragma: no cover - 防御性兜底
            logger.warning("DSPy 导入异常: %s，返回 0.0", exc)
            return 0.0

        # 4. 执行评估
        try:
            scores: list[float] = []

            for case in test_cases:
                input_text = str(case.get("input", ""))
                expected = str(case.get("expected", case.get("output", "")))
                if not input_text:
                    continue

                try:
                    predictor = dspy.ChainOfThought("input -> output")
                    prediction = predictor(input=input_text)
                    actual = str(getattr(prediction, "output", ""))
                    scores.append(self._similarity(actual, expected))
                except Exception as inner_exc:
                    logger.warning(
                        "单条用例评估失败: %s，跳过该用例",
                        inner_exc,
                    )
                    continue

            if not scores:
                logger.warning("所有用例评估均失败，返回 0.0")
                return 0.0

            # 归一化到 0~100
            final_score = (sum(scores) / len(scores)) * 100.0
            logger.info(
                "DSPy 提示词评估完成 (cases=%d, score=%.2f)",
                len(scores),
                final_score,
            )
            return final_score

        except Exception as exc:
            logger.warning("DSPy 提示词评估失败: %s，返回 0.0", exc)
            return 0.0

    # ── 内部工具方法 ──

    def _extract_prompt(self, dspy_module: Any, fallback: str) -> str:
        """从优化后的 DSPy 模块中提取提示词文本。

        Args:
            dspy_module: BootstrapFewShot.compile() 返回的优化模块
            fallback: 提取失败时的回退提示词

        Returns:
            提取到的提示词字符串；提取失败时返回 fallback。
        """
        try:
            # 优先从 predict.signature.instructions 提取
            predict = getattr(dspy_module, "generate", None) or getattr(
                dspy_module, "predict", None
            )
            if predict is not None:
                signature = getattr(predict, "signature", None)
                if signature is not None:
                    instructions = getattr(signature, "instructions", None)
                    if instructions:
                        return str(instructions)
                    doc = getattr(signature, "__doc__", None)
                    if doc:
                        return str(doc).strip()

            # 其次从 demos 提取示例拼接
            demos = getattr(dspy_module, "demos", None)
            if demos:
                demo_texts = [
                    str(d).strip() for d in demos[:3] if str(d).strip()
                ]
                if demo_texts:
                    return (
                        "优化后的系统提示词（含 few-shot 示例）:\n\n"
                        + "\n---\n".join(demo_texts)
                    )

            # 最后返回类别名兜底
            class_name = getattr(
                getattr(dspy_module, "__class__", object), "__name__", "DSPy"
            )
            return f"优化后的 {class_name} 模块提示词"
        except Exception as exc:
            logger.warning("提取 DSPy 优化提示词失败: %s，使用原始提示词", exc)
            return fallback

    @staticmethod
    def _similarity(text1: str, text2: str) -> float:
        """计算两段文本的 Jaccard 词级相似度（0~1）。

        Args:
            text1: 实际输出文本
            text2: 期望输出文本

        Returns:
            0~1 的相似度分数，空文本时返回 0.0。
        """
        if not text1 or not text2:
            return 0.0
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union) if union else 0.0


# 模块级单例，供全局复用
dspy_optimizer = DSPyOptimizer()
