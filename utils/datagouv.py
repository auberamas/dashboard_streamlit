"""Calls to data.gouv.fr: read the metadata of the dataset and download the raw file

Nothing here runs at import time. The machine this project runs on cannot verify the public
certificates with the default bundle, so the windows certificate store is used when the
truststore package is available.
"""
import os
import ssl
import time
from pathlib import Path

import httpx

DATASET_SLUG = "pathologies-effectif-de-patients-par-pathologie-sexe-classe-dage-et-territoire-departement-region"
API_BASE = "https://www.data.gouv.fr/api/1"
RESOURCE_NAME = "effectifs.csv"

METADATA_TIMEOUT = 30  # seconds for the small json call
DOWNLOAD_TIMEOUT = 1800  # the file is close to one gigabyte
MAX_RETRIES = 3
RETRY_WAIT = 2  # seconds doubled at each new try
CHUNK_SIZE = 1024 * 1024  # one megabyte per chunk

# a download smaller than this is treated as a failure rather than saved over the good file
MIN_DOWNLOAD_BYTES = 100 * 1024 * 1024


def say(message):
    print(f"[data.gouv] {message}", flush=True)


class DataGouvError(RuntimeError):
    """Raised when data.gouv.fr cannot be reached or answers something unusable"""


def ssl_context():
    """System certificates when possible, default bundle otherwise"""
    try:
        import truststore  # avoid useless import
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return True


def _retry(call, what):
    """Run a call again a few times, waiting twice as long after each failure"""
    wait = RETRY_WAIT
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return call()
        except (httpx.HTTPError, ssl.SSLError) as error:
            last = error
            say(f"{what} echec {attempt}/{MAX_RETRIES} : {error}")
            if attempt < MAX_RETRIES:
                time.sleep(wait)
                wait *= 2
    raise DataGouvError(f"{what} impossible apres {MAX_RETRIES} tentatives : {last}")


def fetch_resource(slug=DATASET_SLUG, name=RESOURCE_NAME):
    """Metadata of the csv resource of the dataset.

    data.gouv leaves filesize and checksum empty for this dataset so only the date can be compared
    Both are still returned when they are there
    """
    url = f"{API_BASE}/datasets/{slug}/"

    def call():
        with httpx.Client(timeout=METADATA_TIMEOUT, follow_redirects=True,
                          verify=ssl_context()) as client:
            answer = client.get(url)
            answer.raise_for_status()
            return answer.json()

    payload = _retry(call, "lecture des metadonnees data.gouv")

    resources = payload.get("resources") or []
    wanted = name.lower()
    for resource in resources:
        title = (resource.get("title") or "").lower()
        if title == wanted:
            checksum = resource.get("checksum") or {}
            return {
                "resource_id": resource.get("id"),
                "title": resource.get("title"),
                "url": resource.get("url"),
                "format": resource.get("format"),
                "last_modified": resource.get("last_modified"),
                "filesize": resource.get("filesize"),
                "checksum": checksum.get("value") if isinstance(checksum, dict) else None,
            }
    titles = [resource.get("title") for resource in resources]
    raise DataGouvError(f"ressource {name} absente du jeu de donnees, vu : {titles}")


def download(url, target, min_bytes=MIN_DOWNLOAD_BYTES):
    """Stream the file into a temporary neighbour then rename it over the target

    The file is close to one gigabyte so it is never held in memory and the target is only
    replaced once the download is complete and big enough to be credible
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")

    def call():
        written = 0
        with httpx.Client(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True,
                          verify=ssl_context()) as client:
            with client.stream("GET", url) as answer:
                answer.raise_for_status()
                with open(temporary, "wb") as handle:
                    for chunk in answer.iter_bytes(CHUNK_SIZE):
                        handle.write(chunk)
                        written += len(chunk)
        return written

    try:
        size = _retry(call, "telechargement du fichier")
        if size < min_bytes:
            raise DataGouvError(
                f"fichier telecharge trop petit : {size} octets, minimum attendu {min_bytes}")
        os.replace(temporary, target)
        say(f"fichier remplace : {target} ({size} octets)")
        return size
    finally:
        # a failed or refused download never leaves a piece of file behind
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                say(f"fichier temporaire non supprime : {temporary}")
