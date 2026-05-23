"""AI 제공자 추상화 레이어 (litellm + keyring)."""
from __future__ import annotations

import time
from typing import Any

import logging

logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)

import keyring
import keyring.errors
import litellm

litellm.suppress_debug_info = True
litellm.set_verbose = False

KEYRING_SERVICE = "memo_slide_ai"

PROVIDERS: dict[str, dict[str, Any]] = {
    "anthropic": {
        "name": "Anthropic",
        "models": ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"],
        "default_model": "claude-haiku-4-5",
        "key_format": "sk-ant-...",
        "needs_key": True,
    },
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-4.1", "gpt-4o", "gpt-4o-mini", "o3-mini"],
        "default_model": "gpt-4o-mini",
        "key_format": "sk-...",
        "needs_key": True,
    },
    "gemini": {
        "name": "Google Gemini",
        "models": ["gemini/gemini-2.5-pro", "gemini/gemini-2.5-flash"],
        "default_model": "gemini/gemini-2.5-flash",
        "key_format": "AIza...",
        "needs_key": True,
    },
    "ollama": {
        "name": "Ollama (로컬)",
        "models": ["ollama/llama3.2", "ollama/qwen2.5", "ollama/gemma2"],
        "default_model": "ollama/llama3.2",
        "key_format": "",
        "needs_key": False,
        "api_base": "http://localhost:11434",
    },
}

# AI 설정 DB 키 상수
AI_KEY_ENABLED = "ai_enabled"
AI_KEY_PROVIDER = "ai_provider"
AI_KEY_MODEL = "ai_model"
AI_KEY_USAGE_TOKENS = "ai_usage_tokens"
AI_KEY_USAGE_RESET = "ai_usage_reset"
AI_KEY_SHOW_PREVIEW = "ai_show_preview"

AI_DEFAULTS: dict[str, str] = {
    AI_KEY_ENABLED: "0",
    AI_KEY_PROVIDER: "anthropic",
    AI_KEY_MODEL: "claude-haiku-4-5",
    AI_KEY_USAGE_TOKENS: "0",
    AI_KEY_USAGE_RESET: "",
    AI_KEY_SHOW_PREVIEW: "0",
}


# ----- 키링 헬퍼 -----

def save_api_key(provider: str, key: str) -> None:
    keyring.set_password(KEYRING_SERVICE, provider, key)


def load_api_key(provider: str) -> str | None:
    try:
        return keyring.get_password(KEYRING_SERVICE, provider)
    except Exception:
        return None


def delete_api_key(provider: str) -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, provider)
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception:
        pass


# ----- AIProvider 클래스 -----

class AIProvider:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key if api_key is not None else load_api_key(provider)
        self._info = PROVIDERS.get(provider, {})

    def _build_kwargs(self, max_tokens: int) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"model": self.model, "max_tokens": max_tokens}
        if self._info.get("needs_key") and self.api_key:
            kwargs["api_key"] = self.api_key
        if "api_base" in self._info:
            kwargs["api_base"] = self._info["api_base"]
        return kwargs

    def call(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
    ) -> tuple[str, int]:
        """(응답 텍스트, 사용 토큰 수) 반환."""
        kwargs = self._build_kwargs(max_tokens)
        kwargs["messages"] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        response = litellm.completion(**kwargs)
        text = response.choices[0].message.content or ""
        tokens = getattr(getattr(response, "usage", None), "total_tokens", 0) or 0
        return text, int(tokens)

    def test_connection(self) -> tuple[bool, str]:
        """(성공 여부, 메시지) 반환. 실제 짧은 호출로 확인."""
        start = time.time()
        try:
            text, _ = self.call("You are a test assistant.", "Say OK", max_tokens=10)
            elapsed = time.time() - start
            if text.strip():
                return True, f"✓ 연결 성공 ({elapsed:.1f}초)"
            return False, "✗ 응답이 비어 있습니다"
        except litellm.AuthenticationError:
            return False, "✗ 인증 실패: API 키를 확인하세요"
        except litellm.APIConnectionError:
            return False, "✗ 연결 실패: 네트워크 또는 서버를 확인하세요"
        except litellm.RateLimitError:
            return False, "✗ 사용량 한도 초과"
        except litellm.BadRequestError as e:
            return False, f"✗ 잘못된 요청: {e}"
        except Exception as e:
            return False, f"✗ 오류: {type(e).__name__}: {e}"
