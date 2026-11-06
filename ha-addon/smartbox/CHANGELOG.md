# Ändringar

## 1.2.13 (2026-11-06)
- **Färre falsklarm**: tillfälliga nätverksfel (Home Assistant eller väderprognosen svarade inte en stund) är
  varningar, och på Installationer visas de grått för sig – bara riktiga fel visas i rött.
- FTW-drivrutinerna provas automatiskt mot Sourcefuls enhetssimulator vid varje ändring (Sungrow: läsning och
  styrning fungerar; sju av åtta läser rätt).

## 1.2.12 (2026-11-06)
- **NIBE lokalt REST fungerar mot riktiga pumpar** (#145, felanalys av larsfrisk): läsningen kraschade med "Bad file
  descriptor" när pumpen stängde anslutningen efter svaret. Tomt produktnamn (S1255) godtas och modellens register
  väljs, felets typ syns i loggen, och varmvattentemperaturen läses för alla värmepumpar (inte bara Thermia).
- **Bilens faser och maxström lärs in** av laddningarna när installationen inte anger dem.
- **Installationsguiden**: batteri eller växelriktare utan Home Assistant-integration kan väljas via en FTW-drivrutin.
- **Skyline**: avläsningen ligger ovanför staden, höjden anpassas efter huset, billigaste och dyraste timmen märks,
  och soluppgången syns på natten.

## 1.2.11 (2026-11-06)
- **Gästbil** (#131): ladda en bil som inte är din på valfri laddbox – ange kWh och ev. klar-tid i appen (Bil → Gästbil),
  så laddas de billigaste timmarna fram till dess, alltid under säkringen. Avslutas när kabeln dras ur.
- **Effektavgift efter månadens högsta timmar** (#141): för Norges effektledd och nätbolag som tar betalt efter snittet
  av de högsta timmarna i trappsteg (Elförbrukning → Effektavgift efter högsta timmar).
- **Fler batterier kan styras**: färdiga förinställningar för GoodWe, SolarEdge med batteri, Sungrow (mkaiser),
  Huawei LUNA2000, Tesla Powerwall och Enphase – installationsguiden fyller i dem själv. Kör i skuggläge först.
- **Sourcefuls FTW-drivrutiner** (`driver: ftw`): 93 drivrutiner för växelriktare, batterier och mätare som läser
  direkt från enheten utan Home Assistant-integration (t.ex. Pixii). Läsande; styrning slås på per verifierad enhet.
- **Batteriet säljer aldrig när export är avstängd**: urladdningen begränsas till det huset köper.
- Huawei-batterier hittas av installationsguiden (räknades förut som en telefon), och en Powerwall tas inte för en bil.

## 1.2.10 (2026-11-05)
- **Planvyn Skyline** överst på förstasidan i appen och på webben (förvald), med planklockan som val. Dygnet som en
  stad: högt hus = dyr el, tända fönster = huset använder el, solen över staden, bilarna på vägen, batteriet i vattnet.
- **Besparingen räknas mot ett vanligt hushåll** (toppar morgon och kväll) och inklusive moms, i appen, på webben och
  i HA-sensorn. Rättvisare än det tidigare jämna dygnssnittet.
- **Färre falska fel**: en enstaka timeout mot Home Assistant är en varning (fel först efter tre i rad), och loggen
  visar rätt källa och felförloppet en gång.
- Appen: "alla rum" fungerar, raderna i "vad görs nu" ligger i linje, rätt moms i appens priser.
- Webben: landet syns på varje installation, dygnsgrafen är läsbar i mobilen.

## 1.2.9 (2026-11-05)
- **Laddschemat för hela veckan på webben** (#142): Elbil-fliken har en rad per veckodag (som appen), en knapp för
  samma schema alla dagar, och visar vilket mål planen räknar med just nu ("fredag 07:00 · 100 %"). Översikten
  skriver veckodagen.
- **Planklockan på förstasidan** i appen och på webben: en kvart per streck, färg när batteri eller bil gör något,
  solprognosen som krans, dra visaren för att se pris och plan vid valfri tid, och de närmaste 12 timmarna under.
- **Graferna i appens Historik** har tunna linjer och en skala (förut breda band utan värden).
- **Sourcefuls FTW-drivrutiner kan köras** (lua_host.py): alla 54 host-funktioner finns, 91 av 93 drivrutiner startar
  (de två sista kräver inloggning/nyckel). Verifierad mot en riktig Shelly 3EM. Inte inkopplad i motorn än.

## 1.2.8 (2026-11-05)
- **Logg för hela installationen**: allt EnergyWizard läser in, bestämmer (med orsak), skickar till enheterna,
  aviserar och får för fel - från motorn, appen och webben. Webben: sidan Logg (filter, sök, ladda ner 2 dygn som
  supportfil att bifoga i en issue). Appen: Inställningar → Logg. Sparas i ditt hus i 14 dygn, bara ägaren ser den.
- **Bilens värme visas inte som "på" när man kör**: klimatet räknas som förvärmning bara när bilen står hemma och
  inte är i körläge (`shift_state` om bilen har det).

## 1.2.7 (2026-11-05)
- **Inga bilnamn, rum eller personer från ett annat hus**: laddschemat och klimatschemat byggs av dina egna bilar
  (förut fasta "nissan"/"tesla" - andra bilars scheman kunde ignoreras), rummen är dina valda innegivare,
  hälsningen använder bara namn och fraser du själv lagt in, och "Visa som familj" i stället för ett namn.
- **Hushållsmaskiner** (t.ex. tvättmaskin) väljs i installationen (`appliances`), inget fast märke.
- Attributen i Home Assistant (elbil solel) heter efter dina bilar.

## 1.2.6 (2026-11-05)
- **Varning när husbatteriet inte gör som det blir tillsagt**: avviker batteriet från kommandot i mer än 5 minuter
  (t.ex. laddar fast det ska ladda ur) syns en röd ruta i appen och på webben, och en notis skickas.
- **Alla notiser går att stänga av** per kategori (elbil, batteri, sol, värmepump, spabad, elpris, effekt, lampor,
  system, övrigt) under Inställningar → Notiser, på webben och i appen.
- **Egen färg när batteriet laddar ur och säljer** till nätet, skilt från urladdning för eget bruk.
- Upptäckten föreslår inte batteri för en växelriktare som saknar batteri (0 % och 0 W).

## 1.2.5 (2026-11-05)
- **Inga främmande lampnotiser** (#134): appen bevakade och styrde lampor som inte hör till ditt hus. Nu bara lampor du
  själv valt; utan val syns inga lampknappar. "Exportgräns offline" larmar bara om växelriktaren går att begränsa.
- **Husets förbrukning** (#139): batteriets och elmätarens effekt räknas om från kW till W enligt sensorns enhet. Blir
  huset ändå kraftigt negativt visas 0 och loggen säger vilken givare som ser fel ut.
- **Tidslinjen visar bara dina bilar** (#136), med rätt namn, och Spabad/Värmepump bara om de finns.
- **Generisk laddbox (t.ex. Garo) ger laddeffekt** (#140): `power_kw` eller `power` används i översikt, tidslinje och
  basförbrukning.
- **NIBE lokalt REST i tillägget** (#138): användarnamn, lösenord och certifikat-pin går att fylla i under Konfiguration.
- **Spabad (Gecko), SolarEdge och väder** läses ur installationen - inga entitetsnamn från ett annat hus i koden.

## 1.2.4 (2026-11-05)
- **Tillägget hämtar alltid senaste koden**: förut kunde Home Assistant återanvända en gammal byggd kopia trots ny version
  (därför syntes vissa rättningar, t.ex. #125, inte förrän man byggde om själv).
- **Installationsguiden sparar även när en vald enhet saknar givare** (#127) - förut "'NoneType' object has no attribute 'get'".
- **Inne-/utetemperatur utan värmepump** (#128): de valda givarna används även när ingen värmepump styrs, utetemperaturen
  tas från den valda utegivaren om pumpen inte har någon, och Temperaturer-sidan visar dina valda rumsgivare.
- **Huvudsäkringen från installationen** (#129): `fuse.main_fuse_a` används i stället för standardvärdet 25 A.
- **Fasströmmar i ampere** (#130) på Elförbrukning, skalade mot huvudsäkringen - gul från 80 %, röd över säkringen.

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
