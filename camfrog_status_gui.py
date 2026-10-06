"""Compact Camfrog Status Changer using the shared config.json."""
import copy
import json
import logging
import os
import queue
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import camfrog_auto as ca
from clipboard_support import ClipboardController


RUNTIME_CONFIG = ca.BASE / "camfrog-status-runtime.json"
WORKER_MARKER = ca.BASE / "camfrog-status-changer-worker.pid"
MARQUEE_STEP_MIN = 0.5
MARQUEE_STRIDE_DEFAULT = 2
STATUS_SLOTS = 10


def text_to_message(value):
    value = value.strip()
    if not value:
        return None
    if "||" in value:
        th, en = (part.strip() for part in value.split("||", 1))
        if th and en:
            return {"th": th, "en": en}
        return th or en or None
    return value


def message_to_text(value):
    if isinstance(value, dict):
        return f"{value.get('th', '')} || {value.get('en', '')}"
    return str(value or "")


def messages_from_slots(values):
    """Return the configured, non-empty messages represented by the ten GUI slots."""
    result = []
    for value in values:
        message = text_to_message(value)
        if message is not None:
            result.append(message)
    return result


def runtime_config(config):
    """Clone shared settings for a status-only worker; keep the shared PID lock."""
    runtime = copy.deepcopy(config)
    runtime["autoreply"]["enabled"] = False
    runtime.setdefault("autoreply_im", {})["enabled"] = False
    runtime["stats"]["file"] = "camfrog_status_changer_stats.json"
    runtime["log"]["file"] = "camfrog_status_changer.log"
    return runtime


