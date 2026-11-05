# UniFi Sonar

**Een slim dashboard voor je UniFi-netwerk dat in gewone taal vertelt wat er mis is, en wat je eraan kunt doen.**

UniFi Sonar leest je UniFi-controller uit (gateway, switches, access points en alle clients), bewaart een paar weken historie en zoekt zelf naar problemen: zwak wifi-signaal, veel retries, drukke kanalen, kabelproblemen, apparaten die op de verkeerde AP blijven hangen, wifi-instellingen die je netwerk trager maken, poorten die openstaan naar internet en wat de IPS van je gateway tegenhoudt. Bij elke melding staat uitleg en een concreet advies, en als je wilt krijg je een bericht op je telefoon.

> Onofficieel hobbyproject. Niet verbonden aan of goedgekeurd door Ubiquiti. "UniFi" is een merk van Ubiquiti Inc.

![Netwerkoverzicht van UniFi Sonar (demodata)](docs/screenshots/overzicht.png)

## Wat het kan

- **Overzicht:** netwerkscore, open meldingen, je netwerk als boom (gateway → switches → AP's), wifi per access point en grafieken van internetlatency en wifi-ervaring.
- **Slimme meldingen:**
  - zwak signaal (met aparte drempels voor 2,4 en 5/6 GHz), veel retries, slechte ervaringsscore, apparaten die steeds van AP wisselen
  - drukke kanalen en storing van buren, overlappende 2,4 GHz-kanalen, een overbelaste AP
  - pakketfouten op switchpoorten, links die wegvallen, gigabitpoorten die op 100 Mbit draaien, een bijna vol PoE-budget
  - herstarts, offline apparaten, firmware-updates, hoge CPU, geheugen of temperatuur; geen alarm terwijl een apparaat wordt bijgewerkt, en een herstart door een firmware-update telt niet als probleem
  - internetlatency, pieken en pakketverlies
  - **groepering op oorzaak:** hebben meerdere apparaten op dezelfde AP problemen, dan wordt dat één melding "zwakke dekking". Valt (bijna) alles tegelijk weg, dan krijg je één melding dat de controller niets meer hoort, in plaats van tien losse
  - **"blijft hangen":** vaste apparaten die al lang met zwak signaal op een verre AP zitten, terwijl ze de afgelopen week op een andere AP veel beter zaten. Ook na een herstart van een AP. Met een knop *Opnieuw verbinden*
  - **wifi-instellingen:** AP's in hetzelfde 5 GHz-kanaalblok, een ongebruikt 2.4 GHz-kanaal, 40 MHz op 2.4 GHz, band steering of Fast Roaming uit, trage minimale datasnelheid, een te strenge minimum-RSSI en hoog zendvermogen op 2.4 GHz
  - **open naar internet:** UPnP aan, UPnP-mappings op standaardpoorten, SSH/RDP/databases die voor iedereen openstaan en port forwards die vaak worden aangevallen
  - **IPS:** een eigen apparaat dat door de IPS wordt geblokkeerd, krijgt een melding (aanvallen van buiten zijn juist het werk van de IPS)
- **Meldingen versturen** naar Home Assistant, ntfy, Discord, Slack of een eigen webhook. Pas na een instelbare wachttijd (geen bericht bij één uitschieter), een nieuw bericht als het erger wordt, een bericht als het is opgelost, veel tegelijk wordt één bundel, en desgewenst een dagoverzicht. Ook als de controller onbereikbaar is.
- **Meldingen negeren** voor 1 dag, 1 week, 30 dagen of altijd, bijvoorbeeld een laadpaal die nu eenmaal op 100 Mbit draait. IPS-blokkades negeer je per adres, per regel of de combinatie.
- **Internet:** live download- en uploadverkeer, latency, het verkeer over de afgelopen dagen en een **speedtest** met één knop. De test draait op je gateway zelf, dus hij meet je echte internetverbinding en niet je wifi. Alle resultaten blijven bewaard, en zakt de snelheid ver onder wat normaal is voor jouw verbinding, dan krijg je een melding.
- **Wereld:** een live wereldkaart van alle verbindingen door je gateway. Bogen naar elk land waar je apparaten mee praten, inkomend verkeer en wat de IPS of je regioblokkade tegenhield, met per land de belangrijkste domeinen en apparaten, en bij blokkades welke dienst en welk apparaat het doelwit was. Inzoomen kan met scrollen, slepen, knijpen of door op een land in de lijst te klikken. De gegevens komen uit het verkeerslogboek dat UniFi zelf al bijhoudt: geen NetFlow, geen GeoIP-database en geen extra software nodig.
- **Patronen:** per apparaat de favoriete AP, hoe lang het op elke AP zat en wanneer het verbonden is (per uur van de week); per access point hoe druk elk kanaal is per uur van de week.
- **Pagina's** voor apparaten (radio's, poortenraster, PoE, historie), clients (signaal, retries, ervaring en roaming per apparaat), beveiliging (IPS en wat er openstaat naar internet) en een tijdlijn met gebeurtenissen.
- **Probleemoplossing:** één knop kopieert de versie, het controllertype en de laatste fouten, zonder adressen, namen of sleutels, zodat je die in een GitHub-issue kunt plakken.
- **Demomodus** met een nagebootst netwerk, zodat je zonder controller kunt rondkijken.

