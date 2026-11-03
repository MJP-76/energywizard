FROM python:3.11-slim

# VIKTIGT, läs innan du ändrar: Home Assistant Supervisor bygger ett tillägg
# med byggkontext satt till tilläggets EGEN mapp (ha-addon/smartbox/), inte
# repots rot - så en vanlig `COPY smartbox/*.py .` här når inte huvudkoden,
# som ligger i en syskonmapp. Löst genom att klona huvudrepot vid byggtillfället
# istället för att duplicera smartbox/-koden in i den här mappen (skulle annars
# behöva hållas manuellt synkad, en garanterad källa till drift mellan de två
# kopiorna). Avsteg, dokumenterat i DOCS.md: kräver internetåtkomst vid bygge
# (precis som pip/apt redan gör), och är pinnad mot en specifik gren/tagg.
ARG ENERGYWIZARD_REF=main
RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql postgresql-contrib git \
    && rm -rf /var/lib/apt/lists/*

# Commit-id:t gör att byggcachen inte återanvänder en gammal klon (sätts av CI, tomt annars).
ARG ENERGYWIZARD_COMMIT=
RUN echo "EnergyWizard ${ENERGYWIZARD_REF} ${ENERGYWIZARD_COMMIT}" && git clone --depth 1 --branch "${ENERGYWIZARD_REF}" \
        https://github.com/murre87/energywizard /src

# Samma layout som docker-compose-driften: ewapp och webdashboard gör
# sys.path.insert(0, "/smartbox") och importerar motorns moduler därifrån
# (i compose: ./smartbox monterad på /smartbox), så motorn ligger i /smartbox.
RUN cp -r /src/smartbox /smartbox \
    && cp -r /src/ewapp /ewapp \
    && cp -r /src/webdashboard /webdashboard \
    && rm -rf /src

# Motorns beroenden + det gränssnitten installerar i sina egna Dockerfiles
# (ewapp/Dockerfile, webdashboard/Dockerfile) - samma paket, en gemensam miljö.
RUN pip install --no-cache-dir -r /smartbox/requirements.txt \
    && pip install --no-cache-dir fastapi "uvicorn[standard]" requests sqlalchemy \
        "psycopg[binary]" psycopg_pool pandas PyYAML pymodbus pillow

# ewapp/Dockerfile genererar PWA-ikonerna vid bygge - samma steg här.
RUN cd /ewapp && python make_icons.py

WORKDIR /smartbox

COPY rootfs/run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8502 8503
VOLUME /data
CMD ["/run.sh"]
