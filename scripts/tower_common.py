#!/usr/bin/env python3
"""Shared helpers for tower scouting and device monitoring tools."""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any

INDIA_OPERATORS: dict[tuple[int, int], str] = {
    (404, 1): "Vi",
    (404, 2): "Airtel",
    (404, 3): "Airtel",
    (404, 4): "Vi",
    (404, 5): "Vi",
    (404, 7): "Vi",
    (404, 10): "Airtel",
    (404, 11): "Vi",
    (404, 12): "Vi",
    (404, 13): "Vi",
    (404, 14): "Spice",
    (404, 15): "Vi",
    (404, 16): "Airtel",
    (404, 20): "Vi",
    (404, 22): "Vi",
    (404, 24): "Vi",
    (404, 27): "Vi",
    (404, 30): "Vi",
    (404, 31): "Airtel",
    (404, 40): "Airtel",
    (404, 43): "Vi",
    (404, 45): "Airtel",
    (404, 46): "Vi",
    (404, 49): "Airtel",
    (404, 50): "Reliance",
    (404, 51): "BSNL",
    (404, 52): "Reliance",
    (404, 53): "BSNL",
    (404, 54): "BSNL",
    (404, 55): "BSNL",
    (404, 56): "Vi",
    (404, 57): "BSNL",
    (404, 58): "BSNL",
    (404, 59): "BSNL",
    (404, 60): "Vi",
    (404, 62): "BSNL",
    (404, 64): "BSNL",
    (404, 66): "BSNL",
    (404, 67): "Reliance",
    (404, 68): "MTNL",
    (404, 69): "MTNL",
    (404, 70): "Airtel",
    (404, 71): "BSNL",
    (404, 72): "BSNL",
    (404, 73): "BSNL",
    (404, 74): "BSNL",
    (404, 75): "BSNL",
    (404, 76): "BSNL",
    (404, 77): "BSNL",
    (404, 78): "Vi",
    (404, 79): "BSNL",
    (404, 80): "BSNL",
    (404, 81): "BSNL",
    (404, 82): "Vi",
    (404, 83): "Reliance",
    (404, 84): "Vi",
    (404, 85): "Reliance",
    (404, 86): "Vi",
    (404, 87): "Vi",
    (404, 88): "Vi",
    (404, 89): "Vi",
    (404, 90): "Airtel",
    (404, 91): "Aircel",
    (404, 92): "Airtel",
    (404, 93): "Airtel",
    (404, 94): "Airtel",
    (404, 95): "Airtel",
    (404, 96): "Airtel",
    (404, 97): "Airtel",
    (405, 52): "Jio",
    (405, 53): "Jio",
    (405, 54): "Jio",
    (405, 55): "Jio",
    (405, 56): "Jio",
    (405, 57): "Jio",
    (405, 58): "Jio",
    (405, 59): "Jio",
    (405, 60): "Jio",
    (405, 61): "Jio",
    (405, 62): "Jio",
    (405, 63): "Jio",
    (405, 64): "Jio",
    (405, 65): "Jio",
    (405, 66): "Jio",
    (405, 67): "Jio",
    (405, 68): "Jio",
    (405, 69): "Jio",
    (405, 70): "Jio",
    (405, 71): "Jio",
    (405, 72): "Jio",
    (405, 73): "Jio",
    (405, 74): "Jio",
    (405, 75): "Jio",
    (405, 76): "Jio",
    (405, 77): "Jio",
    (405, 78): "Jio",
    (405, 79): "Jio",
    (405, 80): "Jio",
    (405, 81): "Jio",
    (405, 82): "Jio",
    (405, 83): "Jio",
    (405, 84): "Jio",
    (405, 85): "Jio",
    (405, 86): "Jio",
    (405, 87): "Jio",
    (405, 88): "Jio",
}


@dataclass
class CellIdentity:
    mcc: int
    mnc: int
    lac: int
    cid: int
    radio: str = "LTE"
    operator: str = ""
    registered: bool = True

    def key(self) -> str:
        return f"{self.mcc}:{self.mnc}:{self.lac}:{self.cid}:{self.radio}"

    def short_label(self) -> str:
        op = self.operator or operator_name(self.mcc, self.mnc)
        return f"{op} {self.radio} {self.mcc}/{self.mnc} LAC={self.lac} CID={self.cid}"


@dataclass
class SignalMetrics:
    rsrp: int | None = None
    rsrq: int | None = None
    rssnr: int | None = None
    cqi: int | None = None
    gsm_signal: int | None = None
    service_state: int | None = None
    data_state: int | None = None
    neighbor_cells: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeviceCellReport:
    device_id: str
    model: str = ""
    android_version: str = ""
    serving: CellIdentity | None = None
    neighbors: list[CellIdentity] = field(default_factory=list)
    signal: SignalMetrics = field(default_factory=SignalMetrics)
    raw_error: str = ""


