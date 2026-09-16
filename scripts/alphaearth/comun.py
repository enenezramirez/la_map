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
does not suppress it, because this is not a sibling probe. `abrir_tesela`
refuses it, read off a flat open at no extra cost -- a rule about the content
of the one document we allow, rather than about the name of a second one.

That is the third time a claim here outran what was verified. The pattern is
always the same: the fix is checked against the attacks that were known when it
was written.

**And the fourth.** Refusing redirects in `abrir_url` was written up as closing
them, and it closed them for urllib only -- a few KB of XML. The raster's bytes
were fetched by GDAL's `/vsicurl/`, which follows a redirect on its own and has
no setting to stop it: the GDAL 3.12 build here carries no FOLLOWLOCATION or
MAX_REDIRECTS option at all. Reproduced 2026-09-16: the mirror answered 302,
GDAL followed, and the pixel read was the attacker's. So GDAL no longer touches
the network for a tile. `abrir_tesela` serves it through a rasterio opener that
fetches every byte range with `abrir_url`, and GDAL sees one file name and
nothing else.

That trades one problem for another, honestly: the `.tiff` is stored bottom-up,
so reading it directly is exactly the mirrored-image trap this screening was
built to avoid. `leer_ventana_north_up` handles it explicitly, in both
directions, and it is tested in both -- against the `.vrt`'s own north-up
reading of the same window.

