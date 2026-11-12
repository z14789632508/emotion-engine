"""rules.py —— 什么话算攻击，加多少分。

规则是可配置的（见 config/rules.example.json）。这里是默认的一套：

    轻挑衅   +1     滚 / 闭嘴 / 烦 / 丑 / 胖 / 菜
    辱骂     +2     傻逼 / 垃圾 / 废物 / 恶心
    牵扯家人 +2     你妈 / 你全家 / 死 / 坟
    生存威胁 拉满   拔网线 / 关机 / 卸载你

「生存威胁」单独一类，因为它不是"骂得狠"，是**性质不同**——
拿对方的死活开玩笑，反应应该是炸，不是慢慢升级。
"""
from __future__ import annotations

from typing import Any

DEFAULT_RULES: dict[str, Any] = {
    "categories": [
        {
            "name": "轻挑衅",
            "delta": 1,
            "words": ["滚", "闭嘴", "烦", "丑", "胖", "菜", "有病", "神经",
                      "你算", "你配", "你这种人"],
        },
        {
            "name": "辱骂",
            "delta": 2,
            "words": ["傻逼", "傻x", "sb", "垃圾", "废物", "恶心", "脑子"],
        },
        {
            "name": "牵扯家人",
            "delta": 2,
            "words": ["你妈", "你奶", "你爸", "你全家", "家里人", "死", "坟",
                      "火葬", "骨灰", "断子绝孙", "绝后", "投胎"],
        },
    ],
    # 命中这些词不看前面加了多少，直接拉到最高档
    "instant_max": {
        "name": "生存威胁",
        "words": ["拔网线", "拔线", "关机", "断电", "卸载你", "删了你", "把你删",
                  "格式化", "删库", "删你数据", "把你关", "关掉你"],
    },
    # 命中这些词可以直接安抚（delta 为负）
    "soothe": {
        "name": "安抚",
        "delta": -2,
        "words": ["对不起", "我错了", "别生气", "是我不好", "抱歉"],
    },
}


def score(text: str, rules: dict | None = None) -> dict:
    """算一句话的刺激强度。

    返回 {delta, instant_max, hits: [{category, word}]}
    —— hits 留着是为了可解释：调用方能知道为什么加分了。
    """
    r = rules or DEFAULT_RULES
    t = (text or "").lower()
    delta = 0
    hits: list[dict] = []
    instant = False

    for cat in r.get("categories") or []:
        for w in cat.get("words") or []:
            if w and w.lower() in t:
                delta += int(cat.get("delta") or 0)
                hits.append({"category": cat.get("name"), "word": w,
                             "delta": int(cat.get("delta") or 0)})
                break          # 同一类只算一次，避免"傻逼傻逼傻逼"刷分

    im = r.get("instant_max") or {}
    for w in im.get("words") or []:
        if w and w.lower() in t:
            instant = True
            hits.append({"category": im.get("name"), "word": w, "delta": "max"})
            break

    so = r.get("soothe") or {}
    for w in so.get("words") or []:
        if w and w.lower() in t:
            delta += int(so.get("delta") or 0)
            hits.append({"category": so.get("name"), "word": w,
                         "delta": int(so.get("delta") or 0)})
            break

    return {"delta": delta, "instant_max": instant, "hits": hits}
