from app.changes import config_fingerprint, device_fingerprint, diff


def raw(**w):
    wlan = {"name": "Thuis", "enabled": True, "security": "wpapsk", "wpa3_support": True, "wpa3_transition": True,
            "x_passphrase": "geheim1", "wlan_bands": ["2g", "5g"], "fast_roaming_enabled": False,
            "minrate_ng_enabled": True, "minrate_ng_data_rate_kbps": 1000, **w}
    return {"wlans": [wlan], "settings": [{"key": "usg", "upnp_enabled": True}],
            "forwards": [{"name": "NAS", "enabled": True, "proto": "tcp", "dst_port": "22", "fwd": "192.168.1.5", "fwd_port": "22"},
                         {"name": "PS5", "is_upnp": 1, "dst_port": "3074"}],
            "networks": [{"name": "OpenVPN", "vpn_type": "openvpn-server", "enabled": True, "local_port": 1024}],
            "firewall": [{"name": "IoT blok", "enabled": True, "action": "BLOCK"}, {"name": "Intern", "predefined": True}]}


def msgs(a, b):
    return [e["message"] for e in diff(a, b)]


def test_config_changes_are_readable_and_hide_passwords():
    a = config_fingerprint(raw(), "zout")
    assert not any("geheim1" in v for v in a.values())                         # nooit het wachtwoord zelf
    assert not any("PS5" in k for k in a) and not any("Intern" in k for k in a)   # UPnP en ingebouwde regels niet
    b = config_fingerprint(raw(fast_roaming_enabled=True, x_passphrase="geheim2", minrate_ng_data_rate_kbps=6000), "zout")
    m = msgs(a, b)
    assert "Wifi 'Thuis': Fast Roaming uit → aan" in m
    assert "Wifi 'Thuis': wachtwoord gewijzigd" in m
    assert "Wifi 'Thuis': minimale snelheid 2.4 GHz 1 Mbit/s → 6 Mbit/s" in m
    assert msgs(a, a) == []


def test_added_removed_and_settings():
    a = config_fingerprint(raw(), "z")
    r = raw()
    r["networks"][0]["enabled"] = False
    r["forwards"] = r["forwards"][1:]
    r["settings"][0]["upnp_enabled"] = False
    r["wlans"].append({"name": "Gast", "is_guest": True})
    m = msgs(a, config_fingerprint(r, "z"))
    assert "VPN-server 'OpenVPN': ingeschakeld aan → uit" in m
    assert "Port forward 'NAS' verwijderd" in m and "Wifi 'Gast' toegevoegd" in m
    assert "Instelling UPnP: aan → uit" in m
    assert not any(x.startswith("Port forward 'NAS':") for x in m)               # geen losse regels per veld


def test_device_changes():
    d = {"mac": "aa", "name": "AP Woonkamer", "bandsteering": "off",
         "radios": [{"radio": "2.4", "channel": 11, "channel_auto": False, "width": 20, "tx_power_mode": "auto", "min_rssi": None}]}
    a = device_fingerprint([d])
    d2 = {**d, "bandsteering": "prefer_5g", "radios": [{**d["radios"][0], "channel": 6, "tx_power": 17}]}
    m = [e["message"] for e in diff(a, device_fingerprint([d2]), {"aa": "AP Woonkamer"})]
    assert m == ["AP Woonkamer · 2.4 GHz kanaal: 11 → 6", "AP Woonkamer · band steering: uit → voorkeur 5 GHz"]
    assert diff(a, device_fingerprint([d, {"mac": "bb", "name": "Nieuw", "radios": []}])) == []   # nieuw apparaat: geen log