**What is still not closed, stated first:** the mirror decides the bytes. A
hostile one can serve a VRT that passes the source rules and a `.tiff` whose
pixels are wrong, and nothing here can tell -- that is the trust the README
names. What it can no longer do is make this machine connect anywhere else:
urllib and GDAL now fetch through the same guard. An earlier version of this
paragraph said a server could serve one body to the check and another to GDAL by
their user agents; both requests now come from urllib, but a server can still
tell a VRT request from a tile request by the path, so that is not closed
either, only no longer free.
"""

from __future__ import annotations

import collections
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

# The same rule for the VRT's own URL and the tile's, enforced by `abrir_url`
# before the request is made. The earlier note here said checking `r.url`
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

# The only name GDAL is given for a tile. The real URL stays on the Python side,
# so there is nothing in the path for GDAL to resolve siblings or overviews
# against except this opener, which knows one file.
NOMBRE_TESELA = "tesela.tiff"

# How much one ranged request asks for when GDAL reads small. The opener
# interface buffers nothing, and GDAL walks a COG's header 8 bytes to a few KB at
# a time -- 712 reads per tile open, measured -- so without a cache each is its
# own HTTPS round trip. A read at least this big is a compressed block and is
# fetched exactly instead (`_LecturaDeTesela.read`).
BLOQUE_TESELA = 128 * 1024
BLOQUES_EN_CACHE = 64

# Everything one tile open may fetch. GDAL's /vsicurl/ used to read whatever the
# file's own offsets told it to, and the file comes from the mirror; a tile is
# 3.49 GB, so "the header said so" is not a bound. The largest real open is
# step 3's full-resolution read, 40.02 MB measured -- 64 compressed blocks of
# ~630 KB, one per band. A first cap of 64 MB fired on it while reads were still
# rounded to blocks, which is how that rounding was caught.
LIMITE_TESELA = 128 * 1024 * 1024

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
    # Since the tile is served through an opener, a probe that slips past this
    # lands in `_TeselaDelEspejo`, which answers "no such file" without a
    # request -- so this is now the first of two layers, not the only one.
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
    """GET a URL under `prefijo`, refusing every redirect BEFORE it is followed.

    This replaces a check on `r.url` after `urlopen` returned, which read as if
    it covered redirects and does not. `urlopen` FOLLOWS them: by the time a
    response object exists, this machine has already issued the request to
    whatever host the mirror named -- `127.0.0.1` and the rest of the intranet
    included, over plain http, since a Location is not bound by the scheme of
    the request that got it. Measured: one request to the attacker before, none
    after.

    The next version allowed a redirect that stayed under `prefijo`, and a
    review showed that comparison is text: an absolute Location with dot
    segments starts with the prefix and resolves outside it. It is not repaired
    here but removed, because there is nothing for it to decide -- measured
    2026-09-16, the mirror answers the VRT, the .tiff and the listing directly
    (206, 206, 200) and redirects none of them. A redirect is therefore refused
    whatever it names.

    `redirect_request` is the only hook that runs BEFORE the connection, so the
    decision has to live there. Raising rather than returning None is
    deliberate: None makes urllib return the 302 to the caller as if it were the
    answer, and a caller that then parses the body is reading the redirect page.
    The redirect's socket is closed first, and the error is a URLError rather
    than an HTTPError because HTTPError is itself a file object: built around
    the response, it kept the socket open for as long as the exception lived
    (20 refusals kept by a caller, 20 open sockets; now 0), and even built empty
    it warns when it is collected.
    """
    # Without the slash, "…/aef" would admit "…/aef-something-else/".
    if not prefijo.endswith("/"):
        raise ValueError(f"{prefijo!r}: el prefijo debe terminar en '/'")
    url = peticion.full_url if isinstance(peticion, urllib.request.Request) else peticion
    if not url.startswith(prefijo):
        raise ValueError(f"{url}: la URL no esta bajo {prefijo!r}")

    class _SinRedireccion(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            fp.close()
            raise urllib.error.URLError(f"redireccion {code} rechazada, a {newurl!r}")

    return urllib.request.build_opener(_SinRedireccion).open(peticion, timeout=timeout)


class _LecturaDeTesela:
    """A seekable, read-only file object over `_TeselaDelEspejo`'s block cache."""

    def __init__(self, tesela: "_TeselaDelEspejo"):
        self._tesela = tesela
        self._pos = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self) -> None:
        pass

    def tell(self) -> int:
        return self._pos

    def seek(self, desplazamiento: int, desde: int = 0) -> int:
        base = {0: 0, 1: self._pos, 2: self._tesela.tamano()}[desde]
        if base + desplazamiento < 0:
            raise ValueError(f"seek a una posicion negativa: {base + desplazamiento}")
        self._pos = base + desplazamiento
        return self._pos

    def read(self, n: int = -1) -> bytes:
        tamano = self._tesela.tamano()
        fin = tamano if n is None or n < 0 else min(tamano, self._pos + n)
        # A read this size is one compressed block, which GDAL asks for once:
        # fetched exactly, since rounding it to blocks nearly doubled step 3.
        if fin - self._pos >= BLOQUE_TESELA:
            datos = self._tesela._rango(self._pos, fin - 1)
            self._pos = fin
            return datos
        partes = []
        while self._pos < fin:
            indice, desde = divmod(self._pos, BLOQUE_TESELA)
            trozo = self._tesela.bloque(indice)[desde:desde + fin - self._pos]
            partes.append(trozo)
            self._pos += len(trozo)
        return b"".join(partes)


