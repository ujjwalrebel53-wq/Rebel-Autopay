#!/usr/bin/env python3
"""
Tower Device Monitor — count devices on a specific cell tower and estimate load.

Important:
  Telecom operators do NOT expose exact UE counts publicly. This tool provides:
    1. Exact count among YOUR connected/reporting phones on a tower
    2. Estimated network load from RF metrics (RSRP/RSRQ/CQI)
    3. Multi-phone collector mode for distributed counting

Examples:
  python3 scripts/tower_device_monitor.py scan
  python3 scripts/tower_device_monitor.py tower --tower 404:45:13132:218145034
  python3 scripts/tower_device_monitor.py estimate
  python3 scripts/tower_device_monitor.py watch --tower 404:45:13132:218145034 --interval 5
  python3 scripts/tower_device_monitor.py collect --port 8787
  python3 scripts/tower_device_monitor.py report --url http://192.168.1.10:8787
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import request as urllib_request

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tower_common import (  # noqa: E402
    CellIdentity,
    DeviceCellReport,
    SignalMetrics,
    list_adb_devices,
    operator_name,
    parse_tower_spec,
    parse_telephony_dump,
    read_device_report,
    run_adb,
)


@dataclass
class LoadEstimate:
    load_percent: int
    device_range: str
    congestion: str
    confidence: str
    factors: list[str]


@dataclass
class TowerStats:
    tower: CellIdentity
    observed_devices: int
    device_ids: list[str]
    avg_rsrp: float | None
    avg_rsrq: float | None
    avg_cqi: float | None
    load: LoadEstimate | None


def estimate_tower_load(signal: SignalMetrics, observed_devices: int = 1) -> LoadEstimate:
    score = 20.0
    factors: list[str] = []

    if signal.cqi is not None and signal.cqi > 0:
        cqi_factor = max(0, 15 - signal.cqi) * 3.5
        score += cqi_factor
        factors.append(f"CQI={signal.cqi} (lower = heavier airtime contention)")
    if signal.rsrq is not None:
        if signal.rsrq <= -17:
            score += 22
            factors.append(f"RSRQ={signal.rsrq} dB (very poor — likely congested)")
        elif signal.rsrq <= -14:
            score += 12
            factors.append(f"RSRQ={signal.rsrq} dB (moderate congestion)")
        else:
            factors.append(f"RSRQ={signal.rsrq} dB (healthy)")
    if signal.rsrp is not None:
        if signal.rsrp <= -115:
            score += 10
            factors.append(f"RSRP={signal.rsrp} dBm (weak edge-of-cell signal)")
        elif signal.rsrp <= -105:
            score += 5
            factors.append(f"RSRP={signal.rsrp} dBm")
        else:
            factors.append(f"RSRP={signal.rsrp} dBm (strong)")
    if signal.rssnr is not None and signal.rssnr < 5:
        score += 8
        factors.append(f"RSSNR={signal.rssnr} dB (low SINR)")

    score += min(signal.neighbor_cells * 2.5, 15)
    if signal.neighbor_cells:
        factors.append(f"{signal.neighbor_cells} neighbor cell(s) visible")

    score += min(max(observed_devices - 1, 0) * 4, 20)

    load_percent = max(5, min(98, int(score)))
    if load_percent < 35:
        congestion = "Low"
        device_range = "15 – 60"
        confidence = "medium"
    elif load_percent < 60:
        congestion = "Medium"
        device_range = "60 – 180"
        confidence = "medium"
    elif load_percent < 80:
        congestion = "High"
        device_range = "180 – 350"
        confidence = "low"
    else:
        congestion = "Very High"
        device_range = "350 – 700+"
        confidence = "low"

    return LoadEstimate(
        load_percent=load_percent,
        device_range=device_range,
        congestion=congestion,
        confidence=confidence,
        factors=factors,
    )


def scan_connected_devices() -> list[DeviceCellReport]:
    devices = list_adb_devices()
    if not devices:
        raise SystemExit("No adb devices found. Enable USB debugging and connect phone(s).")
    return [read_device_report(serial) for serial in devices]


def group_by_tower(reports: list[DeviceCellReport]) -> dict[str, TowerStats]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"devices": [], "signals": []})

    for report in reports:
        if report.raw_error:
            continue
        if not report.serving:
            continue
        key = report.serving.key()
        grouped[key]["tower"] = report.serving
        grouped[key]["devices"].append(report.device_id)
        grouped[key]["signals"].append(report.signal)

    stats: dict[str, TowerStats] = {}
    for key, bucket in grouped.items():
        tower: CellIdentity = bucket["tower"]
        signals: list[SignalMetrics] = bucket["signals"]
        avg = lambda attr: _avg([getattr(s, attr) for s in signals if getattr(s, attr) is not None])
        merged = SignalMetrics(
            rsrp=_to_int(avg("rsrp")),
            rsrq=_to_int(avg("rsrq")),
            rssnr=_to_int(avg("rssnr")),
            cqi=_to_int(avg("cqi")),
            neighbor_cells=max((s.neighbor_cells for s in signals), default=0),
        )
        device_count = len(bucket["devices"])
        stats[key] = TowerStats(
            tower=tower,
            observed_devices=device_count,
            device_ids=bucket["devices"],
            avg_rsrp=avg("rsrp"),
            avg_rsrq=avg("rsrq"),
            avg_cqi=avg("cqi"),
            load=estimate_tower_load(merged, device_count),
        )
    return stats


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _to_int(value: float | None) -> int | None:
    return int(round(value)) if value is not None else None


def match_tower(report: DeviceCellReport, target: CellIdentity) -> bool:
    if not report.serving:
        return False
    serving = report.serving
    return (
        serving.mcc == target.mcc
        and serving.mnc == target.mnc
        and serving.lac == target.lac
        and serving.cid == target.cid
    )


def print_scan_report(stats: dict[str, TowerStats], reports: list[DeviceCellReport]) -> None:
    print()
    print("=" * 78)
    print("  TOWER DEVICE MONITOR — connected device scan")
    print("=" * 78)
    print(f"  Phones scanned : {len(reports)}")
    print(f"  Unique towers  : {len(stats)}")
    print("-" * 78)

    errors = [r for r in reports if r.raw_error]
    if errors:
        print("\n  Errors:")
        for report in errors:
            print(f"    • {report.device_id}: {report.raw_error}")

    if not stats:
        print("\n  Koi serving cell parse nahi hui. Phone par location permission do.")
        print("=" * 78)
        return

    for idx, tower_stats in enumerate(sorted(stats.values(), key=lambda s: s.observed_devices, reverse=True), 1):
        t = tower_stats.tower
        print(f"\n  [{idx}] {t.short_label()}")
        print(f"      Observed devices (exact) : {tower_stats.observed_devices}")
        print(f"      Device IDs               : {', '.join(tower_stats.device_ids)}")
        if tower_stats.avg_rsrp is not None:
            print(f"      Avg RSRP/RSRQ/CQI        : {tower_stats.avg_rsrp:.0f} / {tower_stats.avg_rsrq:.0f} / {tower_stats.avg_cqi:.0f}")
        if tower_stats.load:
            load = tower_stats.load
            print(f"      Est. network load        : {load.load_percent}% ({load.congestion})")
            print(f"      Est. total devices       : ~{load.device_range} (heuristic, not operator data)")

    print("\n" + "=" * 78)
    print("  Note: 'Observed devices' = sirf tumhare connected phones ka exact count.")
    print("        'Est. total devices' = RF metrics se approximate guess.")
    print("=" * 78)


def print_tower_report(target: CellIdentity, matched: list[DeviceCellReport], all_stats: dict[str, TowerStats]) -> None:
    key = target.key()
    stats = all_stats.get(key)
    print()
    print("=" * 78)
    print("  TOWER DEVICE MONITOR — specific tower")
    print("=" * 78)
    print(f"  Target tower : {target.short_label()}")
    print(f"  Tower key    : {target.mcc}:{target.mnc}:{target.lac}:{target.cid}")
    print("-" * 78)
    print(f"  Observed devices on this tower (exact) : {len(matched)}")

    if matched:
        print("\n  Connected phones:")
        for report in matched:
            label = report.model or report.device_id
            sig = report.signal
            print(f"    • {label} ({report.device_id})")
            if sig.rsrp is not None:
                print(f"        RSRP={sig.rsrp} RSRQ={sig.rsrq} CQI={sig.cqi}")
    else:
        print("\n  Is tower par koi connected phone nahi mila.")
        print("  Tip: tower ke paas phone le jao ya --watch mode use karo.")

    if stats and stats.load:
        load = stats.load
        print("\n  Network load estimate:")
        print(f"    Load %        : {load.load_percent}")
        print(f"    Congestion    : {load.congestion}")
        print(f"    Est. devices  : ~{load.device_range}")
        print(f"    Confidence    : {load.confidence}")
        print("    Factors:")
        for factor in load.factors:
            print(f"      - {factor}")

    print("\n" + "=" * 78)


def cmd_scan(args: argparse.Namespace) -> None:
    reports = scan_connected_devices()
    stats = group_by_tower(reports)
    if args.json:
        print(json.dumps({"reports": [serialize_report(r) for r in reports], "towers": [serialize_stats(s) for s in stats.values()]}, indent=2))
    else:
        print_scan_report(stats, reports)


def cmd_tower(args: argparse.Namespace) -> None:
    target = parse_tower_spec(args.tower)
    reports = scan_connected_devices()
    matched = [r for r in reports if match_tower(r, target)]
    stats = group_by_tower(reports)
    if args.json:
        payload = {
            "target": asdict(target),
            "observed_devices": len(matched),
            "matched": [serialize_report(r) for r in matched],
            "stats": serialize_stats(stats[target.key()]) if target.key() in stats else None,
        }
        print(json.dumps(payload, indent=2))
    else:
        print_tower_report(target, matched, stats)


def cmd_estimate(args: argparse.Namespace) -> None:
    serial = args.serial
    if not serial:
        devices = list_adb_devices()
        if not devices:
            raise SystemExit("No adb device connected.")
        serial = devices[0]
    samples: list[SignalMetrics] = []
    serving: CellIdentity | None = None
    for _ in range(args.samples):
        report = read_device_report(serial)
        if report.raw_error:
            raise SystemExit(report.raw_error)
        if report.serving:
            serving = report.serving
        samples.append(report.signal)
        if args.samples > 1 and args.interval > 0:
            time.sleep(args.interval)

    merged = SignalMetrics(
        rsrp=_to_int(_avg([s.rsrp for s in samples if s.rsrp is not None])),
        rsrq=_to_int(_avg([s.rsrq for s in samples if s.rsrq is not None])),
        rssnr=_to_int(_avg([s.rssnr for s in samples if s.rssnr is not None])),
        cqi=_to_int(_avg([s.cqi for s in samples if s.cqi is not None])),
        neighbor_cells=max((s.neighbor_cells for s in samples), default=0),
    )
    load = estimate_tower_load(merged, observed_devices=1)

    if args.json:
        print(json.dumps({"device": serial, "serving": asdict(serving) if serving else None, "signal": merged.to_dict(), "estimate": asdict(load)}, indent=2))
        return

    print()
    print("=" * 78)
    print("  TOWER LOAD ESTIMATOR")
    print("=" * 78)
    if serving:
        print(f"  Serving cell : {serving.short_label()}")
    print(f"  Samples      : {args.samples}")
    print(f"  RSRP/RSRQ/CQI: {merged.rsrp} / {merged.rsrq} / {merged.cqi}")
    print(f"  Est. load    : {load.load_percent}% ({load.congestion})")
    print(f"  Est. devices : ~{load.device_range} on this sector (approximate)")
    print(f"  Confidence   : {load.confidence}")
    print("=" * 78)


def cmd_watch(args: argparse.Namespace) -> None:
    target = parse_tower_spec(args.tower)
    print(f"Watching tower {target.short_label()} every {args.interval}s. Ctrl+C to stop.")
    try:
        while True:
            reports = scan_connected_devices()
            matched = [r for r in reports if match_tower(r, target)]
            stats = group_by_tower(reports).get(target.key())
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            load_pct = stats.load.load_percent if stats and stats.load else "?"
            print(f"[{ts}] observed={len(matched)} load~{load_pct}% devices={', '.join(r.device_id for r in matched) or '-'}")
            if args.json:
                print(json.dumps({"time": ts, "observed": len(matched), "stats": serialize_stats(stats) if stats else None}))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


COLLECTOR_STATE: dict[str, dict[str, Any]] = {"devices": {}, "towers": {}}


class CollectorHandler(BaseHTTPRequestHandler):
    server_version = "TowerDeviceMonitor/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"ok": True, "devices": len(COLLECTOR_STATE["devices"])})
            return
        if self.path == "/towers":
            self._send_json(200, {"towers": list(COLLECTOR_STATE["towers"].values())})
            return
        parts = self.path.strip("/").split("/")
        if len(parts) == 5 and parts[0] == "tower":
            key = ":".join(parts[1:])
            tower = COLLECTOR_STATE["towers"].get(key)
            if not tower:
                self._send_json(404, {"error": "tower not found"})
                return
            self._send_json(200, tower)
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/report":
            self._send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
            return

        device_id = str(payload.get("device_id", "unknown"))
        mcc = int(payload["mcc"])
        mnc = int(payload["mnc"])
        lac = int(payload["lac"])
        cid = int(payload["cid"])
        radio = str(payload.get("radio", "LTE"))
        tower = CellIdentity(mcc=mcc, mnc=mnc, lac=lac, cid=cid, radio=radio, operator=operator_name(mcc, mnc))
        signal = SignalMetrics(
            rsrp=payload.get("rsrp"),
            rsrq=payload.get("rsrq"),
            rssnr=payload.get("rssnr"),
            cqi=payload.get("cqi"),
            neighbor_cells=int(payload.get("neighbor_cells", 0)),
        )

        COLLECTOR_STATE["devices"][device_id] = {
            "device_id": device_id,
            "model": payload.get("model", ""),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "tower_key": tower.key(),
        }

        key = tower.key()
        bucket = COLLECTOR_STATE["towers"].setdefault(
            key,
            {
                "tower": asdict(tower),
                "tower_key": key,
                "observed_devices": 0,
                "device_ids": [],
                "last_updated": None,
            },
        )
        bucket["device_ids"] = sorted(
            {d["device_id"] for d in COLLECTOR_STATE["devices"].values() if d.get("tower_key") == key}
        )
        bucket["observed_devices"] = len(bucket["device_ids"])
        bucket["last_updated"] = datetime.now(timezone.utc).isoformat()
        bucket["estimate"] = asdict(estimate_tower_load(signal, bucket["observed_devices"]))
        self._send_json(200, {"ok": True, "tower": bucket})


def cmd_collect(args: argparse.Namespace) -> None:
    server = ThreadingHTTPServer((args.host, args.port), CollectorHandler)
    print(f"Collector running on http://{args.host}:{args.port}")
    print("Endpoints:")
    print(f"  POST /report   — phones send cell info")
    print(f"  GET  /towers   — all tower counts")
    print(f"  GET  /tower/MCC/MNC/LAC/CID")
    print(f"  GET  /health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCollector stopped.")


def cmd_report(args: argparse.Namespace) -> None:
    if args.adb:
        devices = list_adb_devices()
        if not devices:
            raise SystemExit("No adb device for report.")
        report = read_device_report(devices[0])
    else:
        try:
            proc = subprocess.run(
                ["dumpsys", "telephony.registry"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except FileNotFoundError:
            proc = run_adb(["shell", "dumpsys", "telephony.registry"])
        if proc.returncode != 0:
            raise SystemExit("Run on Android (Termux) or use --adb from PC.")
        report = parse_telephony_dump(proc.stdout)
        report.device_id = args.device_id

    if report.raw_error or not report.serving:
        raise SystemExit(report.raw_error or "Serving cell not found")

    payload = {
        "device_id": args.device_id,
        "model": report.model,
        "mcc": report.serving.mcc,
        "mnc": report.serving.mnc,
        "lac": report.serving.lac,
        "cid": report.serving.cid,
        "radio": report.serving.radio,
        "rsrp": report.signal.rsrp,
        "rsrq": report.signal.rsrq,
        "rssnr": report.signal.rssnr,
        "cqi": report.signal.cqi,
        "neighbor_cells": report.signal.neighbor_cells,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return

    body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        args.url.rstrip("/") + "/report",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=15) as resp:
        print(resp.read().decode("utf-8"))


def serialize_report(report: DeviceCellReport) -> dict[str, Any]:
    return {
        "device_id": report.device_id,
        "model": report.model,
        "android_version": report.android_version,
        "serving": asdict(report.serving) if report.serving else None,
        "neighbors": [asdict(n) for n in report.neighbors],
        "signal": report.signal.to_dict(),
        "error": report.raw_error,
    }


def serialize_stats(stats: TowerStats | None) -> dict[str, Any] | None:
    if not stats:
        return None
    return {
        "tower": asdict(stats.tower),
        "observed_devices": stats.observed_devices,
        "device_ids": stats.device_ids,
        "avg_rsrp": stats.avg_rsrp,
        "avg_rsrq": stats.avg_rsrq,
        "avg_cqi": stats.avg_cqi,
        "load": asdict(stats.load) if stats.load else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor how many devices use a specific cell tower.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Scan all adb phones and group by tower")
    scan.set_defaults(func=cmd_scan)

    tower = sub.add_parser("tower", help="Check a specific tower (MCC:MNC:LAC:CID)")
    tower.add_argument("--tower", required=True, help="Tower spec, e.g. 404:45:13132:218145034")
    tower.set_defaults(func=cmd_tower)

    estimate = sub.add_parser("estimate", help="Estimate load from one phone's RF metrics")
    estimate.add_argument("--serial", help="adb serial")
    estimate.add_argument("--samples", type=int, default=3, help="Signal samples (default: 3)")
    estimate.add_argument("--interval", type=float, default=1.5, help="Seconds between samples")
    estimate.set_defaults(func=cmd_estimate)

    watch = sub.add_parser("watch", help="Continuously monitor a specific tower")
    watch.add_argument("--tower", required=True, help="Tower spec, e.g. 404:45:13132:218145034")
    watch.add_argument("--interval", type=float, default=5.0, help="Poll interval seconds")
    watch.set_defaults(func=cmd_watch)

    collect = sub.add_parser("collect", help="Start HTTP collector for multiple phones")
    collect.add_argument("--host", default="0.0.0.0")
    collect.add_argument("--port", type=int, default=8787)
    collect.set_defaults(func=cmd_collect)

    report = sub.add_parser("report", help="Send this phone's cell info to collector")
    report.add_argument("--url", default="http://127.0.0.1:8787", help="Collector base URL")
    report.add_argument("--device-id", default="phone-1", help="Unique device label")
    report.add_argument("--adb", action="store_true", help="Read phone via adb from PC")
    report.set_defaults(func=cmd_report)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
