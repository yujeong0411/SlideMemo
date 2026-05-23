"""Slide Memo - Windows 데스크탑용 슬라이드 메모장."""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    Qt,
    QEasingCurve,
    QMimeData,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    QTimer,
    QUrl,
)
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextImageFormat,
    QTextListFormat,
    QTextTableFormat,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLayout,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QStyle,
    QSystemTrayIcon,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from database import DEFAULT_COLOR, IMAGES_DIR, Memo, MemoDatabase


# ----- 상수 -----
TAB_WIDTH = 30          # 인덱스 가로 (기본값; 설정에서 조절)
TAB_WIDTH_MIN = 24
TAB_WIDTH_MAX = 60
EXPANDED_WIDTH = 520
HEIGHT_RATIO = 0.70
ANIM_DURATION = 150  # body 페이드 시간
AUTOSAVE_DELAY = 600
MEMO_TAB_HEIGHT = 116   # 인덱스 세로 (기본값; 설정에서 조절)
MEMO_TAB_HEIGHT_MIN = 60
MEMO_TAB_HEIGHT_MAX = 200
NEW_TAB_HEIGHT = 44

# 8-4 표시 방식: tray=트레이만(Tool 플래그) / taskbar=작업표시줄만 / both=둘 다
DISPLAY_MODE_DEFAULT = "tray"
DISPLAY_MODES = ("tray", "taskbar", "both")

# 리사이즈
MIN_W = 280
MIN_H = 200
RESIZE_GRIP = 6  # 가장자리 드래그 핸들 두께(px)

WEEKDAYS_KO = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

# 8-2 글자색/배경색 팔레트
TEXT_COLOR_PALETTE = [
    "#ef4444",  # 빨강
    "#f97316",  # 주황
    "#eab308",  # 노랑
    "#22c55e",  # 초록
    "#3b82f6",  # 파랑
    "#a855f7",  # 보라
    "#ec4899",  # 분홍
    "#1f2937",  # 검정 (기본 글자색에 가까운 다크)
]
BG_COLOR_PALETTE = [
    "#fef08a",  # 노랑
    "#fed7aa",  # 주황
    "#d9f99d",  # 초록
    "#bfdbfe",  # 파랑
    "#fbcfe8",  # 분홍
    "#e9d5ff",  # 보라
    "#e5e7eb",  # 회색
    None,       # 기본/투명 (배경 해제)
]

COLORS = {
    "ivory":    "#FFEF9F",
    "blush":    "#F5CBCB",
    "peach":    "#FFF2EB",
    "cream":    "#A4CCD9",
    "olive":    "#F1F3E0",
    "lavender": "#F4EEFF",
    "mint":     "#BADFDB",
}

# 그라데이션 프리셋: (x1,y1,x2,y2) + [(stop, hex), ...]
# - sunrise: 로고와 매칭되는 135도 대각선 4색
# - blossom: 180도 위→아래 핑크→크림 2색
GRADIENTS = {
    "sunrise": {
        "coords": (0, 0, 1, 1),
        "stops": [
            (0.0,  "#C6EBD0"),
            (0.35, "#B3D6FB"),
            (0.65, "#DDE4F7"),
            (1.0,  "#FEDB9E"),
        ],
        "representative": "#B3D6FB",  # 탭 색 매핑용 대표색
    },
    "blossom": {
        "coords": (0, 0, 0, 1),
        "stops": [
            (0.0, "#F8C7D9"),
            (1.0, "#FFE3B3"),
        ],
        "representative": "#F8C7D9",
    },
}
COLOR_ORDER = ["sunrise", "blossom", "ivory", "blush", "mint"]


def is_gradient(name: str | None) -> bool:
    return isinstance(name, str) and name in GRADIENTS


def gradient_qss(name: str, *, coords: tuple[float, float, float, float] | None = None) -> str:
    """qlineargradient(...) QSS 문자열. coords로 좌표 오버라이드 가능 (탭 등 짧은 영역)."""
    g = GRADIENTS[name]
    x1, y1, x2, y2 = coords if coords is not None else g["coords"]
    stops = ", ".join(f"stop:{s} {c}" for s, c in g["stops"])
    return f"qlineargradient(x1:{x1}, y1:{y1}, x2:{x2}, y2:{y2}, {stops})"

# 정렬 옵션: (db sort 키, 드롭다운 표시 라벨)
SORT_OPTIONS = [
    ("updated_desc", "수정일 ↓"),
    ("updated_asc", "수정일 ↑"),
    ("title_az", "제목 A-Z"),
    ("created_desc", "생성일 ↓"),
]

STYLE = """
#mainContainer {
    background: transparent;
    border: none;
}
#tabColumn, #tabScroll, #tabsContainer {
    background: transparent;
    border: none;
}
#newTabBtn {
    background-color: rgba(49, 50, 68, 0.85);
    color: #cdd6f4;
    border: none;
    border-radius: 5px;
    font-size: 14pt;
    font-weight: bold;
}
#newTabBtn:hover {
    background-color: rgba(69, 71, 90, 0.95);
    color: #89b4fa;
}
#trashBtn {
    background-color: rgba(49, 50, 68, 0.85);
    color: #cdd6f4;
    border: none;
    border-radius: 5px;
    font-size: 9pt;
}
#trashBtn:hover {
    background-color: rgba(69, 71, 90, 0.95);
    color: #f38ba8;
}
#settingsBtn {
    background-color: rgba(49, 50, 68, 0.85);
    color: #cdd6f4;
    border: none;
    border-radius: 5px;
    font-size: 11pt;
}
#settingsBtn:hover {
    background-color: rgba(69, 71, 90, 0.95);
    color: #89b4fa;
}
QScrollBar:vertical {
    background: transparent;
    width: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(255,255,255,0.18);
    border-radius: 2px;
    min-height: 16px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QMenu {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 4px;
}
QMenu::item {
    padding: 4px 16px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #45475a;
}
QToolTip {
    background-color: #ffffff;
    color: #1e1e2e;
    border: 1px solid #ccc;
    padding: 4px 8px;
}
"""

_HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def resolve_color(value: str | None) -> str:
    """색 이름(프리셋) 또는 hex 코드를 실제 hex 문자열로 변환.
    그라데이션 키면 그 그라데이션의 대표색을 반환 (탭 등 hex가 필요한 곳용)."""
    if value in COLORS:
        return COLORS[value]
    if is_gradient(value):
        return GRADIENTS[value]["representative"]
    if isinstance(value, str) and _HEX_COLOR_RE.fullmatch(value.strip()):
        return value.strip()
    if DEFAULT_COLOR in COLORS:
        return COLORS[DEFAULT_COLOR]
    return GRADIENTS[DEFAULT_COLOR]["representative"]


