"""Find which monitor shows the game window (Windows only)."""

import sys

TITLE = "path of exile 2"  # exact window title of the game
PROCESS_PREFIX = "pathofexile"  # PathOfExile.exe / PathOfExileSteam.exe


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


def process_name(hwnd: int) -> str:
    """Executable name of the window's process, lowercase; empty if unknown."""
    import ctypes
    from ctypes import wintypes

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ""
        return buf.value.replace("\\", "/").rsplit("/", 1)[-1].lower()
    finally:
        kernel32.CloseHandle(handle)


def game_windows() -> list[int]:
    """Windows titled exactly like the game and owned by the game's process (a browser tab is not the game)."""
    out = []
    for hwnd, title in visible_windows():
        if title.lower() != TITLE:
            continue
        name = process_name(hwnd)
        if not name or name.startswith(PROCESS_PREFIX):
            out.append(hwnd)
    return out


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
    user32.MonitorFromWindow.restype = ctypes.c_void_p
    target = user32.MonitorFromWindow(found[0], 2)  # MONITOR_DEFAULTTONEAREST
    monitors: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    def on_monitor(handle, _dc, _rect, _):
        monitors.append(handle)
        return True

    user32.EnumDisplayMonitors(None, None, on_monitor, 0)
    return monitors.index(target) if target in monitors else None


def game_window_rect() -> tuple[int, int, int, int] | None:
    """(x, y, w, h) of the game's client area relative to its monitor, or None. Best effort."""
    try:
        return _game_window_rect()
    except Exception as err:  # cropping is optional; never block recording on it
        print(f"window rect unavailable: {err!r}")
        return None


def _game_window_rect():
    found = game_windows()
    if not found:
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.MonitorFromWindow.restype = ctypes.c_void_p
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    hwnd = found[0]
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(info))
    x, y = origin.x - info.rcMonitor.left, origin.y - info.rcMonitor.top
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w < 64 or h < 64:
        return None
    return x, y, w, h
