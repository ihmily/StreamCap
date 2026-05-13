import os
import sys
from pathlib import Path


def setup_bundled_flet_view() -> None:
    """Point FLET_VIEW_PATH to the bundled flet_desktop view when running as a PyInstaller package."""
    if not getattr(sys, "frozen", False):
        return

    if hasattr(sys, "_MEIPASS"):
        # noinspection PyProtectedMember
        base = Path(sys._MEIPASS)
    else:
        base = Path(sys.executable).parent / "_internal"

    view_path = base / "flet_desktop" / "app" / "flet"
    if (view_path / "flet.exe").is_file():
        os.environ["FLET_VIEW_PATH"] = str(view_path)