def operator_name(mcc: int | None, mnc: int | None) -> str:
    if mcc is None or mnc is None:
        return ""
    return INDIA_OPERATORS.get((mcc, mnc), f"MCC {mcc} / MNC {mnc}")


def run_adb(args: list[str], serial: str | None = None, timeout: int = 25) -> subprocess.CompletedProcess[str]:
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def list_adb_devices() -> list[str]:
    proc = run_adb(["devices"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "adb devices failed")
    devices: list[str] = []
    for line in proc.stdout.splitlines()[1:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def adb_shell(serial: str | None, command: str) -> str:
    proc = run_adb(["shell", command], serial=serial)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "adb shell failed")
    return proc.stdout


def parse_signal_strength(text: str) -> SignalMetrics:
    metrics = SignalMetrics()
    match = re.search(r"mSignalStrength=SignalStrength:\s*([^\n]+)", text)
    if not match:
        return metrics

    parts = match.group(1).strip().split()
    nums: list[int] = []
    for part in parts:
        if part.isdigit() or (part.startswith("-") and part[1:].isdigit()):
            nums.append(int(part))

    if len(nums) >= 10:
        metrics.gsm_signal = nums[0]
        metrics.cqi = nums[7] if nums[7] >= 0 else None
        metrics.rsrp = nums[8] if nums[8] not in (-1, 2147483647) else None
        metrics.rsrq = nums[9] if nums[9] not in (-1, 2147483647) else None
        if len(nums) >= 11:
            metrics.rssnr = nums[10] if nums[10] not in (-1, 2147483647) else None

    service = re.search(r"mServiceState=(\d+)", text)
    if service:
        metrics.service_state = int(service.group(1))
    data = re.search(r"mDataConnectionState=(\d+)", text)
    if data:
        metrics.data_state = int(data.group(1))
    return metrics


def parse_cell_blocks(text: str, registered_only: bool = False) -> list[CellIdentity]:
    cells: list[CellIdentity] = []
    patterns = [
        (r"mGsm\s*=\s*\[([^\]]+)\]", "GSM", "lac", "cid"),
        (r"mLte\s*=\s*\[([^\]]+)\]", "LTE", "tac", "ci"),
        (r"mNr\s*=\s*\[([^\]]+)\]", "NR", "tac", "nci"),
        (r"mWcdma\s*=\s*\[([^\]]+)\]", "WCDMA", "lac", "cid"),
    ]

    for pattern, radio, area_key, id_key in patterns:
        for match in re.finditer(pattern, text, re.DOTALL):
            block = match.group(1)
            mcc = _extract_int(block, "mcc")
            mnc = _extract_int(block, "mnc")
            area = _extract_int(block, area_key)
            cid = _extract_int(block, id_key)
            if None in (mcc, mnc, area, cid):
                continue
            registered = "mRegistered=YES" in block or "registered=YES" in block
            if registered_only and not registered:
                continue
            cells.append(
                CellIdentity(
                    mcc=mcc,
                    mnc=mnc,
                    lac=area,
                    cid=cid,
                    radio=radio,
                    operator=operator_name(mcc, mnc),
                    registered=registered,
                )
            )
    return cells


def _extract_int(block: str, key: str) -> int | None:
    match = re.search(rf"\b{re.escape(key)}=(\d+)\b", block)
    return int(match.group(1)) if match else None


def parse_telephony_dump(text: str) -> DeviceCellReport:
    cells = parse_cell_blocks(text)
    serving = next((c for c in cells if c.registered), cells[0] if cells else None)
    neighbors = [c for c in cells if serving and c.key() != serving.key()]
    signal = parse_signal_strength(text)
    signal.neighbor_cells = len(neighbors)
    return DeviceCellReport(device_id="local", serving=serving, neighbors=neighbors, signal=signal)


def read_device_report(serial: str) -> DeviceCellReport:
    try:
        telephony = adb_shell(serial, "dumpsys telephony.registry")
        model = adb_shell(serial, "getprop ro.product.model").strip()
        android = adb_shell(serial, "getprop ro.build.version.release").strip()
    except RuntimeError as exc:
        return DeviceCellReport(device_id=serial, raw_error=str(exc))

    report = parse_telephony_dump(telephony)
    report.device_id = serial
    report.model = model
    report.android_version = android
    return report


def parse_tower_spec(spec: str) -> CellIdentity:
    parts = spec.replace("/", ":").split(":")
    if len(parts) != 4:
        raise ValueError("Tower spec must be MCC:MNC:LAC:CID")
    mcc, mnc, lac, cid = (int(x) for x in parts)
    return CellIdentity(mcc=mcc, mnc=mnc, lac=lac, cid=cid)