class _TeselaDelEspejo:
    """Serves GDAL exactly one file, NOMBRE_TESELA, every byte through `abrir_url`.

    Implements rasterio's FileContainer interface; `abrir_tesela` registers it.
    Any other name GDAL asks about -- a sibling `.ovr`, an `.aux.xml`, an
    overview named relative to the tile -- is answered "no such file" here,
    without a request.
    """

    def __init__(self, url: str, prefijo: str, timeout: int = 60):
        self.url, self.prefijo, self.timeout = url, prefijo, timeout
        self._tamano: int | None = None
        self._bloques: collections.OrderedDict[int, bytes] = collections.OrderedDict()
        self.bajado = 0
        # rasterio's callbacks swallow the exception and GDAL reports the tile as
        # "not recognized as being in a supported file format" -- which is what a
        # refused redirect looked like. Kept so `abrir_tesela` can say why.
        self.fallo: Exception | None = None

    def _exigir_nombre(self, path: str) -> None:
        if path != NOMBRE_TESELA:
            raise FileNotFoundError(path)

    def isfile(self, path: str) -> bool:
        return path == NOMBRE_TESELA

    def isdir(self, path: str) -> bool:
        return False

    def ls(self, path: str) -> list[str]:
        return []

    def mtime(self, path: str) -> int:
        return 0

    def rm(self, path: str) -> None:
        raise PermissionError(f"{path}: la tesela es de solo lectura")

    def size(self, path: str) -> int:
        self._exigir_nombre(path)
        return self.tamano()

    def open(self, path: str, mode: str = "rb", **kwds) -> _LecturaDeTesela:
        self._exigir_nombre(path)
        if mode != "rb":
            raise PermissionError(f"{path}: modo {mode!r}, la tesela es de solo lectura")
        return _LecturaDeTesela(self)

    def tamano(self) -> int:
        if self._tamano is None:
            self._rango(0, 0)
        return self._tamano

    def bloque(self, indice: int) -> bytes:
        if indice in self._bloques:
            self._bloques.move_to_end(indice)
            return self._bloques[indice]
        inicio = indice * BLOQUE_TESELA
        datos = self._rango(inicio, min(inicio + BLOQUE_TESELA, self.tamano()) - 1)
        self._bloques[indice] = datos
        if len(self._bloques) > BLOQUES_EN_CACHE:
            self._bloques.popitem(last=False)
        return datos

    def _rango(self, inicio: int, fin: int) -> bytes:
        """One Range GET, refused unless the server answers exactly that range.

        A 200 would be the whole 3.49 GB file, and a Content-Range for other
        bytes would be read into the wrong offsets without anything looking
        wrong. The total is pinned on first sight, so a file that changes size
        between requests stops the read instead of mixing two versions.
        """
        try:
            return self._rango_sin_registro(inicio, fin)
        except Exception as e:
            self.fallo = self.fallo or e
            raise

    def _rango_sin_registro(self, inicio: int, fin: int) -> bytes:
        n = fin - inicio + 1
        if self.bajado + n > LIMITE_TESELA:
            raise ValueError(
                f"{self.url}: la lectura supera el tope de {LIMITE_TESELA:,} B por tesela")
        peticion = urllib.request.Request(self.url, headers={"Range": f"bytes={inicio}-{fin}"})
        with abrir_url(peticion, self.prefijo, self.timeout) as r:
            m = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", r.headers.get("Content-Range") or "")
            if r.status != 206 or not m or (int(m[1]), int(m[2])) != (inicio, fin):
                raise ValueError(
                    f"{self.url}: se pidio bytes={inicio}-{fin} y el servidor respondio "
                    f"{r.status} con Content-Range {r.headers.get('Content-Range')!r}")
            if self._tamano is None:
                self._tamano = int(m[3])
            elif int(m[3]) != self._tamano:
                raise ValueError(
                    f"{self.url}: el archivo cambio de tamano entre peticiones "
                    f"({self._tamano:,} -> {int(m[3]):,} B)")
            datos = leer_acotado(r, n)
        if len(datos) != n:
            raise ValueError(f"{self.url}: se pidieron {n:,} B y llegaron {len(datos):,}")
        self.bajado += n
        return datos


