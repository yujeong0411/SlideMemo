"""음성 녹음 + Whisper 텍스트 변환.

- AudioRecorder: sounddevice로 마이크 입력 캡쳐, WAV 파일로 저장
- has_microphone(): 마이크 장치 존재 확인
- WhisperWorker: openai 패키지로 Whisper API 호출 (백그라운드)
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf
from PyQt6.QtCore import QThread, pyqtSignal


class AudioRecorder:
    SAMPLE_RATE = 16000  # Whisper 권장 (16kHz)
    CHANNELS = 1         # 모노
    DTYPE = "int16"

    def __init__(self, max_seconds: int = 300) -> None:
        self.max_seconds = max_seconds
        self._stream: Optional[sd.InputStream] = None
        self._frames: list[np.ndarray] = []
        self._start_time: float = 0.0
        self.is_recording = False

    @property
    def elapsed_seconds(self) -> int:
        if not self.is_recording:
            return 0
        return int(time.time() - self._start_time)

    def start(self) -> None:
        if self.is_recording:
            return
        self._frames = []
        self._start_time = time.time()

        def callback(indata, frames, time_info, status) -> None:  # noqa: ARG001
            # sounddevice는 별도 스레드에서 호출 → 단순 append만
            self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            channels=self.CHANNELS,
            dtype=self.DTYPE,
            callback=callback,
        )
        self._stream.start()
        self.is_recording = True

    def stop_and_save(self, path: Path) -> Optional[Path]:
        """녹음 종료 + WAV 파일 저장. 저장 성공 시 path 반환, 데이터 없으면 None."""
        if not self.is_recording:
            return None
        self.is_recording = False
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        finally:
            self._stream = None
        if not self._frames:
            return None
        audio = np.concatenate(self._frames)
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), audio, self.SAMPLE_RATE, subtype="PCM_16")
        return path

    def abort(self) -> None:
        """저장 없이 녹음 중단."""
        self.is_recording = False
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        finally:
            self._stream = None
        self._frames = []


def has_microphone() -> tuple[bool, str]:
    """마이크 장치 존재 검증. (성공 여부, 에러 메시지)."""
    try:
        for d in sd.query_devices():
            if int(d.get("max_input_channels", 0)) > 0:
                return True, ""
        return False, "마이크 장치를 찾을 수 없습니다."
    except Exception as e:
        return False, f"마이크 확인 실패: {e}"


class WhisperWorker(QThread):
    """OpenAI Whisper API로 음성 → 텍스트 변환."""
    finished = pyqtSignal(str)   # 변환된 텍스트
    errored = pyqtSignal(str)    # 에러 메시지
    progress = pyqtSignal(str)   # 상태 메시지

    def __init__(
        self,
        audio_path: Path,
        api_key: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._audio_path = audio_path
        self._api_key = api_key
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            return
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._api_key)
            with open(self._audio_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                )
            if self._cancelled:
                return
            text = (transcript.text or "").strip()
            self.finished.emit(text)
        except Exception as e:
            if not self._cancelled:
                self.errored.emit(f"{type(e).__name__}: {e}")
