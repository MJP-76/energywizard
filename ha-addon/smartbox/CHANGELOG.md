# Ändringar

## 1.2.33 (2026-11-06)
- **Guiden kommer ihåg dina val** (#173): vilka bilar och enheter du kryssat i, bilarnas namn och batteristorlek sparas
  när du sparar (eller laddar ner filen) och fylls i igen nästa gång, även efter en ny skanning. Förut stod guidens
  förval där igen (alla ikryssade, gissade namn).

## 1.2.32 (2026-11-06)
- **Elmätaren hittas** (#171): en Tibber Pulse med bara köp- och säljeffekt (utan spänning och ström per fas) känns igen
  av installationsguiden. I guiden kan man också välja en egen sensor för **säljeffekt**, så att export syns även när
  mätarens effektsensor bara visar köp.
- **Skuggläget** (#172) visar inte längre skrivningar till en Thermia/Husdata-pump som inte har någon adress.

## 1.2.31 (2026-11-06)
- **Försäljning visades som köp** (#171): Tibber Pulse med nyare entitetsnamn (efter hemmets namn) hittades bara via
  spänning × ström, som saknar tecken. Nu hittas Pulsens köp- och säljeffekt oavsett namn, och loggen säger vilka
  givare elmätaren använder.
- **Effektgivarnas tecken i webben**: Inställningar har reglage för att vända tecknet på nätets och batteriets effekt.
- Laddnivå "inf %" visas inte längre; ogiltiga tal (inf/nan) från Home Assistant räknas som saknade.

## 1.2.30 (2026-11-06)
- **Orimlig batterieffekt** (#139): visar batteriets effektgivare mer än ett husbatteri kan (t.ex. 18,2 kW) räknas den
  inte in i husets förbrukning, och Översikt säger att troligen fel givare valts (t.ex. energi i kWh) och var man
  väljer rätt.

## 1.2.29 (2026-11-06)
- **Aviseringar till eget skript** (#170): mottagaren av aviseringarna kan vara ett skript i Home Assistant (får
  variablerna `title` och `message`) eller vilken notify-tjänst som helst, inte bara en telefon.
- **Nya formulär på webben**: listor, fält och kryssrutor har fått samma formspråk som korten (rundade, egen pil, tydlig
  fokusring), i ljust och mörkt tema.
- **Lugnare logg när Home Assistant är nere**: motorn pausar 30 s efter ett misslyckat försök i stället för att varje
  avläsning försöker igen, felraden skrivs vid tredje försöket och sedan var tionde, och nätverksfel skrivs utan
  felspår.
- Bilens uppdateringsknapp (t.ex. Leaf) trycks i bakgrunden; att tillverkarens moln svarar långsamt är ingen varning.
- Appens felrapporter tar med var felet uppstod.

## 1.2.28 (2026-11-06)
- **Senaste skanningen visas alltid** (#168): resultatet av "Skanna mitt Home Assistant" sparas i installationen och
  visas med datum och tid när man kommer tillbaka till Inställningar, även efter att man sparat och även när Home
  Assistant-appen startat om.
- README: tydligare om solcellsexporten (#169). Vid minuspris regleras bara exporten ner till noll; över 0 kr exporteras
  överskottet som vanligt.

## 1.2.27 (2026-11-06)
- **Webben hämtar alltid senaste versionen** (#167): app.js och style.css länkas med versionsnummer. Home Assistant-appen
  på iOS kunde visa en gammal, sparad stilmall (t.ex. den grå mobilmenyn) trots att en ny version var installerad.
- **Husets förbrukning negativ** (#139): Översikt visar alltid delarna (sol + nät − batteri) när huset räknas negativt,
  så att man ser vilken givare som visar fel. Knappen för att vända batteriets tecken visas när den hjälper.

## 1.2.26 (2026-11-06)
- **Appen hoppade upp till toppen** när man scrollade (stor text): uppdateringen var 5:e sekund ritade om sidan med
  scrollen överst. Scrollpositionen behålls nu.
- **Klockan vreds av misstag** när man scrollade med fingret på den: ett lodrätt drag scrollar nu sidan, och tiden väljs
  först när man vrider eller trycker.

## 1.2.25 (2026-11-06)
- **Inga inbyggda pumpadresser** (#165): Thermia/Husdata läses bara när pumpens adress är angiven (PUMP_IP eller
  `heat_pump.connection.modbus_host`). Förut försökte motorn mot två fasta adresser och skrev ett fel varje minut hos
  den som inte har Husdata.
- **Batteriets tecken** (#166, #139): räknas husets förbrukning negativ men går ihop med omvänt tecken på batteriets
  effekt, föreslår Översikt "Vänd tecknet på batteriets effekt". Ändringen gäller direkt, utan omstart.
- **Mobilmenyn** (#164): den utfällda menyn på webben har tät bakgrund och full textfärg - var grå och svårläst i ljust tema.

## 1.2.24 (2026-11-06)
- **NIBE via myUplink hittas** (#162): entiteter med bara myUplinks parameternummer i namnet (t.ex. "Utomhustemperatur
  (40004)") känns igen, även när enheten inte heter något med värmepump. Installationsguiden sa felaktigt "Husdata
  redan ansluten" när innetemperaturen kom från rumsgivare. Det kräver nu att Husdata faktiskt är vald och att pumpen
  loggar framledning.
- **Skanningen finns kvar** (#163): resultatet av "Skanna mitt Home Assistant" ligger kvar i en timme när man byter flik
  eller när Home Assistant-appen laddar om sidan, tills man sparar.
- Priskällekortet kunde ge ett skriptfel om man bytte flik medan det laddade.

## 1.2.23 (2026-11-06)
- **Dolda flikar** (#161): webben döljer flikarna Spabad, Elbil, Värmepump och Solceller när installationen saknar den
  utrustningen (Solceller ligger kvar om det finns ett husbatteri). Egna flikar kan döljas med `ui: hidden_tabs:
  [prognos, temperaturer]` i house_config.yaml. En dold flik öppnar Översikt.
- **Batteriets effekt i flödesbilden** (#160): batterirutan på Översikt visar effekten, t.ex. "Batteri · 850 W".

## 1.2.22 (2026-11-06)
- Sponsringspåminnelsen berättar vad utvecklingen kostar (runt 1 000 € de senaste veckorna) och visas en gång till
  den här månaden, på installationens språk. Den kan som förut stängas av i inställningarna.
- Appen: sponsringsrutan visas som en ruta mitt på skärmen (låg tidigare längst ner på sidan) och går att scrolla
  med stor text.

## 1.2.21 (2026-11-06)
- **NIBE via Home Assistants myUplink-integration** (#158): ny drivrutin som läser värmepumpen via integrationens
  entiteter. Installationsguiden kopplar dem själv via NIBE:s givarkoder (BT1 ute, BT2 framledning, BT3 retur,
  BT7/BT6 varmvatten, BT50 rum) och gradminuter. För att styra väljer man rumsbörvärdet själv.
- Installationsguiden tog en nätverksskanners post för pumpens nätverkskort (t.ex. NetAlertX, "Nibe") för
  värmepumpen. Nu krävs temperaturgivare eller en climate-entitet.
- **Värmepump-flikens mätvärden** (#159): kortet "Just nu" på webben med kompressor, frekvens, el in, framledning,
  retur och COP. NIBE S1155/S1255 lokalt ger frekvens, el och uppmätt COP ur pumpens energilogg.

## 1.2.20 (2026-11-06)
- Appen med mycket stor text: när en flik måste scrolla fick planlistan på Plan-fliken bara 18 px höjd. Alla delar
  får nu sin naturliga höjd när sidan scrollar.

## 1.2.19 (2026-11-06)
- **Appens hemskärm med stor text**: med förstorad text i telefonen klipptes planklockans staplar av och sol- och
  nätrutorna kläms ihop bakom besparingsraden. Nu krymper planen stegvis, rutorna har en minsta höjd, och får det
  ändå inte plats går hemskärmen att scrolla i stället för att något göms. Provat i 411×914, 411×800 och 360×640 med
  normal och förstorad text, både klocka och Skyline.

## 1.2.18 (2026-11-06)
- **Kallt inne räknas först efter 30 minuter**: notisen "Kallt inomhus!" och värmetvånget oavsett elpris kommer
  först när det varit kallt i 30 minuter i följd. En vädring eller öppen dörr nära givarna (t.ex. 21,8 → 14,6 °C
  under några minuter) ger ingen notis och ingen dyr värme.

## 1.2.17 (2026-11-06)
- **Färdigbyggd bild**: Home Assistant hämtar tillägget som en färdig bild (amd64 och aarch64) i stället för att
  bygga det på din maskin. Uppdateringar går på någon minut och misslyckas inte längre på maskiner med lite minne.
  Den här uppdateringen är den sista som byggs på din maskin, och den kan ta en stund.

## 1.2.16 (2026-11-06)
- **Innetemperaturen räknade in utegivaren** (#149): en utegivare som var förkryssad bland innegivarna gav t.ex.
  (18,2 + 2,4) / 2 = 10,3 °C och larm om kallt hus. Utegivare räknas aldrig in i innetemperaturen. I givarlistan visas
  de som utegivare utan kryssruta, och de går inte att spara som innegivare.
- **Rumsbörvärdet till NIBE, myUplink och HA-climate** (#151): skickades i tiondelar (200 i stället för 20,0 °C) och
  avvisades. Skickas nu i °C. Thermia får exakt samma registervärde som förut.
- **NIBE lokalt** (#152): en lyckad skrivning rapporterades som misslyckad när pumpen (S1255) svarar med hela punkten.
  Ett avvisat anrop loggar nu statuskoden (t.ex. HTTP 403 när ändringar inte är tillåtna i pumpens meny 7.5.15).
- **Utan spabad** (#156): inga spabadsrader i loggen och inga anrop till spadrivrutinen.
- **Loggen live** (#154): Logg-fliken på webben uppdateras var 10:e sekund (kan stängas av).
- Pumpar som sparar börvärdet i hela grader (Thermia) fick samma börvärde omskrivet varje minut när det var en halv
  grad. Avrundningen godtas nu.

## 1.2.15 (2026-11-06)
- **Bilvärmen håller temperaturen**: när du startat värmen från appen och bilen själv stängt av klimatet kollar
  EnergyWizard 10 minuter senare. Har kupén svalnat mer än 1 °C under önskad temperatur startas värmen igen
  (högst 3 gånger, i en timme från knapptrycket, och inte om bilen kört iväg).
- **Thermia via ThermIQ** (#153): ny drivrutin för ThermIQ-MQTT/ThermIQ-ROOM via ThermIQ:s HA-integration. Den läser
  inne-, ute-, framlednings-, retur- och varmvattentemperatur samt gradminuter, kompressor och larm, och styr
  rumsbörvärdet och varmvattnets start/stopp. Installationsguiden känner igen den själv. Den är inte provad mot en
  riktig pump än, så kör i skuggläge först.

## 1.2.14 (2026-11-06)
- **Minutloggen tappades** hos hus vars drivrutin rapporterar på/av som sant/falskt: databasen vägrade raden
  (DatatypeMismatch). Sådana värden sparas nu som 1/0.
- Installationer visar bara fel som **fortfarande uppstår**: ett kvarstående fel rapporteras varje timme, och det som
  inte setts på 75 minuter eller hör till en äldre version försvinner.

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
