# Roadmap

Inte löften om datum - bara vad som är nästa rimliga steg och varför, så det är
tydligt vad som redan är beslutat och vad som väntar på mer underlag.

## Övervägs, väntar på fler verkliga hus att verifiera mot

- **Automatiserade laddnings-/urladdningsbeslut för husbatteri.** Ett riktigt
  elbatteri är snabbt och konkurrerar direkt med sol/nät/elbilsladdning om
  samma watt - en genuint annan optimeringsfråga än husets termiska tröghet
  som redan styrs idag, och ingen betatestare har ännu ett riktigt batteri
  att verifiera besluten mot. `gpm.py` fattar därför medvetet INGA beslut om
  batteriet än. **Drivrutinslagret finns dock redan** (`drivers/battery.py`/
  `battery_generic.py`, upptäcks av entitetsväljaren) - läser SOC/effekt och
  kan sätta ett läge via valfri `select`-entitet, samma generiska
  entitetsstyrning som [Predbat](https://github.com/springfall2008/batpred)
  själv bygger på. Kör gärna Predbat parallellt tills vidare - se
  [kunskapsbanksartikeln](https://murre87.github.io/energywizard/kunskapsbank/husbatteri.html).

  **Predbat, inte [FTW](https://github.com/srcfl/ftw), är referensen för
  själva batteribeslutslogiken** den dagen det byggs: Predbat kör inuti Home
  Assistant (samma plattform vi redan kräver), har redan verifierat stöd för
  GivEnergy/Solis/Huawei/SolarEdge/Sofar/Tesla Powerwall m.fl., och är
  betydligt mer moget (365 stjärnor, 5 391 commits) än FTW (22 stjärnor,
  övergivna 2.x/3.x-linjer). FTW:s enda bidrag hit är ett specifikt, smalt
  mönster: dess opt-in-skrivväg för batteri/solöverskott har en dead-man
  switch (slutar skriva om den inte hör av sig), en tydlig återgång till
  standardläge, och en uppstarts-sweep som städar bort gamla/föräldralösa
  kommandon - värt att återanvända som skyddsnät oavsett vems beslutslogik
  `gpm.py` till slut bygger på.

  **Princip, gäller alla externa projekt vi tittar på, inte bara batteriet:**
  vi ska luta oss mot redan underhållen kod (Predbat, HA:s egna
  integrationer) så mycket som möjligt istället för att bygga och underhålla
  en egen optimerare - minimal egen kodyta, inte en konkurrerande
  implementation. Vi bygger INTE en egen batterioptimerare som konkurrerar
  med Predbats - målet är att komplettera den, inte ersätta den.

  **Koordinering med Predbat, redan utredd:**
  - ~~Steg 1, läs Predbats batterieffekt in i solöverskottsberäkningen~~ -
    **redan löst av arkitekturen, inget att bygga.** `gpm.py`:s
    `avg_net_w` (styr all solöverskott-logik: elbilsladdning, spabad,
    husvärme) kommer från Tibber Pulse och mäts VID HUVUDSÄKRINGEN
    (`homeassistant.read_tibber_data()`, P=U×I på alla tre faser) - alltså
    EFTER att batteriet redan tagit sin del. Om Predbat laddar batteriet
    från solöverskottet syns det automatiskt som mindre överskott i
    `avg_net_w`, utan att vi behöver läsa batteriets effekt separat. Ingen
    dubbelräkning existerar, eftersom vi aldrig räknar fram överskott från
    solproduktionen i sig - vi mäter den riktiga nettosiffran vid mätaren.
    Enda kvarvarande teoretiska risk: två oberoende system kan reagera på
    samma momentana överskott i samma ögonblick - en generell racing-fråga,
    dämpad redan idag av `gpm.py`:s rullande medelvärde (`avg_net_history`).
  - **Steg 2, samplanering - exportsensorn byggd, overifierad mot riktig Predbat.**
    `sensor.smartbox_planerad_last` (`smartbox/planned_load.py`, publiceras av
    `ha_publisher.py`) har elbilens laddplan i attributet `predbat`, i det format
    Predbats `load_forecast` läser: `{tidsstämpel med tidszon: stigande kWh}`.
    Formatet är kontrollerat genom att läsa Predbats källkod
    (`apps/predbat/fetch.py`: `fetch_extra_load_forecast` + `get_from_incrementing`),
    inte gissat. Varje 15-minutersslott får en punkt vid start och slut, så att
    Predbats utjämning inte smetar ut energi över luckorna. Bara elbilen ingår,
    eftersom värmepump och spabad inte har någon plan framåt. Konfiguration och
    dubbelräkningsrisken (`car_charging_hold`) står i
    [kunskapsbanksartikeln](https://murre87.github.io/energywizard/kunskapsbank/husbatteri.html).
    8 tester (`tests/test_planned_load.py`). Aldrig kört mot en riktig
    Predbat-installation: ingen betatestare med batteri + Predbat än.

- **OCPP-laddare via Home Assistants egen OCPP-integration - kod+regex klar,
  overifierad mot riktig laddare.** [lbbrhzn/ocpp](https://github.com/lbbrhzn/ocpp)
  (HACS, mogen, stödjer 1.6J/2.0.1/2.1) kör OCPP-servern inuti Home Assistant
  och exponerar en `switch` (`*_charge_control`) + `number`
  (`*_maximum_current`) - samma entitetsformer `GenericChargerDriver` redan
  läser/skriver. `smartbox/discovery.py` matchar nu entitets-ID:ets suffix
  (inte märkestext - laddarens egen tillverkarsträng, inte "OCPP", syns i HA)
  och föreslår `generic`-drivrutinen automatiskt, med ett nytt regressionstest
  (`tests/test_discovery.py`). Mockat/syntetiskt verifierat, ALDRIG kört mot
  en riktig OCPP-laddare.

- **Exportstyrning för fler växelriktare - byggd, overifierad mot riktig hårdvara.**
  Via redan underhållna HA-integrationer, ingen egen protokollkod (se
  [kunskapsbanken](https://murre87.github.io/energywizard/kunskapsbank/vaxelriktare.html)):
  Growatt (0xAHA/Growatt_ModbusTCP, gräns i % - fungerade redan med
  `generic_number`), Sungrow (mkaiser Modbus-paket, gräns i W + lägesbrytare -
  `generic_number` räknar nu om % till W), Huawei (wlcrs/huawei_solar:s tjänster,
  bekräftade mot integrationens `services.yaml`/`services.py` -
  `drivers/solar_huawei.py`) och Fronius (HA:s inbyggda `modbus.write_register`,
  WMaxLimPct/WMaxLim_Ena - `drivers/solar_modbus_register.py`; registeradresserna
  är omdiskuterade i communityn, därför konfigurerbara). Entitetsväljaren föreslår
  nu bara en %-gräns som %-gräns (tidigare kunde en W-gräns få värdet 0-100 och
  strypa exporten till ~100 W), en W-gräns som `export_limit_w`, och Huawei-
  drivrutinen med växelriktarens enhets-ID. 19 mockade tester (17 drivrutin, 2 entitetsväljare).

- **Fler värmepumpsmärken** (IVT, CTC, Mitsubishi, Viessmann m.fl.) -
  arkitekturen (`smartbox/drivers/heatpump.py`) är byggd för det, men varje
  märke kräver en egen, verifierad implementation - bidrag välkomna.

- **NIBE S-serie: drivrutin byggd, overifierad mot riktig hårdvara.**
  `drivers/heatpump_nibe_local.py` (`nibe_local` i
  `HEAT_PUMP_DRIVER_REGISTRY`) pratar S-seriens (S735/S1255/S1155/S320 m.fl.)
  lokala REST-API - HTTPS-port 8443, Basic-auth, certifikatet PINNAS (SHA-256-
  fingeravtryck, TLS-verifiering stängs aldrig av) - byggd mot
  [srcfl/ftw](https://github.com/srcfl/ftw)s
  [nibe-local-dokumentation](https://github.com/srcfl/ftw/blob/master/docs/nibe-local.md)
  och den faktiska drivrutinskällan (`srcfl/device-drivers`), inte gissad.
  **Ärlig avgränsning:** bara anslutning/enhetsidentifiering + en rå
  datapunktsläsning är bekräftad mot källan - vi har INGEN bekräftad karta
  mellan våra normaliserade fält (`indoor_temp`/`outdoor_temp`/driftläge) och
  NIBE:s faktiska registernummer för dem (källan dokumenterar bara register
  2107/2109, en solöverskott-funktion, inget annat). `read_sensors()`
  returnerar därför bara rådata (antal datapunkter), och ALLA
  `set_*`-metoder returnerar medvetet `False` - exakt samma princip som
  `GenericClimateHeatPumpDriver` redan använder för Husdatas
  registernivå-funktioner. Ansluts via `.env` (`NIBE_LOCAL_HOST`/
  `_USERNAME`/`_PASSWORD`/`_TLS_PIN_SHA256`), inte auto-upptäckt av
  entitetsväljaren (den pratar direkt med pumpen, aldrig via HA - samma skäl
  som Husdata/Thermia inte är HA-upptäckt). Mockade tester bevisar att koden
  anropar rätt endpoints med rätt fält - ALDRIG kört mot en riktig pump. Har
  du en NIBE S-serie-pump? Hör av dig, det är precis den sortens verkliga
  installation som behövs för att identifiera de saknade registren och
  bekräfta resten.

- **NIBE/Bosch/Atlantic/Daikin via myUplink - drivrutin byggd, aldrig körd mot
  ett riktigt konto.** `drivers/heatpump_myuplink.py` pratar med NIBE:s delade
  molnplattform myUplink, som enligt
  [FTW:s enhetskatalog](https://srcfl.github.io/device-drivers/drivers.json)
  även används av Bosch, Atlantic och Daikin - EN drivrutin täcker alltså
  flera märken. **Bekräftat mot myUplinks officiella OpenAPI-spec**
  (`https://api.myuplink.com/swagger/docs/public-v2/swagger.json`): bas-URL,
  `GET /v2/systems/me`, `GET`/`PATCH /v2/devices/{deviceId}/points`,
  token-URL, scopes READSYSTEM/WRITESYSTEM, och `ParameterData`-fälten
  (parameterId/parameterName/value/writable/min/max). **PATCH-kroppens form**
  (`{"<parameterId>": "<värde som sträng>"}`) är bekräftad via två oberoende
  community-rapporterade riktiga anrop (en Home Assistant- och en
  openHAB-issue), inte direkt citerad ur spec-filen - ett steg svagare källa
  än allt annat i drivrutinen, dokumenterat i modulens docstring.

  Genuint annan autentisering än resten av EnergyWizard: specens
  säkerhetsschema heter missvisande "Client Credentials", men en riktig,
  fungerande klient (home-assistant-myuplink) bekräftar att en INTERAKTIV
  webbläsarinloggning + samtycke krävs EN gång. `scripts/myuplink_authorize.py`
  gör det engångssteget och skriver ut en `refresh_token` att lägga i `.env` -
  headless därefter (ingen webbläsare behövs för normal drift). Som NIBE-lokal
  gissar drivrutinen inte på vilket parameterId som betyder vad för ett visst
  märke - användaren konfigurerar själv `heat_pump.entities` i
  `house_config.yaml` med parameterId:n hen hittar via `GET
  /v2/devices/{deviceId}/points`. 9 mockade tester, grönt - **aldrig körd mot
  ett riktigt myUplink-konto**, inget hus i projektet har ett.

- **Balboa-spabad: drivrutin byggd, väntar på verifiering mot riktig
  hårdvara.** `drivers/spa_balboa.py` finns nu - byggd mot HA:s officiella
  `balboa`-integrations DOKUMENTERADE entitetsformer (climate/select/switch/
  fan), inte en gissad protokolltolkning som den tidigare Gecko-genvägen var.
  Fortfarande aldrig körd mot ett riktigt Balboa-system (bara mockade
  tester) - har du ett Balboa-spabad? Hör av dig, det är precis den sortens
  verkliga installation som behövs för att bekräfta den.

- **Delad ML-modellträning på poolad data** från flera hus (bättre solprognoser,
  prismönster). **Telemetrilagret finns nu, är publikt nåbart och PÅ SOM
  STANDARD** (`smartbox/telemetry.py` - skickar bara hashad husidentifierare,
  aktiva drivrutinkategorier, feltyp och version, ingen sensorhistorik;
  `TELEMETRY_OPT_IN=false` stänger av helt). Beslutat 2026-11-01: tidigare
  strikt opt-in (av som standard), ändrat till på som standard för att faktiskt
  samla in data från fler installationer. På
  `https://energywizzard.profitalgos.com/telemetry` (standard i
  `.env.example`), med en reservväg via `ha-gateway`
  (`murrehtpc.axfors.se:8198/telemetry/`, overifierad utifrån - kräver
  portvidarebefordran i routern om den ska användas). Själva den poolade
  modellträningen är fortfarande inte byggd - det här är bara grunden som
  data kan börja samlas på.

- **EMHASS ([emhass.readthedocs.io](https://emhass.readthedocs.io/en/latest/),
  [GitHub](https://github.com/davidusb-geek/emhass)) som ett valfritt,
  framåtblickande planeringslager vid sidan av EnergyWizards egen, reaktiva
  motor.** Genuint annan ansats, inte en duplicerad bit: EMHASS löser ett
  riktigt LP-optimeringsproblem (pris-/solprognos → optimalt schema framåt),
  medan `gpm.py` fattar minut-för-minut-beslut utifrån nuläget. EMHASS saknar
  helt elbilsladdning, spabad och direkt Modbus-styrning (pratar bara med
  HA:s entiteter/tjänster) - skulle alltså komplettera, inte ersätta, det
  EnergyWizard redan gör. Inget konkret utkast än - en idé värd att utforska,
  inte ett beslutat nästa steg.

## Redan klart

- **"Lägg till i Home Assistant"-knapp för Supervisor/HAOS-användare**
  (`ha-addon/smartbox/`, `repository.yaml`, samma `my.home-assistant.io`-
  genväg som [EMHASS](https://github.com/davidusb-geek/emhass)). Sedan 1.1.0
  paketeras även `webdashboard` (port 8503) och `ewapp` (port 8502) i samma
  container, inloggade med tilläggets `dashboard_password`, så engångs-notisen
  om tom konfiguration pekar nu på en adress som finns. Tilläggets inställningar
  läses nu också in från `/data/options.json` (tidigare lästes de aldrig, så
  telemetrireglaget hade ingen effekt). Postgres bundlas lokalt i
  tilläggscontainern (ett enkelt startskript, inte s6-overlay - dokumenterat
  avsteg i Dockerfile-kommentaren). **Verifierat:** startskriptet kört med
  bildens mapplayout (Postgres, motor, båda gränssnitten, inloggning, intern
  proxy webdashboard→ewapp, omstart av kraschat gränssnitt), och bilden byggs
  och röktestas i CI (`tester.yml`, jobbet `ha-tillagg`). **Overifierat:** har
  aldrig körts mot en riktig HAOS/Supervisor-installation - "Lägg till
  repository"-flödet, Supervisorns egen validering av `config.yaml`, och den
  riktiga `homeassistant_api`-proxyn är alla otestade här. Gränssnitten går via
  egna portar, inte HA:s ingress/sidomeny.

- **Termisk säkringsmodell för effektvakten - byggd, mockat verifierad, inte
  körd i ett riktigt hus än.** `smartbox/fuse_guard.py` följer
  [FTW:s `safety.md`](https://github.com/srcfl/ftw/blob/master/docs/safety.md):
  varje fas I² lågpassfiltreras med 60 s tidskonstant (Tibbers 10-sekundersprov),
  bilarna stryps när den filtrerade strömmen går över säkringen - eller direkt i
  10-sekundersloopen när en avläsning går över 1,2 × säkringen - och en laddande bil
  får bara öka när ökningen ryms, aldrig inom 20 s efter en strypning. En kort topp
  (vattenkokare, ugn) stryper alltså inte längre bilen. Ersätter den gamla formeln
  "säkring - husets minutsnitt" på alla fyra ställen i `gpm.py` (via
  `_ev_fuse_room`). Exporterande fas stryps aldrig för. Valfri marginal:
  `fuse_safety_margin_a` (standard 0 A, samma som tidigare). **Medvetet avsteg från
  FTW:** utan färsk Tibber-data faller den tillbaka på den gamla formeln istället
  för att stoppa all laddning. 17 tester (`tests/test_fuse_guard.py`), både
  aktivering och icke-aktivering.

- **Besparingskort och planen i klartext (webdashboard, Översikt + Ekonomi).**
  Idéerna från [FTW](https://github.com/srcfl/ftw):s savings-kort och plan brief,
  egen implementation (ingen kod kopierad - FTW är AGPL). Besparingen är samma
  formel som den publika sidan, med dygn i svensk tid (`smartbox/savings.py`).
  Planen beskriver motorns egen plan: elbilens laddpass ur `ev_plan_slots` och
  värmepumpens grundläge per period enligt exakt samma prisregel som `gpm.py`
  (`smartbox/plan_brief.py`). 25 tester.

- Drivrutinsarkitektur kopplad till huvudstyrloopen (bil/laddare/värmepump/sol/spa)
  - genuint insticksbart, inte bara ett löfte.
- Entitetsväljare med auto-discovery (`webdashboard`, Inställningar-sidan).
- Publik sida med riktiga, verifierbara besparingssiffror.
- Bil-lås/luckor i webdashboard, med samma säkerhetsgräns som `ewapp`: ett eget
  `ew2`-omverifieringsflöde (lösenordet igen, 10 minuters fönster) innan
  ett lås-/luckokommando proxas vidare till `ewapp`:s riktiga Tesla-hantering
  (samma `_secure_ok`/`_unlock_fails`-spärr körs fortfarande där, bara anropad
  härifrån också) - inte en genväg runt säkerhetslagret.
