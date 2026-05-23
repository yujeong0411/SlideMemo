"""AI 기능 정의 및 워커 스레드."""
from __future__ import annotations

import logging
import time

logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)

import litellm
from PyQt6.QtCore import QThread, pyqtSignal

from ai_provider import AIProvider, load_api_key, PROVIDERS

# 각 기능: label, system, user_template({{text}} 치환), needs_selection, max_tokens
AI_FEATURES: dict[str, dict] = {
    "summarize": {
        "label": "요약",
        "system": "You are a concise summarizer. Summarize in the same language as the input. Output only the summary, no preamble.",
        "user_template": "Summarize the following text:\n\n{{text}}",
        "needs_selection": False,
        "max_tokens": 512,
        "output": "replace",  # replace selection or full content
    },
    "translate": {
        "label": "번역 (한↔영)",
        "system": "You are a professional translator. If the input is Korean, translate to English. If English, translate to Korean. Output only the translation.",
        "user_template": "Translate:\n\n{{text}}",
        "needs_selection": False,
        "max_tokens": 1024,
        "output": "replace",
    },
    "spellcheck": {
        "label": "맞춤법 교정",
        "system": "You are a proofreader. Fix spelling, grammar, and punctuation errors. Preserve the original language and style. Output only the corrected text.",
        "user_template": "Fix errors in:\n\n{{text}}",
        "needs_selection": False,
        "max_tokens": 1024,
        "output": "replace",
    },
    "title": {
        "label": "제목 생성",
        "system": "You are a title writer. Generate a short, descriptive title (under 10 words) for the given text. Use the same language as the text. Output only the title.",
        "user_template": "Generate a title for:\n\n{{text}}",
        "needs_selection": False,
        "max_tokens": 64,
        "output": "title",  # put result in title field
    },
    "keywords": {
        "label": "키워드 추출",
        "system": "You are a keyword extractor. Extract 5-10 key terms or phrases from the text. Use the same language. Output only a comma-separated list of keywords.",
        "user_template": "Extract keywords from:\n\n{{text}}",
        "needs_selection": False,
        "max_tokens": 128,
        "output": "append",
    },
}


class AIWorker(QThread):
    finished = pyqtSignal(str, str, int)  # feature_key, result_text, tokens_used
    errored = pyqtSignal(str, str)        # feature_key, error_message
    progress = pyqtSignal(str)            # status_message

    def __init__(
        self,
        feature_key: str,
        provider: str,
        model: str,
        text: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._feature_key = feature_key
        self._provider = provider
        self._model = model
        self._text = text
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            return
        feature = AI_FEATURES.get(self._feature_key)
        if not feature:
            self.errored.emit(self._feature_key, f"알 수 없는 기능: {self._feature_key}")
            return

        api_key = load_api_key(self._provider)
        ai = AIProvider(self._provider, self._model, api_key)

        user_msg = feature["user_template"].replace("{{text}}", self._text)

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            if self._cancelled:
                return
            try:
                result, tokens = ai.call(
                    feature["system"],
                    user_msg,
                    max_tokens=feature["max_tokens"],
                )
                if not self._cancelled:
                    self.finished.emit(self._feature_key, result.strip(), tokens)
                return
            except litellm.InternalServerError as e:
                if attempt < max_attempts and not self._cancelled:
                    self.progress.emit(f"⏳ 서버 과부하, 재시도 중... ({attempt}/{max_attempts - 1})")
                    time.sleep(3)
                    continue
                if not self._cancelled:
                    self.errored.emit(self._feature_key, "서버 과부하 상태입니다. 잠시 후 다시 시도하세요.")
            except litellm.AuthenticationError:
                if not self._cancelled:
                    self.errored.emit(self._feature_key, "API 키 인증 실패. 설정에서 키를 확인하세요.")
                return
            except litellm.RateLimitError:
                if not self._cancelled:
                    self.errored.emit(self._feature_key, "API 사용량 한도 초과. 잠시 후 다시 시도하세요.")
                return
            except litellm.APIConnectionError:
                if not self._cancelled:
                    self.errored.emit(self._feature_key, "서버 연결 실패. 네트워크를 확인하세요.")
                return
            except litellm.BadRequestError as e:
                if not self._cancelled:
                    self.errored.emit(self._feature_key, f"잘못된 요청: {e}")
                return
            except Exception as e:
                if not self._cancelled:
                    self.errored.emit(self._feature_key, f"오류: {type(e).__name__}: {e}")
                return