## Screenshots

Alle screenshots tonen de ingebouwde demodata.

| | |
|---|---|
| ![Issues met uitleg en advies](docs/screenshots/issues.png) | ![Client die na een AP-herstart op een verre AP blijft hangen](docs/screenshots/client-detail.png) |
| **Issues:** elke melding met uitleg en advies, gegroepeerd op oorzaak | **Clientdetail:** de Kindle bleef na een herstart van AP Boven hangen op de verre AP Schuur |
| ![Access point met radio's en kanaalbezetting](docs/screenshots/ap-detail.png) | ![IPS-blokkades en wat er openstaat naar internet](docs/screenshots/beveiliging.png) |
| **Access point:** dekkingsprobleem, radio's, kanaalbezetting en historie | **Beveiliging:** wat de IPS tegenhield en welke poorten openstaan, met het aantal aanvallen per poort |
| ![Live internetverkeer en speedtest](docs/screenshots/internet.png) | ![Patroon van een telefoon: favoriete AP en wanneer verbonden](docs/screenshots/patronen.png) |
| **Internet:** live verkeer en een speedtest vanaf de gateway | **Patronen:** favoriete AP en wanneer een apparaat thuis is |
| ![Wereldkaart met verbindingen per land](docs/screenshots/wereld.png) | ![Meldingen versturen naar ntfy](docs/screenshots/meldingen.png) |
| **Wereld:** met welke landen je netwerk praat, live | **Meldingen versturen** naar je telefoon, Home Assistant of Discord |
| ![Setup-wizard bij eerste gebruik](docs/screenshots/wizard.png) | <img src="docs/screenshots/mobiel.png" alt="Overzicht op een telefoon" width="260"> |
| **Setup-wizard** bij de eerste start | **Ook op je telefoon** |

## Wat je nodig hebt

- Een UniFi-console met de **Network**-app: Dream Machine, Dream Router, Cloud Gateway (UCG), Cloud Key Gen2+ of de zelf-gehoste **UniFi OS Server**.
- Een **API-key**: in UniFi Network via *Instellingen → Control Plane → Integrations → Create API Key*.
- Een kleine Linux-machine die altijd aan staat, bijvoorbeeld een **Proxmox-LXC**, een Raspberry Pi of een andere Debian/Ubuntu-machine. Het gebruikt ongeveer 50 MB geheugen.

Geeft je API-key alleen beperkte gegevens (geen signaal of retries per client)? Dan kun je in de wizard onder *Geavanceerd* ook een lokaal UniFi-account met **View Only**-rechten opgeven.

## Installeren

### Proxmox (aanbevolen)

Draai dit op je **Proxmox-host**, in de shell van de node:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/lexi1986/unifi-sonar/main/scripts/proxmox-lxc.sh)"
```

Het script vraagt een paar dingen, zoals de container-ID, het IP-adres (DHCP of vast) en de opslag. Op alles kun je Enter drukken voor de standaardwaarde. Daarna maakt het een kleine Debian-container aan (1 core, 512 MB, 4 GB), installeert UniFi Sonar erin en toont het adres.

### Debian, Ubuntu of Raspberry Pi OS

```bash
curl -fsSL https://raw.githubusercontent.com/lexi1986/unifi-sonar/main/scripts/install.sh | sudo bash
```

Standaard draait het dashboard op poort 80. Wil je een andere poort, dan zet je `PORT=8080` vóór `bash`:

```bash
curl -fsSL https://raw.githubusercontent.com/lexi1986/unifi-sonar/main/scripts/install.sh | sudo PORT=8080 bash
```

### Eerste keer openen

Ga naar `http://<ip-van-de-machine>`. De **setup-wizard** vraagt:

