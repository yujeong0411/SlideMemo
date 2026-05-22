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
    QPropertyAnimation,
    QRect,
    QSize,
    QTimer,
)
from PyQt6.QtGui import (
    QAction,
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
    QTextCharFormat,
    QTextImageFormat,
    QTextListFormat,
)
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database import DEFAULT_COLOR, IMAGES_DIR, Memo, MemoDatabase


# ----- 상수 -----
TAB_WIDTH = 34          # 인덱스 가로
EXPANDED_WIDTH = 520
HEIGHT_RATIO = 0.70
ANIM_DURATION = 150  # body 페이드 시간
AUTOSAVE_DELAY = 600
MEMO_TAB_HEIGHT = 116   # 인덱스 세로
NEW_TAB_HEIGHT = 44

# 리사이즈
MIN_W = 280
MIN_H = 200
RESIZE_GRIP = 6  # 가장자리 드래그 핸들 두께(px)

COLORS = {
    "ivory":    "#FFEF9F",
    "blush":    "#F5CBCB",
    "peach":    "#FFF2EB",
    "cream":    "#A4CCD9",
    "olive":    "#F1F3E0",
    "lavender": "#F4EEFF",
    "mint":     "#BADFDB",
}
COLOR_ORDER = ["ivory", "blush", "peach", "cream", "olive", "lavender", "mint"]

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
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 4px 6px;
}
"""

_HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def resolve_color(value: str | None) -> str:
    """색 이름(프리셋) 또는 hex 코드를 실제 hex 문자열로 변환."""
    if value in COLORS:
        return COLORS[value]
    if isinstance(value, str) and _HEX_COLOR_RE.fullmatch(value.strip()):
        return value.strip()
    return COLORS[DEFAULT_COLOR]


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
def theme_for(color: str | None) -> dict[str, str]:
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
        background-color: {t["bg"]};
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
    QPushButton#fmtBtn {{
        background-color: transparent;
        color: {t["text"]};
        border: 1px solid transparent;
        border-radius: 3px;
        font-size: 10pt;
    }}
    QPushButton#fmtBtn:hover {{
        background-color: rgba(0,0,0,0.10);
        border: 1px solid {t["border"]};
    }}
    QPushButton#fmtBtn:pressed {{
        background-color: rgba(0,0,0,0.18);
    }}
    """


