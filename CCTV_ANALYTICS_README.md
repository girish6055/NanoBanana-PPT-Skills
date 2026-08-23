# CCTV Analytics Manager

A Windows desktop application for turning each video analytic **on or off
separately for every camera**, tuning its parameters, and saving the result as a
JSON file your video pipeline / VMS can read.

## Analytics covered

| # | Analytic | Key in the config file | Tunable settings |
|---|----------|------------------------|------------------|
| 1 | People Counting | `people_counting` | direction, counter reset interval, confidence |
| 2 | Vehicle Counting | `vehicle_counting` | vehicle types, reset interval, confidence |
| 3 | Canteen Timing | `canteen_timing` | allowed window, max dwell, early-entry alert |
| 4 | Restricted Area | `restricted_area` | zone name, active hours, dwell before alert |
| 5 | Security Post | `security_post` | absence threshold, shift start/end |
| 6 | Gathering (more than 2) | `gathering_more_than_2` | person threshold, sustained duration, grouping distance |
| 7 | Mobile Usage | `mobile_usage` | minimum usage duration, confidence |
| 8 | Machine Idle | `machine_idle` | idle threshold, machine ID, ignore breaks |
| 9 | PPE Violation | `ppe_violation` | required PPE items, grace period, confidence |
| 10 | Door Access (more than 2) | `door_access_more_than_2` | person threshold, time window, door ID |

## Building the .exe

The app is pure Python + tkinter, so the executable has **no runtime
dependencies** — one file, no installer, no Python needed on the target PC.

### Option A — build it on a Windows PC

1. Install Python 3.9+ from <https://python.org> (tick *Add python.exe to PATH*).
2. Double-click **`build_exe.bat`**.
3. Collect the result: **`dist\CCTVAnalyticsManager.exe`**

### Option B — let GitHub build it (no Windows PC needed)

The workflow `.github/workflows/build-cctv-exe.yml` builds the exe on a Windows
runner on every push to this branch, and can also be started by hand:

1. GitHub → **Actions** → *Build CCTV Analytics Manager (Windows exe)* → **Run workflow**.
2. When it finishes, download the **`CCTVAnalyticsManager-windows-exe`** artifact.

> PyInstaller does not cross-compile: a Windows `.exe` can only be produced on
> Windows. `build_exe.sh` builds the equivalent native binary on Linux/macOS.

## Using the app

**Cameras tab** — the camera list on the left, the selected camera's details and
its ten analytics on the right. Tick a box to enable that analytic on that
camera only; `Settings...` opens its parameters. `Enable all` / `Disable all`
act on the selected camera; `Copy to other cameras...` pushes the whole setup
onto any cameras you pick.

**Matrix view tab** — every camera as a row, every analytic as a column. Tick any
cell to toggle one analytic on one camera; click a column header to toggle that
analytic across all cameras, or a row label to toggle every analytic on one camera.

**Saving** — `Ctrl+S`, or *File → Save as...*. The default configuration lives in
`%APPDATA%\CCTVAnalyticsManager\cameras.json`. *File → Export matrix to CSV...*
writes an ON/OFF sheet for reporting or hand-off.

Cameras can also be marked inactive as a whole (the *Camera active* checkbox),
which greys the row out and tells the pipeline to skip that camera entirely.

## Command line

The same executable also runs headless, which is handy for scripting and for
checking a deployment:

```
CCTVAnalyticsManager.exe --list                  # print the camera/analytics matrix
CCTVAnalyticsManager.exe --export-csv out.csv    # write the matrix as CSV
CCTVAnalyticsManager.exe --config site-a.json    # open a specific configuration
CCTVAnalyticsManager.exe --selftest              # verify the config engine
```

## Configuration format

```jsonc
{
  "version": 1,
  "cameras": [
    {
      "camera_id": "CAM-02",
      "name": "Canteen",
      "location": "Block B",
      "stream_url": "rtsp://192.168.1.11:554/stream1",
      "enabled": true,
      "analytics": {
        "canteen_timing": {
          "enabled": true,
          "params": {
            "window_start": "12:30",
            "window_end": "13:30",
            "max_dwell_min": 30,
            "alert_on_early_entry": true
          }
        }
        // ... the remaining nine analytics, each with "enabled" and "params"
      }
    }
  ]
}
```

Every camera always carries all ten analytics, so a consumer can read
`camera["analytics"][key]["enabled"]` without checking whether the key exists.
Configurations written by older builds are upgraded on load: new analytics and
new parameters are filled in with their defaults, and removed ones are dropped.

## Running from source

```bash
python cctv_analytics_app.py          # needs Python 3.9+ with tkinter
```

## Layout

```
cctv_analytics_app.py           entry point (also the PyInstaller target)
cctv_analytics/
    analytics_defs.py           the ten analytics and their parameter schemas
    config.py                   camera model, JSON persistence, CSV export
    gui.py                      tkinter UI (camera tab, matrix tab, dialogs)
    cli.py                      argument parsing, headless commands, self-test
CCTVAnalyticsManager.spec       PyInstaller build definition
build_exe.bat / build_exe.sh    one-command build
```
