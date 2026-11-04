# Ändringar

## 1.2.3 (2026-11-04)
- **Utan spabad syns inget spabad** (#122, #123): ingen spa-bevakning, inga "spabad frånkopplat"-meddelanden och inga
  spabeslut när inget spa är valt. Översiktens bild visar bara installationens bilar och spa.
- **Välj vilken telefon som får aviseringarna** under Inställningar (#123) - förut den första telefonen i HA.
- **Husets förbrukning räknar med batteriet** (#125): sol + nät - batteri, i översikten och historiken.
- **System-fliken**: inget fel när Watchtower saknas (#121) - visar hur man uppdaterar i stället.
- Motorn: bilar och laddboxar läses helt ur installationen (inga inbyggda bilar kvar).

## 1.2.2 (2026-11-04)
- **NIBE S1155/S1255 via pumpens lokala REST-API** (tack lazgeo, #115): läser temperaturer och kompressorstatus,
  certifikatet kontrolleras innan lösenordet skickas. Styrning är avstängd tills man slår på den. Se docs/nibe-local-rest.md.
- En felaktig inställning för en enhet stoppar inte längre hela motorn: felet loggas och motorn kör vidare utan just den enheten.

## 1.2.1 (2026-11-04)
- **Nätet visades fel med Tibber Pulse när man säljer solel** (#114): pulsens fasström saknar tecken, så export syntes
  som köp. Har pulsen köp- och säljeffekt används de nu; installationen hittar dem själv.
- **Loggningen föll varje minut** med en generisk värmepump (`invalid input syntax for type smallint: "auto"`, #112).
- **Elbil-sidan visade Tesla och Nissan** för alla (#113): bilarna kommer nu från installationen, i webben och appen.
- Mobilappen startade inte efter 1.2.0 i vissa fall (pymodbus) - rättat. Lås/luckor i webben fungerar igen.

## 1.2.0 (2026-11-04)
- **Öppna webbgränssnittet fungerar inuti Home Assistant** (Ingress, issue #118): även via Nabu Casa, https och HA-appen,
  och HA:s inloggning gäller. EnergyWizard får en egen panel i sidomenyn.
- Nya installationer kraschade på loggningen varje minut (`temp_garage`) och skickade aviseringar till fel telefon - rättat.
- Givare inne/ute, bilar, laddboxar och telefoner väljs i installationen; inget är inbyggt för ett visst hus.
- Två växelriktare/batteribankar räknas som ett batteri; fritt val av elmätare.
- Tidstariff, Solax Gen2, HeishaMon-paus via kurvan, telemetri med fel som blir GitHub-ärenden.
- Robotgräsklipparen är borttagen.

## 1.1.0
- Startskriptet med samma mapplayout som bilden.
