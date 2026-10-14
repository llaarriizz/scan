# scan_phone

Find the IPv4 address of a phone (or any device) on your local network — from the
command line, with no app, no account, and no cloud service.

`scan_phone.py` pings the subnet, reads the ARP table, and listens to mDNS
(Avahi/Bonjour) to identify hosts. It recognizes common phone vendors by MAC
prefix (Apple, Samsung, Xiaomi, Huawei, Google, OnePlus, and more) and flags
devices that advertise phone-only services.

## Features

- **Subnet sweep** — parallel ICMP pings across your LAN.
- **Vendor detection** — maps the MAC OUI to a manufacturer (Apple, Samsung,
  Xiaomi, Huawei, Google, OnePlus, Motorola, Sony, Vivo, Oppo).
- **mDNS discovery** — uses `avahi-browse` to pick up names and phone services
  like `_companion-link`, `_apple-mobdev`, `_remotepairing`.
- **Target matching** — find a specific device by MAC address, MAC prefix, or
  name substring.
- **Watch mode** — rescan every N seconds until the target shows up.
- **Zero dependencies** — pure Python 3 standard library.

## Requirements

- Linux
- Python 3.8+
- `iputils-ping` (the `ping` command)
- `avahi-utils` — optional, enables name/service discovery

```sh
# Debian/Ubuntu
sudo apt install iputils-ping avahi-utils
```

On some systems a full scan needs elevated privileges to read ARP/ICMP responses:

```sh
sudo python3 scan_phone.py
```

## Usage

```sh
# Print detected phone candidates on your /24 subnet
python3 scan_phone.py

# List every host found, not just likely phones
python3 scan_phone.py --all

# Scan a specific subnet
python3 scan_phone.py -n 192.168.1.0/24

# Find a specific device by MAC (full or prefix)
python3 scan_phone.py --mac AA:BB:CC:DD:EE:FF

# Match a device name substring (case-insensitive)
python3 scan_phone.py --name poco

# Keep scanning every 10 seconds until the target appears
python3 scan_phone.py --mac AA:BB:CC:DD:EE:FF --watch 10

# Tune parallelism for larger networks
python3 scan_phone.py -n 10.0.0.0/22 --workers 256
```

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
192.168.1.17    my-poco-f5                  AC:C1:EE:12:34:56   Xiaomi
192.168.1.23    iPhone-von-Anna             3C:07:54:AB:CD:EF   Apple
------------------------------------------------------------
Found 2 phone(s).
```

## Tips

Android phones rarely broadcast their name over mDNS. The most reliable way to
find one is by MAC address:

1. On the phone, open **Settings → About → Status** and note the **Wi-Fi MAC
   address**.
2. Run `python3 scan_phone.py --mac AA:BB:CC:DD:EE:FF`.

## How it works

1. `default_interface_ipv4()` determines your local IP by opening a UDP socket
   (no packets are actually sent) to derive the default `/24`.
2. `sweep()` sends a single ping per host using a thread pool so the ARP cache
   gets populated.
3. `read_arp_table()` parses `/proc/net/arp` to map IPs to MACs.
4. `browse_mdns()` runs `avahi-browse -artp` to collect names and services.
5. Results are merged, filtered by OUI/name/service hints, and printed.

## Limitations

- ICMP and mDNS can be blocked on some networks or by client isolation
  (common on guest Wi-Fi), in which case hosts may not be visible.
- The OUI database is a curated subset, not the full IEEE registry — unknown
  vendors show as `unknown`.
- IPv4 only.

## License

MIT
