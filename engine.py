"""engine.py —— 情绪状态机本体。

用法：
    from engine import EmotionEngine

    e = EmotionEngine("state.json")
    st = e.hit("user_123", "你个傻逼")
    st["level"]                        # 3
    render_hint(st["level"])           # "【你现在的状态：冒烟】说 4 句。..."

设计三条原则：
1. **档位由代码算，不由模型判** —— 说一万遍"你现在很生气"，模型还是客气
2. **输出行为参数，不输出形容词** —— 告诉它"说 8 句一句一行"，它才照做
3. **渐进 + 回落** —— 一句话不能从 0 跳到满档，满档也不能记一辈子
"""
from __future__ import annotations

import datetime
from typing import Any, Optional

import levels as levels_mod
import rules as rules_mod
import store


def _now() -> datetime.datetime:
    return datetime.datetime.now().astimezone()


class EmotionEngine:
    """一个情绪轴（默认是"愤怒/激动"）。多轴的话起多个实例，状态分开存。"""

    def __init__(self, state_path: str,
                 rules: Optional[dict] = None,
                 levels: Optional[dict] = None,
                 max_level: int = 5,
                 decay_minutes: float = 10,
                 jump_limit: int = 2,
                 cooldown_seconds: float = 3):
        """
        state_path:  状态文件
        rules:       攻击词规则（None 用默认）
        levels:      档位→行为参数（None 用默认）
        max_level:   最高档
        decay_minutes: 多少分钟没人惹就降 1 档
        jump_limit:  一轮最多升几档（防止一句话就炸）
        cooldown_seconds: 同一对象多少秒内只处理一次（防止连发刷屏）
        """
        self.path = state_path
        self.rules = rules if rules is not None else rules_mod.DEFAULT_RULES
        self.levels = levels if levels is not None else levels_mod.DEFAULT_LEVELS
        self.max_level = int(max_level)
        self.decay_minutes = float(decay_minutes)
        self.jump_limit = int(jump_limit)
        self.cooldown_seconds = float(cooldown_seconds)

    # ---------- 读 ----------

    def get(self, obj_id: str, decay: bool = True) -> dict:
        """当前状态（默认顺带算时间衰减）。"""
        data = store.load(self.path)
        rec = store.get(data, obj_id)
        lv = int(rec.get("level") or 0)
        if decay:
            lv = self._decayed(lv, rec.get("last_hit"))
        return self._snapshot(obj_id, lv, rec, decayed=False)

    # ---------- 写 ----------

    def hit(self, obj_id: str, text: str, at: Optional[datetime.datetime] = None) -> dict:
        """收到一句话：先降温，再算刺激，再限制跳级，最后落盘。"""
        now = at or _now()
        data = store.load(self.path)
        rec = store.get(data, obj_id)

        # 冷却：同一对象短时间内只算一次（防止刷屏）
        last_hit = rec.get("last_hit")
        if last_hit and self.cooldown_seconds > 0:
            try:
                gap = (now - datetime.datetime.fromisoformat(last_hit)).total_seconds()
                if 0 <= gap < self.cooldown_seconds:
                    lv = self._decayed(int(rec.get("level") or 0), last_hit, at=now)
                    return self._snapshot(obj_id, lv, rec, decayed=False)
            except Exception:
                pass

        # 1) 时间降温
        before = int(rec.get("level") or 0)
        lv = self._decayed(before, last_hit, at=now)
        decayed = lv != before

        # 2) 打分
        s = rules_mod.score(text, self.rules)
        delta = int(s.get("delta") or 0)
        target = lv + delta
        if s.get("instant_max"):
            target = self.max_level

        # 3) 跳级限制：正常上涨一次最多 jump_limit 档
        #    但 instant_max（生存威胁）不受限 —— 那不是"骂得狠"，是性质不同
        if not s.get("instant_max") and target > lv:
            target = min(target, lv + self.jump_limit)

        new_lv = max(0, min(self.max_level, target))

        # 4) 满档回落：刚上满档那轮不回落，下一轮开始降
        if new_lv == self.max_level and int(rec.get("peak_level") or 0) == self.max_level:
            # 已经满过了，这次再满也往回掉一档，防记仇
            new_lv = max(0, self.max_level - 1)

        hist = list(rec.get("history") or [])
        if s.get("hits"):
            hist.append({
                "at": now.isoformat(timespec="seconds"),
                "from": lv, "to": new_lv,
                "delta": delta,
                "hits": s["hits"],
            })

        rec.update({
            "level": new_lv,
            "peak_level": max(int(rec.get("peak_level") or 0), new_lv),
            "last_hit": now.isoformat(timespec="seconds"),
            "history": hist,
        })
        store.put(data, obj_id, rec)
        store.save(self.path, data)

        return self._snapshot(obj_id, new_lv, rec, decayed=decayed, delta=delta)

    def boost(self, obj_id: str, delta: int, reason: str = "") -> dict:
        """手动加分（不是被骂，而是别的事让你不爽）。"""
        now = _now()
        data = store.load(self.path)
        rec = store.get(data, obj_id)
        lv = max(0, min(self.max_level, int(rec.get("level") or 0) + int(delta)))
        hist = list(rec.get("history") or [])
        hist.append({"at": now.isoformat(timespec="seconds"), "delta": delta,
                     "reason": reason})
        rec.update({"level": lv, "last_hit": now.isoformat(timespec="seconds"),
                    "peak_level": max(int(rec.get("peak_level") or 0), lv),
                    "history": hist})
        store.put(data, obj_id, rec)
        store.save(self.path, data)
        return self._snapshot(obj_id, lv, rec)

    def calm(self, obj_id: str, delta: int = 2) -> dict:
        """被安抚 / 主动消气。"""
        return self.boost(obj_id, -abs(int(delta)), "calm")

    def reset(self, obj_id: str) -> bool:
        data = store.load(self.path)
        ok = store.drop(data, obj_id)
        if ok:
            store.save(self.path, data)
        return ok

    # ---------- 内部 ----------

    def _decayed(self, level: int, last_hit: Optional[str],
                 at: Optional[datetime.datetime] = None) -> int:
        if not last_hit or self.decay_minutes <= 0:
            return max(0, int(level))
        try:
            now = at or _now()
            gap = (now - datetime.datetime.fromisoformat(last_hit)).total_seconds() / 60
            steps = int(gap // self.decay_minutes)
            return max(0, int(level) - steps)
        except Exception:
            return max(0, int(level))

    def _snapshot(self, obj_id: str, level: int, rec: dict,
                  decayed: bool = False, delta: int = 0) -> dict:
        b = levels_mod.render(level, self.levels)
        return {
            "object": obj_id,
            "level": int(level),
            "max_level": self.max_level,
            "name": b.get("name"),
            "behavior": b,
            "hint": levels_mod.render_hint(level, self.levels),
            "tiers": levels_mod.tier_filter(level),
            "decayed": decayed,
            "delta": delta,
            "peak_level": int(rec.get("peak_level") or level),
            "history": (rec.get("history") or [])[-5:],
        }


if __name__ == "__main__":
    import json
    import sys

    e = EmotionEngine(sys.argv[1] if len(sys.argv) > 1 else "emotion_state.json",
                      cooldown_seconds=0)
    oid = "demo"
    for msg in ["你好", "你个傻逼", "滚", "你妈死了", "对不起"]:
        st = e.hit(oid, msg)
        print(f"{msg:<12} → {st['level']} 档 {st['name']}  "
              f"({st['behavior']['sentences']} 句)")