1. het adres van je UniFi-console. Poort 443 en 11443 (UniFi OS Server) worden allebei geprobeerd.
2. je **API-key**.

De wizard test de verbinding, laat zien wat hij vindt (gateway, aantal apparaten en clients) en start daarna met meten. Na een paar minuten verschijnen de eerste meldingen; na een dag historie zijn ze het nauwkeurigst.

### Meldingen op je telefoon

Onder *Instellingen → Meldingen versturen* (het tandwiel rechtsboven) voeg je een kanaal toe:

- **Home Assistant:** maak een automatisering met als trigger *Webhook* en plak de webhook-URL. In de automatisering gebruik je `trigger.json.title`, `trigger.json.message` en `trigger.json.severity`, bijvoorbeeld voor een melding via de Companion-app.
- **ntfy:** installeer de ntfy-app, abonneer je op een topic met een lastig te raden naam en vul `https://ntfy.sh/<topic>` in (of je eigen ntfy-server, eventueel met toegangstoken).
- **Discord** of **Slack:** maak een webhook aan in het kanaal en plak de URL.
- **Eigen webhook:** krijgt JSON met `event`, `severity`, `title`, `message`, `url` en `key`, handig voor n8n of Node-RED.

Met *Testbericht sturen* zie je direct of het aankomt. Wat al openstond toen je het kanaal toevoegde, wordt niet alsnog verstuurd.

## Bijwerken

Je instellingen en historie blijven bij bijwerken altijd staan.

**In een Proxmox-container:** open de console van de container en typ:

```bash
update
```

Het commando kijkt of er een nieuwe versie op GitHub staat, laat zien wat er veranderd is en werkt alles bij. Bij het inloggen in de container zie je ook welke versie draait en op welk adres. Vanaf de Proxmox-host kan het ook:

```bash
pct exec <container-id> -- update
```

**Op Debian, Ubuntu of een Raspberry Pi:**

```bash
sudo unifi-sonar-update
```

Met `--check` kijk je alleen of er een update is; met `--force` installeer je opnieuw, ook als je al de nieuwste versie hebt. De poort die je bij het installeren koos, blijft behouden.

Heb je UniFi Sonar geïnstalleerd vóór versie 1.2? Draai dan één keer het installatiecommando opnieuw (of `pct exec <container-id> -- bash /root/install-unifi-sonar.sh`). Daarna is `update` beschikbaar.

## Privacy en veiligheid

