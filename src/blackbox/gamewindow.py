"""Find which monitor shows the game window (Windows only)."""

import sys

TITLE = "path of exile 2"


def game_monitor_index() -> int | None:
    """Index of the display holding the game window, in EnumDisplayMonitors order; None if not found."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def on_window(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if buf.value.strip().lower() == TITLE and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(on_window, 0)
    if not found:
        return None
    target = user32.MonitorFromWindow(found[0], 2)  # MONITOR_DEFAULTTONEAREST
    monitors: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    def on_monitor(handle, _dc, _rect, _):
        monitors.append(handle)
        return True

    user32.EnumDisplayMonitors(None, None, on_monitor, 0)
    return monitors.index(target) if target in monitors else None
