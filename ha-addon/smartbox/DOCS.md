# EnergyWizard (Supervisor-tillägg)

Kör EnergyWizards huvudmotor (`smartbox`) direkt i Home Assistant OS/Supervisor
- ingen docker-compose, ingen extern databas att sätta upp själv.

## Vad som ingår

Tillägget kör allt i en och samma container:

- **Huvudmotorn** (`smartbox`) - besluten som styr elbil, värmepump,
  solcellsexport, spabad och huvudsäkring.
- **Webdashboard** på port **8503** - dator-/surfplattevyn med
  entitetsväljaren. Knappen **Öppna webbgränssnitt** på tilläggets sida går hit.
- **Mobilappen** (`ewapp`) på port **8502** - öppna
  `http://<din-HA-adress>:8502` i mobilen och lägg den på hemskärmen.

Gränssnitten nås direkt på värdens portar, precis som i docker-compose-driften
(inte via Home Assistants sidomeny/ingress). Motorns engångs-notis om tom
konfiguration pekar därför nu rätt, mot `http://<din-HA-adress>:8503`.

## Kom igång

1. Installera tillägget.
2. Under fliken **Konfiguration**: sätt `dashboard_password`. Utan lösenord
   startas inte gränssnitten alls (det går inte att logga in med ett tomt
   lösenord) - motorn kör ändå.
3. Starta tillägget och klicka på **Öppna webbgränssnitt**. Logga in med
   användarnamn `admin` (eller tomt) och ditt lösenord.
4. Kör entitetsväljaren under **Inställningar**. Den ger dig en färdig
   `house_config.yaml` att ladda ner. Lägg den i
   `/addon_configs/<tilläggets id>_smartbox/house_config.yaml` med
   **File editor**- eller **Samba**-tillägget (eller SSH). En helt tom fil
   (bara `house_id: mitt-hus`) är också ett giltigt utgångsläge där allt bara
   blir overksamt.
5. Starta om tillägget efter att du ändrat filen.
6. Följ loggen (fliken **Log**) - samma utskrifter som
   `docker compose logs -f` ger i den vanliga driften.

Kraschar ett gränssnitt startas det om efter 5 sekunder, utan att motorn
påverkas. Dör motorn startar Supervisor om hela tillägget.

## Home Assistant-åtkomst

Tillägget pratar med Home Assistants Core API via Supervisorns egen proxy
(`homeassistant_api: true` i konfigurationen) - du behöver INTE klistra in
någon egen åtkomsttoken eller IP-adress, till skillnad från den fristående
docker-compose-driften.

## Databas

En lokal Postgres startas inuti tillägget vid uppstart och sparas i
tilläggets egen, bestående konfigurationsmapp (`/config/pgdata` i
containern) - den försvinner inte vid omstart, men är en egen databas,
skild från en eventuell Postgres du redan kör för den vanliga driften.

## Telemetri (valfritt, av som standard i tillägget)

Se huvudrepots README för exakt vad som skickas om du slår på
`telemetry_opt_in` i tilläggets inställningar. (Före version 1.1.0 lästes
tilläggets inställningar aldrig in, så reglaget hade ingen effekt.)

## Kända begränsningar

- Sidan **System** i webdashboard visar "Kunde inte nå Watchtower". Uppdateringar
  sköts av Supervisor i den här driftformen, inte av Watchtower.
- Entitetsväljaren sparar inte `house_config.yaml` själv, den ger dig en fil
  att ladda ner och lägga på plats (steg 4 ovan).

## Overifierat än

Version 1.1.0: startskriptet är kört med samma mapplayout som bilden -
Postgres initieras, motorn startar, båda gränssnitten svarar, inloggning med
`dashboard_password` fungerar, webdashboard når mobilappen internt, och ett
gränssnitt som kraschar startas om. Själva bilden byggs och röktestas
dessutom i CI (`.github/workflows/tester.yml`, jobbet `ha-tillagg`). Tillägget har
däremot
**aldrig körts mot en riktig Home Assistant Supervisor-installation** -
jag saknar en HAOS-maskin att testa "Lägg till repository"-flödet,
Supervisorns egen validering av `config.yaml`, och den riktiga
`homeassistant_api`-proxyn mot. Fungerar det inte som förväntat: öppna ett
GitHub-ärende med loggen från **Log**-fliken.
