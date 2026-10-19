from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from tkinter import Tk, Frame, Label, Button, Entry, StringVar, BooleanVar, Checkbutton
from tkinter import filedialog, messagebox, ttk
from typing import Any


def _payload_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "payload"
    return Path(__file__).resolve().parent.parent / "dist" / "package"


def _read_version() -> str:
    version_file = _payload_root() / "version.txt"
    if version_file.is_file():
        return version_file.read_text(encoding="ascii").strip()
    return "0.0.0"


VERSION = _read_version()
APP_NAME = "CAE Result Analysis & Report Workbench"
INSTALL_DIR_NAME = "CAEReportWorkbench"
REG_KEY = r"Software\CAEReportWorkbench"


def _default_install_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / INSTALL_DIR_NAME
    return Path("C:/") / INSTALL_DIR_NAME


def _find_existing() -> Path | None:
    for hint in (
        _default_install_dir(),
        Path("C:/") / INSTALL_DIR_NAME,
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / INSTALL_DIR_NAME,
    ):
        if (hint / "CAEReportDesktop.exe").is_file():
            return hint
    try:
        import winreg
    except ImportError:
        return None
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(root, REG_KEY) as key:
                value, _ = winreg.QueryValueEx(key, "InstallDir")
                candidate = Path(value)
                if (candidate / "CAEReportDesktop.exe").is_file():
                    return candidate
        except OSError:
            continue
    return None


def _extract_zip_files(root: Path, progress_cb: Any) -> None:
    zip_files = list(root.rglob("*.zip"))
    for idx, zip_path in enumerate(zip_files):
        progress_cb(f"Extracting internal archive: {zip_path.name} ({idx + 1}/{len(zip_files)})")
        extract_dir = zip_path.parent / f"{zip_path.stem}_extracted"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
        except (zipfile.BadZipFile, OSError, EOFError):
            progress_cb(f"  WARNING: Cannot read {zip_path.name}, may be encrypted")


def _create_shortcut(target: Path, shortcut_dir: Path, name: str) -> None:
    shortcut_path = shortcut_dir / f"{name}.lnk"
    ps_command = (
        f"$WScriptShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WScriptShell.CreateShortcut('{shortcut_path}'); "
        f"$Shortcut.TargetPath = '{target}'; "
        f"$Shortcut.WorkingDirectory = '{target.parent}'; "
        f"$Shortcut.Description = '{APP_NAME}'; "
        f"$Shortcut.IconLocation = '{target}'; "
        f"$Shortcut.Save()"
    )
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        pass


def _write_uninstaller(install_dir: Path) -> None:
    batch = install_dir / "uninstall.bat"
    lines = [
        "@echo off",
        "echo Uninstalling CAE Result Analysis & Report Workbench...",
        "echo.",
        'reg delete "HKCU\\Software\\CAEReportWorkbench" /f 2>nul',
        f'rd /s /q "{install_dir}" 2>nul',
        f'del /f /q "%USERPROFILE%\\Desktop\\{APP_NAME}.lnk" 2>nul',
        "echo Uninstall complete.",
        "pause",
    ]
    batch.write_text("\n".join(lines), encoding="ascii")


def _write_registry(install_dir: Path) -> None:
    try:
        import winreg
    except ImportError:
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
            winreg.SetValueEx(key, "InstallDir", 0, winreg.REG_SZ, str(install_dir))
            winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, VERSION)
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            uninstall = install_dir / "uninstall.bat"
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, str(uninstall))
    except OSError:
        pass


def _remove_registry() -> None:
    try:
        import winreg
    except ImportError:
        return
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
    except OSError:
        pass


