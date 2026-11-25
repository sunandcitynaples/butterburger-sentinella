#!/usr/bin/env python3
"""
Butter Burger (Pomigliano d'Arco) - sentinella tavoli

Controlla ogni pochi minuti il sistema di prenotazione del sito e ti avvisa
appena si libera un tavolo per 2 persone, a cena, da oggi ai prossimi 7 giorni.
Non prenota da solo: ti manda la notifica (sul telefono e sul PC) con il link,
poi completi tu la prenotazione.

Uso:
    python butterburger_sentinella.py          -> resta acceso e controlla di continuo
    python butterburger_sentinella.py --test   -> un solo controllo + notifica di prova
    python butterburger_sentinella.py --una-volta -> un controllo e basta (usato da GitHub Actions)

Non serve installare nulla oltre a Python 3.
"""

import json
import os
import platform
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

# ======================= IMPOSTAZIONI =======================
PERSONE = 2
GIORNI_AVANTI = 7            # controlla da oggi fino a oggi + 7 giorni
ORA_MIN = "19:30"            # primo orario accettato (turno delle 19:30)
ORA_MAX = "22:30"            # ultimo orario accettato (turno delle 22:30)
OGNI_MINUTI = 3              # ogni quanti minuti ricontrollare
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")  # stesso nome nell'app ntfy
EMAIL_AVVISI = os.environ.get("EMAIL_AVVISI", "")  # se impostata, l'avviso arriva anche per email
# ============================================================

API = "https://butterburger.it/wp-json/restaurantreservationsandtakeawaysbyfocuson/v1"
SEDE = 1                     # 1 = sala di Via Carlo Poerio (tavoli)
LINK = "https://butterburger.it/prenotazione/"
MINUTI_PREAVVISO = 60        # il sito non accetta prenotazioni a meno di 60 minuti

GIORNI_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI_IT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def get_json(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def giorni_da_controllare():
    """Giorni nella finestra che il ristorante apre alle prenotazioni online."""
    info = get_json(f"{API}/booking-disable-dates/{SEDE}?persons={PERSONE}")["data"]
    date_chiuse = set(info.get("closure_dates", []))
    giorni_chiusi = set(info.get("closure_days", []))  # 0 = domenica ... 6 = sabato
    max_date = date.fromisoformat(info["max_date"]) if info.get("max_date") else None

    oggi = date.today()
    giorni = []
    for i in range(GIORNI_AVANTI + 1):
        d = oggi + timedelta(days=i)
        if max_date and d > max_date:
            break
        if d.isoformat() in date_chiuse:
            continue
        if (d.weekday() + 1) % 7 in giorni_chiusi:
            continue
        giorni.append(d)
    return giorni


def orari_liberi(d):
    """Orari liberi per quel giorno, solo nella fascia serale scelta."""
    dati = get_json(
        f"{API}/booking-available-times/{SEDE}?persons={PERSONE}&date={d.isoformat()}"
    )["data"]
    adesso = datetime.now()
    buoni = []
    for s in dati.get("slots", []):
        ora = s[:5]
        if not (ORA_MIN <= ora <= ORA_MAX):
            continue
        quando = datetime.combine(d, datetime.strptime(ora, "%H:%M").time())
        if quando - adesso < timedelta(minutes=MINUTI_PREAVVISO):
            continue
        buoni.append(ora)
    return buoni


def data_bella(d):
    oggi = date.today()
    if d == oggi:
        prefisso = "stasera"
    elif d == oggi + timedelta(days=1):
        prefisso = "domani"
    else:
        prefisso = GIORNI_IT[d.weekday()]
    return f"{prefisso} {d.day} {MESI_IT[d.month - 1]}"


def notifica_telefono(titolo, testo):
    if not NTFY_TOPIC:
        return
    corpo = json.dumps({
        "topic": NTFY_TOPIC,
        "title": titolo,
        "message": testo,
        "priority": 5,
        "tags": ["hamburger"],
        "click": LINK,
        "actions": [{"action": "view", "label": "Prenota ora", "url": LINK}],
        **({"email": EMAIL_AVVISI} if EMAIL_AVVISI else {}),
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://ntfy.sh/", data=corpo, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(f"  (notifica telefono non inviata: {e})")


def notifica_pc(titolo, testo):
    if os.environ.get("GITHUB_ACTIONS"):
        return
    try:
        so = platform.system()
        if so == "Darwin":
            t = json.dumps(testo, ensure_ascii=False)
            ti = json.dumps(titolo, ensure_ascii=False)
            subprocess.run(
                ["osascript", "-e", f'display notification {t} with title {ti} sound name "Glass"'],
                check=False,
            )
        elif so == "Windows":
            ti = titolo.replace("'", "''")
            t = testo.replace("'", "''")
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "Add-Type -AssemblyName System.Drawing;"
                "$n=New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;"
                f"$n.ShowBalloonTip(10000,'{ti}','{t}','Info');Start-Sleep 11;$n.Dispose()"
            )
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps])
        else:
            subprocess.run(["notify-send", titolo, testo], check=False)
    except Exception:
        pass
    print("\a", end="", flush=True)


