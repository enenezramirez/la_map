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

So the fix is not a better parser. **GDAL now opens one document at the top
level, with the driver pinned:** the `.tiff` itself, with `driver="GTiff"`.
That kills all three bypasses above. The `.vrt` is still fetched and validated,
but only by this module, to learn which `.tiff` a tile declares and to refuse a
tile that points outside the mirror.

**"Exactly one document" was the claim, and a third review showed it was not
true.** Pinning the driver bounds the top-level open and nothing after it:
GTiff honours the `OVERVIEWS/OVERVIEW_FILE` metadata item, and carries that
domain **inside the file's own `GDAL_METADATA` tag**. So a hostile `.tiff` names
a second dataset from within itself, GDAL opens that one **with no driver
pinned**, and it was chained from there to a third host. `GDAL_DISABLE_READDIR_ON_OPEN`
does not suppress it, because this is not a sibling probe. `exigir_sin_overview_externo`
refuses it, read off a flat open at no extra cost -- a rule about the content
of the one document we allow, rather than about the name of a second one.

That is the third time a claim here outran what was verified. The pattern is
always the same: the fix is checked against the attacks that were known when it
was written.

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

import contextlib
import re
import urllib.error
import urllib.request
# stdlib ElementTree is used deliberately rather than adding defusedxml. This
# parses the same XML GDAL will, on purpose: a regex over the raw text would
# read CDATA and character entities differently than GDAL's parser does, and a
# check that disagrees with what it is protecting is not a check.
import xml.etree.ElementTree as ET  # nosec B405

# Everything this screening may read. Verified against both tiles actually used:
# each VRT carries exactly one <SourceDataset>, pointing at its own .tiff here.
PREFIJO_ESPEJO = "/vsis3/us-west-2.opendata.source.coop/tge-labs/aef/"

# The same rule for the VRT's own URL, enforced by `abrir_url` on the redirect
# itself rather than on the response. The earlier note here said checking `r.url`
# covered redirects; a review measured that it does not -- see `abrir_url`.
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
    # Security, not performance: without it GDAL probes sibling paths on open,
    # and a hostile .ovr sitting next to a tile reaches a foreign host even with
    # the driver pinned. Measured both ways against a local server that logs
    # every request, both reads cold and on separate URLs so neither could be
    # answered from the other's /vsicurl cache: 10 requests and 8 sibling probes
    # without it (a directory GET, then HEADs for .aux.xml/.aux/.AUX/...), 2 and
    # none with it. The count is not a constant -- it depends on the extension
    # and on what siblings exist, and a review measured 48 in its own setup --
    # so what is being claimed here is that the probing stops, not a number.
    # `abrir_tesela` is what puts this in force; it used to be convention.
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