- Alles blijft op je eigen machine. Er gaat niets naar internet, behalve het downloaden van de software bij installeren en bijwerken, en de meldingen naar de diensten die je zelf instelt.
- UniFi Sonar **leest alleen**: het verandert geen instellingen in UniFi. De enige acties zijn *Opnieuw verbinden* voor één wifi-apparaat en een speedtest op de gateway starten.
- De API-key en de webhook-adressen staan alleen in `/var/lib/unifi-sonar/config.json`, en alleen de service kan dat bestand lezen. De browser krijgt de sleutel nooit terug en ziet van webhook-adressen alleen het begin.
- Het dashboard heeft **geen login**. Iedereen in je netwerk die het adres kent, kan meekijken, meldingen negeren en een wifi-apparaat opnieuw laten verbinden. Zet het daarom niet open naar internet.
- Het dashboard antwoordt alleen op een IP-adres, `localhost` en lokale namen (`.local`, `.lan`, `.home`, `.internal`, `.home.arpa`). Zo kan een website die je bezoekt het dashboard niet via je browser aansturen (DNS-rebinding). Acties vanaf een andere website worden ook geweigerd. Gebruik je een eigen hostnaam of een reverse proxy, voeg die dan toe onder *Instellingen → Toegang*, of zet `Environment=ALLOWED_HOSTS=sonar.mijndomein.nl` in de service.
- De koppeling wijzigen kan alleen als je de huidige API-key invult.
- Voor de wereldkaart bewaart UniFi Sonar de verbindingen uit het verkeerslogboek van UniFi (welk apparaat met welk domein en land praatte) **48 uur** in de lokale database. Daarna worden ze verwijderd.
- Gebruik je de IPS van je UniFi-gateway en kijk je via een VPN? UniFi Sonar gebruikt bewust geen HTTP `DELETE`, omdat de IPS dat als aanval kan zien (regel 2101603).

## Drempels aanpassen

De standaardwaarden staan in [`app/config.py`](app/config.py) en zijn afgestemd op een gewoon thuisnetwerk. Overschrijven kan per drempel:

```bash
sudo systemctl edit unifi-sonar
```

Zet daarin bijvoorbeeld:

```ini
[Service]
Environment=TH_CLIENT_RETRY_WARN=30
Environment=TH_CLIENT_SIGNAL_WARN_24=-78
```

Daarna `sudo systemctl restart unifi-sonar`.

## Verwijderen

```bash
sudo systemctl disable --now unifi-sonar
sudo rm -rf /opt/unifi-sonar /var/lib/unifi-sonar /etc/systemd/system/unifi-sonar.service
sudo userdel unifi-sonar
```

Of verwijder in Proxmox gewoon de container.

## Ontwikkelen

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8088   # wizard → "Eerst rondkijken met demodata"
.venv/bin/python -m pytest -q
```

| Map/bestand | Rol |
|---|---|
| `app/unifi_client.py` | Uitlezen van UniFi OS (uitgebreide API, officiële API, IPS-flows) en één datamodel |
| `app/collector.py` | Elke minuut meten, delta's berekenen (retries, fouten, throughput), events |
| `app/rules.py` | Alle meldingen, groepering op oorzaak en scores |
| `app/notify.py` | Meldingen versturen (Home Assistant, ntfy, Discord, Slack, webhook) |
| `app/setup.py` | Verbindingstest voor de wizard |
| `app/mock.py` | Nagebootst netwerk met ingebouwde problemen (demomodus) |
| `web/` | Dashboard (vanilla JS, geen build-stap) |
| `web/world.js` | Landsgrenzen voor de wereldkaart, gemaakt met `tools/make_world.py` uit Natural Earth |
| `scripts/` | Installeren (Linux, Proxmox), bijwerken (`update.sh`, wordt het commando `update`) en `dev-deploy.sh` om lokale code naar een test-LXC te zetten |

Ideeën en verbeteringen zijn welkom via issues en pull requests. Plak bij een probleem de debug-info uit *Instellingen → Probleemoplossing*.

Een aantal ideeën is geïnspireerd door [Network Optimizer](https://github.com/Ozark-Connect/NetworkOptimizer), [UI Toolkit](https://github.com/Crosstalk-Solutions/unifi-toolkit) en [Lagezentrum (unifi-HQ)](https://github.com/ProfessorQuantumUniverse/unifi-HQ); er is geen code van overgenomen. De landsgrenzen komen van [Natural Earth](https://www.naturalearthdata.com) (publiek domein).

## Licentie

[MIT](LICENSE)