def write_config(path, config):
    ca.atomic_write(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")


def build_app():
    import tkinter as tk
    from tkinter import messagebox, ttk

    class StatusChanger:
        def __init__(self, config_path):
            self.config_path = Path(config_path).resolve()
            self.runtime_config_path = self.config_path.with_name(RUNTIME_CONFIG.name)
            self.worker_marker_path = self.config_path.with_name(WORKER_MARKER.name)
            self.root = tk.Tk()
            self.root.title("Camfrog Status Changer")
            self.root.geometry("210x470")
            self.root.resizable(False, False)
            self.root.minsize(210, 470)
            self.root.maxsize(210, 470)
            try:
                self.root.iconbitmap(str(ca.BASE / "app.ico"))
            except (tk.TclError, OSError):
                pass
            self.busy = False
            self.close_requested = False
            self.task_results = queue.Queue()
            self.task_poll_job = None
            self.state_job = None
            self.save_job = None
            self.mode = "random"
            try:
                self.config = ca.load_cfg(self.config_path)
            except Exception as exc:
                messagebox.showerror("Camfrog Status Changer", str(exc), parent=self.root)
                self.root.destroy()
                raise SystemExit(2)
            ca.LANG = ca.resolve_lang(self.config.get("language", "auto"))
            self.fields = [tk.StringVar(value="") for _ in range(STATUS_SLOTS)]
            self.step = tk.StringVar(value=str(max(
                MARQUEE_STEP_MIN, self.config["status"]["marquee"]["step_seconds"])))
            self.stride = tk.StringVar(value=str(self.config["status"]["marquee"].get(
                "stride", MARQUEE_STRIDE_DEFAULT)))
            self._load_fields()
            for variable in self.fields:
                variable.trace_add("write", self.schedule_save)
            self._build()
            self.clipboard_controller = ClipboardController(
                self.root, translate=self._translate_clipboard, on_error=self._clipboard_error)
            self.clipboard_controller.install(self.root)
            self.root.protocol("WM_DELETE_WINDOW", self.close_app)
            self.task_poll_job = self.root.after(100, self.poll_task_results)
            self.state_job = self.root.after(500, self.refresh_state)

        def _load_fields(self):
            for var, message in zip(self.fields, self.config["status"]["messages"][:STATUS_SLOTS]):
                var.set(message_to_text(message))
            st = self.config["status"]
            if st["marquee"]["enabled"]:
                self.mode = "marquee"
            elif st["random"]:
                self.mode = "random"

        def _tr(self, en, th):
            return th if ca.LANG == "th" else en

        def _translate_clipboard(self, text):
            en, _, th = text.partition("||")
            th, en = th.strip(), en.strip()
            return th if ca.LANG == "th" and th else en

        def _clipboard_error(self, exc):
            try:
                self.note.configure(text=self._tr(f"Clipboard error: {exc}",
                                                   f"คลิปบอร์ดผิดพลาด: {exc}"))
            except tk.TclError:
                pass

        def _build(self):
            root = self.root
            style = ttk.Style(root)
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
            style.configure("Brand.TLabel", font=("Segoe UI", 9, "bold"), foreground="#126c68")
            style.configure("State.TLabel", font=("Segoe UI", 8, "bold"))
            outer = ttk.Frame(root, padding=(7, 6, 7, 4))
            outer.pack(fill="both", expand=True)

            header = ttk.Frame(outer)
            header.pack(fill="x", pady=(0, 5))
            ttk.Label(header, text="STATUS", style="Brand.TLabel").pack(side="left")
            self.state_label = ttk.Label(header, text="", style="State.TLabel")
            self.state_label.pack(side="right")

            self.tabs = ttk.Notebook(outer)
            self.tabs.pack(fill="both", expand=True)
            self.pages = {}
            for name, mode in (("Random", "random"), ("Marquee", "marquee")):
                page = ttk.Frame(self.tabs, padding=6)
                self.tabs.add(page, text=name)
                self.pages[mode] = page
                self._build_page(page, mode)
            self.tabs.bind("<<NotebookTabChanged>>", self._tab_changed)

            self.note = ttk.Label(outer, text="", font=("Segoe UI", 7), anchor="center",
                                  foreground="#53636d", wraplength=164)
            self.note.pack(fill="x", pady=(4, 2))
            ttk.Label(outer, text="CAMFROG AUTO", style="Brand.TLabel",
                      anchor="center").pack(fill="x")
            selected = 1 if self.mode == "marquee" else 0
            self.tabs.select(selected)

        def _build_page(self, page, mode):
            if mode == "random":
                ttk.Label(page, text=self._tr("Random status pool", "ชุดสถานะสุ่ม"),
                          font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 3))
            else:
                ttk.Label(page, text=self._tr("Marquee status pool", "ชุดสถานะเลื่อน"),
                          font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 3))
                speed = ttk.Frame(page)
                speed.pack(fill="x", pady=(0, 3))
                ttk.Label(speed, text=self._tr("Step", "จังหวะ")).pack(side="left")
                ttk.Spinbox(speed, textvariable=self.step, from_=MARQUEE_STEP_MIN,
                            to=10, increment=0.1, width=4).pack(side="left", padx=(3, 5))
                ttk.Label(speed, text="s").pack(side="left")
                ttk.Label(speed, text=self._tr("Stride", "ก้าว")).pack(side="left", padx=(5, 2))
                ttk.Spinbox(speed, textvariable=self.stride, from_=1, to=10,
                            increment=1, width=2).pack(side="left")

            entries = ttk.Frame(page)
            entries.pack(fill="both", expand=True)
            for index, var in enumerate(self.fields):
                ttk.Label(entries, text=str(index + 1), width=2).grid(
                    row=index, column=0, sticky="w", pady=3)
                entry = ttk.Entry(entries, textvariable=var, width=13)
                entry.grid(row=index, column=1, sticky="ew", pady=3)
            entries.columnconfigure(1, weight=1)

            buttons = ttk.Frame(page)
            buttons.pack(fill="x", pady=(5, 0))
            ttk.Button(buttons, text=self._tr("Enable", "เปิด"),
                       command=lambda m=mode: self.set_enabled(m, True)).pack(
                           side="left", fill="x", expand=True, padx=(0, 3))
            ttk.Button(buttons, text=self._tr("Disable", "ปิด"),
                       command=lambda: self.set_enabled(mode, False)).pack(
                           side="left", fill="x", expand=True, padx=(3, 0))

        def _tab_changed(self, _event=None):
            try:
                page_index = self.tabs.index(self.tabs.select())
                self.mode = "marquee" if page_index == 1 else "random"
            except Exception:
                pass

        def schedule_save(self, *_args):
            if self.save_job is not None:
                try:
                    self.root.after_cancel(self.save_job)
                except tk.TclError:
                    pass
            self.save_job = self.root.after(450, self.save_settings)

        def collect_config(self, enabled=None, mode=None):
            config = ca.load_cfg(self.config_path)
            st = config["status"]
            st["messages"] = messages_from_slots(var.get() for var in self.fields)
            mq = st["marquee"]
            try:
                mq["step_seconds"] = max(MARQUEE_STEP_MIN, float(self.step.get()))
                mq["stride"] = max(1, int(float(self.stride.get())))
            except ValueError as exc:
                raise ValueError(self._tr("Enter valid marquee speed values.",
                                          "กรอกค่าความเร็วข้อความเลื่อนให้ถูกต้อง")) from exc
            if mode is not None:
                st["random"] = mode == "random"
                mq["enabled"] = mode == "marquee"
            if enabled is not None:
                st["enabled"] = enabled
            if st["enabled"] and not st["messages"]:
                raise ValueError(self._tr("Enter at least one status.", "กรอกสถานะอย่างน้อยหนึ่งข้อความ"))
            errors, _warnings = ca.validate(config)
            if errors:
                raise ValueError("\n".join(errors))
            return config

        def save_settings(self, enabled=None, mode=None, notify=False):
            self.save_job = None
            try:
                config = self.collect_config(enabled=enabled, mode=mode)
                write_config(self.config_path, config)
                runtime = runtime_config(config)
                write_config(self.runtime_config_path, runtime)
                self.config = config
                if notify:
                    self.note.configure(text=self._tr("Saved to shared config.json",
                                                      "บันทึกใน config.json แล้ว"))
                return config
            except (OSError, ValueError, KeyError) as exc:
                self.note.configure(text=str(exc), foreground="#a52834")
                return None

        def set_enabled(self, mode, enabled):
            config = self.save_settings(enabled=enabled, mode=mode)
            if config is None:
                return
            self.mode = mode
            if enabled:
                main_pid = ca.running_pid(config)
                worker_pid = self._worker_pid()
                if main_pid:
                    if worker_pid == main_pid:
                        self.note.configure(text=self._tr("Status worker is already running.",
                                                          "ตัวเปลี่ยนสถานะกำลังทำงานอยู่"),
                                             foreground="#138a55")
                    else:
                        self.note.configure(text=self._tr("Settings saved for the running bot.",
                                                          "บันทึกค่าให้บอทที่กำลังทำงานแล้ว"),
                                             foreground="#138a55")
                    return
                self._start_worker(config)
            else:
                main_pid = ca.running_pid(config)
                worker_pid = self._worker_pid()
                if main_pid and worker_pid == main_pid:
                    runtime = runtime_config(config)
                    self.run_task(lambda: self._stop_worker(runtime),
                                  self._tr("Status worker stopped.", "หยุดตัวเปลี่ยนสถานะแล้ว"))
                else:
                    self.note.configure(text=self._tr("Status rotation disabled.",
                                                      "ปิดการเปลี่ยนสถานะแล้ว"), foreground="#53636d")

        def _start_worker(self, config):
            runtime = runtime_config(config)
            args = SimpleNamespace(config=str(self.runtime_config_path), lang=None)

            def start():
                rc = ca.cmd_start(runtime, args)
                if rc == 0:
                    pid = ca.running_pid(runtime)
                    if not pid:
                        raise RuntimeError(self._tr(
                            "Worker started but its process could not be verified.",
                            "เริ่ม worker แล้วแต่ตรวจสอบโปรเซสไม่ได้"))
                    try:
                        self.worker_marker_path.write_text(str(pid), encoding="ascii")
                    except OSError:
                        # Do not leave an untracked worker if its ownership marker
                        # cannot be written; roll it back before reporting failure.
                        ca.cmd_stop(runtime)
                        raise
                return rc

            self.run_task(start, self._tr("Status worker started.", "เริ่มตัวเปลี่ยนสถานะแล้ว"))

        def _stop_worker(self, runtime):
            result = ca.cmd_stop(runtime)
            if result in (None, 0):
                self.worker_marker_path.unlink(missing_ok=True)
            return result

        def _worker_pid(self):
            try:
                pid = int(self.worker_marker_path.read_text(encoding="ascii").strip())
                return pid if ca.pid_alive(pid) else None
            except (OSError, ValueError):
                return None

        def run_task(self, function, done_text, on_done=None):
            if self.busy:
                return False
            self.busy = True
            self.note.configure(text=self._tr("Working…", "กำลังทำงาน…"), foreground="#53636d")

            def worker():
                try:
                    result = function()
                    text = done_text if result in (None, 0) else self._tr("Command failed.", "คำสั่งไม่สำเร็จ")
                    ok = result in (None, 0)
                except Exception as exc:
                    text, ok = str(exc), False
                self.task_results.put((text, ok, on_done))

            try:
                threading.Thread(target=worker, daemon=True, name="camfrog-status-task").start()
                return True
            except RuntimeError as exc:
                self.busy = False
                self.note.configure(text=str(exc), foreground="#a52834")
                return False

        def poll_task_results(self):
            try:
                while True:
                    text, ok, on_done = self.task_results.get_nowait()
                    self.finish_task(text, ok, on_done)
            except queue.Empty:
                pass
            except Exception as exc:
                logging.exception("Could not process Status Changer task result")
                if self.root.winfo_exists():
                    self.note.configure(text=str(exc), foreground="#a52834")
            try:
                self.task_poll_job = self.root.after(100, self.poll_task_results)
            except tk.TclError:
                self.task_poll_job = None

        def finish_task(self, text, ok, on_done=None):
            self.busy = False
            self.note.configure(text=text, foreground="#138a55" if ok else "#a52834")
            self.refresh_state()
            close_after_task = self.close_requested
            self.close_requested = False
            if on_done:
                on_done(ok)
            if close_after_task:
                try:
                    if self.root.winfo_exists():
                        self.close_app()
                except tk.TclError:
                    pass

        def close_app(self):
            """Exit fully, stopping only the status-only worker this window owns."""
            if self.busy:
                self.close_requested = True
                self.note.configure(text=self._tr(
                    "Finishing the current task before exit…",
                    "รอให้งานปัจจุบันเสร็จแล้วปิดโปรแกรม…"), foreground="#53636d")
                return
            try:
                config = ca.load_cfg(self.config_path)
                worker_pid = self._worker_pid()
                running_pid = ca.running_pid(config)
                if worker_pid and worker_pid == running_pid:
                    runtime = runtime_config(config)
                    self.note.configure(text=self._tr(
                        "Stopping the status worker before exit…",
                        "กำลังหยุดตัวเปลี่ยนสถานะก่อนออก…"), foreground="#53636d")
                    started = self.run_task(
                        lambda: self._stop_worker(runtime),
                        self._tr("Status worker stopped.", "หยุดตัวเปลี่ยนสถานะแล้ว"),
                        on_done=self._close_after_worker_stop,
                    )
                    if started:
                        return
                if self.worker_marker_path.exists() and not worker_pid:
                    self.worker_marker_path.unlink(missing_ok=True)
            except Exception as exc:
                logging.exception("Could not prepare a clean Status Changer exit")
                messagebox.showerror(
                    "Camfrog Status Changer",
                    self._tr(
                        f"Could not verify worker shutdown: {exc}",
                        f"ตรวจสอบการหยุด worker ไม่สำเร็จ: {exc}"),
                    parent=self.root,
                )
                return
            self._finalize_close()

        def _close_after_worker_stop(self, ok):
            if ok:
                self._finalize_close()
            else:
                self.note.configure(text=self._tr(
                    "Worker did not confirm shutdown. The window stays open so you can retry.",
                    "worker ยังไม่ยืนยันว่าหยุดแล้ว หน้าต่างยังเปิดไว้ให้ลองใหม่"),
                    foreground="#a52834")

        def _finalize_close(self):
            if self.save_job is not None:
                try:
                    self.root.after_cancel(self.save_job)
                except tk.TclError:
                    pass
                self.save_job = None
                self.save_settings()
            for job in (self.state_job, self.task_poll_job):
                if job is not None:
                    try:
                        self.root.after_cancel(job)
                    except tk.TclError:
                        pass
            try:
                self.root.quit()
            except tk.TclError:
                pass
            try:
                self.root.destroy()
            except tk.TclError:
                pass

        def refresh_state(self):
            if not self.root.winfo_exists():
                return
            try:
                config = ca.load_cfg(self.config_path)
                pid = ca.running_pid(config)
                worker = self._worker_pid()
                running = bool(pid)
                self.state_label.configure(
                    text=(self._tr("WORKER", "ตัวเปลี่ยน") if running and pid == worker else
                          self._tr("RUNNING", "ทำงาน") if running else
                          self._tr("STOPPED", "หยุด")),
                    foreground="#138a55" if running else "#697780",
                )
            except Exception:
                pass
            self.state_job = self.root.after(1200, self.refresh_state)

        def mainloop(self):
            self.root.mainloop()

    return StatusChanger


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if any(arg in ca.CLI_COMMANDS for arg in argv):
        return ca.main(argv)
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    config_path = ca.BASE / "config.json"
    if "--config" in argv:
        index = argv.index("--config")
        if index + 1 < len(argv):
            config_path = Path(argv[index + 1])
    try:
        app = build_app()(config_path)
    except SystemExit as exc:
        return exc.code
    except Exception as exc:
        print(f"Status Changer failed: {exc}")
        return 1
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
