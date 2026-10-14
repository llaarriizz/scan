#!/usr/bin/env python3
"""Find the IPv4 address of a phone on the current local network.

Usage:
    python3 scan_phone.py                       # print phone candidates
    python3 scan_phone.py --all                 # print every host found
    python3 scan_phone.py -n 192.168.1.0/24     # custom subnet
    python3 scan_phone.py --mac AA:BB:CC:DD:EE:FF   # find a specific device
    python3 scan_phone.py --name poco           # match a name substring
    python3 scan_phone.py --mac AA:BB:... --watch 10  # keep watching

Tip: Android phones rarely broadcast their name, so find your phone's Wi-Fi
MAC under Settings > About > Status on the phone, then use --mac.
"""

import argparse
import ipaddress
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# OUI prefixes (first 3 bytes of MAC) commonly used by phones / tablets.
PHONE_OUIS = {
    "00:1B:63": "Apple",
    "00:1E:C2": "Apple",
    "00:23:DF": "Apple",
    "00:25:00": "Apple",
    "00:26:BB": "Apple",
    "3C:07:54": "Apple",
    "40:6C:8F": "Apple",
    "5C:95:AE": "Apple",
    "64:B9:E8": "Apple",
    "70:DE:E2": "Apple",
    "8C:29:37": "Apple",
    "90:B0:ED": "Apple",
    "A4:83:E7": "Apple",
    "AC:BC:32": "Apple",
    "B8:8D:12": "Apple",
    "D0:23:DB": "Apple",
    "DC:2B:2A": "Apple",
    "F0:18:98": "Apple",
    "F0:DB:E2": "Apple",
    "00:12:FB": "Samsung",
    "00:15:99": "Samsung",
    "00:16:32": "Samsung",
    "00:1A:8A": "Samsung",
    "08:37:3D": "Samsung",
    "28:39:5E": "Samsung",
    "2C:AE:2B": "Samsung",
    "34:23:BA": "Samsung",
    "38:AA:3C": "Samsung",
    "5C:0A:5B": "Samsung",
    "78:1F:DB": "Samsung",
    "84:25:DB": "Samsung",
    "94:35:0A": "Samsung",
    "AC:5F:3E": "Samsung",
    "E8:50:8B": "Samsung",
    "F4:0E:22": "Samsung",
    "00:9E:C8": "Xiaomi",
    "0C:1D:AF": "Xiaomi",
    "28:6C:07": "Xiaomi",
    "34:80:B3": "Xiaomi",
    "50:8F:4C": "Xiaomi",
    "64:09:80": "Xiaomi",
    "64:B4:73": "Xiaomi",
    "78:11:DC": "Xiaomi",
    "8C:BE:BE": "Xiaomi",
    "98:FA:E3": "Xiaomi",
    "A4:DA:22": "Xiaomi",
    "AC:C1:EE": "Xiaomi",
    "F0:B4:29": "Xiaomi",
    "FC:64:BA": "Xiaomi",
    "00:E0:FC": "Huawei",
    "04:BD:70": "Huawei",
    "18:59:36": "Huawei",
    "24:69:A5": "Huawei",
    "28:3C:E4": "Huawei",
    "48:00:31": "Huawei",
    "5C:7D:5E": "Huawei",
    "64:09:80": "Huawei",
    "78:6A:89": "Huawei",
    "88:53:D4": "Huawei",
    "A0:8C:F8": "Huawei",
    "AC:E2:15": "Huawei",
    "C8:94:BB": "Huawei",
    "E0:24:7F": "Huawei",
    "F8:01:13": "Huawei",
    "00:3A:98": "Google",
    "3C:5A:B4": "Google",
    "54:60:09": "Google",
    "6C:AD:F8": "Google",
    "94:EB:2C": "Google",
    "A4:77:33": "Google",
    "F4:F5:D8": "Google",
    "F4:F5:E8": "Google",
    "DA:A1:19": "Google",
    "00:0C:29": "OnePlus",
    "34:C9:3F": "OnePlus",
    "64:A2:F9": "OnePlus",
    "8C:53:C3": "OnePlus",
    "94:65:2D": "OnePlus",
    "C0:EE:FB": "OnePlus",
    "AC:3F:A4": "Motorola",
    "C8:14:51": "Motorola",
    "E0:39:48": "Motorola",
    "F8:CF:C5": "Motorola",
    "00:0E:07": "Sony",
    "04:5D:56": "Sony",
    "30:F9:ED": "Sony",
    "54:42:49": "Sony",
    "A0:E4:53": "Sony",
    "B8:F9:34": "Sony",
    "FC:F1:52": "Sony",
    "2C:0E:3D": "Vivo",
    "3C:CD:57": "Vivo",
    "50:6C:BE": "Vivo",
    "68:3E:34": "Vivo",
    "8C:81:26": "Vivo",
    "A0:9B:BD": "Vivo",
    "00:1C:42": "Oppo",
    "1C:77:F6": "Oppo",
    "2C:5B:B8": "Oppo",
    "44:74:6C": "Oppo",
    "68:77:24": "Oppo",
    "8C:44:35": "Oppo",
    "C0:EE:FB": "Oppo",
    "E4:6F:13": "Oppo",
}

