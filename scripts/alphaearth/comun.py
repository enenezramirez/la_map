"""Shared guards for the scripts that read the third-party AEF mirror.

The screening's security review (2026-08-11) closed with three Low findings,
all sharing one precondition: that the mirror at source.coop turns hostile. The
review's own reproduction is what this module answers, and it was reproduced
again here before writing the fix -- a VRT whose source points at
`/vsicurl/http://127.0.0.1:<port>/x.tif` made GDAL issue two real requests to
that host (HEAD /x.tif, GET /). GDAL follows a VRT's sources wherever they
point, so publishing a repointed VRT is enough to aim this machine's network
stack at a host of the publisher's choosing.

`CPL_VSIL_CURL_ALLOWED_EXTENSIONS` was evaluated as the fix and REJECTED,
because measuring it showed it does not hold. With `.vrt,.tiff` allowed -- the
narrowest list this pipeline can actually run on -- a hostile source ending in
`.tif` is blocked (0 requests) but one ending in `.tiff` sails through (2
requests). The pipeline needs `.tiff`, so the attacker just spells it the way
the allowlist already permits. Shipping it would have looked like a mitigation
without being one.

What does hold is checking where the VRT points before GDAL ever opens it, which
is `exigir_fuentes_del_espejo` below.

Its limit, stated rather than glossed: the check fetches the VRT, and GDAL then
fetches it again, so a mirror that serves one body to this check and another to
GDAL defeats it. It stops the realistic case -- a VRT repointed at the source --
not a server that answers differently per request. Nothing short of handing GDAL
the exact validated bytes closes that gap, and the residual risk here is a
one-off script on a laptop.
"""

from __future__ import annotations

import urllib.request
# stdlib ElementTree is used deliberately rather than adding defusedxml. This
# parses the same XML GDAL will, on purpose: a regex over the raw text would
# read CDATA and character entities differently than GDAL's parser does, and a
# check that disagrees with what it is protecting is not a check.
import xml.etree.ElementTree as ET  # nosec B405

# Everything this screening may read. Verified against both tiles actually used:
# each VRT carries exactly one <SourceDataset>, pointing at its own .tiff here.
PREFIJO_ESPEJO = "/vsis3/us-west-2.opendata.source.coop/tge-labs/aef/"

# A VRT measured 27,474 B; 512 KB is generous and still bounded. Needed because
# a Range: header is a request, not a guarantee -- a server may answer 200 with
# a body of any size, so an unbounded read() is the server's decision to make.
LIMITE_VRT = 512 * 1024

# A 1000-key ListObjectsV2 page runs ~250 KB; 4 MB leaves 16x headroom.
LIMITE_LISTADO = 4 * 1024 * 1024

# Zone 14N holds 520 tiles, so one page of 1000 keys covers it and the loop
# never continues. The cap matters because the server hands out the next token:
# a mirror that keeps issuing them makes the loop run as long as it likes.
MAX_PAGINAS = 20

# Same idea one step later: the key list decides how many requests the thread
# pool fires, and that list also comes from the server.
MAX_TESELAS = 2_000

# GDAL's own network guards. Without a timeout a stalled read hangs forever,
# since GDAL_HTTP_MAX_RETRY only bounds retries, not the wait for each one.
ENTORNO_GDAL = {
    "AWS_NO_SIGN_REQUEST": "YES",
    "AWS_REGION": "us-west-2",
    "AWS_DEFAULT_REGION": "us-west-2",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "GDAL_HTTP_MAX_RETRY": "2",
    "GDAL_HTTP_RETRY_DELAY": "1",
    "GDAL_HTTP_CONNECTTIMEOUT": "30",
    "GDAL_HTTP_TIMEOUT": "120",
}


def leer_acotado(respuesta, limite: int) -> bytes:
    """Read at most `limite` bytes, and refuse if the body exceeds it."""
    cuerpo = respuesta.read(limite + 1)
    if len(cuerpo) > limite:
        raise ValueError(f"la respuesta supera el tope de {limite:,} B")
    return cuerpo


def fuentes_del_vrt(xml: bytes) -> list[str]:
    """Every dataset a VRT tells GDAL to open."""
    raiz = ET.fromstring(xml)  # nosec B314
    return [(e.text or "").strip() for e in raiz.iter()
            if e.tag in ("SourceDataset", "SourceFilename")]


def exigir_fuentes_del_espejo(url_https: str, timeout: int = 60) -> list[str]:
    """Refuse a VRT that would send GDAL anywhere but the mirror.

    Fails closed in both directions: a source outside PREFIJO_ESPEJO raises,
    and so does a VRT with no source at all -- if this cannot tell where the
    file points, that is a reason to stop, not to continue.
    """
    with urllib.request.urlopen(url_https, timeout=timeout) as r:  # nosec B310
        fuentes = fuentes_del_vrt(leer_acotado(r, LIMITE_VRT))

    if not fuentes:
        raise ValueError(f"{url_https}: el VRT no declara ninguna fuente legible")
    ajenas = [f for f in fuentes if not f.startswith(PREFIJO_ESPEJO)]
    if ajenas:
        raise ValueError(
            f"{url_https}: el VRT apunta fuera del espejo: {ajenas!r}. "
            f"Se esperaba que toda fuente empezara con {PREFIJO_ESPEJO!r}."
        )
    return fuentes
