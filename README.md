# nexus-poap
Zero-Touch Provisioning for Cisco Nexus switches using POAP
# Zero-Touch Network Provisioning — Cisco Nexus POAP

> Automated switch provisioning using Cisco Power On Auto Provisioning (POAP) — a new Nexus switch plugs in and gets its full configuration automatically with zero manual CLI intervention.

---

## 📌 Project Overview

This project implements a production-ready **Zero-Touch Provisioning (ZTP)** system for Cisco Nexus switches using the built-in **POAP** (Power On Auto Provisioning) feature.

When a new Nexus switch is powered on with no configuration, it automatically:
1. Gets an IP address via DHCP
2. Downloads a Python provisioning script via TFTP
3. Detects its own platform (3K / 5K / 9K)
4. Downloads the correct configuration file
5. Applies the configuration and reboots — fully provisioned ✅

**No console access needed. No manual CLI commands. No human error.**

---

## 🏗️ Architecture

```
[Red Hat Linux Server 192.168.1.100]
 ├── DHCP Server  (dhcp-server)     → hands out IP + Option 66/67
 └── TFTP Server  (tftp-server)     → serves script + config files
          |
          | VLAN 100 (POAP-MGMT)
          |
[Management Switch — Cisco Nexus]
 SVI VLAN 100: 192.168.1.1/24
          |
          | VLAN 100
          |
[New Nexus Switch — mgmt0]
 Receives IP via DHCP → runs POAP → gets config → done ✅
```

---

## 📁 Repository Structure

```
nexus-poap/
├── README.md
├── server/
│   ├── dhcpd.conf              # DHCP server config with Option 66/67
│   └── setup_rhel.sh           # Red Hat server setup script
├── poap/
│   └── poap_script.py          # Universal POAP script (3K/5K/9K)
├── configs/
│   ├── switch_config.cfg       # Sample Nexus 3K config template
│   └── config_rules.md         # Rules every config file must follow
└── docs/
    └── POAP_Implementation_Guide.docx   # Full implementation guide
```

---

## ⚙️ Tech Stack

| Component | Technology |
|---|---|
| Server OS | Red Hat Enterprise Linux 8/9 |
| DHCP Server | dhcp-server (dnf) |
| TFTP Server | tftp-server via systemd socket |
| Firewall | firewalld |
| Script Language | Python 2.7 (NX-OS built-in) |
| Target Platform | Cisco Nexus NX-OS |
| Management Switch | Cisco Nexus (any model) |

---

## 🚀 How It Works

### DHCP Options That Trigger POAP

```
Option 66  →  TFTP Server IP  (192.168.1.100)
Option 67  →  Boot filename   (poap_script.py)
```

When the switch boots with no config, NX-OS reads these DHCP options and automatically downloads and runs the POAP script.

### POAP Script Logic

```
Switch boots → POAP starts
      ↓
DHCP → gets IP + TFTP server + script name
      ↓
Downloads poap_script.py via TFTP
      ↓
Script runs on NX-OS Python 2.7:
  1. run 'show version' → detect platform (3K/5K/9K)
  2. download correct config from TFTP
  3. apply config to startup-config
      ↓
Switch reloads → fully provisioned ✅
```

---

## 📋 Server Setup (Red Hat Linux)

### 1. Install packages
```bash
sudo dnf update -y
sudo dnf install dhcp-server tftp-server -y
```

### 2. Set static IP
```bash
sudo nmcli con mod eth0 ipv4.addresses 192.168.1.100/24
sudo nmcli con mod eth0 ipv4.gateway 192.168.1.1
sudo nmcli con mod eth0 ipv4.method manual
sudo nmcli con up eth0
```

### 3. Configure DHCP (`/etc/dhcp/dhcpd.conf`)
```
default-lease-time 3600;
max-lease-time 7200;
authoritative;

subnet 192.168.1.0 netmask 255.255.255.0 {
    range 192.168.1.10 192.168.1.50;
    option routers 192.168.1.100;
    option tftp-server-name "192.168.1.100";   # Option 66
    option bootfile-name "poap_script.py";      # Option 67
    next-server 192.168.1.100;
}
```

### 4. Start services
```bash
sudo systemctl enable --now dhcpd
sudo systemctl enable --now tftp.socket
```

