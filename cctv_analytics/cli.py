"""Entry point: launches the desktop UI, or runs headless helper commands."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from . import __version__
from .analytics_defs import ANALYTICS, ANALYTIC_KEYS
from .config import AppConfig, ConfigError, default_config_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="CCTVAnalyticsManager",
        description="Enable or disable CCTV analytics separately for each camera.")
    parser.add_argument("--config", metavar="PATH", default=None,
                        help=f"configuration file to open "
                             f"(default: {default_config_path()})")
    parser.add_argument("--list", action="store_true",
                        help="print the camera/analytics matrix and exit")
    parser.add_argument("--export-csv", metavar="PATH", default=None,
                        help="write the matrix to a CSV file and exit")
    parser.add_argument("--selftest", action="store_true",
                        help="verify the configuration engine and exit "
                             "(no window is opened)")
    parser.add_argument("--version", action="version",
                        version=f"CCTV Analytics Manager {__version__}")
    return parser


def print_matrix(config: AppConfig) -> None:
    if not config.cameras:
        print("No cameras configured.")
        return
    width = max(len(c.display_name()) for c in config.cameras) + 2
    print(f"Configuration: {config.path or '(none)'}")
    print(f"{'CAMERA'.ljust(width)}ENABLED ANALYTICS")
    for camera in config.cameras:
        enabled = [k for k in ANALYTIC_KEYS if camera.is_enabled(k)]
        flag = "" if camera.enabled else "  [camera inactive]"
        print(f"{camera.display_name().ljust(width)}"
              f"{', '.join(enabled) if enabled else '-'}{flag}")


def run_selftest() -> int:
    """Exercise the model layer end to end — useful on a machine with no display."""
    import json
    import tempfile

    from .config import Camera, sample_cameras

    config = AppConfig(cameras=sample_cameras())
    assert len(ANALYTICS) == 10, "expected 10 analytics"
    for camera in config.cameras:
        assert len(camera.analytics) == 10

    with tempfile.TemporaryDirectory() as folder:
        path = config.save(os.path.join(folder, "cameras.json"))
        reloaded = AppConfig.load(path)
        assert reloaded.to_dict() == config.to_dict(), "save/load round-trip failed"

        camera = reloaded.cameras[0]
        camera.set_enabled("ppe_violation", True)
        assert camera.is_enabled("ppe_violation")
        camera.set_all(False)
        assert camera.enabled_count() == 0

        reloaded.copy_analytics("CAM-03", ["CAM-01"])
        assert reloaded.get("CAM-01").is_enabled("machine_idle")

        duplicate = reloaded.duplicate("CAM-01")
        assert duplicate.camera_id not in {"CAM-01"}
        try:
            reloaded.add(Camera(camera_id="CAM-01"))
        except ConfigError:
            pass
        else:                                   # pragma: no cover - guard regression
            raise AssertionError("duplicate camera ID was accepted")

        csv_path = reloaded.export_csv(os.path.join(folder, "matrix.csv"))
        assert os.path.getsize(csv_path) > 0

        legacy = {"version": 1, "cameras": [
            {"id": "OLD-1", "analytics": {"people_counting": True, "removed": True}}]}
        legacy_path = os.path.join(folder, "legacy.json")
        with open(legacy_path, "w", encoding="utf-8") as handle:
            json.dump(legacy, handle)
        old = AppConfig.load(legacy_path).cameras[0]
        assert old.is_enabled("people_counting") and len(old.analytics) == 10

    print("Self-test passed: 10 analytics, per-camera toggles, save/load, "
          "copy, CSV export and legacy-config upgrade all OK.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.selftest:
        return run_selftest()

    try:
        config = (AppConfig.load(args.config) if args.config
                  else AppConfig.load_or_default())
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.export_csv:
        config.export_csv(args.export_csv)
        print(f"Matrix written to {args.export_csv}")
        return 0

    if args.list:
        print_matrix(config)
        return 0

    try:
        from .gui import App
    except ImportError:                          # tkinter missing (rare on Windows)
        print("error: this build has no graphical toolkit available (tkinter). "
              "Use --list or --export-csv for headless output.", file=sys.stderr)
        return 3

    app = App(config)
    app.mark_dirty(False)
    app.mainloop()
    return 0
