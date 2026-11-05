"""Instellingen.

Volgorde (laatste wint): standaardwaarden → omgevingsvariabelen (.env) → <DATA_DIR>/config.json.
config.json wordt door de setup-wizard geschreven en is alleen leesbaar voor de service.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_KEYS = ("mode", "controller_url", "site", "api_key", "username", "password", "verify_tls",
               "allowed_hosts", "notify", "home_country")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


@dataclass
class Thresholds:
    """Drempels voor de issue-detectie. Alles is via env te overschrijven (TH_<NAAM>)."""

    # Afgestemd op een echt thuisnetwerk: mediaan retries 2.4 GHz ≈4%, 5 GHz ≈15%;
    # UniFi-satisfaction ligt normaal ≥92.
    client_signal_warn_24: float = -75.0  # dBm, 2.4 GHz (IoT werkt hier nog prima)
    client_signal_crit_24: float = -82.0
    client_signal_warn: float = -74.0     # dBm, 5/6 GHz
    client_signal_crit: float = -80.0
    client_retry_warn: float = 25.0       # % van verzonden pakketten
    client_retry_crit: float = 40.0
    client_satisfaction_warn: float = 80.0
    client_satisfaction_crit: float = 60.0
    client_roams_per_hour: float = 12.0
    client_low_rate_mbps: float = 24.0    # lage linksnelheid bij goed signaal
    radio_cu_warn: float = 60.0           # % kanaalbezetting
    radio_cu_crit: float = 80.0
    radio_interference_warn: float = 35.0  # % bezetting door anderen
    radio_retry_warn: float = 20.0
    radio_retry_min_clients: float = 3.0   # retries op een (bijna) lege radio zijn ruis
    port_errors_per_hour: float = 50.0
    port_flaps_per_hour: float = 3.0
    poe_budget_warn: float = 85.0          # % van budget
    device_cpu_warn: float = 85.0
    device_mem_warn: float = 90.0
    device_temp_warn: float = 75.0         # °C
    wan_latency_warn: float = 50.0         # ms
    wan_latency_crit: float = 150.0
    wan_drops_warn: float = 1.0            # % pakketverlies

    @classmethod
    def from_env(cls) -> "Thresholds":
        t = cls()
        for name in t.__dataclass_fields__:
            setattr(t, name, _float(f"TH_{name.upper()}", getattr(t, name)))
        return t


@dataclass
class Settings:
    mode: str = ""                     # "live", "mock" (demodata) of "" (nog niet ingesteld)
    controller_url: str = ""           # bv. https://192.168.1.10 (UniFi OS)
    site: str = "default"
    api_key: str = ""
    username: str = ""
    password: str = ""
    verify_tls: bool = False
    poll_seconds: int = 60
    retention_days: int = 14
    db_path: str = ""                  # leeg = automatisch in data_dir (los bestand voor demodata)
    data_dir: str = "data"
    mock_seed_hours: int = 6
    home_country: str = "NL"   # waar de bogen op de wereldkaart vertrekken
    allowed_hosts: list = field(default_factory=list)   # extra hostnamen (instellingenpagina); env ALLOWED_HOSTS telt ook
    notify: dict = field(default_factory=dict)          # meldingen naar buiten, zie notify.py
    thresholds: Thresholds = field(default_factory=Thresholds)

    @property
    def configured(self) -> bool:
        return self.mode == "mock" or (self.mode == "live" and bool(self.controller_url)
                                       and bool(self.api_key or (self.username and self.password)))

    @property
    def database(self) -> str:
        if self.db_path:
            return self.db_path
        return str(Path(self.data_dir) / ("demo.db" if self.mode == "mock" else "unifi.db"))

    @property
    def config_file(self) -> Path:
        return Path(self.data_dir) / "config.json"

    @classmethod
    def load(cls, data_dir: str | None = None) -> "Settings":
        s = cls.from_env()
        if data_dir:
            s.data_dir = data_dir
        if s.config_file.exists():
            try:
                stored = json.loads(s.config_file.read_text())
            except (OSError, ValueError):
                stored = {}
            for k in CONFIG_KEYS:
                if k in stored:
                    setattr(s, k, stored[k])
        return s

    def save(self) -> None:
        """Schrijf de verbindingsgegevens weg; alleen leesbaar voor de eigenaar (de service)."""
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        tmp = self.config_file.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({k: getattr(self, k) for k in CONFIG_KEYS}, f, indent=2)
        os.replace(tmp, self.config_file)

    @classmethod
    def from_env(cls) -> "Settings":
        mode = _env("UNIFI_MODE").lower()
        if not mode and _env("UNIFI_URL") and (_env("UNIFI_API_KEY") or _env("UNIFI_USERNAME")):
            mode = "live"   # oude .env-installaties zonder UNIFI_MODE
        return cls(
            mode=mode,
            controller_url=_env("UNIFI_URL").rstrip("/"),
            site=_env("UNIFI_SITE", "default"),
            api_key=_env("UNIFI_API_KEY"),
            username=_env("UNIFI_USERNAME"),
            password=_env("UNIFI_PASSWORD"),
            verify_tls=_env("UNIFI_VERIFY_TLS", "false").lower() in ("1", "true", "yes"),
            poll_seconds=max(15, int(_float("POLL_SECONDS", 60))),
            retention_days=max(1, int(_float("RETENTION_DAYS", 14))),
            db_path=_env("DB_PATH"),
            data_dir=_env("DATA_DIR", "data"),
            mock_seed_hours=int(_float("MOCK_SEED_HOURS", 6)),
            thresholds=Thresholds.from_env(),
        )
