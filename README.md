# scan_phone

Find the IPv4 address of a phone (or any device) on your local network — from the
command line, with no app, no account, and no cloud service.

`scan_phone.py` pings the subnet, reads the ARP table, listens to mDNS
(Avahi/Bonjour) and SSDP (UPnP), then fills in missing names with NetBIOS,
reverse DNS, and a device's web-interface title. It recognizes common phone
vendors by MAC prefix (Apple, Samsung, Xiaomi, Huawei, Google, OnePlus, and
more) and flags devices that advertise phone-only services or use a
randomized (privacy) MAC.

## Quick start

```sh
# 1. Get the script
git clone git@github.com:llaarriizz/scan.git
cd scan

# 2. Make it executable (once)
chmod +x scan_phone.py

# 3. Run it — scans your local /24 and lists likely phones
./scan_phone.py
```

No install, no virtualenv, no `pip` — it only uses the Python 3 standard
library. If no hosts show up, run it with `sudo ./scan_phone.py` so it can read
ARP/ICMP responses, or pass your subnet explicitly with `-n`. For richer device
names, install the optional helpers listed under [Requirements](#requirements).

## Features

- **Subnet sweep** — parallel ICMP pings across your LAN.
- **Vendor detection** — maps the MAC OUI to a manufacturer (Apple, Samsung,
  Xiaomi, Huawei, Google, OnePlus, Motorola, Sony, Vivo, Oppo).
- **Device names** — resolves names from five sources, in order: mDNS
  (Avahi/Bonjour), SSDP/UPnP `friendlyName`, NetBIOS (`nmblookup`), reverse
  DNS (PTR), and the `<title>` of a device's web interface.
- **mDNS discovery** — uses `avahi-browse` to pick up names and phone services
  like `_companion-link`, `_apple-mobdev`, `_remotepairing`.
- **Randomized-MAC detection** — flags locally administered MACs (Android/iOS
  privacy addresses) as likely phones even when no name is advertised.
- **Target matching** — find a specific device by MAC address, MAC prefix, or
  name substring.
- **Watch mode** — rescan every N seconds until the target shows up.
- **Zero Python dependencies** — pure Python 3 standard library.

## Requirements

- Linux
- Python 3.8+
- `iputils-ping` (the `ping` command)
- `avahi-utils` — optional, enables name/service discovery
- `samba-common-bin` (the `nmblookup` command) — optional, enables NetBIOS
  names for Windows/Samba devices

```sh
# Debian/Ubuntu
sudo apt install iputils-ping avahi-utils samba-common-bin
```

On some systems a full scan needs elevated privileges to read ARP/ICMP responses:

```sh
sudo ./scan_phone.py
```

## Usage

```sh
# Print detected phone candidates on your /24 subnet
./scan_phone.py

# List every host found, not just likely phones
./scan_phone.py --all

# Scan a specific subnet
./scan_phone.py -n 192.168.1.0/24

# Find a specific device by MAC (full or prefix)
./scan_phone.py --mac AA:BB:CC:DD:EE:FF

# Match a device name substring (case-insensitive)
./scan_phone.py --name poco

# Keep scanning every 10 seconds until the target appears
./scan_phone.py --mac AA:BB:CC:DD:EE:FF --watch 10

# Tune parallelism for larger networks
./scan_phone.py -n 10.0.0.0/22 --workers 256
```

`python3 scan_phone.py …` works exactly the same if you prefer not to
`chmod +x`.

## Options

| Flag | Description |
| --- | --- |
| `-n`, `--network CIDR` | Subnet to scan. Defaults to your local `/24`. |
| `--all` | Print every host, not just phones. |
| `--mac MAC` | Find a device by full MAC or prefix (e.g. `AA:BB:CC`). |
| `--name NAME` | Match a device-name substring (case-insensitive). |
| `--watch SECONDS` | Rescan every N seconds until the target is found. |
| `--workers N` | Parallel ping workers (default `128`). |

## Output

```
Local IP : 192.168.1.42
Scanning : 192.168.1.0/24
------------------------------------------------------------
IP              NAME                        MAC                 VENDOR
192.168.1.1     DeviceDHCP.Home             CC:BE:59:91:9B:07   unknown
192.168.1.17    my-poco-f5                  AC:C1:EE:12:34:56   Xiaomi
192.168.1.23    iPhone-von-Anna             3C:07:54:AB:CD:EF   Apple
------------------------------------------------------------
Found 2 phone(s).
```

NAME comes from mDNS, SSDP, NetBIOS, reverse DNS, or the device's web title —
whichever responds first in that order. `-` means the device advertises no
name anywhere (common for phones with a randomized MAC).

## Tips

Android phones rarely broadcast their name over mDNS. The most reliable way to
find one is by MAC address:

1. On the phone, open **Settings → About → Status** and note the **Wi-Fi MAC
   address**.
2. Run `./scan_phone.py --mac AA:BB:CC:DD:EE:FF`.

## How it works

1. `default_interface_ipv4()` determines your local IP by opening a UDP socket
   (no packets are actually sent) to derive the default `/24`.
2. `sweep()` sends a single ping per host using a thread pool so the ARP cache
   gets populated.
3. `read_arp_table()` parses `/proc/net/arp` to map IPs to MACs.
4. `browse_mdns()` runs `avahi-browse -artp` and `browse_ssdp()` sends an SSDP
   `M-SEARCH`, in parallel, to collect advertised names and services.
5. Hosts still without a name are queried in parallel for their NetBIOS name
   (`nmblookup -A`), their reverse-DNS record (`socket.gethostbyaddr`), and
   finally the `<title>` of their HTTP/HTTPS front page.
6. Results are merged (mDNS > SSDP > NetBIOS > PTR > web title), filtered by
   OUI/name/service hints, and printed.

## Name resolution order

| Source | Typical winner |
| --- | --- |
| mDNS / Bonjour | iPhones, Chromecasts, Linux boxes, smart speakers |
| SSDP / UPnP `friendlyName` | routers, TVs, printers, consoles |
| NetBIOS (`nmblookup -A`) | Windows PCs, Samba shares |
| Reverse DNS (PTR) | anything your router/Pi-hole registers from DHCP |
| Web UI `<title>` | routers, cameras, IoT devices with port 80 open |

Names are only looked up for hosts that mDNS/SSDP could not name, so the extra
sources cost almost nothing when discovery already worked.

## Limitations

- ICMP and mDNS can be blocked on some networks or by client isolation
  (common on guest Wi-Fi), in which case hosts may not be visible.
- A device is only named if it actually advertises a name: phones with a
  randomized MAC and no DHCP/PTR entry will show up as `-` under NAME. Use
  `--mac` to target them.
- The `randomized` label (locally administered MAC) is a heuristic — privacy
  addresses are common on phones, but VMs and some IoT gear use them too.
- The OUI database is a curated subset, not the full IEEE registry — unknown
  vendors show as `unknown`.
- IPv4 only.

## License

MIT
