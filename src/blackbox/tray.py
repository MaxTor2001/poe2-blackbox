"""System tray icon: open the journal, quit. Optional, the app works without it."""

import os
import webbrowser

from PIL import Image, ImageDraw


def make_icon_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=(150, 30, 30))
    d.ellipse((18, 22, 30, 34), fill=(20, 15, 15))
    d.ellipse((34, 22, 46, 34), fill=(20, 15, 15))
    d.rectangle((26, 40, 38, 50), fill=(20, 15, 15))
    return img


def run_tray(url: str, on_quit, data_dir=None) -> bool:
    """Block in the tray loop until Quit. Returns False immediately if no tray is available."""
    try:
        import pystray
    except Exception:
        return False

    def quit_(icon, item):
        on_quit()
        icon.stop()
        os._exit(0)

    items = [pystray.MenuItem("Open death journal", lambda icon, item: webbrowser.open(url), default=True)]
    if data_dir:
        items.append(pystray.MenuItem("Open clips folder", lambda icon, item: _open_folder(data_dir / "clips")))
    items.append(pystray.MenuItem("Quit", quit_))
    menu = pystray.Menu(*items)
    icon = pystray.Icon("blackbox", make_icon_image(), "PoE2 blackbox", menu)
    try:
        icon.run()
    except Exception:
        return False
    return True


def _open_folder(path) -> None:
    import click

    path.mkdir(parents=True, exist_ok=True)
    click.launch(str(path))
