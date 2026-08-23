"""Tkinter desktop UI for enabling/disabling analytics per camera."""

from __future__ import annotations

import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Dict, List

from .analytics_defs import (ANALYTICS, ANALYTICS_BY_KEY, ANALYTIC_KEYS, BOOL,
                             CHOICE, INT, MULTICHOICE, TEXT, TIME, AnalyticDef,
                             ParamDef)
from .config import AppConfig, Camera, ConfigError, default_config_path

APP_TITLE = "CCTV Analytics Manager"
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ---------------------------------------------------------------- helpers
class ScrollableFrame(ttk.Frame):
    """A frame inside a canvas, with vertical + horizontal scrollbars."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.inner = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Enter>", lambda _e: self._bind_wheel())
        self.canvas.bind("<Leave>", lambda _e: self._unbind_wheel())

    def _on_inner_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _bind_wheel(self) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)      # Windows / macOS
        self.canvas.bind_all("<Button-4>", self._on_wheel)        # X11 scroll up
        self.canvas.bind_all("<Button-5>", self._on_wheel)        # X11 scroll down

    def _unbind_wheel(self) -> None:
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.unbind_all(sequence)

    def _on_wheel(self, event) -> None:
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")

    def clear(self) -> None:
        for child in self.inner.winfo_children():
            child.destroy()


class Tooltip:
    """Minimal hover tooltip — used to explain each analytic."""

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.window = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _event=None) -> None:
        if self.window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        tk.Label(self.window, text=self.text, justify="left", relief="solid",
                 borderwidth=1, background="#ffffe0", padx=6, pady=3,
                 wraplength=320).pack()

    def _hide(self, _event=None) -> None:
        if self.window is not None:
            self.window.destroy()
            self.window = None


class ParamDialog(tk.Toplevel):
    """Modal editor for one analytic's parameters."""

    def __init__(self, master, definition: AnalyticDef, values: Dict[str, object]):
        super().__init__(master)
        self.title(f"{definition.label} - settings")
        self.definition = definition
        self.result: Dict[str, object] | None = None
        self._vars: Dict[str, object] = {}
        self.transient(master)
        self.resizable(False, False)

        ttk.Label(self, text=definition.description, wraplength=420,
                  padding=(12, 10, 12, 6)).grid(row=0, column=0, columnspan=3, sticky="w")

        row = 1
        for param in definition.params:
            row = self._build_param(param, values.get(param.key, param.default), row)

        buttons = ttk.Frame(self, padding=(12, 10))
        buttons.grid(row=row, column=0, columnspan=3, sticky="e")
        ttk.Button(buttons, text="Restore defaults",
                   command=self._restore_defaults).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=4)
        ttk.Button(buttons, text="OK", command=self._on_ok).pack(side="left")

        self.bind("<Return>", lambda _e: self._on_ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _build_param(self, param: ParamDef, value, row: int) -> int:
        ttk.Label(self, text=param.label + ":", padding=(12, 4)).grid(
            row=row, column=0, sticky="nw")

        if param.type == INT:
            var = tk.StringVar(value=str(value))
            ttk.Spinbox(self, from_=param.minimum, to=param.maximum, width=10,
                        textvariable=var).grid(row=row, column=1, sticky="w", pady=2)
        elif param.type == TIME:
            var = tk.StringVar(value=str(value))
            ttk.Entry(self, width=10, textvariable=var).grid(
                row=row, column=1, sticky="w", pady=2)
        elif param.type == BOOL:
            var = tk.BooleanVar(value=bool(value))
            ttk.Checkbutton(self, variable=var).grid(row=row, column=1, sticky="w", pady=2)
        elif param.type == CHOICE:
            var = tk.StringVar(value=str(value))
            ttk.Combobox(self, textvariable=var, values=param.options or [],
                         state="readonly", width=16).grid(row=row, column=1,
                                                          sticky="w", pady=2)
        elif param.type == MULTICHOICE:
            selected = set(value or [])
            box = ttk.Frame(self)
            box.grid(row=row, column=1, sticky="w", pady=2)
            var = {}
            for index, option in enumerate(param.options or []):
                item = tk.BooleanVar(value=option in selected)
                var[option] = item
                ttk.Checkbutton(box, text=option.replace("_", " "), variable=item).grid(
                    row=index // 3, column=index % 3, sticky="w", padx=(0, 10))
        else:                                   # TEXT
            var = tk.StringVar(value=str(value))
            ttk.Entry(self, width=28, textvariable=var).grid(
                row=row, column=1, sticky="w", pady=2)

        self._vars[param.key] = var
        if param.unit:
            ttk.Label(self, text=param.unit, padding=(4, 4)).grid(
                row=row, column=2, sticky="w")
        return row + 1

    def _restore_defaults(self) -> None:
        for param in self.definition.params:
            var = self._vars[param.key]
            if param.type == MULTICHOICE:
                for option, item in var.items():
                    item.set(option in (param.default or []))
            elif param.type == BOOL:
                var.set(bool(param.default))
            else:
                var.set(str(param.default))

    def _on_ok(self) -> None:
        values: Dict[str, object] = {}
        for param in self.definition.params:
            var = self._vars[param.key]
            if param.type == INT:
                try:
                    number = int(str(var.get()).strip())
                except ValueError:
                    messagebox.showerror("Invalid value",
                                         f"'{param.label}' must be a whole number.",
                                         parent=self)
                    return
                if not param.minimum <= number <= param.maximum:
                    messagebox.showerror(
                        "Out of range",
                        f"'{param.label}' must be between {param.minimum} "
                        f"and {param.maximum}.", parent=self)
                    return
                values[param.key] = number
            elif param.type == TIME:
                text = str(var.get()).strip()
                if not TIME_RE.match(text):
                    messagebox.showerror("Invalid time",
                                         f"'{param.label}' must be HH:MM (24-hour).",
                                         parent=self)
                    return
                values[param.key] = text
            elif param.type == BOOL:
                values[param.key] = bool(var.get())
            elif param.type == MULTICHOICE:
                values[param.key] = [opt for opt, item in var.items() if item.get()]
            else:
                values[param.key] = str(var.get()).strip()
        self.result = values
        self.destroy()


class CopyToDialog(tk.Toplevel):
    """Pick the cameras that should receive another camera's analytics setup."""

    def __init__(self, master, source: Camera, cameras: List[Camera]):
        super().__init__(master)
        self.title("Copy analytics to cameras")
        self.result: List[str] | None = None
        self.transient(master)
        self._vars: Dict[str, tk.BooleanVar] = {}

        ttk.Label(self, padding=(12, 10),
                  text=f"Copy every analytic setting from "
                       f"{source.display_name()} to:").pack(anchor="w")

        holder = ScrollableFrame(self)
        holder.pack(fill="both", expand=True, padx=12)
        for camera in cameras:
            if camera.camera_id == source.camera_id:
                continue
            var = tk.BooleanVar(value=False)
            self._vars[camera.camera_id] = var
            ttk.Checkbutton(holder.inner, text=camera.display_name(),
                            variable=var).pack(anchor="w")

        buttons = ttk.Frame(self, padding=12)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Select all",
                   command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(buttons, text="Clear",
                   command=lambda: self._set_all(False)).pack(side="left", padx=6)
        ttk.Button(buttons, text="Copy", command=self._on_ok).pack(side="right")
        ttk.Button(buttons, text="Cancel",
                   command=self.destroy).pack(side="right", padx=6)

        self.geometry("360x420")
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _set_all(self, value: bool) -> None:
        for var in self._vars.values():
            var.set(value)

    def _on_ok(self) -> None:
        self.result = [cid for cid, var in self._vars.items() if var.get()]
        self.destroy()


# ------------------------------------------------------------------- app
class App(tk.Tk):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config_data = config
        self.dirty = False
        self._loading = False                  # suppresses write-back while binding
        self.selected_id: str | None = None
        self.analytic_vars: Dict[str, tk.BooleanVar] = {}
        self.matrix_vars: Dict[str, Dict[str, tk.BooleanVar]] = {}

        self.title(APP_TITLE)
        self.geometry("1180x720")
        self.minsize(940, 560)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_menu()
        self._build_body()
        self._build_statusbar()
        self.refresh_camera_list(select=self.config_data.cameras[0].camera_id
                                 if self.config_data.cameras else None)
        self._bind_shortcuts()

    # -- construction ----------------------------------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New configuration", command=self.on_new)
        file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=self.on_open)
        file_menu.add_separator()
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.on_save)
        file_menu.add_command(label="Save as...", command=self.on_save_as)
        file_menu.add_command(label="Export matrix to CSV...", command=self.on_export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        camera_menu = tk.Menu(menubar, tearoff=0)
        camera_menu.add_command(label="Add camera", accelerator="Ctrl+N",
                                command=self.on_add_camera)
        camera_menu.add_command(label="Duplicate camera", command=self.on_duplicate_camera)
        camera_menu.add_command(label="Rename camera ID...", command=self.on_rename_id)
        camera_menu.add_command(label="Delete camera", accelerator="Del",
                                command=self.on_delete_camera)
        menubar.add_cascade(label="Camera", menu=camera_menu)

        bulk_menu = tk.Menu(menubar, tearoff=0)
        bulk_menu.add_command(label="Enable all analytics on selected camera",
                              command=lambda: self.set_all_for_selected(True))
        bulk_menu.add_command(label="Disable all analytics on selected camera",
                              command=lambda: self.set_all_for_selected(False))
        bulk_menu.add_separator()
        bulk_menu.add_command(label="Enable all analytics on ALL cameras",
                              command=lambda: self.set_all_everywhere(True))
        bulk_menu.add_command(label="Disable all analytics on ALL cameras",
                              command=lambda: self.set_all_everywhere(False))
        bulk_menu.add_separator()
        bulk_menu.add_command(label="Copy analytics from selected camera to...",
                              command=self.on_copy_to)
        menubar.add_cascade(label="Bulk actions", menu=bulk_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Analytics reference", command=self.on_reference)
        help_menu.add_command(label="About", command=self.on_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menubar)

    def _build_body(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        cameras_tab = ttk.Frame(self.notebook)
        matrix_tab = ttk.Frame(self.notebook)
        self.notebook.add(cameras_tab, text="  Cameras  ")
        self.notebook.add(matrix_tab, text="  Matrix view  ")
        self.notebook.bind("<<NotebookTabChanged>>", lambda _e: self.rebuild_matrix())

        self._build_cameras_tab(cameras_tab)
        self.matrix_holder = ScrollableFrame(matrix_tab)
        self.matrix_holder.pack(fill="both", expand=True)

    def _build_cameras_tab(self, parent: ttk.Frame) -> None:
        panes = ttk.PanedWindow(parent, orient="horizontal")
        panes.pack(fill="both", expand=True)

        # ---- left: camera list
        left = ttk.Frame(panes, padding=(0, 4, 6, 0))
        panes.add(left, weight=1)

        search_row = ttk.Frame(left)
        search_row.pack(fill="x", pady=(0, 4))
        ttk.Label(search_row, text="Filter:").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self.refresh_camera_list(
            select=self.selected_id))
        ttk.Entry(search_row, textvariable=self.filter_var).pack(
            side="left", fill="x", expand=True, padx=4)

        columns = ("name", "location", "active")
        self.tree = ttk.Treeview(left, columns=columns, show="tree headings",
                                 selectmode="browse")
        self.tree.heading("#0", text="Camera ID")
        self.tree.heading("name", text="Name")
        self.tree.heading("location", text="Location")
        self.tree.heading("active", text="Analytics on")
        self.tree.column("#0", width=100, minwidth=80)
        self.tree.column("name", width=130, minwidth=80)
        self.tree.column("location", width=110, minwidth=70)
        self.tree.column("active", width=90, minwidth=70, anchor="center")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select_camera)

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=6)
        ttk.Button(buttons, text="Add camera", command=self.on_add_camera).pack(side="left")
        ttk.Button(buttons, text="Duplicate",
                   command=self.on_duplicate_camera).pack(side="left", padx=4)
        ttk.Button(buttons, text="Delete",
                   command=self.on_delete_camera).pack(side="left")

        # ---- right: camera detail + analytics
        right = ttk.Frame(panes, padding=(6, 4, 0, 0))
        panes.add(right, weight=2)

        details = ttk.LabelFrame(right, text="Camera details", padding=8)
        details.pack(fill="x")
        self.var_id = tk.StringVar()
        self.var_name = tk.StringVar()
        self.var_location = tk.StringVar()
        self.var_url = tk.StringVar()
        self.var_camera_enabled = tk.BooleanVar(value=True)

        ttk.Label(details, text="Camera ID:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(details, textvariable=self.var_id,
                  font=("TkDefaultFont", 10, "bold")).grid(row=0, column=1, sticky="w")
        ttk.Button(details, text="Rename...", width=10,
                   command=self.on_rename_id).grid(row=0, column=2, sticky="w", padx=6)

        for row, (label, var) in enumerate(
                (("Name:", self.var_name), ("Location:", self.var_location),
                 ("Stream URL:", self.var_url)), start=1):
            ttk.Label(details, text=label).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(details, textvariable=var)
            entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
            var.trace_add("write", lambda *_: self.on_detail_changed())
        details.columnconfigure(1, weight=1)

        ttk.Checkbutton(details, text="Camera active (analytics run on this camera)",
                        variable=self.var_camera_enabled,
                        command=self.on_camera_enabled_toggled).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

        analytics_frame = ttk.LabelFrame(right, text="Analytics for this camera", padding=8)
        analytics_frame.pack(fill="both", expand=True, pady=(8, 0))

        toolbar = ttk.Frame(analytics_frame)
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Button(toolbar, text="Enable all",
                   command=lambda: self.set_all_for_selected(True)).pack(side="left")
        ttk.Button(toolbar, text="Disable all",
                   command=lambda: self.set_all_for_selected(False)).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Copy to other cameras...",
                   command=self.on_copy_to).pack(side="left")

        holder = ScrollableFrame(analytics_frame)
        holder.pack(fill="both", expand=True)
        for index, definition in enumerate(ANALYTICS):
            var = tk.BooleanVar(value=False)
            self.analytic_vars[definition.key] = var
            row = ttk.Frame(holder.inner)
            row.grid(row=index, column=0, sticky="ew", pady=1)
            check = ttk.Checkbutton(
                row, text=definition.label, variable=var, width=30,
                command=lambda key=definition.key: self.on_toggle_analytic(key))
            check.pack(side="left")
            Tooltip(check, definition.description)
            ttk.Button(row, text="Settings...", width=12,
                       command=lambda key=definition.key: self.on_edit_params(key)
                       ).pack(side="left", padx=6)
            ttk.Label(row, text=definition.description, foreground="#555",
                      wraplength=380).pack(side="left", fill="x", expand=True)

    def _build_statusbar(self) -> None:
        self.status_var = tk.StringVar(value="Ready")
        bar = ttk.Frame(self)
        bar.pack(fill="x", side="bottom")
        ttk.Separator(bar, orient="horizontal").pack(fill="x")
        ttk.Label(bar, textvariable=self.status_var, anchor="w",
                  padding=(8, 3)).pack(fill="x")

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-s>", lambda _e: self.on_save())
        self.bind("<Control-o>", lambda _e: self.on_open())
        self.bind("<Control-n>", lambda _e: self.on_add_camera())
        self.bind("<Delete>", lambda _e: self.on_delete_camera())

    # -- state -----------------------------------------------------------
    def mark_dirty(self, dirty: bool = True) -> None:
        self.dirty = dirty
        path = self.config_data.path or "(unsaved)"
        self.title(f"{APP_TITLE} - {os.path.basename(path)}{'*' if dirty else ''}")

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def selected_camera(self) -> Camera | None:
        return self.config_data.get(self.selected_id) if self.selected_id else None

    def visible_cameras(self) -> List[Camera]:
        needle = self.filter_var.get().strip().lower()
        if not needle:
            return list(self.config_data.cameras)
        return [c for c in self.config_data.cameras
                if needle in c.camera_id.lower() or needle in c.name.lower()
                or needle in c.location.lower()]

    # -- camera list -----------------------------------------------------
    def refresh_camera_list(self, select: str | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        for camera in self.visible_cameras():
            self.tree.insert(
                "", "end", iid=camera.camera_id, text=camera.camera_id,
                values=(camera.name, camera.location,
                        f"{camera.enabled_count()}/{len(ANALYTIC_KEYS)}"),
                tags=() if camera.enabled else ("inactive",))
        self.tree.tag_configure("inactive", foreground="#999")

        children = self.tree.get_children()
        target = select if select in children else (children[0] if children else None)
        if target:
            self.tree.selection_set(target)
            self.tree.see(target)
        else:
            self.selected_id = None
            self.load_camera_into_form(None)
        self.set_status(f"{len(self.config_data.cameras)} camera(s) configured")

    def on_select_camera(self, _event=None) -> None:
        selection = self.tree.selection()
        self.selected_id = selection[0] if selection else None
        self.load_camera_into_form(self.selected_camera())

    def load_camera_into_form(self, camera: Camera | None) -> None:
        self._loading = True
        try:
            self.var_id.set(camera.camera_id if camera else "")
            self.var_name.set(camera.name if camera else "")
            self.var_location.set(camera.location if camera else "")
            self.var_url.set(camera.stream_url if camera else "")
            self.var_camera_enabled.set(bool(camera.enabled) if camera else False)
            for key, var in self.analytic_vars.items():
                var.set(camera.is_enabled(key) if camera else False)
        finally:
            self._loading = False

    def update_tree_row(self, camera: Camera) -> None:
        if self.tree.exists(camera.camera_id):
            self.tree.item(camera.camera_id, text=camera.camera_id,
                           values=(camera.name, camera.location,
                                   f"{camera.enabled_count()}/{len(ANALYTIC_KEYS)}"),
                           tags=() if camera.enabled else ("inactive",))

    # -- edits -----------------------------------------------------------
    def on_detail_changed(self) -> None:
        camera = self.selected_camera()
        if self._loading or camera is None:
            return
        camera.name = self.var_name.get()
        camera.location = self.var_location.get()
        camera.stream_url = self.var_url.get()
        self.update_tree_row(camera)
        self.mark_dirty()

    def on_camera_enabled_toggled(self) -> None:
        camera = self.selected_camera()
        if self._loading or camera is None:
            return
        camera.enabled = bool(self.var_camera_enabled.get())
        self.update_tree_row(camera)
        self.mark_dirty()
        state = "active" if camera.enabled else "inactive"
        self.set_status(f"{camera.display_name()} marked {state}")

    def on_toggle_analytic(self, key: str) -> None:
        camera = self.selected_camera()
        if self._loading or camera is None:
            return
        enabled = bool(self.analytic_vars[key].get())
        camera.set_enabled(key, enabled)
        self.update_tree_row(camera)
        if camera.camera_id in self.matrix_vars:
            self.matrix_vars[camera.camera_id][key].set(enabled)
        self.mark_dirty()
        self.set_status(f"{ANALYTICS_BY_KEY[key].label} "
                        f"{'enabled' if enabled else 'disabled'} on "
                        f"{camera.display_name()}")

    def on_edit_params(self, key: str) -> None:
        camera = self.selected_camera()
        if camera is None:
            return
        definition = ANALYTICS_BY_KEY[key]
        state = camera.analytics[key]
        dialog = ParamDialog(self, definition, state.params)
        self.wait_window(dialog)
        if dialog.result is not None:
            state.params = dialog.result
            self.mark_dirty()
            self.set_status(f"Settings updated for {definition.label} on "
                            f"{camera.display_name()}")

    def set_all_for_selected(self, enabled: bool) -> None:
        camera = self.selected_camera()
        if camera is None:
            return
        camera.set_all(enabled)
        self.load_camera_into_form(camera)
        self.update_tree_row(camera)
        self.rebuild_matrix()
        self.mark_dirty()
        self.set_status(f"All analytics {'enabled' if enabled else 'disabled'} on "
                        f"{camera.display_name()}")

    def set_all_everywhere(self, enabled: bool) -> None:
        if not self.confirm(f"{'Enable' if enabled else 'Disable'} every analytic on "
                            f"all {len(self.config_data.cameras)} cameras?"):
            return
        self.config_data.set_all(enabled)
        self.refresh_all()
        self.mark_dirty()
        self.set_status(f"All analytics {'enabled' if enabled else 'disabled'} "
                        f"on every camera")

    def on_copy_to(self) -> None:
        camera = self.selected_camera()
        if camera is None:
            return
        dialog = CopyToDialog(self, camera, self.config_data.cameras)
        self.wait_window(dialog)
        if not dialog.result:
            return
        changed = self.config_data.copy_analytics(camera.camera_id, dialog.result)
        self.refresh_all()
        self.mark_dirty()
        self.set_status(f"Analytics copied to {changed} camera(s)")

    # -- camera CRUD -----------------------------------------------------
    def on_add_camera(self) -> None:
        camera_id = simpledialog.askstring(
            "Add camera", "Camera ID:", parent=self,
            initialvalue=self.config_data.next_camera_id())
        if not camera_id:
            return
        try:
            camera = self.config_data.add(Camera(camera_id=camera_id.strip()))
        except ConfigError as exc:
            messagebox.showerror("Cannot add camera", str(exc), parent=self)
            return
        self.filter_var.set("")
        self.refresh_camera_list(select=camera.camera_id)
        self.rebuild_matrix()
        self.mark_dirty()
        self.set_status(f"Camera {camera.camera_id} added")

    def on_duplicate_camera(self) -> None:
        camera = self.selected_camera()
        if camera is None:
            return
        copy = self.config_data.duplicate(camera.camera_id)
        self.filter_var.set("")
        self.refresh_camera_list(select=copy.camera_id)
        self.rebuild_matrix()
        self.mark_dirty()
        self.set_status(f"Camera duplicated as {copy.camera_id}")

    def on_rename_id(self) -> None:
        camera = self.selected_camera()
        if camera is None:
            return
        new_id = simpledialog.askstring("Rename camera ID", "New camera ID:",
                                        parent=self, initialvalue=camera.camera_id)
        if not new_id or new_id.strip() == camera.camera_id:
            return
        try:
            self.config_data.rename_id(camera.camera_id, new_id)
        except ConfigError as exc:
            messagebox.showerror("Cannot rename", str(exc), parent=self)
            return
        self.refresh_camera_list(select=camera.camera_id)
        self.rebuild_matrix()
        self.mark_dirty()

    def on_delete_camera(self) -> None:
        camera = self.selected_camera()
        if camera is None:
            return
        if not self.confirm(f"Delete camera {camera.display_name()}?"):
            return
        self.config_data.remove(camera.camera_id)
        self.refresh_camera_list()
        self.rebuild_matrix()
        self.mark_dirty()
        self.set_status(f"Camera {camera.camera_id} deleted")

    # -- matrix ----------------------------------------------------------
    def rebuild_matrix(self) -> None:
        if not hasattr(self, "matrix_holder"):
            return
        self.matrix_holder.clear()
        self.matrix_vars = {}
        grid = self.matrix_holder.inner

        ttk.Label(grid, text="Camera", font=("TkDefaultFont", 9, "bold"),
                  padding=(6, 6)).grid(row=0, column=0, sticky="w")
        for column, key in enumerate(ANALYTIC_KEYS, start=1):
            definition = ANALYTICS_BY_KEY[key]
            header = ttk.Button(
                grid, text=definition.short, width=11,
                command=lambda k=key: self.toggle_column(k))
            header.grid(row=0, column=column, padx=1, pady=2)
            Tooltip(header, f"{definition.description}\n\n"
                            f"Click to switch this analytic on/off for every camera.")

        for row, camera in enumerate(self.config_data.cameras, start=1):
            label = ttk.Button(grid, text=camera.display_name(), width=26,
                               command=lambda cid=camera.camera_id: self.toggle_row(cid))
            label.grid(row=row, column=0, sticky="w", padx=(4, 8), pady=1)
            Tooltip(label, "Click to switch every analytic on/off for this camera.")
            self.matrix_vars[camera.camera_id] = {}
            for column, key in enumerate(ANALYTIC_KEYS, start=1):
                var = tk.BooleanVar(value=camera.is_enabled(key))
                self.matrix_vars[camera.camera_id][key] = var
                ttk.Checkbutton(
                    grid, variable=var,
                    command=lambda cid=camera.camera_id, k=key:
                    self.on_matrix_toggle(cid, k)).grid(row=row, column=column)

        if not self.config_data.cameras:
            ttk.Label(grid, text="No cameras configured yet - add one on the "
                                 "Cameras tab.", padding=12).grid(row=1, column=0,
                                                                  columnspan=6, sticky="w")

    def on_matrix_toggle(self, camera_id: str, key: str) -> None:
        camera = self.config_data.get(camera_id)
        if camera is None:
            return
        enabled = bool(self.matrix_vars[camera_id][key].get())
        camera.set_enabled(key, enabled)
        self.update_tree_row(camera)
        if camera_id == self.selected_id:
            self.analytic_vars[key].set(enabled)
        self.mark_dirty()
        self.set_status(f"{ANALYTICS_BY_KEY[key].label} "
                        f"{'enabled' if enabled else 'disabled'} on "
                        f"{camera.display_name()}")

    def toggle_column(self, key: str) -> None:
        turn_on = not all(c.is_enabled(key) for c in self.config_data.cameras)
        self.config_data.set_analytic_for_all(key, turn_on)
        self.refresh_all()
        self.mark_dirty()
        self.set_status(f"{ANALYTICS_BY_KEY[key].label} "
                        f"{'enabled' if turn_on else 'disabled'} on every camera")

    def toggle_row(self, camera_id: str) -> None:
        camera = self.config_data.get(camera_id)
        if camera is None:
            return
        turn_on = camera.enabled_count() < len(ANALYTIC_KEYS)
        camera.set_all(turn_on)
        self.refresh_all()
        self.mark_dirty()
        self.set_status(f"All analytics {'enabled' if turn_on else 'disabled'} on "
                        f"{camera.display_name()}")

    def refresh_all(self) -> None:
        self.refresh_camera_list(select=self.selected_id)
        self.load_camera_into_form(self.selected_camera())
        self.rebuild_matrix()

    # -- file actions ----------------------------------------------------
    def confirm(self, question: str) -> bool:
        return messagebox.askyesno(APP_TITLE, question, parent=self)

    def maybe_save_changes(self) -> bool:
        """Returns False when the user cancels the pending action."""
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel(
            APP_TITLE, "Save changes to the current configuration?", parent=self)
        if answer is None:
            return False
        if answer:
            return self.on_save()
        return True

    def on_new(self) -> None:
        if not self.maybe_save_changes():
            return
        self.config_data = AppConfig(cameras=[], path="")
        self.selected_id = None
        self.refresh_all()
        self.mark_dirty(False)
        self.set_status("New empty configuration")

    def on_open(self) -> None:
        if not self.maybe_save_changes():
            return
        path = filedialog.askopenfilename(
            title="Open configuration", parent=self,
            filetypes=[("Configuration", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.config_data = AppConfig.load(path)
        except ConfigError as exc:
            messagebox.showerror("Cannot open file", str(exc), parent=self)
            return
        self.selected_id = None
        self.refresh_all()
        self.mark_dirty(False)
        self.set_status(f"Loaded {path}")

    def on_save(self) -> bool:
        if not self.config_data.path:
            return self.on_save_as()
        try:
            path = self.config_data.save()
        except OSError as exc:
            messagebox.showerror("Cannot save", str(exc), parent=self)
            return False
        self.mark_dirty(False)
        self.set_status(f"Saved to {path}")
        return True

    def on_save_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            title="Save configuration", parent=self, defaultextension=".json",
            initialfile=os.path.basename(self.config_data.path or "cameras.json"),
            filetypes=[("Configuration", "*.json"), ("All files", "*.*")])
        if not path:
            return False
        try:
            self.config_data.save(path)
        except OSError as exc:
            messagebox.showerror("Cannot save", str(exc), parent=self)
            return False
        self.mark_dirty(False)
        self.set_status(f"Saved to {path}")
        return True

    def on_export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export matrix", parent=self, defaultextension=".csv",
            initialfile="analytics_matrix.csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.config_data.export_csv(path)
        except OSError as exc:
            messagebox.showerror("Cannot export", str(exc), parent=self)
            return
        self.set_status(f"Matrix exported to {path}")

    def on_reference(self) -> None:
        lines = [f"- {d.label}\n    {d.description}" for d in ANALYTICS]
        messagebox.showinfo("Analytics reference", "\n".join(lines), parent=self)

    def on_about(self) -> None:
        messagebox.showinfo(
            "About",
            f"{APP_TITLE}\n\n"
            "Enable or disable each analytic separately for every camera, "
            "tune its parameters, and save the result as a JSON configuration "
            "your video pipeline can read.\n\n"
            f"Configuration file:\n{self.config_data.path or default_config_path()}",
            parent=self)

    def on_close(self) -> None:
        if self.maybe_save_changes():
            self.destroy()