def avvisa(titolo, testo):
    print(f"\n*** {titolo}: {testo}\n    {LINK}\n")
    notifica_telefono(titolo, testo)
    notifica_pc(titolo, testo)


def controlla():
    """Restituisce l'insieme di (giorno, orario) liberi in questo momento."""
    trovati = set()
    for d in giorni_da_controllare():
        for ora in orari_liberi(d):
            trovati.add((d, ora))
        time.sleep(1)  # una richiesta al secondo, per non pesare sul sito
    return trovati


STATO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stato.json")


def una_volta():
    """Un solo controllo; ricorda in stato.json cosa ha già segnalato."""
    try:
        with open(STATO, encoding="utf-8") as f:
            prima = set(json.load(f))
    except (OSError, ValueError):
        prima = set()
    ora_ora = datetime.now().strftime("%d/%m %H:%M")
    try:
        liberi = controlla()
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
        print(f"[{ora_ora}] errore temporaneo ({e}), riprovo al prossimo giro")
        return
    chiavi = {f"{d.isoformat()} {ora}" for d, ora in liberi}
    nuovi = sorted((d, ora) for d, ora in liberi if f"{d.isoformat()} {ora}" not in prima)
    if nuovi:
        righe = [f"{data_bella(d)} alle {ora}" for d, ora in nuovi]
        avvisa("Tavolo libero da Butter Burger!", "; ".join(righe))
    else:
        print(f"[{ora_ora}] liberi ora: {len(liberi)} (nessuno nuovo)")
    with open(STATO, "w", encoding="utf-8") as f:
        json.dump(sorted(chiavi), f)


def main():
    if "--una-volta" in sys.argv:
        try:
            una_volta()
        except Exception as e:  # mai far fallire l'automazione: niente email di errore
            print(f"errore imprevisto ({e}), riprovo al prossimo giro")
        return
    test = "--test" in sys.argv
    print(f"Sentinella Butter Burger: {PERSONE} persone, {ORA_MIN}-{ORA_MAX}, "
          f"prossimi {GIORNI_AVANTI} giorni, controllo ogni {OGNI_MINUTI} min.")
    print("Lascia questa finestra aperta. Ctrl+C per fermare.\n")

    gia_avvisati = set()
    while True:
        ora_ora = datetime.now().strftime("%d/%m %H:%M")
        try:
            liberi = controlla()
            nuovi = sorted(liberi - gia_avvisati)
            if nuovi:
                righe = [f"{data_bella(d)} alle {ora}" for d, ora in nuovi]
                avvisa("Tavolo libero da Butter Burger!", "; ".join(righe))
            elif liberi:
                print(f"[{ora_ora}] ancora liberi (già segnalati): {len(liberi)}")
            else:
                print(f"[{ora_ora}] nessun tavolo libero")
            # Se un posto sparisce e poi si libera di nuovo, ti riavvisa
            gia_avvisati = liberi
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
            print(f"[{ora_ora}] errore temporaneo ({e}), riprovo al prossimo giro")

        if test:
            avvisa("Prova sentinella Butter Burger", "Le notifiche funzionano.")
            break

        attesa = OGNI_MINUTI * 60 + random.randint(-30, 30)
        time.sleep(max(60, attesa))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSentinella fermata.")
