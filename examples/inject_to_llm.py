"""examples/inject_to_llm.py —— 把情绪状态拼成 prompt 段落。

核心是这个函数：`build_block()`。

它输出**行为参数**，不是形容词。区别在于：

    形容词："你现在很生气"        → 模型可能还是客气地回一句
    行为参数："说 8 句，一句一行"  → 它真的会照做
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import EmotionEngine  # noqa: E402


def build_block(engine: EmotionEngine, obj_id: str,
                lexicon: list | None = None,
                pick: int = 5) -> str:
    """拼一段可以塞进 system prompt 或 user message 的文字。

    没有情绪（0 档）时返回空字符串 —— 别让模型看到"你现在很平静"这种废话。
    """
    st = engine.get(obj_id)
    if st["level"] <= 0:
        return ""

    block = st["hint"]

    # 词库：这一档能用的那几层，随机抽几条
    if lexicon:
        allowed = set(st["tiers"])
        pool = [x for x in lexicon if x.get("tag") in allowed]
        if pool:
            import random
            picked = random.sample(pool, min(pick, len(pool)))
            verbatim = st["behavior"].get("must_verbatim")
            if verbatim:
                block += "\n【这一轮必须原样发出去，一个字都别改】\n"
                block += "\n".join(f"· {x.get('text')}" for x in picked)
            else:
                block += "\n【可以用的句子（参考，不用照抄）】\n"
                block += "\n".join(f"- {x.get('text')}" for x in picked)

    return block


if __name__ == "__main__":
    # 演示：从 0 挨骂到 5 档，看每档注入什么
    path = "_ex.json"
    if os.path.exists(path):
        os.remove(path)

    e = EmotionEngine(path, cooldown_seconds=0)
    lexicon = [
        {"text": "你嘴上功夫比手上功夫利索多了", "tag": "seed"},
        {"text": "耗子扛枪窝里横", "tag": "seed"},
        {"text": "茅坑里的石头又臭又硬", "tag": "defense"},
        {"text": "你这种人也就这点出息", "tag": "heavy"},
    ]
    for msg in ["你个傻逼", "滚", "你妈死了"]:
        st = e.hit("demo", msg)
        print(f"\n--- 被骂「{msg}」→ {st['level']} 档 {st['name']} ---")
        print(build_block(e, "demo", lexicon))
    os.remove(path)