MAC_RE = re.compile(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")

# Words that typically appear in a phone/tablet's advertised mDNS name.
PHONE_NAME_HINTS = (
    "iphone",
    "ipad",
    "ipod",
    "galaxy",
    "pixel",
    "oneplus",
    "redmi",
    "poco",
    "huawei",
    "honor",
    "moto",
    "oppo",
    "vivo",
    "realme",
    "xiaomi",
    "phone",
)

# Bonjour/zc service types announced only by phones/tablets (mostly Apple).
PHONE_SERVICE_HINTS = (
    "_companion-link",
    "_asquic",
    "_apple-mobdev",
    "_remotepairing",
    "_rdlink",
)


def default_interface_ipv4():
    """Return the local IPv4 used for outbound traffic (no traffic sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def ping(ip):
    try:
        subprocess.run(
            ["ping", "-c", "1", "-W", "1", str(ip)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        subprocess.run(
            ["ping", "-c", "1", str(ip)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def sweep(network, workers):
    hosts = list(network.hosts())
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(ping, hosts))


def read_arp_table():
    entries = {}
    if not os.path.exists("/proc/net/arp"):
        return entries
    with open("/proc/net/arp") as fh:
        next(fh, None)
        for line in fh:
            parts = line.split()
            if len(parts) >= 4 and parts[3] != "00:00:00:00:00:00":
                entries[parts[0]] = parts[3].upper()
    return entries


def vendor_for(mac):
    prefix = mac[:8].upper()
    return PHONE_OUIS.get(prefix)


def unescape_avahi(text):
    """Decode avahi-browse escapes: \\DDD is a decimal byte, e.g. \\032 -> ' '."""
    out = bytearray()
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 3 < len(text) and text[i + 1 : i + 4].isdigit():
            out.append(int(text[i + 1 : i + 4]))
            i += 4
        else:
            out.append(ord(text[i]))
            i += 1
    return out.decode("utf-8", "replace")


UUID_RE = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)


def clean_name(name):
    """Turn Android JSON/y blob service names into a readable device name."""
    if not name:
        return name
    if name.startswith("{"):
        match = re.search(r'"(?:nm|name)"\s*:\s*"([^"]+)"', name)
        if match:
            return match.group(1).strip()
    return name.strip()


def browse_mdns(timeout=8):
    """Return {ipv4: {"name": ..., "phone": bool}} from mDNS (avahi) responses."""
    if not shutil.which("avahi-browse"):
        return {}
    try:
        result = subprocess.run(
            ["avahi-browse", "-artp"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {}

    candidates = {}
    for line in result.stdout.splitlines():
        if not line.startswith("="):
            continue
        parts = line.split(";")
        # =;iface;proto;name;type;domain;hostname;address;port;txt
        if len(parts) < 9 or parts[2] != "IPv4":
            continue
        ip = parts[7]
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            continue
        service_name = unescape_avahi(parts[3]).strip()
        hostname = unescape_avahi(parts[6]).strip()
        if hostname.endswith(".local"):
            hostname = hostname[: -len(".local")]
        service = parts[4]
        txt = parts[9] if len(parts) > 9 else ""

        txt_name = ""
        match = re.search(r'(?:^|[ "])(?:name|nm)=([^"\s]+)', txt)
        if match:
            txt_name = match.group(1)

        names = []
        for cand in (clean_name(service_name), txt_name, hostname):
            if cand and not UUID_RE.match(cand) and cand not in names:
                names.append(cand)
        if not names:
            names = [n for n in (service_name, hostname) if n]

        hit_name = any(
            h in n.lower()
            for n in (service_name, hostname, txt_name)
            for h in PHONE_NAME_HINTS
        )
        is_phone = any(h in service for h in PHONE_SERVICE_HINTS) or hit_name

        best = names[0] if names else ""
        prev = candidates.get(ip)
        if prev is None or (not prev["name"] and best):
            candidates[ip] = {"name": best, "phone": is_phone}

    return candidates


def scan_once(network, workers):
    """Run one sweep and return a list of host rows."""
    sweep(network, workers)
    arp = read_arp_table()
    mdns = browse_mdns()

    ips = {ip for ip in arp if ipaddress.ip_address(ip) in network}
    ips |= {ip for ip in mdns if ipaddress.ip_address(ip) in network}

    rows = []
    for ip in sorted(ips, key=ipaddress.ip_address):
        mac = arp.get(ip, "")
        vendor = vendor_for(mac) if mac else None
        info = mdns.get(ip, {})
        name = info.get("name", "")
        is_phone = bool(vendor) or info.get("phone", False)
        label = vendor or ("phone" if is_phone else "unknown")
        rows.append((ip, name, mac, label, is_phone))
    return rows


def show(rows):
    print(f"{'IP':<16}{'NAME':<28}{'MAC':<20}VENDOR")
    for ip, name, mac, label, _ in rows:
        print(f"{ip:<16}{(name or '-'):<28}{(mac or '-'):<20}{label}")


def main():
    parser = argparse.ArgumentParser(
        description="Find a phone's IPv4 address on the local network."
    )
    parser.add_argument("-n", "--network", help="CIDR range, e.g. 192.168.1.0/24")
    parser.add_argument("--all", action="store_true", help="print every host")
    parser.add_argument(
        "--mac",
        help="find a specific device by MAC (full or prefix), e.g. AA:BB:CC:DD:EE:FF",
    )
    parser.add_argument("--name", help="match a device name substring (case-insensitive)")
    parser.add_argument(
        "--watch",
        type=int,
        metavar="SECONDS",
        help="keep scanning every N seconds until the target is found",
    )
    parser.add_argument(
        "--workers", type=int, default=128, help="parallel ping workers (default 128)"
    )
    args = parser.parse_args()

    target_mac = args.mac.upper().replace("-", ":") if args.mac else None
    target_name = args.name.lower() if args.name else None

    local_ip = default_interface_ipv4()
    if args.network:
        network = ipaddress.ip_network(args.network, strict=False)
    else:
        network = ipaddress.ip_network(f"{local_ip}/24", strict=False)

    def matches(row):
        _, name, mac, _, _ = row
        if target_mac and target_mac in mac:
            return True
        if target_name and target_name in name.lower():
            return True
        return False

    print(f"Local IP : {local_ip}")
    print(f"Scanning : {network}")
    print("-" * 60)

    while True:
        rows = scan_once(network, args.workers)

        if target_mac or target_name:
            hits = [r for r in rows if matches(r)]
            if hits:
                show(hits)
                print("-" * 60)
                print(f"Found {len(hits)} match(es).")
                return
            print(f"Target not found on {network}.")
        else:
            phones = [r for r in rows if r[4]]
            show(rows if args.all else phones)
            print("-" * 60)
            if phones:
                print(f"Found {len(phones)} phone(s).")
            elif rows:
                print("No phone detected (try --all or target one with --mac).")
            else:
                print(
                    "No hosts found: try running with sudo, or pass -n with your subnet.",
                    file=sys.stderr,
                )
            return

        if not args.watch:
            return
        try:
            time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped.", file=sys.stderr)
            return


if __name__ == "__main__":
    main()