def abrir_url(peticion, prefijo: str, timeout: int = 60):
    """GET, refusing any redirect that leaves `prefijo` BEFORE it is followed.

    This replaces a check on `r.url` after `urlopen` returned, which read as if
    it covered redirects and does not. `urlopen` FOLLOWS them: by the time a
    response object exists, this machine has already issued the request to
    whatever host the mirror named -- `127.0.0.1` and the rest of the intranet
    included, over plain http, since a Location is not bound by the scheme of
    the request that got it. The body was refused, which is why nothing hostile
    ever reached the parser, but the request itself is precisely the capability
    the module docstring says this exists to remove. Measured: one request to
    the attacker before, none after.

    `redirect_request` is the only hook that runs BEFORE the connection, so the
    decision has to live there. Raising HTTPError rather than returning None is
    deliberate: None makes urllib return the 302 to the caller as if it were the
    answer, and a caller that then parses the body is reading the redirect page.
    """
    url = peticion.full_url if isinstance(peticion, urllib.request.Request) else peticion
    if not url.startswith(prefijo):
        raise ValueError(f"{url}: la URL no esta bajo {prefijo!r}")

    class _SinSalida(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not newurl.startswith(prefijo):
                raise urllib.error.HTTPError(
                    newurl, code,
                    f"redireccion fuera del espejo, a {newurl!r}", headers, fp)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    return urllib.request.build_opener(_SinSalida).open(peticion, timeout=timeout)


@contextlib.contextmanager
def abrir_tesela(ruta: str, **opciones):
    """The only way this pipeline opens a tile: driver pinned, environment in force.

    Two review findings meet here, and both are the same shape: an invariant
    that was true when written and optional afterwards.

    The driver pin is what the whole design rests on -- a nested VRT named
    `.tiff` is *deliberately* accepted by the source rules, because every real
    source is called that, so an open without `driver="GTiff"` anywhere brings
    back every bypass this module closed. It was retyped at five call sites and
    enforced at none.

    ENTORNO_GDAL was documented as the thing that stops sibling probing, but only
    two scripts applied it, by convention. Measured with it absent: the guard
    passed a tile, GDAL probed 48 sibling paths, found a hostile `.ovr` and
    opened it WITHOUT a pinned driver -- `exigir_sin_overview_externo` never saw
    it, because it arrived by sibling probe rather than by OVERVIEW_FILE.

    Applied through `rasterio.Env` rather than `os.environ`, so it covers the
    lazy /vsicurl reads that happen inside the `with`, and so importing this
    module does not rewrite the caller's environment as a side effect.
    """
    import rasterio

    with rasterio.Env(**ENTORNO_GDAL):
        with rasterio.open(ruta, driver="GTiff", **opciones) as ds:
            yield ds


def a_vsicurl(fuente: str) -> str:
    """Turn a validated /vsis3/<bucket>/<key> source into a /vsicurl/ URL.

    Anonymous HTTPS rather than S3 protocol, so the read path is the same one
    the guard already checked, against the same hard-coded host.
    """
    if not fuente.startswith("/vsis3/"):
        raise ValueError(f"{fuente!r}: no es una fuente /vsis3/")
    bucket, _, clave = fuente[len("/vsis3/"):].partition("/")
    return f"/vsicurl/https://s3.us-west-2.amazonaws.com/{bucket}/{clave}"


def exigir_sin_overview_externo(ruta: str) -> None:
    """Refuse a .tiff that names another dataset for GDAL to open as overviews.

    Pinning the driver bounds the top-level open and nothing after it. GTiff
    reads OVERVIEWS/OVERVIEW_FILE out of the file's own GDAL_METADATA tag and
    opens whatever it names, unpinned -- so the tile can hand GDAL a second
    document from inside itself. A flat open sees the item without fetching it,
    so refusing costs nothing.
    """
    with abrir_tesela(ruta) as ds:
        etiquetas = ds.tags(ns="OVERVIEWS")
    if etiquetas:
        raise ValueError(
            f"{ruta}: el .tiff declara overviews externas {etiquetas!r}. "
            "GDAL abriria ese segundo dataset sin driver fijado."
        )


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

    # Checked here and not only in the caller: this is the one place that
    # flips, so a degenerate dataset must not reach the flip by falling through
    # the north-up test. A guard that depends on being called in the right
    # order is a guard with a precondition nobody reads.
    bordes_north_up(ds)

    # Bounds in BOTH branches: rasterio silently clips an over-long window, so
    # the north-up branch used to truncate where the bottom-up one raised.
    if fila < 0 or alto <= 0 or ancho <= 0:
        raise RuntimeError(f"ventana invalida: fila={fila} alto={alto} ancho={ancho}")
    if fila + alto > ds.height:
        raise RuntimeError(
            f"ventana fuera del raster: fila {fila}+{alto} sobre alto {ds.height}"
        )

    if ds.bounds.top > ds.bounds.bottom:            # north-up
        return ds.read(window=Window(col, fila, ancho, alto))

    datos = ds.read(window=Window(col, ds.height - fila - alto, ancho, alto))
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

    # Redirects are refused before they are followed; the check on r.url stays as
    # a second reading of the same rule, in case a handler is ever bypassed.
    with abrir_url(url_https, PREFIJO_HTTPS, timeout) as r:
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
        # A conservative alphabet rather than a list of things to forbid. The
        # '..' rule alone was evaded with %2e%2e: curl percent-decodes before it
        # normalises dot segments, so the request left the mirror's prefix while
        # the literal check saw nothing. This also disposes of ?, #, @ and \.
        clave = f[len(PREFIJO_ESPEJO):]
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", clave) or ".." in clave.split("/"):
            raise ValueError(
                f"{origen}: la clave {clave!r} sale del juego de caracteres "
                "permitido o del prefijo. El prefijo se compara como texto, y "
                "curl decodifica antes de normalizar los segmentos."
            )
        if f.lower().endswith(".vrt"):
            raise ValueError(
                f"{origen}: la fuente {f!r} es otro VRT. Cada tesela del "
                "espejo apunta a su propio .tiff, y encadenar VRTs dejaria a "
                "GDAL siguiendo fuentes que esta guarda nunca vio."
            )
