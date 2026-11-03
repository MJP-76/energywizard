# Hjälp till att översätta EnergyWizard / Help translate EnergyWizard

*English below.*

EnergyWizard skrivs på svenska och finns på engelska. Vill du rätta en text, eller lägga till
ett helt nytt språk? Det tar några minuter, och du behöver inte kunna programmera.

## Rätta eller fyll i en text

1. Öppna [`smartbox/i18n/en.json`](smartbox/i18n/en.json) (eller ditt språks fil) på GitHub.
2. Tryck på pennan (Edit) uppe till höger.
3. Varje rad är `"svensk text": "översättning"`. Ändra bara texten till höger.
4. Tryck **Commit changes** och sedan **Propose changes**. Klart. Vi tittar på det och tar in det.

`#` står för ett tal eller ett värde, till exempel `"Laddar # kW": "Charging # kW"`. Behåll lika
många `#` i översättningen. En tom översättning (`""`) betyder att svenskan visas tills någon fyller i.

## Hitta texter som saknas

I webben: **Inställningar → Språk → Ladda ner texter som saknar översättning**. Du får en fil
med de texter du själv har sett utan översättning. Fyll i dem och klistra in i språkfilen, eller
skicka filen i ett [ärende](https://github.com/murre87/energywizard/issues/new).

## Lägga till ett nytt språk

1. Kopiera `smartbox/i18n/en.json` till en ny fil med språkkoden, till exempel `de.json` eller `fi.json`.
2. Ändra `"_language"` till språkets namn, och översätt texterna till höger.
3. Lägg till språket i [`smartbox/i18n/languages.json`](smartbox/i18n/languages.json), till exempel `"de": "Deutsch"`.
4. Skicka in ändringen som ovan. Språket syns sedan i alla språkväljare.

Du behöver inte översätta allt på en gång. Det som saknas visas på svenska.

---

## English

EnergyWizard is written in Swedish and available in English. Want to fix a text or add a whole
new language? It takes a few minutes, and you do not need to know how to code.

**Fix a text:** open [`smartbox/i18n/en.json`](smartbox/i18n/en.json) on GitHub, press the pencil
(Edit), change the text on the right of `"Swedish text": "translation"`, then **Commit changes** and
**Propose changes**. `#` stands for a number or a value. Keep the same number of `#`. An empty
translation (`""`) shows the Swedish text until someone fills it in.

**Find missing texts:** in the web app, **Settings → Language → Download texts that are not translated yet**.

**Add a language:** copy `en.json` to e.g. `de.json`, set `"_language"`, translate the right-hand
side, add the language to [`languages.json`](smartbox/i18n/languages.json) (`"de": "Deutsch"`) and
propose the change. Anything you have not translated is shown in Swedish.

Thank you! ❤️
