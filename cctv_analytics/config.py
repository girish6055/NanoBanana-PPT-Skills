"""Camera / analytics configuration model and JSON persistence."""

from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List

from .analytics_defs import ANALYTICS, ANALYTICS_BY_KEY, ANALYTIC_KEYS

CONFIG_VERSION = 1
APP_NAME = "CCTVAnalyticsManager"


def default_config_dir() -> str:
    """Per-user config directory, following the platform convention."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config")
    return os.path.join(base, APP_NAME)


def default_config_path() -> str:
    return os.path.join(default_config_dir(), "cameras.json")


@dataclass
class AnalyticState:
    enabled: bool = False
    params: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"enabled": bool(self.enabled), "params": dict(self.params)}


@dataclass
class Camera:
    camera_id: str
    name: str = ""
    location: str = ""
    stream_url: str = ""
    enabled: bool = True
    analytics: Dict[str, AnalyticState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.ensure_analytics()

    def ensure_analytics(self) -> None:
        """Add any analytic missing from this camera, drop unknown ones.

        Keeps configs written by an older build usable after new analytics
        are added, and fills in parameters introduced later.
        """
        for definition in ANALYTICS:
            state = self.analytics.get(definition.key)
            if state is None:
                self.analytics[definition.key] = AnalyticState(
                    enabled=definition.default_enabled,
                    params=definition.default_params(),
                )
                continue
            defaults = definition.default_params()
            for key, value in defaults.items():
                state.params.setdefault(key, value)
            for key in list(state.params):
                if key not in defaults:
                    del state.params[key]
        for key in list(self.analytics):
            if key not in ANALYTICS_BY_KEY:
                del self.analytics[key]

    # -- convenience -----------------------------------------------------
    def is_enabled(self, analytic_key: str) -> bool:
        state = self.analytics.get(analytic_key)
        return bool(state and state.enabled)

    def set_enabled(self, analytic_key: str, enabled: bool) -> None:
        self.analytics[analytic_key].enabled = bool(enabled)

    def set_all(self, enabled: bool) -> None:
        for state in self.analytics.values():
            state.enabled = bool(enabled)

    def enabled_count(self) -> int:
        return sum(1 for s in self.analytics.values() if s.enabled)

    def display_name(self) -> str:
        return f"{self.camera_id} - {self.name}" if self.name else self.camera_id

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "location": self.location,
            "stream_url": self.stream_url,
            "enabled": bool(self.enabled),
            "analytics": {k: v.to_dict() for k, v in self.analytics.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Camera":
        analytics: Dict[str, AnalyticState] = {}
        for key, raw in (data.get("analytics") or {}).items():
            if isinstance(raw, bool):          # tolerate a plain on/off map
                analytics[key] = AnalyticState(enabled=raw, params={})
            else:
                analytics[key] = AnalyticState(
                    enabled=bool(raw.get("enabled", False)),
                    params=dict(raw.get("params") or {}),
                )
        return cls(
            camera_id=str(data.get("camera_id") or data.get("id") or "").strip(),
            name=str(data.get("name") or ""),
            location=str(data.get("location") or ""),
            stream_url=str(data.get("stream_url") or data.get("rtsp_url") or ""),
            enabled=bool(data.get("enabled", True)),
            analytics=analytics,
        )


class ConfigError(Exception):
    """Raised when a configuration file cannot be read or is malformed."""


@dataclass
class AppConfig:
    cameras: List[Camera] = field(default_factory=list)
    path: str = ""

    # -- camera management ----------------------------------------------
    def get(self, camera_id: str) -> Camera | None:
        for camera in self.cameras:
            if camera.camera_id == camera_id:
                return camera
        return None

    def has(self, camera_id: str) -> bool:
        return self.get(camera_id) is not None

    def next_camera_id(self) -> str:
        index = len(self.cameras) + 1
        while self.has(f"CAM-{index:02d}"):
            index += 1
        return f"CAM-{index:02d}"

    def add(self, camera: Camera) -> Camera:
        if not camera.camera_id:
            raise ConfigError("Camera ID cannot be empty.")
        if self.has(camera.camera_id):
            raise ConfigError(f"Camera ID '{camera.camera_id}' already exists.")
        self.cameras.append(camera)
        return camera

    def remove(self, camera_id: str) -> None:
        self.cameras = [c for c in self.cameras if c.camera_id != camera_id]

    def rename_id(self, old_id: str, new_id: str) -> None:
        new_id = new_id.strip()
        if not new_id:
            raise ConfigError("Camera ID cannot be empty.")
        if new_id != old_id and self.has(new_id):
            raise ConfigError(f"Camera ID '{new_id}' already exists.")
        camera = self.get(old_id)
        if camera is None:
            raise ConfigError(f"Unknown camera '{old_id}'.")
        camera.camera_id = new_id

    def duplicate(self, camera_id: str) -> Camera:
        source = self.get(camera_id)
        if source is None:
            raise ConfigError(f"Unknown camera '{camera_id}'.")
        copy = Camera.from_dict(source.to_dict())
        copy.camera_id = self.next_camera_id()
        copy.name = f"{source.name} (copy)" if source.name else copy.camera_id
        self.cameras.append(copy)
        return copy

    def copy_analytics(self, source_id: str, target_ids: List[str]) -> int:
        """Copy one camera's analytics setup onto other cameras."""
        source = self.get(source_id)
        if source is None:
            raise ConfigError(f"Unknown camera '{source_id}'.")
        payload = {k: v.to_dict() for k, v in source.analytics.items()}
        changed = 0
        for target_id in target_ids:
            target = self.get(target_id)
            if target is None or target is source:
                continue
            target.analytics = {
                k: AnalyticState(enabled=v["enabled"], params=dict(v["params"]))
                for k, v in payload.items()
            }
            target.ensure_analytics()
            changed += 1
        return changed

    def set_all(self, enabled: bool) -> None:
        for camera in self.cameras:
            camera.set_all(enabled)

    def set_analytic_for_all(self, analytic_key: str, enabled: bool) -> None:
        for camera in self.cameras:
            camera.set_enabled(analytic_key, enabled)

    # -- persistence -----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": CONFIG_VERSION,
            "cameras": [c.to_dict() for c in self.cameras],
        }

    def save(self, path: str | None = None) -> str:
        target = path or self.path or default_config_path()
        directory = os.path.dirname(os.path.abspath(target))
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=False)
        os.replace(tmp, target)     # atomic: never leave a half-written config
        self.path = target
        return target

    @classmethod
    def load(cls, path: str) -> "AppConfig":
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            raise ConfigError(f"File not found: {path}")
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Not a valid configuration file: {exc}")
        if not isinstance(data, dict) or "cameras" not in data:
            raise ConfigError("Configuration file has no 'cameras' section.")
        config = cls(path=path)
        for raw in data.get("cameras") or []:
            camera = Camera.from_dict(raw)
            if camera.camera_id and not config.has(camera.camera_id):
                config.cameras.append(camera)
        return config

    @classmethod
    def load_or_default(cls, path: str | None = None) -> "AppConfig":
        target = path or default_config_path()
        if os.path.exists(target):
            try:
                return cls.load(target)
            except ConfigError:
                pass
        return cls(cameras=sample_cameras(), path=target)

    def export_csv(self, path: str) -> str:
        """Write the enable/disable matrix as CSV for reporting or hand-off."""
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Camera ID", "Name", "Location", "Camera enabled"] +
                            [ANALYTICS_BY_KEY[k].label for k in ANALYTIC_KEYS])
            for camera in self.cameras:
                writer.writerow(
                    [camera.camera_id, camera.name, camera.location,
                     "YES" if camera.enabled else "NO"] +
                    ["ON" if camera.is_enabled(k) else "OFF" for k in ANALYTIC_KEYS]
                )
        return path


def sample_cameras() -> List[Camera]:
    """Starter set shown the first time the app runs."""
    seeds = [
        ("CAM-01", "Main Gate", "Entrance",
         ["people_counting", "vehicle_counting", "restricted_area"]),
        ("CAM-02", "Canteen", "Block B",
         ["people_counting", "canteen_timing", "gathering_more_than_2"]),
        ("CAM-03", "Shop Floor", "Production",
         ["ppe_violation", "machine_idle", "mobile_usage"]),
        ("CAM-04", "Security Post", "Perimeter",
         ["security_post", "restricted_area"]),
        ("CAM-05", "Server Room Door", "Block A",
         ["door_access_more_than_2", "restricted_area"]),
    ]
    cameras: List[Camera] = []
    for camera_id, name, location, enabled_keys in seeds:
        camera = Camera(camera_id=camera_id, name=name, location=location,
                        stream_url=f"rtsp://192.168.1.{len(cameras) + 10}:554/stream1")
        camera.set_all(False)
        for key in enabled_keys:
            camera.set_enabled(key, True)
        cameras.append(camera)
    return cameras