class MemoTabButton(QPushButton):
    """메모별 색깔 탭. 세로 회전한 제목을 표시."""

    side = "right"  # 클래스 변수: 윈도우가 좌/우 전환 시 갱신

    def __init__(self, memo: Memo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.memo_id = memo.id
        self.color_name = memo.color
        self._bg = resolve_color(memo.color)
        self._fg = _text_color_for(self._bg)
        self.memo_title = memo.title.strip() or "(제목 없음)"
        self.is_pinned = memo.is_pinned
        self.setFixedHeight(MEMO_TAB_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        tip = ("📌 " if self.is_pinned else "") + self.memo_title
        self.setToolTip(tip)
        self.update_style(selected=False)

    def paintEvent(self, event) -> None:  # noqa: N802
        # 1) 기본 그리기 (stylesheet 배경/보더)
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

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
        bg = self._bg
        fg = self._fg
        # 본문과 만나는 쪽(accent)은 side 반대편
        accent = "left" if MemoTabButton.side == "right" else "right"
        if selected:
            # 선택 탭: accent 쪽 어두운 보더 + 그쪽 둥근 모서리, 반대쪽은 각짐
            if accent == "left":
                radius = (
                    "border-top-left-radius: 5px;"
                    "border-bottom-left-radius: 5px;"
                    "border-top-right-radius: 0;"
                    "border-bottom-right-radius: 0;"
                )
            else:
                radius = (
                    "border-top-right-radius: 5px;"
                    "border-bottom-right-radius: 5px;"
                    "border-top-left-radius: 0;"
                    "border-bottom-left-radius: 0;"
                )
            self.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {bg};"
                f"  border: none;"
                f"  border-{accent}: 3px solid {fg};"
                f"  {radius}"
                f"}}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {bg};"
                f"  border: none;"
                f"  border-{accent}: 3px solid transparent;"
                f"  border-radius: 5px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  border-{accent}: 3px solid {fg};"
                f"}}"
            )


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
        bg = COLORS[self.color_name]
        self.setStyleSheet(
            f"background-color: {bg};"
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


class FormatToolbar(QWidget):
    """리치텍스트 서식바: 굵게/기울임/밑줄/취소선 + 불릿/번호 리스트."""

    def __init__(self, editor: QTextEdit, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = editor
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._add_btn("B", "굵게 (Ctrl+B)", self.toggle_bold, bold=True)
        self._add_btn("I", "기울임 (Ctrl+I)", self.toggle_italic, italic=True)
        self._add_btn("U", "밑줄 (Ctrl+U)", self.toggle_underline, underline=True)
        self._add_btn("S", "취소선", self.toggle_strike, strike=True)
        self._add_btn("•", "불릿 목록", self.bullet_list)
        self._add_btn("1.", "번호 목록", self.numbered_list)
        layout.addStretch(1)

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


class DragGrip(QWidget):
    """탭 컬럼 상단의 세로 이동 그립 (크기 변경 없이 y 위치만 이동)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("드래그하여 세로 위치 이동")
        self._press_global = None
        self._start_geom = None
        icon_path = _resource_path("icon.png")
        self._icon_pixmap: QPixmap | None = None
        if icon_path.exists():
            pm = QPixmap(str(icon_path))
            if not pm.isNull():
                self._icon_pixmap = pm.scaled(
                    30, 30,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._icon_pixmap is not None:
            x = (self.width() - self._icon_pixmap.width()) // 2
            y = (self.height() - self._icon_pixmap.height()) // 2
            painter.drawPixmap(x, y, self._icon_pixmap)
        else:
            painter.setBrush(QColor("#6c7086"))
            painter.setPen(Qt.PenStyle.NoPen)
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
        # 0=오른쪽, 1=왼쪽 가장자리
        self.side = "left" if db.get_setting_int("side", 0) == 1 else "right"

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

    # ----- setup -----
    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(STYLE)
        self.setWindowTitle("Slide Memo")
        # 폭이 24~520 사이로 변경 가능해야 함 (접힘=24, 펼침=520).
        # 화면 안에 항상 전체가 들어오도록 폭 자체가 슬라이드함.
        self.setMinimumWidth(TAB_WIDTH)
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
        self.container.setMinimumWidth(TAB_WIDTH)
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

        # 제목 입력 (한 줄 전체)
        self.title_input = QLineEdit()
        self.title_input.setObjectName("titleInput")
        self.title_input.setPlaceholderText("제목")
        self.title_input.textChanged.connect(self._on_text_changed)
        ep.addWidget(self.title_input)

        # 에디터 (서식바가 참조하므로 먼저 생성)
        self.editor = RichPasteTextEdit()
        self.editor.setObjectName("editor")
        self.editor.setFont(self.editor_font)
        self.editor.setAcceptRichText(True)  # 이미지 붙여넣기 + 서식 지원
        self.editor.textChanged.connect(self._on_text_changed)

        # 서식바: 좌측 = 서식 버튼 / 우측 = 색상 dot + 복사 버튼
        self.format_toolbar = FormatToolbar(self.editor)
        fmt_layout = self.format_toolbar.layout()
        self.color_buttons: dict[str, ColorDot] = {}
        for name in COLOR_ORDER:
            dot = ColorDot(name)
            dot.clicked.connect(lambda _checked, n=name: self._on_color_changed(n))
            fmt_layout.addWidget(dot)
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
        fmt_layout.addWidget(self.custom_color_btn)
        fmt_layout.addSpacing(6)
        self._copy_icon = QIcon(str(_resource_path("content_copy.svg")))
        self._check_icon = QIcon(str(_resource_path("check.svg")))
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

        body_layout.addWidget(editor_panel, stretch=1)

        # ---- 우측 탭 컬럼 (항상 보임) ----
        self.tab_column = QWidget(self.container)
        self.tab_column.setObjectName("tabColumn")
        self.tab_column.setFixedWidth(TAB_WIDTH)
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

        # 하단: 휴지통 버튼 + 새 메모 버튼
        self.trash_btn = QPushButton("🗑")
        self.trash_btn.setObjectName("trashBtn")
        self.trash_btn.setFixedHeight(NEW_TAB_HEIGHT)
        self.trash_btn.setToolTip("휴지통")
        self.trash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trash_btn.clicked.connect(self._enter_trash_mode)
        col_layout.addWidget(self.trash_btn)

        self.new_tab_btn = QPushButton("＋")
        self.new_tab_btn.setObjectName("newTabBtn")
        self.new_tab_btn.setFixedHeight(NEW_TAB_HEIGHT)
        self.new_tab_btn.setToolTip("새 메모 (Ctrl+N)")
        self.new_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_tab_btn.clicked.connect(self.create_new_memo)
        col_layout.addWidget(self.new_tab_btn)

        root.addWidget(self.tab_column)

        # 리사이즈 드래그 핸들 (container 위에 absolute positioning)
        self.handle_left = ResizeHandle(self.container, "left")
        self.handle_right = ResizeHandle(self.container, "right")
        self.handle_top = ResizeHandle(self.container, "top")
        self.handle_bottom = ResizeHandle(self.container, "bottom")

        # 좌/우 가장자리 레이아웃 적용
        self._apply_side_layout()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_handles()

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
        """리사이즈 핸들 위치 + 가시성 갱신 (side / 펼침 상태 반영)."""
        if not hasattr(self, "handle_left"):
            return
        w = self.container.width()
        h = self.container.height()
        body_w = max(0, w - TAB_WIDTH)
        grip_h = max(0, h - 2 * RESIZE_GRIP)
        show = self.is_expanded
        if self.side == "right":
            # 본문이 좌측 → 좌측 가장자리가 폭 조절 핸들
            self.handle_left.setGeometry(0, RESIZE_GRIP, RESIZE_GRIP, grip_h)
            self.handle_top.setGeometry(0, 0, body_w, RESIZE_GRIP)
            self.handle_bottom.setGeometry(0, h - RESIZE_GRIP, body_w, RESIZE_GRIP)
            self.handle_left.setVisible(show)
            self.handle_right.setVisible(False)
        else:
            # 본문이 우측 → 우측 가장자리가 폭 조절 핸들
            self.handle_right.setGeometry(w - RESIZE_GRIP, RESIZE_GRIP, RESIZE_GRIP, grip_h)
            self.handle_top.setGeometry(TAB_WIDTH, 0, body_w, RESIZE_GRIP)
            self.handle_bottom.setGeometry(TAB_WIDTH, h - RESIZE_GRIP, body_w, RESIZE_GRIP)
            self.handle_right.setVisible(show)
            self.handle_left.setVisible(False)
        self.handle_top.setVisible(show)
        self.handle_bottom.setVisible(show)
        if show:
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

    def _setup_shortcuts(self) -> None:
        for keys, slot in [
            ("Escape", self.collapse),
            ("Ctrl+N", self.create_new_memo),
            ("Ctrl+F", self.focus_search),
            ("Ctrl+S", self.save_now),
            ("Ctrl+Shift+C", self._copy_memo_text),
            ("Ctrl+B", self.format_toolbar.toggle_bold),
            ("Ctrl+I", self.format_toolbar.toggle_italic),
            ("Ctrl+U", self.format_toolbar.toggle_underline),
        ]:
            sc = QShortcut(QKeySequence(keys), self)
            sc.activated.connect(slot)

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
        # 접힌 상태에선 폭이 TAB_WIDTH라 user_width를 덮어쓰면 안 됨
        # (접힌 채 세로 이동 그립을 드래그한 경우)
        if self.is_expanded:
            self.user_width = g.width()
        self.user_height = g.height()
        self.user_y = g.y()
        self.db.set_setting_int("window_width", self.user_width)
        self.db.set_setting_int("window_height", self.user_height)
        self.db.set_setting_int("window_y", self.user_y)

    def _expanded_geometry(self) -> QRect:
        rect = self._screen_rect()
        if self.side == "right":
            x = rect.right() - self.user_width + 1
        else:
            x = rect.x()
        return QRect(x, self.user_y, self.user_width, self.user_height)

    def _collapsed_geometry(self) -> QRect:
        rect = self._screen_rect()
        # 폭 자체를 TAB_WIDTH로 만들어 화면 가장자리에 탭만 노출.
        if self.side == "right":
            x = rect.right() - TAB_WIDTH + 1
        else:
            x = rect.x()
        return QRect(x, self.user_y, TAB_WIDTH, self.user_height)

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
        self.body.show()
        self._update_handles()
        # body opacity 0 → 1 페이드 인
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.body_opacity.opacity())
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()
        self.raise_()
        self.activateWindow()

    def collapse(self) -> None:
        if not self.is_expanded:
            return
        self.save_now()
        if self.trash_mode:
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
        self.trash_btn.setText(f"🗑\n{n}" if n else "🗑")
        self.trash_btn.setToolTip(f"휴지통 ({n})")

    # ----- 휴지통 모드 -----
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
        self.trash_btn.hide()
        self.new_tab_btn.hide()
        self._refresh_memo_tabs()

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
        self.trash_btn.show()
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
        is_preset = current_color in COLORS
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
            self.db.soft_delete(memo_id)
            if self.current_memo and self.current_memo.id == memo_id:
                self._clear_editor()
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


def load_app_icon() -> QIcon | None:
    """루트의 icon.ico/icon.png을 QIcon으로 로드. 없으면 None."""
    for name in ("icon.ico", "icon.png"):
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
    quit_act = QAction("종료", menu)
    quit_act.triggered.connect(window.request_quit)
    menu.addAction(quit_act)
    tray.setContextMenu(menu)

    def on_activate(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            window.toggle()

    tray.activated.connect(on_activate)
    return tray


def main() -> int:
    # HiDPI 환경에서 좌표/스케일 어긋남 방지 (QApplication 생성 전에 호출)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
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
