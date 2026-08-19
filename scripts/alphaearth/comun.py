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

Two rounds of review later, the design changed, and the reason is worth stating
because it is the general lesson: **inspecting the document does not bound what
GDAL does with it.** Every version of the guard that reasoned about NAMES was
bypassed by something that GDAL decides by CONTENT.

* Round one: element names were matched case-sensitively. GDAL matches them
  with EQUAL(), so `<sourcefilename>` was followed and never seen. Fixed --
  matching is case-insensitive and namespace-stripped.
* Round two, and the one that ended the approach: refusing sources whose name
  ends in `.vrt` refuses a NAME. The VRT driver identifies a VRT by its header,
  so a hostile mirror serves the nested VRT called `.tiff` -- which is what
  every real source is called. And the element allowlist bounds nothing either:
  `<GDAL_WMS>` names its target in `<ServerUrl>`, `GDALTileIndexDataset` in
  `<IndexDataset>`, and both are dispatched on content with a decoy
  `<SourceFilename>` satisfying the rule. Both verified end to end.

So the fix is not a better parser. **GDAL now opens exactly one document, and
the driver is pinned when it does:** the `.tiff` itself, with `driver="GTiff"`.
There is no second open for a nested document to hijack, and no sniffing for a
disguised one to win. The `.vrt` is still fetched and validated, but only by
this module, to learn which `.tiff` a tile declares and to refuse a tile that
points outside the mirror.

That trades one problem for another, honestly: the `.tiff` is stored bottom-up,
so reading it directly is exactly the mirrored-image trap this screening was
built to avoid. `leer_ventana_north_up` handles it explicitly, in both
directions, and it is tested in both -- against the `.vrt`'s own north-up
reading of the same window.

**What is still not closed, stated first:** the mirror can tell this check and
GDAL apart trivially. The two requests carry different user agents
(`Python-urllib/…` versus `GDAL/…`), so a server that wants to serve one body
here and another to GDAL can. This was previously written up as the expensive
attack; it is not expensive. What the design does buy is that a hostile body
now has to arrive through the single pinned-driver GTiff open, rather than
through any document GDAL might be led to open next.
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
    # Both off by default in GDAL today, and neither is a default worth
    # inheriting: with the first on, a VRT may carry Python to run; with the
    # second, a VRT band may read an arbitrary local file. Pinned so the answer
    # does not depend on the environment the script happens to run in.
    "GDAL_VRT_ENABLE_PYTHON": "NO",
    "GDAL_VRT_ENABLE_RAWRASTERBAND": "NO",
}


def a_vsicurl(fuente: str) -> str:
    """Turn a validated /vsis3/<bucket>/<key> source into a /vsicurl/ URL.

    Anonymous HTTPS rather than S3 protocol, so the read path is the same one
    the guard already checked, against the same hard-coded host.
    """
    if not fuente.startswith("/vsis3/"):
        raise ValueError(f"{fuente!r}: no es una fuente /vsis3/")
    bucket, _, clave = fuente[len("/vsis3/"):].partition("/")
    return f"/vsicurl/https://s3.us-west-2.amazonaws.com/{bucket}/{clave}"


def bordes_north_up(ds):
    """(oeste, norte, este, sur) with north above south, whatever the row order.

    The mirror stores its COGs bottom-up, so a dataset opened straight off the
    .tiff reports its north and south swapped. Everything downstream reasons in
    north-up terms; this is the single place that knows the difference.
    """
    b = ds.bounds
    if b.top == b.bottom:
        raise RuntimeError(f"bounds degenerados: top == bottom == {b.top}")
    return b.left, max(b.top, b.bottom), b.right, min(b.top, b.bottom)


def leer_ventana_north_up(ds, col: int, fila: int, ancho: int, alto: int):
    """Read a window whose `fila` counts from the NORTH edge, flipping if needed.

    This is the guard that replaced `exigir_north_up`, and it is stronger for
    the same reason that one existed: refusing a bottom-up dataset only worked
    while something else was correcting the orientation. Here nothing else is,
    so refusing is not an option -- it has to be handled, in both directions,
    and a silently mirrored read is the one failure that produces a plausible
    wrong answer instead of an error.
    """
    from rasterio.windows import Window

    if ds.bounds.top > ds.bounds.bottom:            # north-up
        return ds.read(window=Window(col, fila, ancho, alto))

    fila_archivo = ds.height - fila - alto          # bottom-up
    if fila_archivo < 0:
        raise RuntimeError(
            f"ventana fuera del raster: fila {fila}+{alto} sobre alto {ds.height}"
        )
    datos = ds.read(window=Window(col, fila_archivo, ancho, alto))
    return datos[:, ::-1, :]


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
