import os

# Tests draaien als demo: alleen daar mag de API zonder inlog. test_hardening.py zet zelf een echte koppeling neer.
os.environ.setdefault("NO_DOTENV", "1")
os.environ.setdefault("UNIFI_MODE", "mock")
