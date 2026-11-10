# Changelog

All notable changes to UniFi Sonar. Versions follow [semantic versioning](https://semver.org).

## 1.10.0 – 2026-11-10

### Added
- **Devices without a name** on the Clients page: Sonar guesses what each one is from what it looked up in the past week (connections and AdGuard), its vendor and its hostname, and shows the evidence and how sure it is. A generic domain (Google Play, iCloud) never outweighs a known vendor with a fixed MAC address, so a Nest Hub isn't called a phone. A smart device on your main network gets a hint to move it to your IoT network.
- **Set name**: give a device a name in UniFi itself, from that list or from the new *What is this?* card in the device details. The UniFi app sees the name too.
- **Quarantine**: block a device until you release it, with the reason next to it. Offered next to malware and phishing that AdGuard blocked, on those issues and in the device details. A schedule never lets a quarantined device go, a pause can't replace it, and an issue reminds you while it lasts.

## 1.9.0 – 2026-11-10

### Added
- **AdGuard Home integration** (optional, read-only), set up under Settings → AdGuard Home. One or more AdGuard servers, each with its own address and login.
  - **Names instead of IP addresses**: connections that UniFi can't name get the name the device looked up just before, so the World page shows `api.tuya.com` instead of an address.
  - **What your smart devices look up**: per smart device and server, the domains it uses. After a week of learning, a new domain gives a notification.
  - **DNS servers watched**: Sonar asks each DNS server a question every 2 minutes. If one stops answering, gets slow, has protection off, gets errors from its upstream, or two AdGuards are set up differently (for example a rewrite on only one), you get an issue.
  - **Malware and phishing** that AdGuard blocked, per device. Critical when the IPS stepped in for the same device too.
  - **Devices that skip AdGuard**: internet traffic but not a single DNS query, usually their own DNS server or DNS-over-HTTPS.
  - **Devices with their own DNS server**: listed separately, with whether your network redirects them to AdGuard (a NAT rule) or your firewall stops them. Queries redirected through the gateway are recognised by the gateway's LAN address.
- **Privacy**: domains are only kept for smart devices and servers. For phones, laptops and tablets Sonar only counts how much they look up, unless you change that in Settings or per device.

## 1.8.0 – 2026-11-09

### Added
- **Vulnerability check** under Security, in three steps from careful to active:
  - **Exploited flaws**: Ubiquiti's advisories are compared with your firmware and with CISA's list of flaws that are really being exploited. Those become critical.
  - **Your public address** (off by default): a daily lookup at Shodan InternetDB. Your address is then sent to Shodan. Each open port Shodan sees is matched against your port forwards, UPnP mappings and VPN servers: ports that match are fine, ports of something switched off are probably outdated (they become a finding after two weeks), and ports your controller knows nothing about are a finding. For a forwarded port you also see what else that device has open inside your network.
  - **Port check** (you start it): about 30 admin ports, slowly, only on devices from your controller. It only connects and closes, and it runs in its own process without your API key. Smart devices and guests are skipped.
- The page always shows **what was looked at and what wasn't**, so "nothing found" can't be mistaken for "all clear". UniFi OS Server has no readable version, so it says "check yourself" with the minimum safe version.
- A notification only gives the number of findings; the details stay in Sonar.
- **Review** under From own devices on the Security page now filters the blocks table to your own devices.

## 1.7.0 – 2026-11-09

### Security
- **Login is now required** for a real network. The first password needs a one-time code that is shown on the machine itself. Only the demo can run without a login. After updating, an install without a login shows that code.
- **Encrypted backups**: Sonar can write them but only open them with your password or a recovery code that you see once.
- **Controller certificate pinning**: with certificate verification off, Sonar records the certificate on first connection and refuses to send its key if it changes.
- **Sessions can be revoked**: see logged-in devices under Settings → Access and log them out. Everyone has to log in once after this update.
- **Saved MQTT passwords and webhook tokens** no longer follow a changed address.
- **Updates** only install published releases, and Python packages are checked against fixed hashes.

## 1.6.0 – 2026-11-09

### Added
- **Why was this blocked?** Click a blocked connection on the World page to see the firewall rule, region block or IPS signature that stopped it, who tried what, and whether you need to do anything.

## 1.5.0 – 2026-11-09

### Added
- **Passkeys** as an optional way to log in, next to the password. They need HTTPS and a host name.

## 1.4.0 – 2026-11-08

### Added
- **Backups of your UniFi controller**: Sonar keeps a copy of the automatic backups and can have a fresh one made every day. A warning appears when there is no recent backup.
- **Optional login** with a password, under Settings → Access.
- **Delay under load (bufferbloat)**: a grade from A+ to F during the speed test.
- **Presence in Home Assistant**: chosen devices as a `device_tracker` via MQTT.
- **Wall display**: a calm full-screen view, optionally with the globe, and a black-and-white version for e-paper.

### Fixed
- After a single failed request Sonar could stay on the limited official API until it was restarted. It now tries the richer source again every 5 minutes.

## 1.3.0 – 2026-11-08

The first release on GitHub.

### Added
- **English**: the whole app, issues, advice, notifications and Home Assistant sensor names in English or Dutch. Switch with NL | EN in the top bar; the first start follows your browser language.
- **DNS leaks**: devices that bypass your own DNS server (Pi-hole, AdGuard) with plain DNS, DNS-over-TLS or DNS-over-HTTPS.
- **Firewall audit**: rules that never match, and allow rules that open your main network to IoT, guests or the internet.
- **Ubiquiti security advisories** matched against the firmware of your devices and Network app (checked every 6 hours, can be switched off).
- **Internet outages and availability** over 24 hours, 7, 30 and 90 days and per month.
- **Usage per device**, per day, and per category when Traffic Identification is on.
- **Failed Wi-Fi connections** per band, with the step where it went wrong, plus the anomalies UniFi itself noticed per device.
- **Neighbouring networks and channel advice** per access point, using interference Sonar measured before (also from non-Wi-Fi sources).
- **Fixed pause times** for groups of devices, also across midnight.
- **Wi-Fi speed at this spot**: a speed test from your phone or laptop to Sonar, with room, AP, band and signal.
- **Public IP changed** on the timeline and as a notification.
- **Network segmentation**: networks, firewall zones, an interactive "access between networks" diagram, and smart-home devices on the main network.
- **Change log** of settings, a **network map**, **pausing the internet** per device and **Home Assistant via MQTT** with auto-discovery.
- **3D globe** on the world page, with flowing streams per connection.

### Changed
- Firewall rule targets show the hostname or IP address instead of the vendor name.

## 1.2.0 – 2026-11-05

### Added
- `update` command inside the Proxmox container, like the community scripts.
- World map with live connections per country, zooming, and details of blocked traffic.
- "This device" on the overview, and data usage per day and month.
- Notifications for new devices and rotating private Wi-Fi addresses.

## 1.1.0 – 2026-11-05

### Added
- Sending notifications (Home Assistant, ntfy, Discord, Slack, webhook).
- Wi-Fi settings checks, ports open to the internet, and patterns per device and access point.
- Internet page with live traffic and a speed test on the gateway.

## 1.0.0 – 2026-11-05

- First version: overview, issues with explanation and advice, devices, clients, IPS, timeline and the setup wizard.