### 5. Open firewall
```bash
sudo firewall-cmd --permanent --add-service=dhcp
sudo firewall-cmd --permanent --add-service=tftp
sudo firewall-cmd --reload
```

### 6. Place files
```bash
sudo cp poap_script.py /var/lib/tftpboot/
sudo cp switch_config.cfg /var/lib/tftpboot/
sudo chown nobody:nobody /var/lib/tftpboot/*
sudo chmod 644 /var/lib/tftpboot/*

# SELinux fix (important on RHEL)
sudo setsebool -P tftp_home_dir on
sudo restorecon -Rv /var/lib/tftpboot/
```

---

## 🔀 Management Switch Config (Cisco Nexus)

```
vlan 100
  name POAP-MGMT

interface Ethernet1/1          ! port facing Red Hat server
  switchport mode access
  switchport access vlan 100
  no shutdown

interface Ethernet1/2          ! port facing Nexus 3K mgmt0
  switchport mode access
  switchport access vlan 100
  no shutdown

feature interface-vlan
interface vlan 100
  ip address 192.168.1.1/24
  no shutdown
```

---

## ▶️ Trigger POAP on Switch

```bash
switch# write erase
switch# reload
# At prompt: Abort Power On Auto Provisioning [yes/skip/no]: no
```

---

## 📊 Monitoring

```bash
# Watch DHCP on Red Hat server
sudo journalctl -u dhcpd -f

# Watch TFTP transfers
sudo journalctl -u tftp.socket -f

# Watch everything
sudo journalctl -f | grep -iE 'dhcp|tftp'

# Check POAP log on switch after provisioning
show file bootflash:poap.log
```

---

## ✅ Config File Rules

Every `switch_config.cfg` must follow these rules:

| Rule | Reason |
|---|---|
| No `version x.x.x` at top | Causes NX-OS version mismatch errors |
| Must have `no boot poap enable` | Prevents infinite POAP loop on reboot |
| Correct `boot nxos` image path | Must match actual .bin on bootflash |
| Remove unsupported features | Prevents silent failures |
| Last line: `copy running-config startup-config` | Ensures config persists after reload |
| Use config from same NX-OS version | Prevents command compatibility errors |

---

## 🔧 Troubleshooting

| Issue | Fix |
|---|---|
| Switch not getting DHCP | Check both mgmt switch ports are access VLAN 100 |
| TFTP permission denied | `sudo restorecon -Rv /var/lib/tftpboot/` (SELinux) |
| dhcpd not starting | `sudo dhcpd -t -cf /etc/dhcp/dhcpd.conf` to check syntax |
| POAP loop after reboot | Add `no boot poap enable` to config file |
| Firewall blocking | `sudo firewall-cmd --list-all` — verify dhcp and tftp listed |

---

## 📄 Full Documentation

See [`docs/POAP_Implementation_Guide.docx`](docs/POAP_Implementation_Guide.docx) for the complete step-by-step implementation guide including topology diagrams, all commands, verification steps, and a pre-deployment checklist.

---

## 💼 Resume Description

> Designed and implemented a Zero-Touch Provisioning system for Cisco Nexus switches using POAP, reducing manual switch configuration time from ~2 hours to under 10 minutes by automating config delivery via a custom Python script, Red Hat TFTP/DHCP server, and Cisco NX-OS — eliminating 100% of manual CLI intervention.

---

## 🧠 Key Learnings

- NX-OS Python `cli()` must be imported — not available as a global on all versions
- Always use 3 fallback CLI methods (`cli.cli`, `cisco.cli`, `vsh subprocess`) for compatibility across NX-OS versions
- SELinux on Red Hat blocks TFTP by default — `setsebool -P tftp_home_dir on` is required
- `boot poap enable` in the config causes an infinite POAP loop — always use `no boot poap enable`
- Config file must be from the same NX-OS version as the target switch
- DHCP Options 66 and 67 are mandatory — without them POAP never starts

---

## 📌 Platforms Tested

| Platform | NX-OS Version | Status |
|---|---|---|
| Cisco Nexus 3K | 7.0.3.I7.6 | ✅ Tested |

---

*Mustafa Indorewala — Network Engineering Project | March 2026*
