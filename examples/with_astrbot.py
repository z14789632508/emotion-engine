"""examples/with_astrbot.py —— 接到 AstrBot 的示例。

放进 `core/data/plugins/你的插件/main.py`，每次 LLM 请求前把情绪注入进去。
"""
import os
import sys

sys.path.insert(0, r"F:\work\Project\emotion-engine")

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register

from engine import EmotionEngine

STATE = r"D:\DSH\shared\emotion_state.json"
LEXICON = [
    {"text": "耗子扛枪窝里横", "tag": "seed"},
    {"text": "茅坑里的石头又臭又硬", "tag": "defense"},
]


@register("emotion_engine", "local", "代码级情绪状态机", "1.0.0")
class EmotionPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.engine = EmotionEngine(STATE)

    @filter.on_llm_request()
    async def inject(self, event: AstrMessageEvent, req: ProviderRequest) -> None:
        uid = str(event.get_sender_id() or "")
        if not uid:
            return
        # 先说一句，才知道该多生气
        st = self.engine.hit(uid, event.get_message_str() or "")
        if st["level"] <= 0:
            return
        try:
            from astrbot.core.agent.message import TextPart
            req.extra_user_content_parts.append(TextPart(text="\n" + st["hint"]))
        except Exception:
            req.prompt = (req.prompt or "") + "\n" + st["hint"]
