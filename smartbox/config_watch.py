"""Startar om motorn när house_config.yaml ändras (t.ex. när entitetsväljaren sparar en ny).

Motorn läser konfigurationen bara vid start. När filen ändras skickar vi SIGTERM till oss
själva, så att samma avstängning som vid en uppdatering körs: batteriet släpps till
växelriktarens eget läge, och Docker (restart: unless-stopped) startar motorn igen.
"""
import os
import signal
import threading
import time

CHECK_EVERY_S = 30


def _signature(path):
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def changed(path, before, signature=None):
    """Ny signatur om filen ändrats sedan before, annars None. En fil som försvinner räknas inte.
    signature(path) kan ge en egen signatur, t.ex. bara de fält som kräver omstart."""
    now = (signature or _signature)(path)
    if now is None or now == before:
        return None
    return now


def start(path, on_change=None, every_s=CHECK_EVERY_S, signature=None):
    """Bevakar path i en bakgrundstråd. on_change anropas en gång när filen ändrats."""
    if on_change is None:
        def on_change():
            print(f"🔄 {path} har ändrats - startar om motorn för att läsa in den.")
            os.kill(os.getpid(), signal.SIGTERM)
    sig_fn = signature or _signature
    first = sig_fn(path)

    def loop():
        sig = first
        while True:
            time.sleep(every_s)
            new = changed(path, sig, sig_fn)
            if new is not None:
                time.sleep(2)                 # låt skrivningen bli klar
                on_change()
                return

    t = threading.Thread(target=loop, name="config-watch", daemon=True)
    t.start()
    return t
