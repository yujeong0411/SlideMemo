"""설정 다이얼로그 (일반 / AI / 정보 탭)."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ai_provider import (
    AI_KEY_ENABLED,
    AI_KEY_MODEL,
    AI_KEY_PROVIDER,
    AI_KEY_SHOW_PREVIEW,
    AI_KEY_USAGE_RESET,
    AI_KEY_USAGE_TOKENS,
    PROVIDERS,
    AIProvider,
    delete_api_key,
    load_api_key,
    save_api_key,
)
from database import MemoDatabase

_KEY_HELP_URLS: dict[str, str] = {
    "anthropic": "https://console.anthropic.com/",
    "openai": "https://platform.openai.com/api-keys",
    "gemini": "https://aistudio.google.com/apikey",
    "ollama": "https://ollama.com/download",
}

_COST_PER_1K: dict[str, float] = {
    "anthropic": 0.0008,
    "openai": 0.003,
    "gemini": 0.0,
    "ollama": 0.0,
}


class _TestWorker(QThread):
    result_ready = pyqtSignal(bool, str)

    def __init__(self, provider: str, model: str, key: str | None) -> None:
        super().__init__()
        self._provider = provider
        self._model = model
        self._key = key

    def run(self) -> None:
        ai = AIProvider(self._provider, self._model, self._key)
        ok, msg = ai.test_connection()
        self.result_ready.emit(ok, msg)


class SettingsDialog(QDialog):
    def __init__(self, db: MemoDatabase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self._test_worker: _TestWorker | None = None
        self._original_key: str | None = None

        self.setWindowTitle("설정")
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "일반")
        tabs.addTab(self._build_ai_tab(), "AI")
        tabs.addTab(self._build_info_tab(), "정보")
        root.addWidget(tabs)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save_and_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._load_settings()

    # ── 일반 탭 ──────────────────────────────────────────────────
    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # 앱 위치
        side_form = QFormLayout()
        side_form.setVerticalSpacing(8)
        self._side_combo = QComboBox()
        self._side_combo.addItem("오른쪽 가장자리", 0)
        self._side_combo.addItem("왼쪽 가장자리", 1)
        side_form.addRow("앱 위치:", self._side_combo)
        note = QLabel("※ 위치 변경은 앱 재시작 후 적용됩니다.")
        note.setStyleSheet("color: gray; font-size: 9pt;")
        side_form.addRow("", note)
        outer.addLayout(side_form)

        # 인덱스 탭 설정 그룹
        outer.addWidget(self._build_tab_geometry_group())

        outer.addStretch(1)
        return w

    def _build_tab_geometry_group(self) -> QGroupBox:
        group = QGroupBox("인덱스 탭 설정")
        form = QFormLayout(group)
        form.setVerticalSpacing(10)

        # 가로 폭 슬라이더 (12 ~ 60 px) — 각 메모 탭(슬라이드 노출 폭)
        self._tab_width_slider = QSlider(Qt.Orientation.Horizontal)
        self._tab_width_slider.setRange(12, 60)
        self._tab_width_slider.setSingleStep(1)
        self._tab_width_slider.setPageStep(4)
        self._tab_width_lbl = QLabel("30 px")
        self._tab_width_lbl.setMinimumWidth(48)
        self._tab_width_slider.valueChanged.connect(
            lambda v: self._tab_width_lbl.setText(f"{v} px")
        )
        width_row = QHBoxLayout()
        width_row.setContentsMargins(0, 0, 0, 0)
        width_row.addWidget(self._tab_width_slider, stretch=1)
        width_row.addWidget(self._tab_width_lbl)
        form.addRow("가로 폭:", width_row)

        # 세로 길이 슬라이더 (60 ~ 200 px) — 각 메모 탭 하나의 높이
        self._memo_tab_height_slider = QSlider(Qt.Orientation.Horizontal)
        self._memo_tab_height_slider.setRange(60, 200)
        self._memo_tab_height_slider.setSingleStep(1)
        self._memo_tab_height_slider.setPageStep(10)
        self._memo_tab_height_lbl = QLabel("116 px")
        self._memo_tab_height_lbl.setMinimumWidth(48)
        self._memo_tab_height_slider.valueChanged.connect(
            lambda v: self._memo_tab_height_lbl.setText(f"{v} px")
        )
        height_row = QHBoxLayout()
        height_row.setContentsMargins(0, 0, 0, 0)
        height_row.addWidget(self._memo_tab_height_slider, stretch=1)
        height_row.addWidget(self._memo_tab_height_lbl)
        form.addRow("세로 길이:", height_row)

        return group

    # ── AI 탭 ────────────────────────────────────────────────────
    def _build_ai_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        # 마스터 토글
        self._ai_enabled_chk = QCheckBox("AI 기능 사용")
        outer.addWidget(self._ai_enabled_chk)

        # 나머지 AI 설정을 묶는 컨테이너 (토글로 한 번에 enable/disable)
        self._ai_body = QWidget()
        form = QFormLayout(self._ai_body)
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(10)

        # 제공자
        self._provider_combo = QComboBox()
        for pid, pinfo in PROVIDERS.items():
            self._provider_combo.addItem(pinfo["name"], pid)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("제공자:", self._provider_combo)

        # API 키 행
        key_row = QHBoxLayout()
        key_row.setContentsMargins(0, 0, 0, 0)
        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText("API 키 입력")
        key_row.addWidget(self._key_edit)
        self._eye_btn = QPushButton("👁")
        self._eye_btn.setFixedWidth(30)
        self._eye_btn.setCheckable(True)
        self._eye_btn.setToolTip("키 표시/숨김")
        self._eye_btn.toggled.connect(
            lambda on: self._key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        key_row.addWidget(self._eye_btn)
        self._test_btn = QPushButton("테스트")
        self._test_btn.setFixedWidth(60)
        self._test_btn.clicked.connect(self._run_test)
        key_row.addWidget(self._test_btn)
        self._key_row_widget = QWidget()
        self._key_row_widget.setLayout(key_row)
        form.addRow("API 키:", self._key_row_widget)

        # 키 발급 도움말
        self._key_help_lbl = QLabel()
        self._key_help_lbl.setOpenExternalLinks(False)
        self._key_help_lbl.linkActivated.connect(
            lambda url: QDesktopServices.openUrl(QUrl(url))
        )
        self._key_help_lbl.setStyleSheet("font-size: 9pt;")
        form.addRow("", self._key_help_lbl)

        # 모델
        self._model_combo = QComboBox()
        form.addRow("모델:", self._model_combo)

        outer.addWidget(self._ai_body)

        # 구분선
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(0,0,0,0.12);")
        outer.addWidget(sep)

        # 사용량
        usage_header = QLabel("── 이번 달 사용량 ──")
        usage_header.setStyleSheet("color: gray; font-size: 9pt;")
        outer.addWidget(usage_header)

        usage_row = QHBoxLayout()
        self._usage_lbl = QLabel("토큰: 0")
        usage_row.addWidget(self._usage_lbl)
        usage_row.addStretch(1)
        reset_btn = QPushButton("통계 초기화")
        reset_btn.setFixedWidth(80)
        reset_btn.clicked.connect(self._reset_usage)
        usage_row.addWidget(reset_btn)
        outer.addLayout(usage_row)

        # 미리보기 체크
        self._preview_chk = QCheckBox("AI 결과 적용 전 미리보기")
        outer.addWidget(self._preview_chk)

        # 테스트 결과
        self._test_result_lbl = QLabel()
        self._test_result_lbl.setWordWrap(True)
        self._test_result_lbl.setStyleSheet("font-size: 9pt;")
        outer.addWidget(self._test_result_lbl)

        outer.addStretch(1)

        # 마스터 토글 연결
        self._ai_enabled_chk.toggled.connect(self._ai_body.setEnabled)
        return w

    # ── 정보 탭 ──────────────────────────────────────────────────
    def _build_info_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(QLabel("<b>Slide Memo</b>"))
        layout.addWidget(QLabel("버전: 0.1.0"))
        layout.addWidget(QLabel("PyQt6 기반 Windows 슬라이드 메모장"))
        layout.addSpacing(8)
        db_lbl = QLabel(f"데이터 위치: {self.db.db_path.parent}")
        db_lbl.setStyleSheet("font-size: 9pt; color: gray;")
        db_lbl.setWordWrap(True)
        layout.addWidget(db_lbl)
        open_btn = QPushButton("데이터 폴더 열기")
        open_btn.setFixedWidth(120)
        open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.db.db_path.parent))
            )
        )
        layout.addWidget(open_btn)
        layout.addStretch(1)
        return w

    # ── 설정 로드 ─────────────────────────────────────────────────
    def _load_settings(self) -> None:
        # 일반
        side = self.db.get_setting_int("side", 0)
        self._side_combo.setCurrentIndex(1 if side == 1 else 0)

        # 인덱스 탭 설정 (값/범위는 main.py 상수와 동일)
        tab_w = max(12, min(self.db.get_setting_int("tab_width", 30), 60))
        self._tab_width_slider.setValue(tab_w)
        self._tab_width_lbl.setText(f"{tab_w} px")
        tab_h = max(60, min(self.db.get_setting_int("memo_tab_height", 116), 200))
        self._memo_tab_height_slider.setValue(tab_h)
        self._memo_tab_height_lbl.setText(f"{tab_h} px")

        # AI
        enabled = self.db.get_setting_str(AI_KEY_ENABLED, "0") == "1"
        provider = self.db.get_setting_str(AI_KEY_PROVIDER, "anthropic")
        model = self.db.get_setting_str(AI_KEY_MODEL, "")
        show_preview = self.db.get_setting_str(AI_KEY_SHOW_PREVIEW, "0") == "1"
        tokens = int(self.db.get_setting_str(AI_KEY_USAGE_TOKENS, "0") or "0")

        # provider 콤보 (signal 차단 후 설정 → 직접 초기화)
        self._provider_combo.blockSignals(True)
        idx = self._provider_combo.findData(provider)
        self._provider_combo.setCurrentIndex(max(0, idx))
        self._provider_combo.blockSignals(False)

        # 모델/키/도움말 초기화
        self._apply_provider_ui(provider, model)

        self._ai_enabled_chk.setChecked(enabled)
        self._ai_body.setEnabled(enabled)
        self._preview_chk.setChecked(show_preview)

        self._check_monthly_reset()
        tokens = int(self.db.get_setting_str(AI_KEY_USAGE_TOKENS, "0") or "0")
        self._update_usage_lbl(tokens, provider)

    def _apply_provider_ui(self, provider: str, current_model: str = "") -> None:
        """제공자에 맞게 키 필드/도움말/모델 콤보 갱신."""
        needs_key = PROVIDERS.get(provider, {}).get("needs_key", True)

        self._key_row_widget.setVisible(needs_key)
        self._key_help_lbl.setVisible(needs_key)

        if needs_key:
            url = _KEY_HELP_URLS.get(provider, "")
            self._key_help_lbl.setText(f'<a href="{url}">API 키 발급 페이지 →</a>')
            self._original_key = load_api_key(provider)
            self._key_edit.setText(self._original_key or "")
        else:
            self._original_key = None

        # 모델 콤보
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        models = PROVIDERS.get(provider, {}).get("models", [])
        for m in models:
            self._model_combo.addItem(m, m)
        if current_model in models:
            self._model_combo.setCurrentIndex(models.index(current_model))
        self._model_combo.blockSignals(False)

    def _check_monthly_reset(self) -> None:
        stored_ym = self.db.get_setting_str(AI_KEY_USAGE_RESET, "")
        current_ym = datetime.now().strftime("%Y-%m")
        if stored_ym != current_ym:
            self.db.set_setting_str(AI_KEY_USAGE_TOKENS, "0")
            self.db.set_setting_str(AI_KEY_USAGE_RESET, current_ym)

    def _update_usage_lbl(self, tokens: int, provider: str) -> None:
        cost = tokens / 1000.0 * _COST_PER_1K.get(provider, 0.001)
        if cost > 0:
            self._usage_lbl.setText(f"토큰: {tokens:,}  (예상 비용: ${cost:.3f})")
        else:
            self._usage_lbl.setText(f"토큰: {tokens:,}")

    # ── 이벤트 핸들러 ─────────────────────────────────────────────
    def _on_provider_changed(self) -> None:
        provider = self._provider_combo.currentData()
        current_model = self._model_combo.currentData() or ""
        self._apply_provider_ui(provider, current_model)
        tokens = int(self.db.get_setting_str(AI_KEY_USAGE_TOKENS, "0") or "0")
        self._update_usage_lbl(tokens, provider)
        self._test_result_lbl.clear()

    def _run_test(self) -> None:
        if self._test_worker and self._test_worker.isRunning():
            return
        provider = self._provider_combo.currentData()
        model = self._model_combo.currentData() or ""
        key = self._key_edit.text().strip() or None

        self._test_btn.setEnabled(False)
        self._test_result_lbl.setStyleSheet("font-size: 9pt; color: gray;")
        self._test_result_lbl.setText("⏳ 테스트 중...")

        self._test_worker = _TestWorker(provider, model, key)
        self._test_worker.result_ready.connect(self._on_test_result)
        self._test_worker.start()

    def _on_test_result(self, ok: bool, msg: str) -> None:
        self._test_btn.setEnabled(True)
        color = "#2d8a4e" if ok else "#c0392b"
        self._test_result_lbl.setStyleSheet(f"font-size: 9pt; color: {color};")
        self._test_result_lbl.setText(msg)

    def _reset_usage(self) -> None:
        self.db.set_setting_str(AI_KEY_USAGE_TOKENS, "0")
        self.db.set_setting_str(AI_KEY_USAGE_RESET, datetime.now().strftime("%Y-%m"))
        provider = self._provider_combo.currentData()
        self._update_usage_lbl(0, provider)

    # ── 저장 ─────────────────────────────────────────────────────
    def _save_and_accept(self) -> None:
        provider = self._provider_combo.currentData()
        model = (
            self._model_combo.currentData()
            or PROVIDERS.get(provider, {}).get("default_model", "")
        )

        # API 키 — 변경된 경우만 keyring 갱신
        if PROVIDERS.get(provider, {}).get("needs_key"):
            new_key = self._key_edit.text().strip()
            if new_key and new_key != self._original_key:
                if self._original_key:
                    delete_api_key(provider)
                save_api_key(provider, new_key)

        self.db.set_setting_str(
            AI_KEY_ENABLED, "1" if self._ai_enabled_chk.isChecked() else "0"
        )
        self.db.set_setting_str(AI_KEY_PROVIDER, provider)
        self.db.set_setting_str(AI_KEY_MODEL, model)
        self.db.set_setting_str(
            AI_KEY_SHOW_PREVIEW, "1" if self._preview_chk.isChecked() else "0"
        )
        self.db.set_setting_int("side", self._side_combo.currentData())

        # 인덱스 탭 설정
        self.db.set_setting_int("tab_width", self._tab_width_slider.value())
        self.db.set_setting_int(
            "memo_tab_height", self._memo_tab_height_slider.value()
        )

        self.accept()
