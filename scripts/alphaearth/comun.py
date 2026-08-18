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

Its limits, and the ordering here is deliberate -- the first version of this
module stated only the third one, which is the hardest attack, while two
one-line mutations walked past the guard. A review caught both. Naming the
expensive limit and skipping the cheap ones is how a guard gets trusted further
than it earned, which is the exact failure this module was written to avoid:

1. Every spelling GDAL accepts has to be checked, not the one the real files
   use. GDAL matches these element names with EQUAL(), so `<sourcefilename>`
   is followed just like `<SourceFilename>`; the first version compared exact
   case and let four other spellings through, verified end to end.
2. One level of checking is a checked door in front of an unchecked one. A
   source that is itself a `.vrt` under the mirror's own prefix satisfied the
   prefix test, and GDAL then followed ITS sources anywhere -- free for a
   hostile mirror, since the nested file sits in its own bucket. Chained VRTs
   are refused outright rather than recursed into: every real tile points at
   its own `.tiff`, so nothing legitimate is lost.
3. What remains, and is not closed: this check fetches the VRT and GDAL then
   fetches it again, so a server that serves one body here and another to GDAL
   wins. Nothing short of handing GDAL the exact validated bytes closes that,
   and the residual risk is a one-off script on a laptop.
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

# The same rule for the VRT's own URL. Checked on the response too, not just the
# request: urllib follows redirects, so without this the mirror could 302 the
# check onto a third host and that host would supply the bytes being validated.
PREFIJO_HTTPS = ("https://s3.us-west-2.amazonaws.com/us-west-2.opendata.source.coop/"
                 "tge-labs/aef/")

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
    # Off by default in GDAL today, but this is not a default worth inheriting:
    # with it on, a VRT may carry Python to run. Pinned so the answer does not
    # depend on the environment the script happens to run in.
    "GDAL_VRT_ENABLE_PYTHON": "NO",
}


def leer_acotado(respuesta, limite: int) -> bytes:
    """Read at most `limite` bytes, and refuse if the body exceeds it."""
    cuerpo = respuesta.read(limite + 1)
    if len(cuerpo) > limite:
        raise ValueError(f"la respuesta supera el tope de {limite:,} B")
    return cuerpo


def fuentes_del_vrt(xml: bytes) -> list[str]:
    """Every dataset a VRT tells GDAL to open.

    Case-insensitive on purpose, and this is not a nicety: GDAL matches these
    element names with EQUAL(), so it follows <sourcefilename> exactly as it
    follows <SourceFilename>. An exact-case check reads as correct and lets
    every other spelling through -- which is how the first version of this
    guard was bypassed.
    """
    # See the note on the import above for why stdlib ElementTree is used here.
    raiz = ET.fromstring(xml)  # nosec B314
    return [(e.text or "").strip() for e in raiz.iter()
            if e.tag.split("}")[-1].lower() in ("sourcedataset", "sourcefilename")]


def exigir_fuentes_del_espejo(url_https: str, timeout: int = 60) -> list[str]:
    """Refuse a VRT that would send GDAL anywhere but the mirror.

    Fails closed on everything it cannot vouch for: a source outside
    PREFIJO_ESPEJO, a path that walks out of it with '..', a source that is
    itself a VRT (GDAL would open that one and follow ITS sources, so one level
    of checking would be a checked door in front of an unchecked one), and a
    VRT with no readable source at all -- if this cannot tell where the file
    points, that is a reason to stop, not to continue.
    """
    if not url_https.startswith(PREFIJO_HTTPS):
        raise ValueError(f"{url_https}: la URL no esta bajo {PREFIJO_HTTPS!r}")

    # fixed https prefix, checked above and again on the response
    with urllib.request.urlopen(url_https, timeout=timeout) as r:  # nosec B310
        if not r.url.startswith(PREFIJO_HTTPS):
            raise ValueError(f"{url_https}: redirigido fuera del espejo, a {r.url!r}")
        fuentes = fuentes_del_vrt(leer_acotado(r, LIMITE_VRT))

    exigir_fuentes_bajo_el_espejo(fuentes, url_https)
    return fuentes


def exigir_fuentes_bajo_el_espejo(fuentes: list[str], origen: str) -> None:
    """The rules themselves, separate from fetching so they can be tested.

    Split out after a review found the fetching version untestable in practice:
    the URL check fires first, so a harness pointing at a local server got a
    rejection for the wrong reason and read as proof the rules worked.
    """
    if not fuentes:
        raise ValueError(f"{origen}: el VRT no declara ninguna fuente legible")

    for f in fuentes:
        if not f.startswith(PREFIJO_ESPEJO):
            raise ValueError(
                f"{origen}: el VRT apunta fuera del espejo: {f!r}. "
                f"Se esperaba que toda fuente empezara con {PREFIJO_ESPEJO!r}."
            )
        if ".." in f.split("/"):
            raise ValueError(
                f"{origen}: la fuente {f!r} sale del prefijo con '..'. "
                "El prefijo se compara como texto y GDAL resuelve los segmentos."
            )
        if f.lower().endswith(".vrt"):
            raise ValueError(
                f"{origen}: la fuente {f!r} es otro VRT. Cada tesela del "
                "espejo apunta a su propio .tiff, y encadenar VRTs dejaria a "
                "GDAL siguiendo fuentes que esta guarda nunca vio."
            )
