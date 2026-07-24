#!/usr/bin/env python3
"""
LLM backend for JarvisLab voice call.
Priority:
  1) JARVIS_API_KEY / OPENAI_API_KEY + JARVIS_BASE_URL / OPENAI_BASE_URL
  2) Hermes xAI OAuth token from %LOCALAPPDATA%/hermes/auth.json
  3) Local rule-based fallback
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_SYSTEM = (
    "Bạn là Jarvis, trợ lý giọng nói tiếng Việt. "
    "Trả lời ngắn gọn, tự nhiên như nói chuyện ngoài đời (1–3 câu). "
    "Không markdown, không bullet, không emoji trừ khi user dùng. "
    "Nếu user tạm biệt / bye / thôi / dừng thì trả lời tạm biệt ngắn."
)


def _hermes_auth_path() -> Path:
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "hermes" / "auth.json"


def _load_xai_token() -> str | None:
    path = _hermes_auth_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    providers = data.get("providers") or {}
    xai = providers.get("xai-oauth") or providers.get("xai") or {}
    tokens = xai.get("tokens") or {}
    if isinstance(tokens, dict):
        return tokens.get("access_token") or tokens.get("api_key") or tokens.get("token")
    if isinstance(tokens, list) and tokens:
        t0 = tokens[0] or {}
        if isinstance(t0, dict):
            return t0.get("access_token") or t0.get("api_key")
    return None


def resolve_llm_config() -> dict[str, Any]:
    """Pick API credentials without mixing OpenAI keys into xAI endpoints.

    Priority:
      1) JARVIS_API_KEY (+ optional JARVIS_BASE_URL / JARVIS_MODEL)
      2) XAI_API_KEY or Hermes xAI OAuth → api.x.ai
      3) OPENAI_API_KEY → OPENAI_BASE_URL or api.openai.com

    OPENAI_API_KEY is often set for other tools and is invalid on api.x.ai;
    preferring it before the Hermes xAI token caused HTTP 400 Incorrect API key.
    """
    jarvis_key = os.environ.get("JARVIS_API_KEY")
    jarvis_base = (os.environ.get("JARVIS_BASE_URL") or "").rstrip("/")
    jarvis_model = os.environ.get("JARVIS_MODEL")

    if jarvis_key:
        return {
            "api_key": jarvis_key,
            "base_url": jarvis_base or "https://api.x.ai/v1",
            "model": jarvis_model
            or os.environ.get("OPENAI_MODEL")
            or "grok-4-1-fast-non-reasoning",
        }

    xai_key = os.environ.get("XAI_API_KEY") or _load_xai_token()
    if xai_key:
        return {
            "api_key": xai_key,
            "base_url": jarvis_base or "https://api.x.ai/v1",
            "model": jarvis_model
            or os.environ.get("OPENAI_MODEL")
            or "grok-4-1-fast-non-reasoning",
        }

    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        openai_base = (
            jarvis_base
            or (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
            or "https://api.openai.com/v1"
        )
        return {
            "api_key": openai_key,
            "base_url": openai_base,
            "model": jarvis_model
            or os.environ.get("OPENAI_MODEL")
            or "gpt-4o-mini",
        }

    return {"api_key": None, "base_url": "", "model": jarvis_model or ""}


def rule_based_reply(text: str) -> str:
    t = (text or "").lower().strip()
    if any(x in t for x in ("tạm biệt", "tam biet", "bye", "thôi", "thoi", "dừng", "dung")):
        return "Tạm biệt. Gọi lại khi cần nhé."
    if any(x in t for x in ("xin chào", "chào", "hello", "hi ", "hi,")):
        return "Chào bạn, tôi là Jarvis. Bạn cần gì?"
    if any(x in t for x in ("tên", "là ai", "bạn là")):
        return "Tôi là Jarvis, trợ lý giọng nói thời gian thực."
    if any(x in t for x in ("giờ", "thời gian", "mấy giờ")):
        return f"Bây giờ là {time.strftime('%H giờ %M')}."
    if any(x in t for x in ("cảm ơn", "cam on", "thank")):
        return "Không có gì."
    if not t:
        return "Tôi chưa nghe rõ, bạn nói lại được không?"
    return f"Bạn nói: {text}. Tôi đang nghe đây."


def chat_completion(
    user_text: str,
    history: list[dict[str, str]] | None = None,
    system: str = DEFAULT_SYSTEM,
    timeout: float = 45.0,
) -> tuple[str, str]:
    """
    Returns (reply, backend_name).
    backend_name: llm | rules
    """
    cfg = resolve_llm_config()
    if not cfg["api_key"] or not cfg["base_url"]:
        return rule_based_reply(user_text), "rules"

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-12:])  # keep short for voice
    messages.append({"role": "user", "content": user_text})

    body = json.dumps(
        {
            "model": cfg["model"],
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 180,
        }
    ).encode("utf-8")

    url = f"{cfg['base_url']}/chat/completions"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            return rule_based_reply(user_text), "rules"
        # strip accidental markdown
        content = content.replace("**", "").replace("`", "").strip()
        return content, "llm"
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:240]
        except Exception:
            pass
        print(f"[llm] error: HTTP {e.code} {detail or e}", flush=True)
        return rule_based_reply(user_text), "rules"
    except Exception as e:
        print(f"[llm] error: {e}", flush=True)
        return rule_based_reply(user_text), "rules"


def is_goodbye(text: str) -> bool:
    t = (text or "").lower().strip()
    keys = (
        "tạm biệt",
        "tam biet",
        "bye",
        "goodbye",
        "thôi dừng",
        "dừng lại",
        "kết thúc",
        "ket thuc",
        "cúp máy",
        "cup may",
    )
    return any(k in t for k in keys)


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "Xin chào"
    reply, backend = chat_completion(q)
    print(f"[{backend}] {reply}")