@contextlib.contextmanager
def abrir_tesela(url: str, prefijo: str = PREFIJO_HTTPS, **opciones):
    """The only way this pipeline opens a tile, and GDAL makes no request in it.

    Every review finding on this module has had the same shape: an invariant
    that was true when written and optional afterwards. So each one lives here,
    where no caller can leave it out.

    **The driver pin** is what the design rests on -- a nested VRT named `.tiff`
    is *deliberately* accepted by the source rules, because every real source is
    called that, so an open without `driver="GTiff"` brings back every bypass
    this module closed. It was retyped at five call sites and enforced at none.

    **ENTORNO_GDAL**, applied through `rasterio.Env` so it covers the reads that
    happen inside the `with`, and so importing this module does not rewrite the
    caller's environment. It used to be applied by convention in two scripts.

    **The bytes.** GDAL is handed NOMBRE_TESELA and an opener, never the URL.
    Through `/vsicurl/` it followed a redirect with no setting to stop it -- the
    pixel came from the attacker, reproduced -- and it probed siblings next to
    the URL. Now every range goes through `abrir_url`, which refuses redirects,
    and every other name ends at the opener. What the opener cannot stop is an
    ABSOLUTE path GDAL decides to open, which is why the last rule stays.

    **No external overviews.** GTiff reads OVERVIEWS/OVERVIEW_FILE out of the
    file's own GDAL_METADATA tag and opens whatever it names, unpinned -- and an
    absolute `/vsicurl/…` there goes around the opener. The flat open sees the
    item without fetching it, so it is refused before any open that would follow
    it. It used to be a separate function the scripts had to remember to call
    first; a review pointed out this was the one guard still left to memory.

    Cost against the real run, measured 2026-09-16: 25.1 MB for step 2 and
    77.0 MB for step 3, less than `/vsicurl/` fetched for the same reads (39.8
    and 78.8), and slower, since each range is its own HTTPS request. See the
    README.
    """
    import rasterio
    from rasterio.abc import FileContainer

    FileContainer.register(_TeselaDelEspejo)
    if not url.startswith(prefijo):
        raise ValueError(f"{url}: la URL no esta bajo {prefijo!r}")
    tesela = _TeselaDelEspejo(url, prefijo)

    try:
        with rasterio.Env(**ENTORNO_GDAL):
            with rasterio.open(NOMBRE_TESELA, driver="GTiff", opener=tesela) as ds:
                etiquetas = ds.tags(ns="OVERVIEWS")
                if etiquetas:
                    raise ValueError(
                        f"{url}: el .tiff declara overviews externas {etiquetas!r}. "
                        "GDAL abriria ese segundo dataset sin driver fijado."
                    )
                if not opciones:
                    yield ds
                    return
            with rasterio.open(NOMBRE_TESELA, driver="GTiff", opener=tesela,
                               **opciones) as ds:
                yield ds
    # Any failure, not only RasterioIOError: a review found a refused range
    # during an OVERVIEW_LEVEL open surfacing as a bare SystemError ("returned a
    # result with an exception set"), because the callback's exception stays
    # pending inside GDAL. It still failed closed, but said nothing useful.
    except Exception as e:
        if tesela.fallo is not None and e is not tesela.fallo:
            raise tesela.fallo from e
        raise


def a_https(fuente: str) -> str:
    """Turn a validated /vsis3/<bucket>/<key> source into the tile's HTTPS URL.

    Anonymous HTTPS rather than S3 protocol, so the read path is the same one
    the guard already checked, against the same hard-coded host.
    """
    if not fuente.startswith("/vsis3/"):
        raise ValueError(f"{fuente!r}: no es una fuente /vsis3/")
    bucket, _, clave = fuente[len("/vsis3/"):].partition("/")
    return f"https://s3.us-west-2.amazonaws.com/{bucket}/{clave}"


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

    # Bounds in BOTH branches and on BOTH axes: rasterio silently clips an
    # over-long window. The north-up branch used to truncate where the bottom-up
    # one raised, and columns were never checked at all -- a review found an
    # overflowing `col` clipped in silence, feeding step 3's cosine a narrower
    # window than the one it reports.
    if fila < 0 or col < 0 or alto <= 0 or ancho <= 0:
        raise RuntimeError(
            f"ventana invalida: col={col} fila={fila} ancho={ancho} alto={alto}")
    if fila + alto > ds.height:
        raise RuntimeError(
            f"ventana fuera del raster: fila {fila}+{alto} sobre alto {ds.height}"
        )
    if col + ancho > ds.width:
        raise RuntimeError(
            f"ventana fuera del raster: col {col}+{ancho} sobre ancho {ds.width}"
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
