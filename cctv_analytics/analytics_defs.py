"""Definitions of the CCTV analytics that can be enabled per camera.

Each analytic carries a small parameter schema so the UI can render the right
editor widgets without hard-coding a form per analytic.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional

# Parameter types understood by the UI layer.
INT = "int"
TIME = "time"
BOOL = "bool"
CHOICE = "choice"
MULTICHOICE = "multichoice"
TEXT = "text"


@dataclass(frozen=True)
class ParamDef:
    key: str
    label: str
    type: str
    default: Any
    options: Optional[List[str]] = None
    minimum: int = 0
    maximum: int = 10_000
    unit: str = ""


@dataclass(frozen=True)
class AnalyticDef:
    key: str
    label: str
    short: str          # column header in the matrix view
    description: str
    default_enabled: bool = False
    params: List[ParamDef] = field(default_factory=list)

    def default_params(self) -> dict:
        return {p.key: (list(p.default) if isinstance(p.default, list) else p.default)
                for p in self.params}


ANALYTICS: List[AnalyticDef] = [
    AnalyticDef(
        key="people_counting",
        label="People Counting",
        short="People\nCount",
        description="Counts people crossing a virtual line or entering a zone.",
        default_enabled=True,
        params=[
            ParamDef("direction", "Count direction", CHOICE, "both",
                     options=["in", "out", "both"]),
            ParamDef("reset_interval_min", "Counter reset interval", INT, 60,
                     minimum=0, maximum=1440, unit="min"),
            ParamDef("min_confidence", "Minimum confidence", INT, 60,
                     minimum=1, maximum=100, unit="%"),
        ],
    ),
    AnalyticDef(
        key="vehicle_counting",
        label="Vehicle Counting",
        short="Vehicle\nCount",
        description="Counts vehicles crossing a line, split by vehicle class.",
        params=[
            ParamDef("vehicle_types", "Vehicle types", MULTICHOICE,
                     ["car", "truck", "bus", "two_wheeler"],
                     options=["car", "truck", "bus", "two_wheeler", "bicycle", "forklift"]),
            ParamDef("reset_interval_min", "Counter reset interval", INT, 60,
                     minimum=0, maximum=1440, unit="min"),
            ParamDef("min_confidence", "Minimum confidence", INT, 60,
                     minimum=1, maximum=100, unit="%"),
        ],
    ),
    AnalyticDef(
        key="canteen_timing",
        label="Canteen Timing",
        short="Canteen\nTiming",
        description="Flags canteen use outside the allowed window or beyond the "
                    "permitted dwell time.",
        params=[
            ParamDef("window_start", "Allowed from", TIME, "12:30"),
            ParamDef("window_end", "Allowed until", TIME, "13:30"),
            ParamDef("max_dwell_min", "Max dwell time", INT, 30,
                     minimum=1, maximum=480, unit="min"),
            ParamDef("alert_on_early_entry", "Alert on early entry", BOOL, True),
        ],
    ),
    AnalyticDef(
        key="restricted_area",
        label="Restricted Area",
        short="Restricted\nArea",
        description="Raises an alert when a person enters a restricted zone.",
        params=[
            ParamDef("zone_name", "Zone name", TEXT, "Zone-1"),
            ParamDef("active_from", "Active from", TIME, "00:00"),
            ParamDef("active_until", "Active until", TIME, "23:59"),
            ParamDef("dwell_seconds", "Minimum dwell before alert", INT, 3,
                     minimum=0, maximum=3600, unit="s"),
        ],
    ),
    AnalyticDef(
        key="security_post",
        label="Security Post",
        short="Security\nPost",
        description="Detects an unmanned security post — guard absent for longer "
                    "than the allowed period.",
        params=[
            ParamDef("absence_threshold_sec", "Absence threshold", INT, 120,
                     minimum=5, maximum=7200, unit="s"),
            ParamDef("shift_start", "Shift start", TIME, "00:00"),
            ParamDef("shift_end", "Shift end", TIME, "23:59"),
        ],
    ),
    AnalyticDef(
        key="gathering_more_than_2",
        label="Gathering (more than 2)",
        short="Gather\n>2",
        description="Alerts when more than two people gather together for longer "
                    "than the configured duration.",
        params=[
            ParamDef("person_threshold", "Alert above N people", INT, 2,
                     minimum=1, maximum=50, unit="people"),
            ParamDef("duration_sec", "Sustained for", INT, 30,
                     minimum=1, maximum=3600, unit="s"),
            ParamDef("proximity_m", "Grouping distance", INT, 2,
                     minimum=1, maximum=20, unit="m"),
        ],
    ),
    AnalyticDef(
        key="mobile_usage",
        label="Mobile Usage",
        short="Mobile\nUsage",
        description="Detects mobile phone usage in areas where it is not allowed.",
        params=[
            ParamDef("min_duration_sec", "Minimum usage duration", INT, 5,
                     minimum=1, maximum=600, unit="s"),
            ParamDef("min_confidence", "Minimum confidence", INT, 70,
                     minimum=1, maximum=100, unit="%"),
        ],
    ),
    AnalyticDef(
        key="machine_idle",
        label="Machine Idle",
        short="Machine\nIdle",
        description="Flags a machine or workstation left idle beyond the "
                    "allowed time.",
        params=[
            ParamDef("idle_threshold_min", "Idle threshold", INT, 10,
                     minimum=1, maximum=480, unit="min"),
            ParamDef("machine_id", "Machine / station ID", TEXT, ""),
            ParamDef("ignore_breaks", "Ignore scheduled breaks", BOOL, True),
        ],
    ),
    AnalyticDef(
        key="ppe_violation",
        label="PPE Violation",
        short="PPE\nViolation",
        description="Detects missing personal protective equipment.",
        params=[
            ParamDef("required_items", "Required PPE", MULTICHOICE,
                     ["helmet", "vest"],
                     options=["helmet", "vest", "gloves", "mask", "goggles", "boots"]),
            ParamDef("grace_period_sec", "Grace period before alert", INT, 5,
                     minimum=0, maximum=600, unit="s"),
            ParamDef("min_confidence", "Minimum confidence", INT, 70,
                     minimum=1, maximum=100, unit="%"),
        ],
    ),
    AnalyticDef(
        key="door_access_more_than_2",
        label="Door Access (more than 2)",
        short="Door\n>2",
        description="Detects tailgating — more than two people passing through a "
                    "door on a single access event.",
        params=[
            ParamDef("person_threshold", "Alert above N people", INT, 2,
                     minimum=1, maximum=20, unit="people"),
            ParamDef("window_sec", "Within time window", INT, 10,
                     minimum=1, maximum=300, unit="s"),
            ParamDef("door_id", "Door ID", TEXT, ""),
        ],
    ),
]

ANALYTICS_BY_KEY = {a.key: a for a in ANALYTICS}
ANALYTIC_KEYS = [a.key for a in ANALYTICS]