def _text_color_for(hex_color: str) -> str:
    """배경 hex의 밝기에 따라 어두운/밝은 글자색을 고른다."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#1e1e2e"
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#1e1e2e" if luminance > 0.55 else "#f5f5f5"


# 프리셋은 라이트 톤이라 어두운 글자, 커스텀 다크 색이면 밝은 글자로 전환.
# 그라데이션은 라이트 톤 가정 → 어두운 글자 + 에디터 투명 처리(bodyPanel 한 장에 그라데이션이 비쳐 보이게).
def theme_for(color: str | None) -> dict[str, str]:
    if is_gradient(color):
        return {
            "bg": gradient_qss(color),
            "editor_bg": "transparent",
            "text": "#1e1e2e",
            "text_sub": "rgba(30, 30, 46, 0.55)",
            "border": "rgba(0, 0, 0, 0.15)",
            "focus": "#1e1e2e",
            "input_bg": "rgba(255, 255, 255, 0.35)",
        }
    base = resolve_color(color)
    if _text_color_for(base) == "#1e1e2e":
        return {
            "bg": base,
            "editor_bg": base,
            "text": "#1e1e2e",
            "text_sub": "rgba(30, 30, 46, 0.55)",
            "border": "rgba(0, 0, 0, 0.15)",
            "focus": "#1e1e2e",
            "input_bg": "rgba(0, 0, 0, 0.05)",
        }
    return {
        "bg": base,
        "editor_bg": base,
        "text": "#f5f5f5",
        "text_sub": "rgba(245, 245, 245, 0.6)",
        "border": "rgba(255, 255, 255, 0.22)",
        "focus": "#f5f5f5",
        "input_bg": "rgba(255, 255, 255, 0.10)",
    }


def body_stylesheet(t: dict[str, str]) -> str:
    return f"""
    #bodyPanel {{
        background: {t["bg"]};
        border: 1px solid {t["border"]};
        border-radius: 8px;
    }}
    QLineEdit#searchInput {{
        background-color: {t["input_bg"]};
        color: {t["text"]};
        border: 1px solid {t["border"]};
        border-radius: 4px;
        padding: 4px 8px;
        selection-background-color: {t["focus"]};
    }}
    QLineEdit#searchInput:focus {{
        border: 1px solid {t["focus"]};
    }}
    QLineEdit#titleInput {{
        background-color: transparent;
        color: {t["text"]};
        border: none;
        border-bottom: 1px solid {t["border"]};
        font-size: 13pt;
        font-weight: bold;
        padding: 4px;
    }}
    QLineEdit#titleInput:focus {{
        border-bottom: 1px solid {t["focus"]};
    }}
    QTextEdit#editor {{
        background-color: {t["editor_bg"]};
        color: {t["text"]};
        border: 1px solid {t["border"]};
        border-radius: 4px;
        padding: 6px;
        selection-background-color: {t["focus"]};
    }}
    QTextEdit#editor QWidget {{
        background-color: {t["editor_bg"]};
    }}
    QTextEdit#editor:focus {{
        border: 1px solid {t["focus"]};
    }}
    QPushButton#iconBtn {{
        background-color: transparent;
        color: {t["text"]};
        border: none;
        padding: 4px 8px;
        font-size: 12pt;
    }}
    QPushButton#iconBtn:hover {{
        background-color: rgba(0,0,0,0.10);
        border-radius: 4px;
    }}
    QPushButton#backBtn {{
        background-color: {t["input_bg"]};
        color: {t["text"]};
        border: 1px solid {t["border"]};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 10pt;
        text-align: left;
    }}
    QPushButton#backBtn:hover {{
        background-color: rgba(0,0,0,0.12);
    }}
    QComboBox#sortCombo {{
        background-color: {t["input_bg"]};
        color: {t["text"]};
        border: 1px solid {t["border"]};
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 9pt;
    }}
    QComboBox#sortCombo:hover {{
        border: 1px solid {t["focus"]};
    }}
    QComboBox#sortCombo::drop-down {{
        border: none;
        width: 16px;
    }}
    QComboBox#sortCombo QAbstractItemView {{
        background-color: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        selection-background-color: #45475a;
        outline: 0;
    }}
    QPushButton#fmtBtn, QToolButton#fmtBtn {{
        background-color: transparent;
        color: {t["text"]};
        border: 1px solid transparent;
        border-radius: 3px;
        font-size: 10pt;
    }}
    QPushButton#fmtBtn:hover, QToolButton#fmtBtn:hover {{
        background-color: rgba(0,0,0,0.10);
        border: 1px solid {t["border"]};
    }}
    QPushButton#fmtBtn:pressed, QToolButton#fmtBtn:pressed {{
        background-color: rgba(0,0,0,0.18);
    }}
    QToolButton#fmtBtn::menu-indicator {{
        width: 0;
        height: 0;
    }}
    QPushButton#aiFeatureBtn {{
        background-color: rgba(0,0,0,0.06);
        color: {t["text"]};
        border: 1px solid {t["border"]};
        border-radius: 4px;
        font-size: 8pt;
        padding: 2px 7px;
    }}
    QPushButton#aiFeatureBtn:hover {{
        background-color: rgba(0,0,0,0.13);
        border: 1px solid {t["focus"]};
    }}
    QPushButton#aiFeatureBtn:pressed {{
        background-color: rgba(0,0,0,0.20);
    }}
    """


class MemoTabButton(QPushButton):
    """메모별 색깔 탭. 세로 회전한 제목을 표시."""

    side = "right"  # 클래스 변수: 윈도우가 좌/우 전환 시 갱신
    button_height = MEMO_TAB_HEIGHT  # 클래스 변수: 설정에서 조절 시 갱신

    SEL_BAR_WIDTH = 4  # 선택 인디케이터 띠 굵기 (px)
    SEL_BAR_COLOR = "#4a4a52"  # 어두운 회색 (검정보다 부드럽게)

    def __init__(self, memo: Memo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.memo_id = memo.id
        self.color_name = memo.color
        if is_gradient(memo.color):
            # 탭은 세로로 길쭉 → 위→아래 짧은 그라데이션으로 표현
            self._bg = gradient_qss(memo.color, coords=(0, 0, 0, 1))
            self._fg = "#1e1e2e"
        else:
            self._bg = resolve_color(memo.color)
            self._fg = _text_color_for(self._bg)
        self.memo_title = memo.title.strip() or "(제목 없음)"
        self.is_pinned = memo.is_pinned
        self._selected = False
        self.setFixedHeight(MemoTabButton.button_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        tip = ("📌 " if self.is_pinned else "") + self.memo_title
        self.setToolTip(tip)
        self.update_style(selected=False)

    def paintEvent(self, event) -> None:  # noqa: N802
        # 1) 기본 그리기 (stylesheet 배경)
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1.5) 선택 인디케이터 — stylesheet border가 좌/우 모드에서 가시성이 일관되지 않아
        #     직접 그린다. accent는 본문과 만나는 면 = side의 반대편.
        if self._selected:
            accent = "left" if MemoTabButton.side == "right" else "right"
            bar_w = MemoTabButton.SEL_BAR_WIDTH
            if accent == "left":
                bar_rect = QRect(0, 0, bar_w, self.height())
            else:
                bar_rect = QRect(self.width() - bar_w, 0, bar_w, self.height())
            painter.fillRect(bar_rect, QColor(MemoTabButton.SEL_BAR_COLOR))

        # 2) 고정 표시 (회전 전, 탭 상단 중앙)
        pin_h = 0
        if self.is_pinned:
            pin_h = 15
            pf = self.font()
            pf.setPointSize(9)
            painter.setFont(pf)
            painter.setPen(QColor(self._fg))
            painter.drawText(
                QRect(0, 1, self.width(), pin_h),
                int(Qt.AlignmentFlag.AlignCenter),
                "📌",
            )

        # 3) 세로 회전 제목 (시계방향 90도 → 위에서 아래로 읽힘)
        #    고정 표시가 있으면 그만큼 아래로 내려서 중앙 정렬
        painter.translate(self.width() / 2, (self.height() + pin_h) / 2)
        painter.rotate(90)
        font = self.font()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(self._fg))
        fm = painter.fontMetrics()
        avail_h = self.height() - pin_h
        max_w = avail_h - 10
        elided = fm.elidedText(self.memo_title, Qt.TextElideMode.ElideRight, max_w)
        rect = QRect(
            -avail_h // 2, -self.width() // 2, avail_h, self.width()
        )
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), elided)
        painter.end()

    def update_style(self, selected: bool) -> None:
        # stylesheet은 배경 + 둥근 모서리만 담당. 선택 인디케이터는 paintEvent에서 직접 그림.
        self._selected = selected
        bg = self._bg
        # accent 반대쪽만 둥글게 (선택 시), 미선택 시는 균일 5px
        accent = "left" if MemoTabButton.side == "right" else "right"
        if selected:
            if accent == "left":
                radius = (
                    "border-top-left-radius: 0;"
                    "border-bottom-left-radius: 0;"
                    "border-top-right-radius: 5px;"
                    "border-bottom-right-radius: 5px;"
                )
            else:
                radius = (
                    "border-top-right-radius: 0;"
                    "border-bottom-right-radius: 0;"
                    "border-top-left-radius: 5px;"
                    "border-bottom-left-radius: 5px;"
                )
            self.setStyleSheet(
                f"QPushButton {{"
                f"  background: {bg};"
                f"  border: none;"
                f"  {radius}"
                f"}}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{"
                f"  background: {bg};"
                f"  border: none;"
                f"  border-radius: 5px;"
                f"}}"
            )
        self.update()


class ColorDot(QPushButton):
    """색상 선택용 작은 원형 버튼."""

    def __init__(self, color_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color_name = color_name
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(color_name)
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        border_color = "#1e1e2e" if selected else "rgba(0,0,0,0.25)"
        border_w = 2 if selected else 1
        if is_gradient(self.color_name):
            bg = gradient_qss(self.color_name)
        else:
            bg = COLORS[self.color_name]
        self.setStyleSheet(
            f"background: {bg};"
            f" border: {border_w}px solid {border_color};"
            f" border-radius: 8px;"
        )


class RichPasteTextEdit(QTextEdit):
    """클립보드 이미지를 파일로 저장 후 에디터에 바로 표시하는 리치 텍스트 에디터."""

    IMG_MAX_WIDTH = 440  # 에디터 폭에 맞춘 이미지 표시 최대 폭

    def insertFromMimeData(self, source: QMimeData) -> None:  # noqa: N802
        if source is not None and source.hasImage():
            image = source.imageData()
            if isinstance(image, QImage) and not image.isNull():
                self._insert_image(image)
                return
        super().insertFromMimeData(source)

    def _insert_image(self, image: QImage) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        path = IMAGES_DIR / f"img_{ts}.png"
        if not image.save(str(path), "PNG"):
            return
        fmt = QTextImageFormat()
        fmt.setName(path.as_posix())  # 절대경로 → toHtml 시 <img src=...>
        w, h = image.width(), image.height()
        if w > self.IMG_MAX_WIDTH:
            ratio = self.IMG_MAX_WIDTH / w
            fmt.setWidth(self.IMG_MAX_WIDTH)
            fmt.setHeight(h * ratio)
        else:
            fmt.setWidth(w)
            fmt.setHeight(h)
        self.textCursor().insertImage(fmt)


class LinkDialog(QDialog):
    """링크 삽입 다이얼로그 (표시 텍스트 + URL)."""

    def __init__(self, display_text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("링크 삽입")
        self.setMinimumWidth(320)
        layout = QFormLayout(self)
        self.text_edit = QLineEdit(display_text)
        self.text_edit.setPlaceholderText("표시 텍스트")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://...")
        layout.addRow("표시 텍스트:", self.text_edit)
        layout.addRow("URL:", self.url_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str]:
        return self.text_edit.text().strip(), self.url_edit.text().strip()


class TableDialog(QDialog):
    """표 삽입 다이얼로그 (행/열/헤더)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("표 삽입")
        layout = QVBoxLayout(self)
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("행:"))
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 20)
        self.rows_spin.setValue(3)
        size_row.addWidget(self.rows_spin)
        size_row.addSpacing(12)
        size_row.addWidget(QLabel("열:"))
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 10)
        self.cols_spin.setValue(3)
        size_row.addWidget(self.cols_spin)
        size_row.addStretch(1)
        layout.addLayout(size_row)
        self.header_check = QCheckBox("헤더 행 포함")
        self.header_check.setChecked(True)
        layout.addWidget(self.header_check)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("삽입")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[int, int, bool]:
        return self.rows_spin.value(), self.cols_spin.value(), self.header_check.isChecked()


class FlowLayout(QLayout):
    """가로로 채우다 폭이 부족하면 다음 줄로 wrap. Qt 공식 FlowLayout 기반.
    추가 보정:
    - fixed-size 위젯의 sizeHint 우회 (_effective_size)
    - width<=0인 첫 layout 패스에서 한 줄 높이 fallback (heightForWidth) — 부모 layout이
      비정상으로 큰 wrap 높이를 받아 윈도우 자식들이 어긋난 위치에 잠시 그려지는
      "공중부양" 현상 방지."""

    _QWIDGETSIZE_MAX = 16777215

    def __init__(
        self,
        parent: QWidget | None = None,
        margin: int = 0,
        h_spacing: int = -1,
        v_spacing: int = -1,
    ) -> None:
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items: list = []

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def addSpacing(self, size: int) -> None:  # noqa: N802
        self.addItem(
            QSpacerItem(
                size, 1,
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum,
            )
        )

    def horizontalSpacing(self) -> int:  # noqa: N802
        if self._h_spacing >= 0:
            return self._h_spacing
        return self._smart_spacing(QStyle.PixelMetric.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self) -> int:  # noqa: N802
        if self._v_spacing >= 0:
            return self._v_spacing
        return self._smart_spacing(QStyle.PixelMetric.PM_LayoutVerticalSpacing)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        # 첫 layout 패스에서 width가 결정되기 전 0으로 호출되면 wrap이 극단적으로
        # 일어나 매우 큰 높이를 반환 → 부모 layout이 그 값을 받아 잠깐 비정상 배치 →
        # 윈도우 자식 위젯들이 "공중부양"하는 시각 글리치. 한 줄 높이 fallback.
        if width <= 0:
            return self._single_row_height()
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def _single_row_height(self) -> int:
        h = 0
        for item in self._items:
            h = max(h, self._effective_size(item).height())
        margins = self.contentsMargins()
        return h + margins.top() + margins.bottom()

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(self._effective_size(item))
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )
        return size

    def _effective_size(self, item) -> QSize:
        sh = item.sizeHint()
        w = item.widget()
        if w is None:
            return sh
        width = (
            w.minimumWidth()
            if w.minimumWidth() == w.maximumWidth()
            and w.maximumWidth() < self._QWIDGETSIZE_MAX
            else sh.width()
        )
        height = (
            w.minimumHeight()
            if w.minimumHeight() == w.maximumHeight()
            and w.maximumHeight() < self._QWIDGETSIZE_MAX
            else sh.height()
        )
        return QSize(width, height)

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(),
            -margins.right(), -margins.bottom(),
        )
        x = effective.x()
        y = effective.y()
        line_height = 0
        for item in self._items:
            wid = item.widget()
            space_x = self.horizontalSpacing()
            if space_x == -1 and wid is not None:
                space_x = wid.style().layoutSpacing(
                    QSizePolicy.ControlType.PushButton,
                    QSizePolicy.ControlType.PushButton,
                    Qt.Orientation.Horizontal,
                )
            space_y = self.verticalSpacing()
            if space_y == -1 and wid is not None:
                space_y = wid.style().layoutSpacing(
                    QSizePolicy.ControlType.PushButton,
                    QSizePolicy.ControlType.PushButton,
                    Qt.Orientation.Vertical,
                )
            esize = self._effective_size(item)
            next_x = x + esize.width() + space_x
            if next_x - space_x > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + space_y
                next_x = x + esize.width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), esize))
            x = next_x
            line_height = max(line_height, esize.height())
        return y + line_height - rect.y() + margins.bottom()

    def _smart_spacing(self, pm) -> int:
        parent = self.parent()
        if parent is None:
            return -1
        if parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)
        return parent.spacing()


