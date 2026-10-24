"""
Start the dashboard

    python run.py

1. makes sure the dashboard has data to show using the most prepared file found in data/
2. looks for a newer file on data.gouv.fr and rebuilds the dashboard data if there is one
3. starts streamlit and opens the browser

The local files are never removed before the new ones are ready so any failure at step 2
(no network or data.gouv down or cleaning error) only prints a warning and the dashboard
starts with what is already on disk even if it is not up to date

Options
    --skip-update -> do not look for a newer file
    --port 8501 -> port of the dashboard
    --no-browser -> do not open the browser
"""

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

# the project folder is the folder of this file so the script runs from any directory
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RAW_CSV = ROOT / "data" / "effectifs.csv"
CLEAN_CSV = ROOT / "data" / "effectifs_clean.csv"
TABLES = ROOT / "processing" / "tables.pkl"


def say(message):
    print(f"[run] {message}", flush=True)

# ** STEP 1 DATA TO SHOW **

def prepare():
    """Make sure the dashboard can start using the most prepared file available

    From the most prepared to the rawest: the aggregated tables then the cleaned csv then the
    raw csv. With nothing at all the raw file is downloaded
    """
    if TABLES.exists():
        return

    if CLEAN_CSV.exists():
        say("tables absentes: reconstruction depuis le csv nettoye")
        from utils.tables import build_tables
        build_tables()
        return

    if RAW_CSV.exists():
        say("csv nettoye absent: nettoyage du fichier brut (environ 1 a 2 minutes)")
        from cleaning_analysis.clean import run as clean_run
        clean_run()
        return

    say("aucune donnee locale: telechargement depuis data.gouv.fr")
    refresh()


# ** STEP 2 UPDATE **

def refresh():
    """Download the newer file when there is one and rebuild the dashboard data

    Returns a short sentence saying what happened. It raises when something goes wrong and
    the caller decides what to do with the error
    """
    from utils import state
    from utils.datagouv import download, fetch_resource

    resource = fetch_resource()
    remote = resource["last_modified"]
    local = state.read_state()

    def remember(size):
        state.write_state({
            "remote_last_modified": remote,
            "downloaded_at": state.now_utc(),
            "size_bytes": size,
            "resource_id": resource["resource_id"],
        })

    if RAW_CSV.exists():
        # first launch with a file already there: keep it and remember the remote date
        if local["remote_last_modified"] is None:
            remember(RAW_CSV.stat().st_size)
            return "version locale conservee"
        if not state.is_outdated(local["remote_last_modified"], remote):
            return "donnees deja a jour"

    say("nouvelle version disponible: telechargement (environ 1 Go)")
    size = download(resource["url"], RAW_CSV)

    say("nettoyage de la nouvelle version")
    from cleaning_analysis.clean import run as clean_run
    clean_run()

    # written last so a failed cleaning is tried again at the next launch
    remember(size)
    return "donnees mises a jour"


# ** STEP 3 DASHBOARD **
def open_when_ready(port):
    """Open the browser once the dashboard answers"""
    for _ in range(90):
        try:
            socket.create_connection(("localhost", port), 1).close()
            webbrowser.open(f"http://localhost:{port}")
            return
        except OSError:
            time.sleep(1)


def launch(port, browser=True):
    """Run streamlit in this terminal until it is stopped"""
    # headless skips the email question of the first run and the browser is opened here
    environment = dict(os.environ, STREAMLIT_SERVER_HEADLESS="true")
    command = [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
               "--server.port", str(port)]

    if browser:
        threading.Thread(target=open_when_ready, args=(port,), daemon=True).start()

    say(f"tableau de bord sur http://localhost:{port} (Ctrl+C pour arreter)")
    try:
        return subprocess.call(command, cwd=ROOT, env=environment)
    except KeyboardInterrupt:
        return 0


# ** MAIN **

def main(argv=None):
    parser = argparse.ArgumentParser(description="Lance le tableau de bord")
    parser.add_argument("--skip-update", action="store_true", help="ne pas chercher de nouvelle version")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    args = parser.parse_args(argv)

    try:
        prepare()
    except Exception as error:
        say(f"impossible de preparer les donnees: {error}")
        say("placez data/effectifs.csv a la main ou verifiez la connexion puis relancez")
        return 1

    if not args.skip_update:
        try:
            say(refresh())
        except Exception as error:
            say(f"mise a jour impossible: {error}")
            say("le tableau de bord demarre avec les donnees locales")

    return launch(args.port, browser=not args.no_browser)


if __name__ == "__main__":
    sys.exit(main())
