"""시스템 시작 시 자동 실행 — Windows/macOS/Linux 분기.

공개 API:
- is_supported() -> bool
- is_enabled() -> bool
- set_enabled(enable: bool) -> tuple[bool, str]
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path


APP_NAME = "SlideMemo"
MAC_LABEL = "com.user.slidememo"


def _autostart_command() -> str:
    """OS 자동 실행에 등록할 명령 문자열. 경로에 공백 가능 → 따옴표 처리."""
    exe = sys.executable
    script = os.path.abspath(sys.argv[0])
    if os.path.normcase(exe) == os.path.normcase(script):
        # PyInstaller --onefile: sys.executable이 곧 .exe
        return f'"{exe}"'
    return f'"{exe}" "{script}"'


def _autostart_argv() -> list[str]:
    """plist/desktop용 인자 리스트 형태."""
    exe = sys.executable
    script = os.path.abspath(sys.argv[0])
    if os.path.normcase(exe) == os.path.normcase(script):
        return [exe]
    return [exe, script]


# ── Windows ───────────────────────────────────────────────────────────
_WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _win_is_enabled() -> bool:
    try:
        import winreg
    except ImportError:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY, 0, winreg.KEY_READ
        ) as k:
            value, _ = winreg.QueryValueEx(k, APP_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def _win_set_enabled(enable: bool) -> tuple[bool, str]:
    try:
        import winreg
    except ImportError:
        return False, "winreg를 사용할 수 없습니다."
    try:
        if enable:
            cmd = _autostart_command()
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as k:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, cmd)
            return True, "자동 실행이 등록되었습니다."
        # 해제
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as k:
                winreg.DeleteValue(k, APP_NAME)
            return True, "자동 실행이 해제되었습니다."
        except FileNotFoundError:
            return True, "이미 해제되어 있습니다."
    except OSError as e:
        return False, f"레지스트리 작업에 실패했습니다: {e}"


# ── macOS ─────────────────────────────────────────────────────────────
_MAC_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"

_MAC_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
{args}
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""


def _mac_is_enabled() -> bool:
    return _MAC_PLIST_PATH.exists()


def _mac_set_enabled(enable: bool) -> tuple[bool, str]:
    try:
        if enable:
            args = _autostart_argv()
            args_xml = "\n".join(
                f"        <string>{a}</string>" for a in args
            )
            content = _MAC_PLIST_TEMPLATE.format(label=MAC_LABEL, args=args_xml)
            _MAC_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            _MAC_PLIST_PATH.write_text(content, encoding="utf-8")
            # launchctl load — 권한/세션 문제로 실패 가능, stderr 반환
            res = subprocess.run(
                ["launchctl", "load", str(_MAC_PLIST_PATH)],
                capture_output=True, text=True,
            )
            if res.returncode != 0:
                err = (res.stderr or res.stdout).strip()
                return False, f"launchctl load 실패: {err or '알 수 없는 오류'}"
            return True, "자동 실행이 등록되었습니다."
        # 해제
        if _MAC_PLIST_PATH.exists():
            subprocess.run(
                ["launchctl", "unload", str(_MAC_PLIST_PATH)],
                capture_output=True, text=True,
            )
            _MAC_PLIST_PATH.unlink()
        return True, "자동 실행이 해제되었습니다."
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"오류가 발생했습니다: {e}"


# ── Linux ─────────────────────────────────────────────────────────────
_LINUX_DESKTOP_PATH = (
    Path.home() / ".config" / "autostart" / "slidememo.desktop"
)

_LINUX_DESKTOP_TEMPLATE = """[Desktop Entry]
Type=Application
Name=Slide Memo
Exec={exec_cmd}
X-GNOME-Autostart-enabled=true
"""


def _linux_is_enabled() -> bool:
    return _LINUX_DESKTOP_PATH.exists()


def _linux_set_enabled(enable: bool) -> tuple[bool, str]:
    try:
        if enable:
            exec_cmd = _autostart_command()
            content = _LINUX_DESKTOP_TEMPLATE.format(exec_cmd=exec_cmd)
            _LINUX_DESKTOP_PATH.parent.mkdir(parents=True, exist_ok=True)
            _LINUX_DESKTOP_PATH.write_text(content, encoding="utf-8")
            return True, "자동 실행이 등록되었습니다."
        if _LINUX_DESKTOP_PATH.exists():
            _LINUX_DESKTOP_PATH.unlink()
        return True, "자동 실행이 해제되었습니다."
    except OSError as e:
        return False, f"파일 작업에 실패했습니다: {e}"


# ── 공개 API ──────────────────────────────────────────────────────────
def is_supported() -> bool:
    return platform.system() in ("Windows", "Darwin", "Linux")


def is_enabled() -> bool:
    sys_name = platform.system()
    if sys_name == "Windows":
        return _win_is_enabled()
    if sys_name == "Darwin":
        return _mac_is_enabled()
    if sys_name == "Linux":
        return _linux_is_enabled()
    return False


def set_enabled(enable: bool) -> tuple[bool, str]:
    sys_name = platform.system()
    if sys_name == "Windows":
        return _win_set_enabled(enable)
    if sys_name == "Darwin":
        return _mac_set_enabled(enable)
    if sys_name == "Linux":
        return _linux_set_enabled(enable)
    return False, "현재 OS에서는 자동 실행이 지원되지 않습니다."
