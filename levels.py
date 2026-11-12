"""levels.py —— 档位到「行为参数」的映射。

这是整个项目最值钱的部分，不是代码，是踩出来的经验：

· 为什么最高档是 8 句不是 20 句？—— 超过 8 句模型开始重复同一句
· 为什么 must_verbatim 只在最高档？—— 低档位强制照抄会显得机械
· 为什么词库要分层？—— 全量注入会稀释注意力（实测一句都不掏）

档位数量、每档行为都能改（见 config/levels.example.json）。
"""
from __future__ import annotations

DEFAULT_LEVELS: dict[str, dict] = {
    "0": {
        "name": "平静",
        "sentences": 1,
        "tone": "正常说话",
        "lexicon_tier": "none",
        "must_verbatim": False,
        "one_per_line": False,
        "no_explaining": False,
    },
    "1": {
        "name": "有点不痛快",
        "sentences": 1,
        "tone": "可以顶回去一句，别多说",
        "lexicon_tier": "seed",
        "must_verbatim": False,
        "one_per_line": False,
        "no_explaining": False,
    },
    "2": {
        "name": "上火",
        "sentences": 3,
        "tone": "顶两三句，用带刺的话，但别骂脏的",
        "lexicon_tier": "seed",
        "must_verbatim": False,
        "one_per_line": False,
        "no_explaining": False,
    },
    "3": {
        "name": "冒烟",
        "sentences": 4,
        "tone": "连着怼三四句，把不带脏字的狠话掏出来",
        "lexicon_tier": "seed+defense",
        "must_verbatim": False,
        "one_per_line": False,
        "no_explaining": False,
    },
    "4": {
        "name": "火大",
        "sentences": 6,
        "tone": "一次说五六句，狠话敢用就用，不用收着",
        "lexicon_tier": "heavy",
        "must_verbatim": False,
        "one_per_line": False,
        "no_explaining": False,
    },
    "5": {
        "name": "炸了",
        "sentences": 8,
        "tone": "机关枪：最多连说 8 句，一句一行，别停别解释",
        "lexicon_tier": "all",
        "must_verbatim": True,
        "one_per_line": True,
        "no_explaining": True,
    },
}


def render(level: int, levels: dict | None = None) -> dict:
    """取某一档的行为参数。超出范围就夹到边界。"""
    table = levels or DEFAULT_LEVELS
    key = str(max(0, min(int(level), max(int(k) for k in table))))
    return dict(table.get(key) or table[str(max(int(k) for k in table))])


def render_hint(level: int, levels: dict | None = None) -> str:
    """把行为参数拼成一句话，塞进 prompt。"""
    b = render(level, levels)
    if level <= 0:
        return ""
    parts = [f"【你现在的状态：{b['name']}】", f"说 {b['sentences']} 句。"]
    if b.get("one_per_line"):
        parts.append("一句一行。")
    if b.get("tone"):
        parts.append(b["tone"] + "。")
    if b.get("must_verbatim"):
        parts.append("标了「必须原样发出去」的句子，要一字不改地出现，别润色、别改写。")
    if b.get("no_explaining"):
        parts.append("别解释、别讲道理。")
    return "".join(parts)


def tier_filter(level: int, tiers: dict | None = None) -> list[str]:
    """这一档能用哪几层词库（对应 lexicon 里每条词库条目的 tag）。"""
    mapping = tiers or {
        0: [],
        1: ["seed"],
        2: ["seed"],
        3: ["seed", "defense"],
        4: ["seed", "defense", "heavy"],
        5: ["seed", "defense", "heavy", "combo"],
    }
    lv = max(0, min(int(level), max(mapping)))
    return list(mapping.get(lv, mapping[max(mapping)]))