class InstallerApp:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(f"{APP_NAME} Setup v{VERSION}")
        self.root.resizable(False, False)
        self.root.geometry("520x440")
        try:
            self.root.iconbitmap(default=sys.executable)
        except Exception:
            pass

        main = Frame(self.root, padx=24, pady=24)
        main.pack(fill="both", expand=True)

        Label(main, text=APP_NAME, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        Label(main, text=f"Version {VERSION}", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 16))

        existing = _find_existing()
        self._is_update = existing is not None
        self._existing_dir = existing
        if self._is_update:
            Label(
                main,
                text=f"Existing installation found at:\n{existing}",
                fg="#0078d4",
                font=("Segoe UI", 9),
                justify="left",
            ).pack(anchor="w", pady=(0, 12))

        dir_frame = Frame(main)
        dir_frame.pack(fill="x", pady=(0, 12))
        Label(dir_frame, text="Install location:", font=("Segoe UI", 9)).pack(anchor="w")

        entry_frame = Frame(dir_frame)
        entry_frame.pack(fill="x", pady=(4, 0))
        self.dir_var = StringVar(
            value=str(existing) if self._is_update else str(_default_install_dir())
        )
        self.dir_entry = Entry(entry_frame, textvariable=self.dir_var, font=("Segoe UI", 9))
        self.dir_entry.pack(side="left", fill="x", expand=True)
        Button(
            entry_frame,
            text="Browse...",
            command=self._browse_dir,
            font=("Segoe UI", 9),
            padx=8,
        ).pack(side="left", padx=(6, 0))

        self.desktop_var = BooleanVar(value=True)
        Checkbutton(
            main,
            text="Create desktop shortcut",
            variable=self.desktop_var,
            font=("Segoe UI", 9),
        ).pack(anchor="w")

        if self._is_update:
            Label(
                main,
                text="Update mode: existing files will be replaced.\n"
                "Workspace data (projects, captures) will not be affected.",
                font=("Segoe UI", 9),
                fg="#555",
                justify="left",
            ).pack(anchor="w", pady=(16, 0))

        self.status_var = StringVar(value="Ready to install.")
        Label(
            main, textvariable=self.status_var, font=("Segoe UI", 9), fg="#555"
        ).pack(anchor="w", pady=(8, 4))

        self.progress = ttk.Progressbar(main, mode="determinate", length=472)
        self.progress.pack(fill="x", pady=(0, 16))

        btn_frame = Frame(main)
        btn_frame.pack(fill="x")
        self.install_btn = Button(
            btn_frame,
            text="Update" if self._is_update else "Install",
            command=self._install,
            font=("Segoe UI", 10, "bold"),
            bg="#0078d4",
            fg="white",
            padx=24,
            pady=4,
        )
        self.install_btn.pack(side="right")
        Button(
            btn_frame,
            text="Cancel",
            command=self.root.destroy,
            font=("Segoe UI", 10),
            padx=16,
            pady=4,
        ).pack(side="right", padx=(0, 8))

        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def _browse_dir(self) -> None:
        chosen = filedialog.askdirectory(title="Select Installation Folder")
        if chosen:
            self.dir_var.set(chosen)

    def _update_status(self, msg: str, progress_val: int | None = None) -> None:
        self.status_var.set(msg)
        if progress_val is not None:
            self.progress["value"] = progress_val
        self.root.update_idletasks()

    def _install(self) -> None:
        install_dir = Path(self.dir_var.get())
        if not install_dir:
            messagebox.showerror("Error", "Please select an installation directory.")
            return

        self.install_btn.config(state="disabled")
        try:
            self._do_install(install_dir)
        except Exception as exc:
            self._update_status(f"Installation failed: {exc}")
            messagebox.showerror("Error", f"Installation failed:\n{exc}")
            self.install_btn.config(state="normal")
        else:
            self._update_status("Installation complete!", 100)
            messagebox.showinfo(
                "Success",
                f"Installation complete!\n\n"
                f"Location: {install_dir}\n\n"
                f'Run "{install_dir / "CAEReportDesktop.exe"}" to start.',
            )
            self.root.destroy()

    def _do_install(self, install_dir: Path) -> None:
        payload = _payload_root()
        if not payload.is_dir():
            raise RuntimeError(f"Payload directory not found: {payload}")

        if self._is_update and self._existing_dir and self._existing_dir != install_dir:
            self._update_status("Migrating from previous installation...", 5)
            if self._existing_dir.is_dir():
                shutil.rmtree(self._existing_dir)
            _remove_registry()

        self._update_status("Preparing installation directory...", 10)
        install_dir.mkdir(parents=True, exist_ok=True)

        payload_items = list(payload.iterdir())
        total = len(payload_items)

        for idx, item in enumerate(payload_items):
            progress = 10 + int(70 * idx / max(total, 1))
            dest = install_dir / item.name
            self._update_status(f"Extracting: {item.name} ({idx + 1}/{total})", progress)

            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        self._update_status("Extracting internal archives...", 85)
        _extract_zip_files(install_dir, self._update_status)

        _write_registry(install_dir)
        _write_uninstaller(install_dir)

        self._update_status("Creating shortcuts...", 90)
        if self.desktop_var.get():
            try:
                desktop_dir = Path(os.environ["USERPROFILE"]) / "Desktop"
                _create_shortcut(
                    install_dir / "CAEReportDesktop.exe",
                    desktop_dir,
                    APP_NAME,
                )
            except Exception:
                pass

        self._update_status("Installation complete!", 100)


def main() -> None:
    app = InstallerApp()
    app.root.mainloop()


if __name__ == "__main__":
    main()