class FormatToolbar(QWidget):
    """리치텍스트 서식바: 굵게/기울임/밑줄/취소선 + 불릿/번호 리스트.
    폭이 부족하면 FlowLayout이 자동으로 다음 줄로 wrap한다."""

    def __init__(self, editor: QTextEdit, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = editor
        layout = FlowLayout(self, margin=0, h_spacing=2, v_spacing=2)
        sp = self.sizePolicy()
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)
        # 첫 표시 시 한 줄 높이를 보장해 wrap된 큰 값이 부모로 전파되지 않게 한다.
        self.setMinimumHeight(24)

        self._add_icon_btn("fmt_bold.svg", "굵게 (Ctrl+B)", self.toggle_bold)
        self._add_icon_btn("fmt_italic.svg", "기울임 (Ctrl+I)", self.toggle_italic)
        self._add_icon_btn("fmt_underline.svg", "밑줄 (Ctrl+U)", self.toggle_underline)
        self._add_icon_btn("fmt_strike.svg", "취소선", self.toggle_strike)
        self._add_color_menu_btn("fmt_text_color.svg", "글자색", kind="text")
        self._add_color_menu_btn("fmt_bg_color.svg", "배경색", kind="bg")
        self._add_sep()
        self._add_icon_btn("fmt_bullet.svg", "불릿 목록", self.bullet_list)
        self._add_icon_btn("fmt_numbered.svg", "번호 목록", self.numbered_list)
        self._add_icon_btn(
            "fmt_align_left.svg", "왼쪽 정렬", lambda: self.set_alignment("left")
        )
        self._add_icon_btn(
            "fmt_align_center.svg", "가운데 정렬", lambda: self.set_alignment("center")
        )
        self._add_icon_btn(
            "fmt_align_right.svg", "오른쪽 정렬", lambda: self.set_alignment("right")
        )
        self._add_sep()
        self._add_icon_btn("link_icon.svg", "링크 삽입 (Ctrl+K)", self.insert_link)
        self._add_icon_btn("fmt_table.svg", "표 삽입", self.insert_table)
        self._add_datetime_btn()
        # FlowLayout은 좌측 정렬 + 자동 wrap이라 stretch가 필요 없다.

    # ----- height for width 위임 (FlowLayout이 폭에 따라 wrap된 높이 계산) -----
    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self.layout().heightForWidth(width)

    def _add_btn(
        self,
        label: str,
        tip: str,
        slot,
        *,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        strike: bool = False,
    ) -> QPushButton:
        b = QPushButton(label, self)
        b.setObjectName("fmtBtn")
        b.setToolTip(tip)
        b.setFixedSize(28, 24)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # 클릭해도 에디터 포커스 유지
        f = b.font()
        f.setBold(bold)
        f.setItalic(italic)
        f.setUnderline(underline)
        f.setStrikeOut(strike)
        b.setFont(f)
        b.clicked.connect(slot)
        self.layout().addWidget(b)
        return b

    # ----- 서식 토글 (선택 영역 있으면 그 영역, 없으면 이후 입력에 적용) -----
    def toggle_bold(self) -> None:
        normal = int(QFont.Weight.Normal)
        is_bold = self.editor.fontWeight() > normal
        self.editor.setFontWeight(
            QFont.Weight.Normal if is_bold else QFont.Weight.Bold
        )
        self.editor.setFocus()

    def toggle_italic(self) -> None:
        self.editor.setFontItalic(not self.editor.fontItalic())
        self.editor.setFocus()

    def toggle_underline(self) -> None:
        self.editor.setFontUnderline(not self.editor.fontUnderline())
        self.editor.setFocus()

    def toggle_strike(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(
            not self.editor.currentCharFormat().fontStrikeOut()
        )
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def bullet_list(self) -> None:
        self.editor.textCursor().createList(QTextListFormat.Style.ListDisc)
        self.editor.setFocus()

    def numbered_list(self) -> None:
        self.editor.textCursor().createList(QTextListFormat.Style.ListDecimal)
        self.editor.setFocus()

    # ----- 정렬 (선택영역 또는 현재 줄) -----
    def set_alignment(self, where: str) -> None:
        mapping = {
            "left": Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignCenter,
            "right": Qt.AlignmentFlag.AlignRight,
        }
        fmt = QTextBlockFormat()
        fmt.setAlignment(mapping.get(where, Qt.AlignmentFlag.AlignLeft))
        # mergeBlockFormat은 선택영역이 있으면 그 영역의 모든 블록, 없으면 현재 블록에 적용.
        self.editor.textCursor().mergeBlockFormat(fmt)
        self.editor.setFocus()

    # ----- 글자색 / 배경색 (선택영역 필수) -----
    def _toast_no_selection(self) -> None:
        win = self.editor.window()
        if hasattr(win, "_show_toast"):
            win._show_toast("색을 적용할 텍스트를 먼저 선택하세요.")

    def apply_text_color(self, color_hex: str) -> None:
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            self._toast_no_selection()
            return
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color_hex))
        cursor.mergeCharFormat(fmt)
        self.editor.setFocus()

    def apply_bg_color(self, color_hex: str | None) -> None:
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            self._toast_no_selection()
            return
        fmt = QTextCharFormat()
        if color_hex is None:
            # 배경 해제 → transparent brush
            fmt.setBackground(QBrush(Qt.GlobalColor.transparent))
        else:
            fmt.setBackground(QColor(color_hex))
        cursor.mergeCharFormat(fmt)
        self.editor.setFocus()

    def pick_custom_text_color(self) -> None:
        chosen = QColorDialog.getColor(
            QColor("#1f2937"), self, "글자색 선택",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
        if chosen.isValid():
            self.apply_text_color(chosen.name())

    def pick_custom_bg_color(self) -> None:
        chosen = QColorDialog.getColor(
            QColor("#fef08a"), self, "배경색 선택",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
        if chosen.isValid():
            self.apply_bg_color(chosen.name())

    def _add_color_menu_btn(self, svg_name: str, tip: str, *, kind: str) -> QToolButton:
        """kind='text' or 'bg'. 클릭 시 8색 그리드 + 사용자 정의 메뉴 팝업."""
        btn = QToolButton(self)
        btn.setObjectName("fmtBtn")
        btn.setToolTip(tip)
        btn.setFixedSize(28, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        icon_path = _asset(svg_name)
        if icon_path.exists():
            btn.setIcon(QIcon(str(icon_path)))
            btn.setIconSize(QSize(16, 16))
        btn.setMenu(self._build_color_menu(btn, kind))
        self.layout().addWidget(btn)
        return btn

    def _build_color_menu(self, anchor: QWidget, kind: str) -> QMenu:
        palette = TEXT_COLOR_PALETTE if kind == "text" else BG_COLOR_PALETTE
        menu = QMenu(self)

        # 8 swatches in 4x2 grid
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setSpacing(4)
        for i, color in enumerate(palette):
            sw = QPushButton()
            sw.setFixedSize(22, 22)
            sw.setCursor(Qt.CursorShape.PointingHandCursor)
            if color is None:
                # "기본" / 배경 해제 — 대각선 빗금으로 표시
                sw.setText("✕")
                sw.setStyleSheet(
                    "background: white; color: #888; border: 1px solid rgba(0,0,0,0.2);"
                    " font-size: 9pt;"
                )
                sw.setToolTip("배경 해제")
            else:
                sw.setStyleSheet(
                    f"background: {color}; border: 1px solid rgba(0,0,0,0.2);"
                )
                sw.setToolTip(color)
            sw.clicked.connect(
                lambda _c, h=color, k=kind: self._on_swatch_clicked(h, k, menu)
            )
            grid.addWidget(sw, i // 4, i % 4)
        wa = QWidgetAction(menu)
        wa.setDefaultWidget(grid_w)
        menu.addAction(wa)

        menu.addSeparator()
        custom_act = menu.addAction("사용자 정의...")
        if kind == "text":
            custom_act.triggered.connect(self.pick_custom_text_color)
        else:
            custom_act.triggered.connect(self.pick_custom_bg_color)
        return menu

    def _on_swatch_clicked(self, color_hex: str | None, kind: str, menu: QMenu) -> None:
        if kind == "text":
            # 글자색은 None 값이 없지만 안전상 체크
            if color_hex is not None:
                self.apply_text_color(color_hex)
        else:
            self.apply_bg_color(color_hex)
        menu.close()

    # ----- 구분선 / 드롭다운 헬퍼 -----
    def _add_sep(self) -> None:
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(18)
        sep.setStyleSheet("color: rgba(0,0,0,0.15);")
        self.layout().addWidget(sep)

    def _add_icon_btn(self, svg_name: str, tip: str, slot) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("fmtBtn")
        btn.setToolTip(tip)
        btn.setFixedSize(28, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        icon_path = _asset(svg_name)
        if icon_path.exists():
            btn.setIcon(QIcon(str(icon_path)))
            btn.setIconSize(QSize(16, 16))
        btn.clicked.connect(slot)
        self.layout().addWidget(btn)
        return btn

    def _add_datetime_btn(self) -> None:
        btn = QToolButton(self)
        btn.setObjectName("fmtBtn")
        btn.setToolTip("날짜/시간 삽입")
        btn.setFixedSize(28, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        icon_path = _asset("calendar_icon.svg")
        if icon_path.exists():
            btn.setIcon(QIcon(str(icon_path)))
            btn.setIconSize(QSize(16, 16))
        menu = QMenu(btn)
        menu.addAction("윈도우 메모장 포맷  (F5)", lambda: self.insert_datetime("notepad"))
        menu.addAction("날짜만  (Ctrl+;)", lambda: self.insert_datetime("date"))
        menu.addAction("시간만  (Ctrl+Shift+;)", lambda: self.insert_datetime("time"))
        menu.addAction("ISO 형식  (Ctrl+Alt+;)", lambda: self.insert_datetime("iso"))
        menu.addAction("한국식  (Ctrl+Shift+H)", lambda: self.insert_datetime("korean"))
        btn.setMenu(menu)
        self.layout().addWidget(btn)

    # ----- 링크 삽입 -----
    def insert_link(self) -> None:
        cursor = self.editor.textCursor()
        selected = cursor.selectedText().strip()

        if selected:
            url, ok = QInputDialog.getText(
                self, "링크 삽입", "URL:", text=""
            )
            if not ok or not url.strip():
                self.editor.setFocus()
                return
            url = url.strip()
            display = selected
        else:
            dlg = LinkDialog(parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                self.editor.setFocus()
                return
            display, url = dlg.values()
            if not url:
                self.editor.setFocus()
                return

        if url and not url.startswith(("http://", "https://", "ftp://", "mailto:")):
            url = "https://" + url

        fmt = QTextCharFormat()
        fmt.setAnchor(True)
        fmt.setAnchorHref(url)
        fmt.setForeground(QColor("#89b4fa"))
        fmt.setFontUnderline(True)

        cursor = self.editor.textCursor()
        if selected:
            cursor.mergeCharFormat(fmt)
        else:
            cursor.insertText(display if display else url, fmt)

        # 링크 삽입 후 서식 초기화
        reset = QTextCharFormat()
        reset.setAnchor(False)
        reset.setAnchorHref("")
        reset.setForeground(self.editor.palette().windowText().color())
        reset.setFontUnderline(False)
        self.editor.setCurrentCharFormat(reset)
        self.editor.setFocus()

    # ----- 표 삽입 -----
    def insert_table(self) -> None:
        dlg = TableDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.editor.setFocus()
            return

        rows, cols, has_header = dlg.values()

        fmt = QTextTableFormat()
        fmt.setCellPadding(4)
        fmt.setCellSpacing(0)
        fmt.setBorderStyle(QTextTableFormat.BorderStyle.BorderStyle_Solid)
        fmt.setBorder(1)
        fmt.setWidth(QTextTableFormat.WidthType.PercentageWidth if False else fmt.width())

        cursor = self.editor.textCursor()
        table = cursor.insertTable(rows, cols, fmt)

        if has_header:
            header_fmt = QTextCharFormat()
            header_fmt.setFontWeight(QFont.Weight.Bold)
            for col in range(cols):
                cell = table.cellAt(0, col)
                cell_cursor = cell.firstCursorPosition()
                cell_cursor.mergeCharFormat(header_fmt)
                cell_cursor.insertText(f"헤더{col + 1}")

        # 첫 셀로 커서 이동
        first_cell = table.cellAt(0, 0).firstCursorPosition()
        self.editor.setTextCursor(first_cell)
        self.editor.setFocus()

    # ----- 날짜/시간 삽입 -----
    def insert_datetime(self, fmt_key: str) -> None:
        now = datetime.now()
        if fmt_key == "notepad":
            raw = now.strftime("%p %I:%M %Y-%m-%d")
            text = raw.replace("AM", "오전").replace("PM", "오후")
        elif fmt_key == "date":
            text = now.strftime("%Y-%m-%d")
        elif fmt_key == "time":
            text = now.strftime("%H:%M")
        elif fmt_key == "iso":
            text = now.strftime("%Y-%m-%dT%H:%M:%S")
        else:  # korean
            text = f"{now.strftime('%Y년 %m월 %d일')} {WEEKDAYS_KO[now.weekday()]}"

        self.editor.textCursor().insertText(text)
        self.editor.setFocus()


class DragGrip(QWidget):
    """탭 컬럼 상단의 세로 이동 그립 (크기 변경 없이 y 위치만 이동)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("드래그하여 세로 위치 이동")
        self._press_global = None
        self._start_geom = None
        self._drag_icon: QIcon | None = None
        icon_path = _asset("pan_tool.svg")
        if icon_path.exists():
            self._drag_icon = QIcon(str(icon_path))

    def paintEvent(self, event) -> None:  # noqa: N802
        from PyQt6.QtCore import QRect
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 다른 탭 버튼과 동일한 어두운 배경
        painter.setBrush(QColor(49, 50, 68, 216))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 5, 5)
        if self._drag_icon is not None and not self._drag_icon.isNull():
            # tab_column 폭에 비례 — 너무 작으면 안 보이고 너무 크면 그립 영역 초과
            icon_size = max(12, min(int(self.width() * 0.55), 32))
            x = (self.width() - icon_size) // 2
            y = (self.height() - icon_size) // 2
            self._drag_icon.paint(painter, QRect(x, y, icon_size, icon_size))
        else:
            painter.setBrush(QColor("#cdd6f4"))
            cx = self.width() / 2
            cy = self.height() / 2
            for dx in (-5, 0, 5):
                for dy in (-3, 3):
                    painter.drawEllipse(int(cx + dx - 1.5), int(cy + dy - 1.5), 3, 3)
        painter.end()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._start_geom = self.window().geometry()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._press_global is None:
            return super().mouseMoveEvent(event)
        win = self.window()
        if not isinstance(win, SlideMemoWindow):
            return
        dy = event.globalPosition().toPoint().y() - self._press_global.y()
        g = self._start_geom
        screen = win._screen_rect()
        new_y = g.y() + dy
        new_y = max(
            screen.y(),
            min(new_y, screen.y() + screen.height() - g.height()),
        )
        win.setGeometry(g.x(), new_y, g.width(), g.height())
        event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if self._press_global is not None:
            self._press_global = None
            self._start_geom = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            win = self.window()
            if isinstance(win, SlideMemoWindow):
                win._save_user_size()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ResizeHandle(QWidget):
    """창 가장자리에 깔리는 투명 드래그 핸들. edge ∈ {left, top, bottom}."""

    def __init__(self, parent: QWidget, edge: str) -> None:
        super().__init__(parent)
        self.edge = edge
        self.setStyleSheet("background: transparent;")
        if edge in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        self._press_global = None
        self._start_geom = None

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._start_geom = self.window().geometry()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._press_global is None:
            return super().mouseMoveEvent(event)
        win = self.window()
        if not isinstance(win, SlideMemoWindow):
            return
        delta = event.globalPosition().toPoint() - self._press_global
        g = self._start_geom
        screen = win._screen_rect()

        if self.edge == "left":
            # 우측 모드: 좌측 가장자리 드래그 → 폭 조절 (우측 끝 고정)
            new_w = max(MIN_W, min(g.width() - delta.x(), screen.width()))
            new_x = g.x() + (g.width() - new_w)
            new_x = max(screen.x(), new_x)
            win.setGeometry(new_x, g.y(), new_w, g.height())
        elif self.edge == "right":
            # 좌측 모드: 우측 가장자리 드래그 → 폭 조절 (좌측 끝 고정)
            new_w = max(MIN_W, min(g.width() + delta.x(), screen.width()))
            if g.x() + new_w > screen.x() + screen.width():
                new_w = screen.x() + screen.width() - g.x()
            win.setGeometry(g.x(), g.y(), new_w, g.height())
        elif self.edge == "top":
            new_h = max(MIN_H, min(g.height() - delta.y(), screen.height()))
            new_y = g.y() + (g.height() - new_h)
            new_y = max(screen.y(), new_y)
            win.setGeometry(g.x(), new_y, g.width(), new_h)
        elif self.edge == "bottom":
            new_h = max(MIN_H, min(g.height() + delta.y(), screen.height()))
            max_bottom = screen.y() + screen.height()
            if g.y() + new_h > max_bottom:
                new_h = max_bottom - g.y()
            win.setGeometry(g.x(), g.y(), g.width(), new_h)
        event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if self._press_global is not None:
            self._press_global = None
            self._start_geom = None
            win = self.window()
            if isinstance(win, SlideMemoWindow):
                win._save_user_size()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class SlideMemoWindow(QWidget):
    def __init__(self, db: MemoDatabase) -> None:
        super().__init__()
        self.db = db
        self.current_memo: Memo | None = None
        self.is_expanded = False
        self.trash_mode = False
        self._trash_preview_id: int | None = None  # 휴지통에서 미리보기 중인 메모
        self._quitting = False
        self._ai_worker: object | None = None
        self._ai_pending: str | None = None  # 진행 중인 feature_key
        # 0=오른쪽, 1=왼쪽 가장자리
        self.side = "left" if db.get_setting_int("side", 0) == 1 else "right"

        self._load_tab_geometry()  # tab_width 등을 _setup_window/_build_ui 전에 결정
        self._load_display_mode()  # Tool 플래그 결정에 필요
        self._setup_window()
        self._setup_fonts()
        self._build_ui()
        self._setup_animation()
        self._setup_shortcuts()
        self._setup_autosave()
        self._apply_memo_theme(DEFAULT_COLOR)  # 초기 테마
        self._load_user_size()  # DB에서 사용자 사이즈 로드 (없으면 기본값)
        self.body.hide()  # 시작은 접힘 상태 → body는 숨김
        self.handle_left.hide()
        self.handle_right.hide()
        self.handle_top.hide()
        self.handle_bottom.hide()
        self._position_collapsed()
        self._refresh_memo_tabs(select_first=True)
        self._refresh_ai_bar()
        # 첫 expand 시 발생하는 lazy init 버벅임을 줄이기 위해 사용자가 안 보는
        # 사이 (윈도우 show 직전) body 위젯을 offscreen pixmap에 한 번 render.
        # → editor의 QTextDocument 초기화, stylesheet 적용, FlowLayout 첫 패스,
        # 폰트 캐시가 미리 트리거된다.
        self._warm_up_body()

    def _warm_up_body(self) -> None:
        try:
            self.body.ensurePolished()
            self.format_toolbar.ensurePolished()
            self.editor.ensurePolished()
            self.title_input.ensurePolished()
            self.body.layout().activate()
            warm_size = self._expanded_geometry().size()
            if warm_size.width() > 0 and warm_size.height() > 0:
                pix = QPixmap(warm_size)
                pix.fill(Qt.GlobalColor.transparent)
                self.body.render(pix)
        except Exception:
            pass  # warm-up은 실패해도 앱 동작에 무관

    # ----- setup -----
    def _load_tab_geometry(self) -> None:
        """DB에서 인덱스 탭 폭/각 탭 높이 로드. 범위 밖 값은 clamp."""
        w = self.db.get_setting_int("tab_width", TAB_WIDTH)
        self.tab_width = max(TAB_WIDTH_MIN, min(w, TAB_WIDTH_MAX))
        h = self.db.get_setting_int("memo_tab_height", MEMO_TAB_HEIGHT)
        self.memo_tab_height = max(MEMO_TAB_HEIGHT_MIN, min(h, MEMO_TAB_HEIGHT_MAX))
        MemoTabButton.button_height = self.memo_tab_height

    def _apply_btn_icon_sizes(self) -> None:
        """tab_width에 따라 컬럼 버튼 아이콘/폰트 크기를 비례 조절.
        (DragGrip은 paintEvent에서 자체 폭 기반으로 그리므로 자동 반응)"""
        size = max(12, min(int(self.tab_width * 0.55), 32))
        self.settings_btn.setIconSize(QSize(size, size))
        self.trash_btn.setIconSize(QSize(size, size))
        # new_tab_btn의 "＋" 텍스트 크기도 함께 줄임
        font = self.new_tab_btn.font()
        font.setPointSize(max(9, int(size * 0.85)))
        self.new_tab_btn.setFont(font)

    def _load_display_mode(self) -> None:
        """display_mode: 'tray' / 'taskbar' / 'both'."""
        m = self.db.get_setting_str("display_mode", DISPLAY_MODE_DEFAULT)
        self.display_mode = m if m in DISPLAY_MODES else DISPLAY_MODE_DEFAULT

    def _window_flags_for_mode(self) -> Qt.WindowType:
        """display_mode에 맞는 윈도우 플래그 조합."""
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        # Tool 플래그가 있으면 작업표시줄에 안 뜸 (트레이 전용에 적합).
        if self.display_mode == "tray":
            flags |= Qt.WindowType.Tool
        return flags

    def _setup_window(self) -> None:
        self.setWindowFlags(self._window_flags_for_mode())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(STYLE)
        self.setWindowTitle("Slide Memo")
        # 폭이 tab_width~사용자 드래그 폭 사이로 변경 가능 (접힘=tab_width, 펼침=user_width).
        # 화면 안에 항상 전체가 들어오도록 폭 자체가 슬라이드함.
        self.setMinimumWidth(self.tab_width)
        # setMaximumWidth 안 둠 - 사용자가 좌측 드래그로 키울 수 있어야 함

    def _setup_fonts(self) -> None:
        families = set(QFontDatabase.families())
        if "D2Coding" in families:
            self.editor_font = QFont("D2Coding", 11)
        else:
            self.editor_font = QFont("Consolas", 11)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.container = QFrame(self)
        self.container.setObjectName("mainContainer")
        self.container.setMinimumWidth(self.tab_width)
        outer.addWidget(self.container)

        root = QHBoxLayout(self.container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 본문 (좌측, 펼친 상태에서만 보임) ----
        self.body = QWidget(self.container)
        self.body.setObjectName("bodyPanel")
        self.body.setMinimumWidth(0)  # 폭 0까지 줄어들 수 있어야 슬라이드 가능
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(6)
        root.addWidget(self.body, stretch=1)

        # 상단: 검색바 (일반 모드) / 돌아가기 버튼 (휴지통 모드)
        top = QHBoxLayout()
        top.setSpacing(4)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("🔍 제목·본문 검색...")
        self.search_input.textChanged.connect(self._on_search_changed)
        top.addWidget(self.search_input, stretch=1)

        self.back_btn = QPushButton("←  휴지통 닫기")
        self.back_btn.setObjectName("backBtn")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self._exit_trash_mode)
        self.back_btn.hide()
        top.addWidget(self.back_btn, stretch=1)

        # 정렬 드롭다운
        self.sort_combo = QComboBox()
        self.sort_combo.setObjectName("sortCombo")
        self.sort_combo.setFixedWidth(92)
        self.sort_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        for _key, label in SORT_OPTIONS:
            self.sort_combo.addItem(label)
        saved = self.db.get_setting_int("sort_mode", 0)
        self.sort_combo.setCurrentIndex(max(0, min(saved, len(SORT_OPTIONS) - 1)))
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        top.addWidget(self.sort_combo)
        body_layout.addLayout(top)

        # 에디터 패널 (제목+색상 / 본문 / 미리보기 버튼)
        editor_panel = QWidget()
        ep = QVBoxLayout(editor_panel)
        ep.setContentsMargins(0, 0, 0, 0)
        ep.setSpacing(4)

        # 제목 줄: 제목 입력 + 색상 dot들 + 사용자 정의(+) 가로 배치
        self.title_input = QLineEdit()
        self.title_input.setObjectName("titleInput")
        self.title_input.setPlaceholderText("제목")
        self.title_input.textChanged.connect(self._on_text_changed)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)
        title_row.addWidget(self.title_input, stretch=1)
        self.color_buttons: dict[str, ColorDot] = {}
        for name in COLOR_ORDER:
            dot = ColorDot(name)
            dot.clicked.connect(lambda _checked, n=name: self._on_color_changed(n))
            title_row.addWidget(dot)
            self.color_buttons[name] = dot
        # 사용자 지정 색상 버튼 (+): 클릭 시 색상 선택 다이얼로그
        self.custom_color_btn = QPushButton("+")
        self.custom_color_btn.setFixedSize(16, 16)
        self.custom_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_color_btn.setToolTip("사용자 지정 색상...")
        self.custom_color_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.custom_color_btn.setStyleSheet(
            "background-color: rgba(0,0,0,0.05); color: #1e1e2e;"
            " border: 1px dashed rgba(0,0,0,0.4); border-radius: 8px;"
            " font-weight: bold;"
        )
        self.custom_color_btn.clicked.connect(self._on_custom_color)
        title_row.addWidget(self.custom_color_btn)
        ep.addLayout(title_row)

        # 에디터 (서식바가 참조하므로 먼저 생성)
        self.editor = RichPasteTextEdit()
        self.editor.setObjectName("editor")
        self.editor.setFont(self.editor_font)
        self.editor.setAcceptRichText(True)  # 이미지 붙여넣기 + 서식 지원
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self._show_editor_context_menu)

        # 서식바: 서식 버튼들만 + 복사 버튼 (색상 dot/사용자 정의는 제목 줄로 분리)
        self.format_toolbar = FormatToolbar(self.editor)
        fmt_layout = self.format_toolbar.layout()
        fmt_layout.addSpacing(6)
        self._copy_icon = QIcon(str(_asset("content_copy.svg")))
        self._check_icon = QIcon(str(_asset("check.svg")))
        self.copy_btn = QPushButton()
        self.copy_btn.setObjectName("iconBtn")
        self.copy_btn.setToolTip("메모 본문 전체 복사 (Ctrl+Shift+C)")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setFixedSize(28, 24)
        self.copy_btn.setIcon(self._copy_icon)
        self.copy_btn.setIconSize(QSize(17, 17))
        self.copy_btn.clicked.connect(self._copy_memo_text)
        fmt_layout.addWidget(self.copy_btn)

        ep.addWidget(self.format_toolbar)
        ep.addWidget(self.editor, stretch=1)

        # AI 기능 바 (에디터 하단, AI 활성 시만 표시)
        self._ai_bar = QWidget()
        ai_bar_layout = QHBoxLayout(self._ai_bar)
        ai_bar_layout.setContentsMargins(0, 2, 0, 2)
        ai_bar_layout.setSpacing(4)
        from ai_features import AI_FEATURES
        for _key, _info in AI_FEATURES.items():
            _btn = QPushButton(_info["label"])
            _btn.setObjectName("aiFeatureBtn")
            _btn.setCursor(Qt.CursorShape.PointingHandCursor)
            _btn.setToolTip(f"{_info['label']}")
            _btn.clicked.connect(lambda _checked, k=_key: self._run_ai_feature(k))
            ai_bar_layout.addWidget(_btn)
        ai_bar_layout.addStretch(1)
        self._ai_bar.hide()
        ep.addWidget(self._ai_bar)

        # AI 진행 상태 표시줄 (에디터 하단, 평소엔 숨김)
        self._ai_status_lbl = QLabel()
        self._ai_status_lbl.setObjectName("aiStatusLbl")
        self._ai_status_lbl.setStyleSheet(
            "background: rgba(0,0,0,0.06); color: #5c5f77;"
            " font-size: 9pt; padding: 2px 6px; border-radius: 3px;"
        )
        self._ai_status_lbl.hide()
        ep.addWidget(self._ai_status_lbl)

        body_layout.addWidget(editor_panel, stretch=1)

        # 토스트 메시지 (body 하단 중앙, 평소엔 숨김)
        self._toast_lbl = QLabel(self.body)
        self._toast_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toast_lbl.setStyleSheet(
            "background: rgba(30,30,46,0.82); color: #cdd6f4;"
            " font-size: 9pt; padding: 4px 10px; border-radius: 6px;"
        )
        self._toast_lbl.hide()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._toast_lbl.hide)

        # ---- 우측 탭 컬럼 (항상 보임) ----
        self.tab_column = QWidget(self.container)
        self.tab_column.setObjectName("tabColumn")
        self.tab_column.setFixedWidth(self.tab_width)
        col_layout = QVBoxLayout(self.tab_column)
        col_layout.setContentsMargins(0, 0, 0, 0)
        col_layout.setSpacing(0)

        # 세로 이동 그립 (맨 위)
        self.drag_grip = DragGrip(self.tab_column)
        col_layout.addWidget(self.drag_grip)

        # 스크롤 가능한 탭 목록
        self.tab_scroll = QScrollArea(self.tab_column)
        self.tab_scroll.setObjectName("tabScroll")
        self.tab_scroll.setWidgetResizable(True)
        self.tab_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.tab_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.tab_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.tabs_container = QWidget()
        self.tabs_container.setObjectName("tabsContainer")
        self.tabs_layout = QVBoxLayout(self.tabs_container)
        self.tabs_layout.setContentsMargins(2, 4, 2, 4)
        self.tabs_layout.setSpacing(5)  # 각 인덱스가 떨어져 보이게
        self.tabs_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tab_scroll.setWidget(self.tabs_container)
        col_layout.addWidget(self.tab_scroll, stretch=1)

        # 하단: 설정 + 휴지통 + 새 메모 버튼
        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.setFixedHeight(NEW_TAB_HEIGHT)
        self.settings_btn.setToolTip("설정")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setIcon(QIcon(str(_asset("settings_icon.svg"))))
        self.settings_btn.clicked.connect(self._open_settings)
        col_layout.addWidget(self.settings_btn)

        self.trash_btn = QPushButton()
        self.trash_btn.setObjectName("trashBtn")
        self.trash_btn.setFixedHeight(NEW_TAB_HEIGHT)
        self.trash_btn.setToolTip("휴지통")
        self.trash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trash_btn.setIcon(QIcon(str(_asset("delete_icon.svg"))))
        self.trash_btn.clicked.connect(self._toggle_trash_mode)
        col_layout.addWidget(self.trash_btn)

        # 휴지통 갯수 배지 (trash_btn 우측 상단에 absolute)
        self._trash_badge = QLabel(self.trash_btn)
        self._trash_badge.setObjectName("trashBadge")
        self._trash_badge.setStyleSheet(
            "background: #ef4444; color: white;"
            " border-radius: 7px; font-size: 7pt; font-weight: bold;"
            " padding: 1px 4px;"
        )
        self._trash_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._trash_badge.hide()

        self.new_tab_btn = QPushButton("＋")
        self.new_tab_btn.setObjectName("newTabBtn")
        self.new_tab_btn.setFixedHeight(NEW_TAB_HEIGHT)
        self.new_tab_btn.setToolTip("새 메모 (Ctrl+N)")
        self.new_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_tab_btn.clicked.connect(self.create_new_memo)
        col_layout.addWidget(self.new_tab_btn)

        root.addWidget(self.tab_column)

        # 본문 영역 가장자리 드래그 핸들 (펼친 상태에서만 표시)
        self.handle_left = ResizeHandle(self.container, "left")
        self.handle_right = ResizeHandle(self.container, "right")
        self.handle_top = ResizeHandle(self.container, "top")
        self.handle_bottom = ResizeHandle(self.container, "bottom")

        # 좌/우 가장자리 레이아웃 적용
        self._apply_side_layout()
        # 초기 아이콘/폰트 크기 (tab_width 반응형)
        self._apply_btn_icon_sizes()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_handles()
        if hasattr(self, "_trash_badge"):
            self._update_trash_btn()

    def _apply_side_layout(self) -> None:
        """side에 따라 [본문][탭] 또는 [탭][본문] 순서로 재배치."""
        MemoTabButton.side = self.side
        root = self.container.layout()
        root.removeWidget(self.body)
        root.removeWidget(self.tab_column)
        if self.side == "right":
            root.addWidget(self.body, stretch=1)
            root.addWidget(self.tab_column)
        else:
            root.addWidget(self.tab_column)
            root.addWidget(self.body, stretch=1)

    def _update_handles(self) -> None:
        """리사이즈 핸들 위치 + 가시성 갱신 (side / 펼침 상태 반영).
        - 좌/우 핸들: 펼친 상태에서만 본문 가장자리 폭 조절용
        - handle_top/bottom: 펼친 상태에서만 본문 영역 위/아래 (tab_column 영역 위에는
          DragGrip이 위치 이동을 담당하므로 안 깔린다)
        - tab_col_bottom_grip (col_layout 안의 위젯): + 버튼 아래에 항상 깔림"""
        if not hasattr(self, "handle_left"):
            return
        w = self.container.width()
        h = self.container.height()
        body_w = max(0, w - self.tab_width)
        grip_h = max(0, h - 2 * RESIZE_GRIP)
        show = self.is_expanded
        if self.side == "right":
            body_x = 0  # 본문이 좌측에 위치
            self.handle_left.setGeometry(0, RESIZE_GRIP, RESIZE_GRIP, grip_h)
            self.handle_left.setVisible(show)
            self.handle_right.setVisible(False)
        else:
            body_x = self.tab_width  # 본문이 우측에 위치
            self.handle_right.setGeometry(
                w - RESIZE_GRIP, RESIZE_GRIP, RESIZE_GRIP, grip_h
            )
            self.handle_right.setVisible(show)
            self.handle_left.setVisible(False)
        self.handle_top.setGeometry(body_x, 0, body_w, RESIZE_GRIP)
        self.handle_bottom.setGeometry(body_x, h - RESIZE_GRIP, body_w, RESIZE_GRIP)
        self.handle_top.setVisible(show)
        self.handle_bottom.setVisible(show)
        for hw in (
            self.handle_left, self.handle_right,
            self.handle_top, self.handle_bottom,
        ):
            hw.raise_()

    def _setup_animation(self) -> None:
        # 윈도우 폭은 즉시 변경하고 body의 opacity만 페이드.
        # → 슬라이드 효과 없음, 본문만 부드럽게 나타났다 사라짐.
        self.body_opacity = QGraphicsOpacityEffect(self.body)
        self.body_opacity.setOpacity(0.0)
        self.body.setGraphicsEffect(self.body_opacity)
        self.fade_anim = QPropertyAnimation(self.body_opacity, b"opacity")
        self.fade_anim.setDuration(ANIM_DURATION)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.fade_anim.finished.connect(self._on_fade_done)

    def _on_fade_done(self) -> None:
        # 접힘 fade-out 종료 → body hide + 윈도우 즉시 축소 + 핸들 갱신
        if not self.is_expanded:
            self.body.hide()
            self.setGeometry(self._collapsed_geometry())
            self._update_handles()

    def _open_settings(self) -> None:
        from settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.db, self)
        dlg.exec()
        self.apply_side_settings()
        self.apply_tab_geometry_settings()
        self.apply_display_mode_settings()
        self._refresh_ai_bar()

    def _refresh_ai_bar(self) -> None:
        enabled = self.db.get_setting_str("ai_enabled", "0") == "1"
        self._ai_bar.setVisible(enabled)

    def _on_escape(self) -> None:
        if self._ai_pending is not None:
            self._cancel_ai()
        else:
            self.collapse()

    def _setup_shortcuts(self) -> None:
        for keys, slot in [
            ("Escape", self._on_escape),
            ("Ctrl+N", self.create_new_memo),
            ("Ctrl+F", self.focus_search),
            ("Ctrl+S", self.save_now),
            ("Ctrl+Shift+C", self._copy_memo_text),
            ("Ctrl+B", self.format_toolbar.toggle_bold),
            ("Ctrl+I", self.format_toolbar.toggle_italic),
            ("Ctrl+U", self.format_toolbar.toggle_underline),
            # 링크
            ("Ctrl+K", self.format_toolbar.insert_link),
            # 날짜/시간
            ("F5", lambda: self.format_toolbar.insert_datetime("notepad")),
            ("Ctrl+;", lambda: self.format_toolbar.insert_datetime("date")),
            ("Ctrl+Shift+;", lambda: self.format_toolbar.insert_datetime("time")),
            ("Ctrl+Alt+;", lambda: self.format_toolbar.insert_datetime("iso")),
            ("Ctrl+Shift+H", lambda: self.format_toolbar.insert_datetime("korean")),
            # AI 기능
            ("Ctrl+Alt+S", lambda: self._run_ai_feature("summarize")),
            ("Ctrl+Alt+R", lambda: self._run_ai_feature("rewrite")),
            ("Ctrl+Alt+T", lambda: self._run_ai_feature("translate")),
            ("Ctrl+Alt+P", lambda: self._run_ai_feature("spellcheck")),
            ("Ctrl+Alt+H", lambda: self._run_ai_feature("title")),
            ("Ctrl+Alt+O", lambda: self._run_ai_feature("outline")),
            ("Ctrl+Alt+K", lambda: self._run_ai_feature("keywords")),
            ("Ctrl+Alt+Space", lambda: self._run_ai_feature("continue")),
        ]:
            sc = QShortcut(QKeySequence(keys), self)
            sc.activated.connect(slot)

    # ----- AI 컨텍스트 메뉴 -----
    def _show_editor_context_menu(self, pos) -> None:
        from ai_features import AI_FEATURES

        menu = self.editor.createStandardContextMenu()

        ai_enabled = self.db.get_setting_str("ai_enabled", "0") == "1"
        if ai_enabled:
            menu.addSeparator()
            ai_menu = menu.addMenu("✨ AI")
            for key, info in AI_FEATURES.items():
                act = QAction(info["label"], ai_menu)
                act.triggered.connect(lambda _checked, k=key: self._run_ai_feature(k))
                ai_menu.addAction(act)

            if self._ai_pending is not None:
                menu.addSeparator()
                cancel_act = QAction("AI 취소 (ESC)", menu)
                cancel_act.triggered.connect(self._cancel_ai)
                menu.addAction(cancel_act)

        menu.exec(self.editor.mapToGlobal(pos))

    # ----- AI 실행 -----
    def _run_ai_feature(self, feature_key: str) -> None:
        from ai_features import AI_FEATURES, AIWorker

        if self.db.get_setting_str("ai_enabled", "0") != "1":
            self._show_toast("AI 기능이 비활성화되어 있습니다. 설정에서 활성화하세요.")
            return

        if self._ai_worker is not None and self._ai_worker.isRunning():
            self._show_toast("AI가 이미 작업 중입니다. 잠시 후 다시 시도하세요.")
            return

        feature = AI_FEATURES.get(feature_key)
        if not feature:
            return

        # 텍스트 수집: 선택 영역 우선, 없으면 전체 본문
        cursor = self.editor.textCursor()
        text = cursor.selectedText() if cursor.hasSelection() else self.editor.toPlainText()
        text = text.strip()
        if not text:
            self._show_toast("처리할 텍스트가 없습니다.")
            return

        provider = self.db.get_setting_str("ai_provider", "anthropic")
        model = self.db.get_setting_str("ai_model", "")
        if not model:
            from ai_provider import PROVIDERS
            model = PROVIDERS.get(provider, {}).get("default_model", "")

        show_preview = self.db.get_setting_str("ai_show_preview", "0") == "1"

        self._ai_pending = feature_key
        self._show_ai_progress(f"⏳ AI {feature['label']} 중...")

        self._ai_worker = AIWorker(feature_key, provider, model, text, parent=self)
        self._ai_worker.finished.connect(
            lambda k, r, t: self._on_ai_finished(k, r, t, show_preview)
        )
        self._ai_worker.errored.connect(self._on_ai_error)
        self._ai_worker.progress.connect(self._show_ai_progress)
        self._ai_worker.start()

    def _cancel_ai(self) -> None:
        if self._ai_worker is not None:
            self._ai_worker.cancel()
        self._ai_pending = None
        self._ai_status_lbl.hide()
        self._show_toast("AI 작업이 취소되었습니다.")

    def _on_ai_finished(self, feature_key: str, result: str, tokens: int, show_preview: bool) -> None:
        self._ai_pending = None
        self._ai_status_lbl.hide()

        # 토큰 사용량 누적
        prev = int(self.db.get_setting_str("ai_usage_tokens", "0") or "0")
        self.db.set_setting_str("ai_usage_tokens", str(prev + tokens))

        if show_preview:
            self._show_ai_preview(feature_key, result)
        else:
            self._apply_ai_result(feature_key, result)

    def _on_ai_error(self, feature_key: str, msg: str) -> None:
        self._ai_pending = None
        self._ai_status_lbl.hide()
        self._show_toast(f"AI 오류: {msg}")

    def _show_ai_preview(self, feature_key: str, result: str) -> None:
        from ai_features import AI_FEATURES

        feature = AI_FEATURES.get(feature_key, {})
        label = feature.get("label", feature_key)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"AI {label} — 미리보기")
        dlg.resize(480, 360)
        dlg.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        info_lbl = QLabel(f"<b>{label}</b> 결과를 적용하시겠습니까?")
        layout.addWidget(info_lbl)

        preview = QTextBrowser()
        preview.setPlainText(result)
        layout.addWidget(preview, stretch=1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("적용")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_ai_result(feature_key, result)

    def _apply_ai_result(self, feature_key: str, result: str) -> None:
        from ai_features import AI_FEATURES

        feature = AI_FEATURES.get(feature_key, {})
        output = feature.get("output", "replace")
        cursor = self.editor.textCursor()

        if output == "title":
            self.title_input.setText(result)
            self._show_toast(f"✓ 제목이 생성되었습니다.")
        elif output == "replace":
            if cursor.hasSelection():
                cursor.insertText(result)
            else:
                cursor.select(QTextCursor.SelectionType.Document)
                cursor.insertText(result)
            self.editor.setTextCursor(cursor)
        elif output == "append":
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(f"\n\n{result}")
            self.editor.setTextCursor(cursor)
        elif output == "insert":
            # 커서 위치에 이어 쓰기 (현재 위치 기준)
            if not cursor.hasSelection():
                cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(f" {result}")
            self.editor.setTextCursor(cursor)

        self.editor.setFocus()

    def _show_ai_progress(self, msg: str) -> None:
        self._ai_status_lbl.setText(msg)
        self._ai_status_lbl.show()

    def _show_toast(self, msg: str, duration_ms: int = 2500) -> None:
        self._toast_lbl.setText(msg)
        self._toast_lbl.adjustSize()
        # body 하단 중앙 위치
        bw = self.body.width()
        bh = self.body.height()
        tw = self._toast_lbl.width() + 20
        th = self._toast_lbl.height()
        self._toast_lbl.setFixedSize(max(tw, 160), th + 6)
        x = (bw - self._toast_lbl.width()) // 2
        y = bh - self._toast_lbl.height() - 12
        self._toast_lbl.move(x, y)
        self._toast_lbl.raise_()
        self._toast_lbl.show()
        self._toast_timer.start(duration_ms)

    def _setup_autosave(self) -> None:
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self.save_now)

    # ----- geometry -----
    def _screen_rect(self) -> QRect:
        screen = QGuiApplication.screenAt(self.pos())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def _load_user_size(self) -> None:
        rect = self._screen_rect()
        default_h = int(rect.height() * HEIGHT_RATIO)
        default_y = rect.y() + (rect.height() - default_h) // 2
        self.user_width = self.db.get_setting_int("window_width", EXPANDED_WIDTH)
        self.user_height = self.db.get_setting_int("window_height", default_h)
        self.user_y = self.db.get_setting_int("window_y", default_y)
        # 화면 범위로 clamp (해상도 변경 대응)
        self.user_width = max(MIN_W, min(self.user_width, rect.width()))
        self.user_height = max(MIN_H, min(self.user_height, rect.height()))
        self.user_y = max(
            rect.y(),
            min(self.user_y, rect.y() + rect.height() - self.user_height),
        )

    def _save_user_size(self) -> None:
        g = self.geometry()
        # 접힌 상태에선 폭이 tab_width라 user_width를 덮어쓰면 안 됨
        # (접힌 채 세로 이동 그립을 드래그한 경우)
        if self.is_expanded:
            self.user_width = g.width()
        self.user_height = g.height()
        self.user_y = g.y()
        self.db.set_setting_int("window_width", self.user_width)
        self.db.set_setting_int("window_height", self.user_height)
        self.db.set_setting_int("window_y", self.user_y)

    def apply_side_settings(self) -> None:
        """side(좌/우 가장자리) 변경 즉시 반영. toggle_side와 거의 동일하지만
        DB에서 값을 다시 읽어 적용한다."""
        new_side_int = self.db.get_setting_int("side", 0)
        new_side = "left" if new_side_int == 1 else "right"
        if new_side == self.side:
            return
        self.side = new_side
        self._apply_side_layout()
        self.setGeometry(
            self._expanded_geometry() if self.is_expanded
            else self._collapsed_geometry()
        )
        self._update_handles()
        self._refresh_memo_tabs()
        self._update_tabs_selected()

    def apply_display_mode_settings(self) -> None:
        """display_mode 재로드 후 윈도우 플래그/트레이 가시성 즉시 갱신."""
        prev = self.display_mode
        self._load_display_mode()
        if self.display_mode == prev:
            return
        was_visible = self.isVisible()
        self.setWindowFlags(self._window_flags_for_mode())
        # 트레이 가시성
        tray = getattr(self, "_tray", None)
        if tray is not None:
            if self.display_mode == "taskbar":
                tray.hide()
            else:
                tray.show()
        # setWindowFlags 호출 후엔 윈도우가 hide되므로 show 재호출 + geometry 복구
        if was_visible:
            if self.is_expanded:
                self.setGeometry(self._expanded_geometry())
            else:
                self.setGeometry(self._collapsed_geometry())
            self.show()
            self._update_handles()

    def apply_tab_geometry_settings(self) -> None:
        """설정 다이얼로그 OK 후 호출. 인덱스 탭 폭/각 탭 높이를 DB에서 재로드해 반영.
        접힌 상태면 윈도우 폭도 즉시 반영, 펼친 상태면 다음 접기 때 반영.
        """
        self._load_tab_geometry()
        # 폭 즉시 반영 (탭 컬럼 + 컨테이너 최소 폭)
        self.tab_column.setFixedWidth(self.tab_width)
        self.container.setMinimumWidth(self.tab_width)
        self.setMinimumWidth(self.tab_width)
        # 컬럼 버튼 아이콘/폰트 크기 반응형 갱신
        self._apply_btn_icon_sizes()
        # 각 메모 탭 높이 갱신 → 탭 다시 그리기
        MemoTabButton.button_height = self.memo_tab_height
        self._refresh_memo_tabs()
        self._update_tabs_selected()
        # 접힌 상태만 즉시 반영. 펼친 상태는 _collapsed_geometry가 다음 접기 때 새 값 사용.
        if not self.is_expanded:
            self.setGeometry(self._collapsed_geometry())
        self._update_handles()

    def _expanded_geometry(self) -> QRect:
        rect = self._screen_rect()
        if self.side == "right":
            x = rect.right() - self.user_width + 1
        else:
            x = rect.x()
        return QRect(x, self.user_y, self.user_width, self.user_height)

    def _collapsed_geometry(self) -> QRect:
        rect = self._screen_rect()
        # 폭 자체를 tab_width로 만들어 화면 가장자리에 탭만 노출.
        if self.side == "right":
            x = rect.right() - self.tab_width + 1
        else:
            x = rect.x()
        return QRect(x, self.user_y, self.tab_width, self.user_height)

    def _position_collapsed(self) -> None:
        self.setGeometry(self._collapsed_geometry())

    # ----- expand / collapse -----
    def toggle(self) -> None:
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()

    def toggle_side(self) -> None:
        """좌/우 가장자리 전환."""
        self.side = "left" if self.side == "right" else "right"
        self.db.set_setting_int("side", 1 if self.side == "left" else 0)
        self._apply_side_layout()
        self.setGeometry(
            self._expanded_geometry() if self.is_expanded
            else self._collapsed_geometry()
        )
        self._update_handles()
        self._refresh_memo_tabs()
        self._update_tabs_selected()

    def expand(self) -> None:
        if not self.isVisible():
            self.show()
        if self.is_expanded:
            self.raise_()
            self.activateWindow()
            return
        self.is_expanded = True
        # 윈도우 폭/위치는 즉시 펼침 사이즈로 (tab_column 위치는 변함 없음)
        self.setGeometry(self._expanded_geometry())
        # body.show() 전에 layout을 강제 activate해 FlowLayout이 정상 폭 기준으로
        # 첫 패스를 계산하게 한다. 그렇지 않으면 width=0 짧은 순간 wrap된 큰 높이가
        # 부모 layout으로 전파되어 메모 탭이 잠깐 어긋난 위치에 그려진다.
        self.body.layout().activate()
        self.body.show()
        self._update_handles()
        # body opacity 0 → 1 페이드 인
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.body_opacity.opacity())
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()
        self.raise_()
        self.activateWindow()

    def collapse(self, *, exit_trash: bool = True) -> None:
        if not self.is_expanded:
            return
        self.save_now()
        if exit_trash and self.trash_mode:
            self._exit_trash_mode()  # 접을 때 휴지통 모드 해제
        self.is_expanded = False
        # body opacity → 0 페이드 아웃. 끝나면 _on_fade_done에서 윈도우 축소.
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.body_opacity.opacity())
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.start()

    # ----- memo tab column -----
    def _refresh_memo_tabs(self, *, select_first: bool = False) -> None:
        if self.trash_mode:
            memos = self.db.list_trashed_memos()
        else:
            keyword = self.search_input.text() if hasattr(self, "search_input") else ""
            memos = self.db.search(keyword, sort=self._current_sort_key())

        # 기존 탭 제거
        while self.tabs_layout.count():
            item = self.tabs_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        current_id = self.current_memo.id if self.current_memo else None
        for memo in memos:
            btn = MemoTabButton(memo)
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            if self.trash_mode:
                # 휴지통: 좌클릭=내용 미리보기 / 우클릭=복원·영구삭제 메뉴
                btn.update_style(selected=(memo.id == self._trash_preview_id))
                btn.clicked.connect(
                    lambda _c, mid=memo.id: self._preview_trashed(mid)
                )
                btn.customContextMenuRequested.connect(
                    lambda _pos, mid=memo.id, b=btn: self._show_trash_menu(mid, b)
                )
            else:
                btn.update_style(selected=(memo.id == current_id))
                btn.clicked.connect(lambda _c, mid=memo.id: self.select_memo(mid))
                btn.customContextMenuRequested.connect(
                    lambda pos, mid=memo.id, b=btn: self._show_tab_context_menu(pos, mid, b)
                )
            self.tabs_layout.addWidget(btn)

        self._update_trash_btn()

        if self.trash_mode:
            return

        # 현재 선택된 메모가 검색/삭제로 사라지면 에디터 정리
        if current_id is not None and current_id not in {m.id for m in memos}:
            self._clear_editor()

        # 비어 있을 때 첫 항목 자동 선택
        if select_first and self.current_memo is None and memos:
            self._load_memo(memos[0])
            self._update_tabs_selected()

    def _update_trash_btn(self) -> None:
        n = self.db.count_trashed()
        self.trash_btn.setToolTip(f"휴지통 ({n})" if n else "휴지통")
        if n > 0:
            self._trash_badge.setText(str(n) if n < 100 else "99+")
            self._trash_badge.adjustSize()
            # trash_btn 우측 상단 — width가 아직 0이면 tab_width를 fallback으로
            bw = self.trash_btn.width() or self.tab_width
            self._trash_badge.move(
                max(2, bw - self._trash_badge.width() - 2), 2
            )
            self._trash_badge.show()
            self._trash_badge.raise_()
        else:
            self._trash_badge.hide()

    # ----- 휴지통 모드 -----
    def _toggle_trash_mode(self) -> None:
        if self.trash_mode:
            self._exit_trash_mode()
        else:
            self._enter_trash_mode()

    def _enter_trash_mode(self) -> None:
        if self.trash_mode:
            return
        if self.db.count_trashed() == 0:
            QMessageBox.information(self, "휴지통", "휴지통이 비어 있습니다.")
            return
        self.save_now()
        self.trash_mode = True
        self._trash_preview_id = None
        # 휴지통 메모는 보기 전용
        self.editor.setReadOnly(True)
        self.title_input.setReadOnly(True)
        self.search_input.hide()
        self.sort_combo.hide()
        self.back_btn.show()
        self.new_tab_btn.hide()
        self._refresh_memo_tabs()
        # 진입 시 펼침 상태였다면 접음 (휴지통 메모 클릭하면 다시 펼치며 미리보기)
        if self.is_expanded:
            self.collapse(exit_trash=False)

    def _exit_trash_mode(self) -> None:
        if not self.trash_mode:
            return
        self.trash_mode = False
        self._trash_preview_id = None
        self.editor.setReadOnly(False)
        self.title_input.setReadOnly(False)
        self.back_btn.hide()
        self.search_input.show()
        self.sort_combo.show()
        self.new_tab_btn.show()
        # 휴지통 진입 전에 보던 메모로 에디터 복원
        if self.current_memo is not None:
            try:
                self._load_memo(self.db.get(self.current_memo.id))
            except KeyError:
                self._clear_editor()
        else:
            self._clear_editor()
        self._refresh_memo_tabs()
        self._update_tabs_selected()

    def _after_trash_change(self) -> None:
        """휴지통 변경(복원/영구삭제) 후 갱신. 휴지통이 비면 일반 모드로 복귀."""
        if self.trash_mode and self.db.count_trashed() == 0:
            self._exit_trash_mode()  # 빈 화면 대신 일반 모드로 자동 복귀
        else:
            self._refresh_memo_tabs()

    def _preview_trashed(self, memo_id: int) -> None:
        """휴지통 메모 내용을 읽기 전용으로 에디터에 표시 (current_memo는 안 건드림)."""
        # 이미 같은 메모 미리보기 중이고 펼친 상태면 토글로 접기
        if self._trash_preview_id == memo_id and self.is_expanded:
            self.collapse(exit_trash=False)
            return
        try:
            memo = self.db.get(memo_id)
        except KeyError:
            return
        self._trash_preview_id = memo_id
        self.title_input.blockSignals(True)
        self.editor.blockSignals(True)
        self.title_input.setText(memo.title)
        if memo.content and Qt.mightBeRichText(memo.content):
            self.editor.setHtml(memo.content)
        else:
            self.editor.setPlainText(memo.content)
        self.title_input.blockSignals(False)
        self.editor.blockSignals(False)
        self._apply_memo_theme(memo.color)
        self._update_color_buttons(memo.color)
        # 미리보기 중인 탭만 강조
        for i in range(self.tabs_layout.count()):
            w = self.tabs_layout.itemAt(i).widget()
            if isinstance(w, MemoTabButton):
                w.update_style(selected=(w.memo_id == memo_id))
        # 접힌 상태에서 휴지통 메모를 누른 경우 본문을 펼친다
        self.expand()

    def _show_trash_menu(self, memo_id: int, button: QPushButton) -> None:
        try:
            memo = self.db.get(memo_id)
        except KeyError:
            return
        menu = QMenu(self)
        restore_act = menu.addAction("복원")
        menu.addSeparator()
        purge_act = menu.addAction("영구 삭제")
        chosen = menu.exec(button.mapToGlobal(button.rect().center()))

        if chosen == restore_act:
            self.db.restore(memo_id)
            if self._trash_preview_id == memo_id:
                self._trash_preview_id = None
            self._after_trash_change()
        elif chosen == purge_act:
            reply = QMessageBox.question(
                self,
                "영구 삭제 확인",
                f"'{memo.title or '(제목 없음)'}' 메모를 완전히 삭제할까요?\n"
                "첨부 이미지도 함께 삭제되며 복구할 수 없습니다.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            _delete_memo_images(memo.content)
            self.db.delete(memo_id)
            if self._trash_preview_id == memo_id:
                self._trash_preview_id = None
            self._after_trash_change()

    def _update_tabs_selected(self) -> None:
        current_id = self.current_memo.id if self.current_memo else None
        for i in range(self.tabs_layout.count()):
            w = self.tabs_layout.itemAt(i).widget()
            if isinstance(w, MemoTabButton):
                w.update_style(selected=(w.memo_id == current_id))

    def select_memo(self, memo_id: int) -> None:
        # 이미 선택된 메모를 다시 누르면 토글 (열려있으면 접고, 접혀있으면 펴기)
        if self.current_memo and self.current_memo.id == memo_id:
            if self.is_expanded:
                self.collapse()
            else:
                self.expand()
            return
        # 다른 메모 → 전환하면서 펼침
        self.save_now()
        try:
            memo = self.db.get(memo_id)
        except KeyError:
            return
        self._load_memo(memo)
        self._update_tabs_selected()
        self.expand()

    def _load_memo(self, memo: Memo) -> None:
        self.current_memo = memo
        self.title_input.blockSignals(True)
        self.editor.blockSignals(True)
        self.title_input.setText(memo.title)
        # content가 HTML이면 setHtml, 옛 plain text 메모면 setPlainText
        if memo.content and Qt.mightBeRichText(memo.content):
            self.editor.setHtml(memo.content)
        else:
            self.editor.setPlainText(memo.content)
        self.title_input.blockSignals(False)
        self.editor.blockSignals(False)
        # round-trip된 HTML로 동기화 → 불필요한 자동저장 방지
        self.current_memo.content = self.editor.toHtml()
        self._update_color_buttons(memo.color)
        self._apply_memo_theme(memo.color)

    def _clear_editor(self) -> None:
        self.current_memo = None
        self.title_input.blockSignals(True)
        self.editor.blockSignals(True)
        self.title_input.clear()
        self.editor.clear()
        self.title_input.blockSignals(False)
        self.editor.blockSignals(False)
        self._update_color_buttons(DEFAULT_COLOR)
        self._apply_memo_theme(DEFAULT_COLOR)

    def _apply_memo_theme(self, color_name: str | None) -> None:
        """선택된 메모 색을 본문(메모장) 배경/입력 요소에 반영."""
        t = theme_for(color_name)
        self.body.setStyleSheet(body_stylesheet(t))
        # 색상 점 버튼은 항상 자기 색깔 유지하므로 별도 처리 없음.

    def _update_color_buttons(self, current_color: str) -> None:
        is_preset = current_color in COLORS or is_gradient(current_color)
        for name, btn in self.color_buttons.items():
            btn.set_selected(name == current_color)
        # 커스텀(+) 버튼: 프리셋이 아니면 그 색을 칠하고 선택 강조
        if is_preset:
            self.custom_color_btn.setText("+")
            self.custom_color_btn.setStyleSheet(
                "background-color: rgba(0,0,0,0.05); color: #1e1e2e;"
                " border: 1px dashed rgba(0,0,0,0.4); border-radius: 8px;"
                " font-weight: bold;"
            )
        else:
            bg = resolve_color(current_color)
            self.custom_color_btn.setText("")
            self.custom_color_btn.setStyleSheet(
                f"background-color: {bg};"
                f" border: 2px solid #1e1e2e; border-radius: 8px;"
            )

    # ----- new / delete -----
    def create_new_memo(self) -> None:
        if self.trash_mode:
            self._exit_trash_mode()
        # 새 메모는 제목·본문이 비어 어떤 검색어와도 매칭되지 않음.
        # 검색 필터가 걸려 있으면 새 메모가 탭에서 사라지므로 검색어를 비운다.
        # (_refresh_memo_tabs가 아래에서 명시적으로 호출되므로 시그널은 막아둠)
        if self.search_input.text():
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)
        self.save_now()
        memo = self.db.create()
        # _load_memo가 title/editor를 빈 값으로 세팅 + 색 테마 적용까지 처리.
        # (예전엔 current_memo만 갈아끼워서 UI에 직전 메모 내용이 남아있었음)
        self._load_memo(memo)
        self._refresh_memo_tabs()
        self._update_tabs_selected()
        self.expand()
        self.title_input.setFocus()

    def _show_tab_context_menu(self, pos, memo_id: int, button: QPushButton) -> None:
        try:
            memo = self.db.get(memo_id)
        except KeyError:
            return
        menu = QMenu(self)
        pin_act = menu.addAction(
            "📌 고정 해제" if memo.is_pinned else "📌 고정"
        )
        menu.addSeparator()
        del_act = menu.addAction("🗑 휴지통으로 이동")
        chosen = menu.exec(button.mapToGlobal(pos))

        if chosen == pin_act:
            self.db.set_pinned(memo_id, not memo.is_pinned)
            if self.current_memo and self.current_memo.id == memo_id:
                self.current_memo.is_pinned = not memo.is_pinned
            self._refresh_memo_tabs()
            return

        if chosen == del_act:
            reply = QMessageBox.question(
                self,
                "삭제 확인",
                "이 메모를 휴지통으로 보낼까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            is_current = bool(self.current_memo and self.current_memo.id == memo_id)

            # 삭제 전에 이웃 메모 확인
            neighbor: Memo | None = None
            if is_current:
                all_memos = self.db.list_all(sort=self._current_sort_key())
                ids = [m.id for m in all_memos]
                if memo_id in ids:
                    idx = ids.index(memo_id)
                    if idx > 0:
                        neighbor = all_memos[idx - 1]
                    elif len(all_memos) > 1:
                        neighbor = all_memos[1]

            self.db.soft_delete(memo_id)

            if is_current:
                self.current_memo = None
                self._refresh_memo_tabs()
                if neighbor is not None:
                    self._load_memo(neighbor)
                    self._update_tabs_selected()
                else:
                    self.collapse()   # body 숨긴 뒤 clear → 노란 화면 안 보임
                    self._clear_editor()
            else:
                self._refresh_memo_tabs()

    # ----- text change / autosave -----
    def _on_text_changed(self) -> None:
        if self.current_memo is None:
            return
        self.autosave_timer.start(AUTOSAVE_DELAY)

    def _on_color_changed(self, color: str) -> None:
        if self.current_memo is None:
            return
        self.current_memo = self.db.update(self.current_memo.id, color=color)
        actual = self.current_memo.color  # DB가 정규화한 최종 색
        self._update_color_buttons(actual)
        self._apply_memo_theme(actual)
        self._refresh_memo_tabs()

    def _on_custom_color(self) -> None:
        """색상 선택 다이얼로그로 사용자 지정 hex 색상을 적용."""
        if self.current_memo is None:
            return
        initial = QColor(resolve_color(self.current_memo.color))
        chosen = QColorDialog.getColor(
            initial, self, "메모 색상 선택",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
        if chosen.isValid():
            self._on_color_changed(chosen.name())  # '#rrggbb'

    def save_now(self) -> None:
        if self.current_memo is None:
            return
        self.autosave_timer.stop()
        title = self.title_input.text()
        content = self.editor.toHtml()  # 이미지 포함 위해 HTML로 저장
        if title == self.current_memo.title and content == self.current_memo.content:
            return
        try:
            self.current_memo = self.db.update(
                self.current_memo.id, title=title, content=content
            )
        except KeyError:
            self.current_memo = None
            return
        # 제목 변경 시 tooltip 갱신을 위해 탭 다시 그림
        self._refresh_memo_tabs()

    # ----- sort -----
    def _current_sort_key(self) -> str:
        idx = self.sort_combo.currentIndex()
        if 0 <= idx < len(SORT_OPTIONS):
            return SORT_OPTIONS[idx][0]
        return SORT_OPTIONS[0][0]

    def _on_sort_changed(self, index: int) -> None:
        self.db.set_setting_int("sort_mode", index)  # 즉시 저장
        self._refresh_memo_tabs()
        self._update_tabs_selected()

    # ----- copy -----
    def _copy_memo_text(self) -> None:
        # 현재 메모 본문 전체를 plain text로 클립보드에 복사 (빈 메모도 안전)
        text = self.editor.toPlainText()
        QApplication.clipboard().setText(text)
        # 1초간 체크 아이콘 피드백
        self.copy_btn.setIcon(self._check_icon)
        QTimer.singleShot(1000, lambda: self.copy_btn.setIcon(self._copy_icon))

    # ----- search -----
    def _on_search_changed(self, _text: str) -> None:
        self._refresh_memo_tabs()

    def focus_search(self) -> None:
        if self.trash_mode:
            return
        if not self.is_expanded:
            self.expand()
        self.search_input.setFocus()
        self.search_input.selectAll()

    # ----- shutdown -----
    def request_quit(self) -> None:
        self._quitting = True
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._quitting:
            event.ignore()
            self.collapse()
            return
        try:
            self.save_now()
        finally:
            self.db.close()
        event.accept()
        QApplication.instance().quit()


def _memo_image_paths(html: str) -> list[Path]:
    """메모 HTML(content)에서 ~/.memo_slide/images/ 안의 첨부 이미지 경로 추출."""
    out: list[Path] = []
    try:
        images_root = IMAGES_DIR.resolve()
    except OSError:
        return out
    for m in re.finditer(r'<img[^>]+src="([^"]+)"', html or ""):
        src = m.group(1)
        for prefix in ("file:///", "file://"):
            if src.startswith(prefix):
                src = src[len(prefix):]
        try:
            p = Path(src)
            if p.exists() and p.resolve().parent == images_root:
                out.append(p)
        except OSError:
            continue
    return out


def _delete_memo_images(html: str) -> None:
    """메모에 첨부된 이미지 파일들을 디스크에서 삭제."""
    for p in _memo_image_paths(html):
        try:
            p.unlink()
            print(f"[trash] 첨부 이미지 삭제: {p.name}")
        except OSError as e:
            print(f"[trash] 이미지 삭제 실패: {p.name} ({e})")


def _resource_path(name: str) -> Path:
    """PyInstaller --onefile 실행 시엔 sys._MEIPASS, dev 시엔 main.py 옆을 본다."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def _asset(name: str) -> Path:
    """assets/ 폴더 내 리소스 경로."""
    return _resource_path(f"assets/{name}")


def load_app_icon() -> QIcon | None:
    """루트의 logo.ico/logo.png을 QIcon으로 로드. 없으면 None."""
    for name in ("logo.ico", "logo.png"):
        p = _resource_path(name)
        if p.exists():
            return QIcon(str(p))
    return None


def _fallback_tray_icon() -> QIcon:
    """파일 아이콘이 없을 때 동적으로 그리는 fallback."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#89b4fa"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 4, 28, 24, 4, 4)
    painter.setPen(QColor("#1e1e2e"))
    f = QFont("Segoe UI", 11)
    f.setBold(True)
    painter.setFont(f)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "M")
    painter.end()
    return QIcon(pixmap)


def make_tray_icon(window: SlideMemoWindow, icon: QIcon | None = None) -> QSystemTrayIcon:
    from settings_dialog import SettingsDialog

    if icon is None:
        icon = load_app_icon() or _fallback_tray_icon()
    tray = QSystemTrayIcon(icon, window)
    tray.setToolTip("Slide Memo")

    menu = QMenu()
    toggle_act = QAction("열기 / 접기", menu)
    toggle_act.triggered.connect(window.toggle)
    menu.addAction(toggle_act)
    side_act = QAction("왼쪽 / 오른쪽 가장자리 전환", menu)
    side_act.triggered.connect(window.toggle_side)
    menu.addAction(side_act)
    menu.addSeparator()
    settings_act = QAction("⚙ 설정", menu)
    def _open_settings_from_tray() -> None:
        SettingsDialog(window.db, window).exec()
        window.apply_side_settings()
        window.apply_tab_geometry_settings()
        window.apply_display_mode_settings()
        window._refresh_ai_bar()

    settings_act.triggered.connect(_open_settings_from_tray)
    menu.addAction(settings_act)
    menu.addSeparator()
    quit_act = QAction("종료", menu)
    quit_act.triggered.connect(window.request_quit)
    menu.addAction(quit_act)
    tray.setContextMenu(menu)

    def on_activate(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            window.toggle()

    tray.activated.connect(on_activate)
    return tray


def _set_windows_app_user_model_id() -> None:
    """Windows 작업표시줄이 logo.ico를 쓰게 한다.
    AppUserModelID를 명시 안 하면 호스트(python.exe) 아이콘이 표시됨."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "anthropic.slidememo.app"
        )
    except (OSError, AttributeError):
        pass  # 구버전 Windows 등 — 아이콘이 기본값으로 떨어지더라도 앱은 정상 동작


def main() -> int:
    # HiDPI 환경에서 좌표/스케일 어긋남 방지 (QApplication 생성 전에 호출)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    _set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Slide Memo")

    app_icon = load_app_icon()
    if app_icon is not None:
        app.setWindowIcon(app_icon)

    db = MemoDatabase()
    # 30일 지난 휴지통 항목 자동 영구삭제 (+ 첨부 이미지 정리)
    for removed in db.cleanup_old_trash(days=30):
        _delete_memo_images(removed.content)

    window = SlideMemoWindow(db)
    if app_icon is not None:
        window.setWindowIcon(app_icon)
    window.show()

    tray = make_tray_icon(window, app_icon)
    tray.show()
    window._tray = tray  # 참조 유지

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
