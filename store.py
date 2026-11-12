"""store.py —— 按对象持久化情绪状态。

为什么按对象存：不能对谁都记仇。A 骂了你，你气 B 就没道理。

文件长这样：
{
  "objects": {
    "user_123": {
      "level": 3,
      "last_hit": "2026-11-12T20:44:30+08:00",
      "history": [{"at": "...", "delta": 2, "hits": [...]}, ...]
    }
  }
}
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any

KEEP_HISTORY = 50


def load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            raise ValueError("not a dict")
        d.setdefault("objects", {})
        return d
    except Exception:
        return {"objects": {}}


def save(path: str, data: dict) -> None:
    """原子写：先写临时文件再 replace，中途崩了不会留下半个 JSON。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get(data: dict, obj_id: str) -> dict:
    return dict((data.get("objects") or {}).get(obj_id) or {})


def put(data: dict, obj_id: str, rec: dict) -> None:
    hist = list(rec.get("history") or [])[-KEEP_HISTORY:]
    rec["history"] = hist
    data.setdefault("objects", {})[obj_id] = rec


def drop(data: dict, obj_id: str) -> bool:
    objs = data.get("objects") or {}
    if obj_id in objs:
        del objs[obj_id]
        return True
    return False
