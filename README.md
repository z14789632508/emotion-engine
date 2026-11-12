# emotion-engine

**把情绪从 prompt 层拉到代码层。**

一个不依赖 LLM 判断的情绪状态机：刺激 → 打分 → 分档 → **输出行为参数**。

```python
from engine import EmotionEngine

e = EmotionEngine("state.json")
st = e.hit("user_123", "你个傻逼")
st["level"]      # 2
st["hint"]       # "【你现在的状态：上火】说 3 句。顶两三句，用带刺的话，但别骂脏的。"
```

---

## 它解决什么问题

先说清楚现有情绪系统的共同弱点：

```
prompt 里写：情绪分 0-10 级，你要跟着变
      ↓
模型：好，那我一直是 3 级吧
      ↓
你骂它十句，它还是 3 级
```

**因为没人真的在数。**

这个库数。

```
骂一句 +2 → 写进 JSON → 下一轮直接告诉它"你现在 5 档"
```

**这不是建议，是当前状态。**

---

## 输出的不是形容词，是行为参数

这是和所有同类项目最根本的区别。

别人的情绪系统：

```json
{"mood": "angry", "intensity": 7}
```

模型收到这个，可能还是客气地回一句"我理解你的感受"。

**这个输出的是**：

```json
{
  "level": 5,
  "behavior": {
    "sentences": 8,
    "one_per_line": true,
    "must_verbatim": true,
    "no_explaining": true
  },
  "hint": "【你现在的状态：炸了】说 8 句。一句一行。机关枪：最多连说 8 句，一句一行，别停别解释。"
}
```

| 你给模型 | 它可能的行为 |
|---|---|
| “你现在很生气” | 客气地说“我很生气” |
| “说 8 句，一句一行，别解释” | **真的照做** |

---

## 三条设计原则

### ① 档位由代码算，不由模型判

模型判断"自己该有多生气"这件事，**天然偏向克制**。与其指望它，不如直接用规则打分。

### ② 渐进上升，限制跳级

```
本轮 2 档 → 下轮最多 4 档（jump_limit=2）
```

防止"一句话就炸"。真实情绪是渐进的。

**例外**：`instant_max` 类的词（比如"我要把你删了"）不受跳级限制——那不是"骂得狠"，是**性质不同**。

### ③ 满档回落，不记仇

```
刚到满档那轮不回落，下一轮开始降一档
```

防止"记仇一辈子"。

---

## 用法

### 收到消息时打分

```python
from engine import EmotionEngine
from levels import render_hint

e = EmotionEngine("emotion_state.json")

st = e.hit(sender_id, message_text)
if st["level"] > 0:
    prompt += "\n\n" + render_hint(st["level"])
```

### 手动加分 / 消气

```python
e.boost("user_123", 2, reason="他放了你鸽子")
e.calm("user_123")        # 默认 -2
e.reset("user_123")       # 清零
```

### 只读当前状态

```python
st = e.get("user_123")    # 默认顺带算时间衰减
st["level"], st["tiers"]
```

---

## 状态文件

```json
{
  "objects": {
    "user_123": {
      "level": 3,
      "peak_level": 4,
      "last_hit": "2026-11-12T20:44:30+08:00",
      "history": [
        {"at": "...", "from": 2, "to": 3, "delta": 1,
         "hits": [{"category": "轻挑衅", "word": "滚", "delta": 1}]}
      ]
    }
  }
}
```

**按对象存** —— 不能对谁都记仇。A 骂了你，你气 B 就没道理。

`history` 里带 `hits`，是为了**可解释**：能查出为什么加分、哪句话触发的。

---

## 配置

`rules.py` 里的 `DEFAULT_RULES` 是一套默认规则，可以直接改，也可以传自己的：

```python
rules = {
    "categories": [
        {"name": "轻挑衅", "delta": 1, "words": ["滚", "烦"]},
        {"name": "辱骂", "delta": 2, "words": ["垃圾", "废物"]},
    ],
    "instant_max": {"name": "威胁", "words": ["删了你"]},
    "soothe": {"name": "安抚", "delta": -2, "words": ["对不起"]},
}
e = EmotionEngine("state.json", rules=rules)
```

档位表同理（`levels.DEFAULT_LEVELS`），改 `sentences` / `tone` / `lexicon_tier` 就行。

---

## 词库分层

**这个库不带词库**——词是内容，不是通用资产。

它只提供**分层机制**：每条词库条目带一个 `tag`，按档位决定能用哪几层。

```python
lexicon = [
    {"text": "耗子扛枪窝里横", "tag": "seed"},          # 不带脏字的阴阳
    {"text": "茅坑里的石头又臭又硬", "tag": "defense"},  # 被针对时的防身
    {"text": "你这种人也就这点出息", "tag": "heavy"},    # 放开骂
]
```

默认映射：

| 档位 | 可用层 |
|---|---|
| 0 | 无 |
| 1-2 | seed |
| 3 | seed + defense |
| 4 | seed + defense + heavy |
| 5 | 全部 |

**为什么分层**：全量注入会稀释注意力（实测一句都不掏）。而且低档位就放狠话，人物会崩。

---

## 一个关键的措辞细节

这是实测出来的，写在这里免得别人重新踩：

| 注入措辞 | 模型的实际行为 |
|---|---|
| “必须原话” | 短回一句就完了 |
| “必须原话照说” | 有时照搬，有时不 |
| **“这一轮必须原样发出去，一个字都别改” + 项目符号列出来** | **才会真的逐字照搬** |

而且**只在高档位用**。低档位用"参考，不用照抄"——强迫照抄会显得机械。

`examples/inject_to_llm.py` 里就是这么写的。

---

## 实测

```
你好       → 0 档 平静，1 句
你个傻逼    → 2 档 上火，3 句
滚         → 3 档 冒烟，4 句
你妈死了    → 5 档 炸了，8 句（跳级限制 2，3+2=5）
对不起     → 3 档 冒烟，4 句（安抚 -2）
```

时间衰减（每 10 分钟 -1）：

```
连骂两次 → 4 档
+10 分钟 → 3 档
+25 分钟 → 2 档
+50 分钟 → 0 档
```

---

## 限制

老实说：

- **纯规则，抓不到语境**。"你上次也是这么说的"——不知道这是翻旧账
- **单轴**。只有"愤怒/激动"一个维度。开心、难过要起第二个实例
- **关键词会误伤**。"笑死了"里的"死"会 +2（除非你把它加进白名单）
- **没有多语言**。规则是按中文写的

要更准的话，得叠一层小模型判断——但那就不是"零成本"了。

---

## 参考

- [emotion-ladder-persona](https://github.com/LucasDevKid9/emotion-ladder-persona) —— 0-10 情绪阶梯的 prompt 实现，本项目的"跨级限制"和"满档回落"受它启发

## License

MIT
