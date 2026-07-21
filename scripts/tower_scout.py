#!/usr/bin/env python3
"""
Tower Scout — fetch cell towers and communication masts near your location.

Data sources:
  1. OpenStreetMap (Overpass) — physical telecom towers, no API key needed
  2. OpenCelliD — cell IDs (MCC/MNC/LAC/CID) when OPENCELLID_API_KEY is set

Examples:
  python3 scripts/tower_scout.py
  python3 scripts/tower_scout.py --place "Connaught Place, Delhi"
  python3 scripts/tower_scout.py --lat 28.6139 --lon 77.2090 --radius 3
  python3 scripts/tower_scout.py --json > towers.json
  python3 scripts/tower_scout.py --adb
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any

USER_AGENT = "TowerScout/1.0 (SkillX; contact: skillx_community)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OPENCELLID_AREA_URL = "https://opencellid.org/cell/getInArea"
IP_API_URL = "http://ip-api.com/json/?fields=status,message,lat,lon,city,regionName,country"

# Common India MCC/MNC → operator labels (404 / 405)
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
    (405, 890): "Jio",
    (405, 891): "Jio",
    (405, 892): "Jio",
    (405, 893): "Jio",
    (405, 894): "Jio",
    (405, 895): "Jio",
    (405, 896): "Jio",
    (405, 897): "Jio",
    (405, 898): "Jio",
    (405, 899): "Jio",
    (405, 900): "Jio",
    (405, 901): "Jio",
    (405, 902): "Jio",
    (405, 903): "Jio",
    (405, 904): "Jio",
    (405, 905): "Jio",
    (405, 906): "Jio",
    (405, 907): "Jio",
    (405, 908): "Jio",
    (405, 909): "Jio",
    (405, 910): "Jio",
    (405, 911): "Jio",
    (405, 912): "Jio",
    (405, 913): "Jio",
    (405, 914): "Jio",
    (405, 915): "Jio",
    (405, 916): "Jio",
    (405, 917): "Jio",
    (405, 918): "Jio",
    (405, 919): "Jio",
    (405, 920): "Jio",
    (405, 921): "Jio",
    (405, 922): "Jio",
    (405, 923): "Jio",
    (405, 924): "Jio",
    (405, 925): "Jio",
    (405, 926): "Jio",
    (405, 927): "Jio",
    (405, 928): "Jio",
    (405, 929): "Jio",
    (405, 930): "Jio",
    (405, 931): "Jio",
    (405, 932): "Jio",
}


@dataclass
class Location:
    lat: float
    lon: float
    label: str = ""


@dataclass
class TowerRecord:
    source: str
    kind: str
    lat: float
    lon: float
    distance_km: float
    name: str = ""
    operator: str = ""
    radio: str = ""
    mcc: int | None = None
    mnc: int | None = None
    lac: int | None = None
    cid: int | None = None
    height_m: float | None = None
    tags: dict[str, str] = field(default_factory=dict)


def http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_post(url: str, data: str, timeout: int = 60) -> bytes:
    payload = data.encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bbox_for_radius(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    lat_delta = radius_km / 111.0
    cos_lat = max(math.cos(math.radians(lat)), 0.01)
    lon_delta = radius_km / (111.0 * cos_lat)
    return lat - lat_delta, lon - lon_delta, lat + lat_delta, lon + lon_delta


def operator_name(mcc: int | None, mnc: int | None) -> str:
    if mcc is None or mnc is None:
        return ""
    return INDIA_OPERATORS.get((mcc, mnc), f"MCC {mcc} / MNC {mnc}")


def resolve_location(args: argparse.Namespace) -> Location:
    if args.lat is not None and args.lon is not None:
        return Location(args.lat, args.lon, f"{args.lat:.5f}, {args.lon:.5f}")

    if args.place:
        params = urllib.parse.urlencode({"q": args.place, "format": "json", "limit": 1})
        data = json.loads(http_get(f"{NOMINATIM_URL}?{params}"))
        if not data:
            raise SystemExit(f"Place not found: {args.place}")
        hit = data[0]
        return Location(float(hit["lat"]), float(hit["lon"]), hit.get("display_name", args.place))

    ip_data = json.loads(http_get(IP_API_URL))
    if ip_data.get("status") != "success":
        raise SystemExit(f"IP geolocation failed: {ip_data.get('message', 'unknown error')}")
    label = ", ".join(x for x in [ip_data.get("city"), ip_data.get("regionName"), ip_data.get("country")] if x)
    return Location(float(ip_data["lat"]), float(ip_data["lon"]), label or "IP location")


TELECOM_TOWER_TYPES = {
    "communication",
    "mast",
    "mobile",
    "radio",
    "broadcast",
    "observation",
}


def is_telecom_tower(tags: dict[str, str]) -> bool:
    tower_type = tags.get("tower:type", "")
    if tower_type in {"cooling", "defensive", "minaret", "bell_tower", "watchtower"}:
        return False
    if tower_type in TELECOM_TOWER_TYPES:
        return True
    if tags.get("communication:mobile_phone") == "yes":
        return True
    if any(key.startswith("telecom") or key.startswith("communication:") for key in tags):
        return True
    if tags.get("man_made") == "mast":
        return True
    if tags.get("man_made") == "tower" and tower_type in {"", "tower"}:
        return tags.get("operator") or tags.get("brand") or tags.get("mast:type") == "mobile"
    return False


def fetch_osm_towers(location: Location, radius_km: float) -> list[TowerRecord]:
    radius_m = int(radius_km * 1000)
    query = f"""
    [out:json][timeout:60];
    (
      node(around:{radius_m},{location.lat},{location.lon})["tower:type"="communication"];
      way(around:{radius_m},{location.lat},{location.lon})["tower:type"="communication"];
      node(around:{radius_m},{location.lat},{location.lon})["tower:type"="mast"];
      way(around:{radius_m},{location.lat},{location.lon})["tower:type"="mast"];
      node(around:{radius_m},{location.lat},{location.lon})["man_made"="mast"];
      way(around:{radius_m},{location.lat},{location.lon})["man_made"="mast"];
      node(around:{radius_m},{location.lat},{location.lon})["communication:mobile_phone"="yes"];
      way(around:{radius_m},{location.lat},{location.lon})["communication:mobile_phone"="yes"];
      node(around:{radius_m},{location.lat},{location.lon})["telecom"];
      way(around:{radius_m},{location.lat},{location.lon})["telecom"];
    );
    out center tags;
    """
    try:
        raw = http_post(OVERPASS_URL, f"data={urllib.parse.quote(query)}")
    except urllib.error.URLError as exc:
        print(f"[!] OpenStreetMap query failed: {exc}", file=sys.stderr)
        return []

    payload = json.loads(raw)
    towers: list[TowerRecord] = []
    for element in payload.get("elements", []):
        tags = {str(k): str(v) for k, v in element.get("tags", {}).items()}
        if not is_telecom_tower(tags):
            continue
        if element["type"] == "node":
            lat, lon = element["lat"], element["lon"]
        else:
            center = element.get("center")
            if not center:
                continue
            lat, lon = center["lat"], center["lon"]

        tower_type = tags.get("tower:type", tags.get("man_made", "tower"))
        operator = tags.get("operator", tags.get("brand", tags.get("owner", "")))
        height = tags.get("height")
        height_m = None
        if height:
            match = re.search(r"([\d.]+)", height.replace(",", "."))
            if match:
                height_m = float(match.group(1))

        towers.append(
            TowerRecord(
                source="OpenStreetMap",
                kind=tower_type,
                lat=lat,
                lon=lon,
                distance_km=haversine_km(location.lat, location.lon, lat, lon),
                name=tags.get("name", ""),
                operator=operator,
                height_m=height_m,
                tags=tags,
            )
        )
    return towers


def fetch_opencellid_towers(location: Location, radius_km: float, api_key: str) -> list[TowerRecord]:
    min_lat, min_lon, max_lat, max_lon = bbox_for_radius(location.lat, location.lon, radius_km)
    params = urllib.parse.urlencode(
        {
            "key": api_key,
            "BBOX": f"{min_lat},{min_lon},{max_lat},{max_lon}",
            "format": "json",
            "limit": 50,
        }
    )
    try:
        raw = http_get(f"{OPENCELLID_AREA_URL}?{params}")
    except urllib.error.URLError as exc:
        print(f"[!] OpenCelliD query failed: {exc}", file=sys.stderr)
        return []

    payload = json.loads(raw)
    if isinstance(payload, dict) and payload.get("error"):
        print(f"[!] OpenCelliD error: {payload.get('error')}", file=sys.stderr)
        return []

    cells = payload.get("cells", payload if isinstance(payload, list) else [])
    towers: list[TowerRecord] = []
    for cell in cells:
        lat = float(cell.get("lat", 0))
        lon = float(cell.get("lon", 0))
        if not lat and not lon:
            continue
        mcc = int(cell["mcc"]) if cell.get("mcc") is not None else None
        mnc = int(cell["mnc"]) if cell.get("mnc") is not None else None
        towers.append(
            TowerRecord(
                source="OpenCelliD",
                kind="cell",
                lat=lat,
                lon=lon,
                distance_km=haversine_km(location.lat, location.lon, lat, lon),
                operator=operator_name(mcc, mnc),
                radio=str(cell.get("radio", "")),
                mcc=mcc,
                mnc=mnc,
                lac=int(cell["lac"]) if cell.get("lac") is not None else None,
                cid=int(cell.get("cellid", cell.get("cid", 0)) or 0) or None,
                tags={k: str(v) for k, v in cell.items() if k not in {"lat", "lon"}},
            )
        )
    return towers


def fetch_adb_cell_info() -> list[TowerRecord]:
    try:
        proc = subprocess.run(
            ["adb", "shell", "dumpsys", "telephony.registry"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except FileNotFoundError:
        raise SystemExit("adb not found. Install Android platform-tools and connect your phone.")

    if proc.returncode != 0:
        raise SystemExit(f"adb failed: {proc.stderr.strip() or proc.stdout.strip()}")

    text = proc.stdout
    records: list[TowerRecord] = []

    patterns = [
        (
            r"mGsm\s*=\s*\[.*?\bmcc=(\d+)\b.*?\bmnc=(\d+)\b.*?\blac=(\d+)\b.*?\bcid=(\d+)\b",
            "GSM",
        ),
        (
            r"mLte\s*=\s*\[.*?\bmcc=(\d+)\b.*?\bmnc=(\d+)\b.*?\btac=(\d+)\b.*?\bci=(\d+)\b",
            "LTE",
        ),
        (
            r"mNr\s*=\s*\[.*?\bmcc=(\d+)\b.*?\bmnc=(\d+)\b.*?\btac=(\d+)\b.*?\bnci=(\d+)\b",
            "NR",
        ),
    ]

    for pattern, radio in patterns:
        for match in re.finditer(pattern, text, re.DOTALL):
            mcc, mnc, lac, cid = (int(x) for x in match.groups())
            records.append(
                TowerRecord(
                    source="ADB (connected phone)",
                    kind="serving_cell",
                    lat=0.0,
                    lon=0.0,
                    distance_km=0.0,
                    operator=operator_name(mcc, mnc),
                    radio=radio,
                    mcc=mcc,
                    mnc=mnc,
                    lac=lac,
                    cid=cid,
                )
            )

    if not records:
        print("[!] No serving cell parsed from adb output. Grant phone permissions and retry.", file=sys.stderr)
    return records


def dedupe_towers(towers: list[TowerRecord]) -> list[TowerRecord]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[TowerRecord] = []
    for tower in towers:
        if tower.source == "OpenCelliD":
            key = ("cell", tower.mcc, tower.mnc, tower.lac, tower.cid, tower.radio)
        elif tower.source.startswith("ADB"):
            key = ("adb", tower.mcc, tower.mnc, tower.lac, tower.cid, tower.radio)
        else:
            key = ("osm", round(tower.lat, 5), round(tower.lon, 5), tower.name, tower.kind)
        if key in seen:
            continue
        seen.add(key)
        unique.append(tower)
    unique.sort(key=lambda t: t.distance_km)
    return unique


def print_report(location: Location, radius_km: float, towers: list[TowerRecord]) -> None:
    print()
    print("=" * 72)
    print("  TOWER SCOUT — surrounding tower intel")
    print("=" * 72)
    print(f"  Location : {location.label}")
    print(f"  Coords   : {location.lat:.6f}, {location.lon:.6f}")
    print(f"  Radius   : {radius_km:g} km")
    print(f"  Found    : {len(towers)} tower(s)")
    print("-" * 72)

    if not towers:
        print("  Koi tower nahi mila. Radius badhao ya OpenCelliD API key set karo.")
        print("=" * 72)
        return

    for idx, tower in enumerate(towers, start=1):
        print(f"\n  [{idx}] {tower.source} · {tower.kind}")
        if tower.name:
            print(f"      Name     : {tower.name}")
        if tower.operator:
            print(f"      Operator : {tower.operator}")
        if tower.radio:
            print(f"      Radio    : {tower.radio}")
        if tower.mcc is not None:
            print(f"      MCC/MNC  : {tower.mcc}/{tower.mnc}")
        if tower.lac is not None:
            print(f"      LAC/TAC  : {tower.lac}")
        if tower.cid is not None:
            print(f"      Cell ID  : {tower.cid}")
        if tower.height_m is not None:
            print(f"      Height   : {tower.height_m:g} m")
        if tower.lat or tower.lon:
            print(f"      Lat/Lon  : {tower.lat:.6f}, {tower.lon:.6f}")
            print(f"      Distance : {tower.distance_km:.2f} km")
        if tower.tags and tower.source == "OpenStreetMap":
            interesting = {k: v for k, v in tower.tags.items() if k in {"tower:type", "material", "ref", "note"}}
            if interesting:
                print(f"      Tags     : {interesting}")

    print("\n" + "=" * 72)
    maps_url = f"https://www.openstreetmap.org/?mlat={location.lat}&mlon={location.lon}#map=14/{location.lat}/{location.lon}"
    print(f"  Map view : {maps_url}")
    print("=" * 72)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch surrounding telecom tower information near a location.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Tips:\n"
            "  • No args → uses your public IP for approximate location\n"
            "  • Set OPENCELLID_API_KEY for cell tower IDs (MCC/MNC/LAC/CID)\n"
            "  • --adb reads the serving cell from a USB-connected Android phone\n"
        ),
    )
    parser.add_argument("--lat", type=float, help="Latitude")
    parser.add_argument("--lon", type=float, help="Longitude")
    parser.add_argument("--place", help='Place name, e.g. "Andheri West, Mumbai"')
    parser.add_argument("--radius", type=float, default=5.0, help="Search radius in km (default: 5)")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")
    parser.add_argument("--adb", action="store_true", help="Read serving cell via adb (ignores location search)")
    parser.add_argument("--opencellid-key", default=os.environ.get("OPENCELLID_API_KEY", ""), help="OpenCelliD API key")
    parser.add_argument("--no-osm", action="store_true", help="Skip OpenStreetMap tower lookup")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.adb:
        towers = fetch_adb_cell_info()
        location = Location(0.0, 0.0, "Connected Android device")
        if args.json:
            print(json.dumps({"location": asdict(location), "towers": [asdict(t) for t in towers]}, indent=2))
        else:
            print_report(location, 0, towers)
        return

    if (args.lat is None) ^ (args.lon is None):
        raise SystemExit("Both --lat and --lon are required together.")

    location = resolve_location(args)
    towers: list[TowerRecord] = []

    if not args.no_osm:
        towers.extend(fetch_osm_towers(location, args.radius))

    if args.opencellid_key:
        towers.extend(fetch_opencellid_towers(location, args.radius, args.opencellid_key))
    elif not args.no_osm:
        print("[i] Tip: set OPENCELLID_API_KEY for cell IDs (MCC/MNC/LAC/CID).", file=sys.stderr)

    towers = dedupe_towers(towers)

    if args.json:
        payload = {
            "location": asdict(location),
            "radius_km": args.radius,
            "count": len(towers),
            "towers": [asdict(t) for t in towers],
        }
        print(json.dumps(payload, indent=2))
    else:
        print_report(location, args.radius, towers)


if __name__ == "__main__":
    main()
