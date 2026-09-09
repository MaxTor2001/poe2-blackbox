"""Find which monitor shows the game window (Windows only)."""

import sys

TITLE = "path of exile"


def visible_windows() -> list[tuple[int, str]]:
    """(hwnd, title) of every visible top-level window with a title (Windows only)."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    out: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def on_window(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if buf.value.strip() and user32.IsWindowVisible(hwnd):
            out.append((hwnd, buf.value.strip()))
        return True

    user32.EnumWindows(on_window, 0)
    return out


def game_windows() -> list[int]:
    return [hwnd for hwnd, title in visible_windows() if TITLE in title.lower()]


def game_running() -> bool | None:
    """True/False on Windows; None where we cannot tell (record all the time there)."""
    if sys.platform != "win32":
        return None
    return bool(game_windows())


def game_monitor_index() -> int | None:
    """Index of the display holding the game window, in EnumDisplayMonitors order; None if not found."""
    found = game_windows()
    if not found:
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    target = user32.MonitorFromWindow(found[0], 2)  # MONITOR_DEFAULTTONEAREST
    monitors: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    def on_monitor(handle, _dc, _rect, _):
        monitors.append(handle)
        return True

    user32.EnumDisplayMonitors(None, None, on_monitor, 0)
    return monitors.index(target) if target in monitors else None
