# AlphaEarth screening — one-off analysis, not part of the pipeline

These six scripts are the screening approved in `DATOS.md §3.6` and run on
2026-08-11. They are archived here so the numbers that entry publishes can be
re-derived rather than taken on trust — the same standard this project applies
to every external source.

**They are not part of the data pipeline.** `scripts/process_data.py` builds
everything in `data/` and does not import anything from this folder. Nothing
here produces a published layer, and by the rule in `§3.6` nothing it produces
may reach the Investment Index or share a field with a cited figure.

## Running them

Needs one dependency the pipeline does not use:

```bash
venv/Scripts/pip install rasterio
```

Run in order. Each writes its intermediate to `raw_data/alphaearth/`, which is
gitignored — these are working files, not published data.

| script | what it does | cost |
|---|---|---|
| `00_sondear_bucket.py` | learns the mirror's layout | a few KB |
| `01_localizar_teselas.py` | finds the zone-14N tiles covering the project | 711 KB |
| `02_bajar_overview.py` | reads the 160 m overview over the extent | ~3.8 MB |
| `03_verificar_overview.py` | checks unit norm and georeferencing | ~1 MB |
| `04_agregar_ageb.py` | builds the 431 × 64 AGEB table | local |
| `05_tamizaje.py` | the two cosine questions, plus sensitivity | local |
| `comun.py` | guards shared by the steps that touch the network | — |

Total transfer is about **4.5 MB**, against the **1.20 GB** a full-resolution
year over this extent would cost. The screening as run on 2026-08-11 cost
**4.4 MB**; the extra ~82 KB is the VRT each of steps 2 and 3 now fetches to
check where it points before GDAL opens it.

## Three traps, and why the code asserts rather than assumes

1. **The COGs are stored bottom-up.** Opening a `.tiff` directly returns north
   and south swapped, which would hand every AGEB the embedding of its
   *mirrored* location with nothing downstream looking wrong. Everything here
   goes through the `.vrt`, and refuses to continue if the y resolution is not
   negative.
2. **De-quantization is `((v/127.5)**2) * sign(v)`** — squared and
   sign-preserving, not a linear rescale. A linear one leaves the vectors off
   the unit sphere and distorts every cosine similarity computed from them.
3. **The VRTs reference their sources over `/vsis3/`**, so anonymous S3 access
   must be enabled or GDAL retries without credentials until it gives up.

The STAC index is deliberately not used: reading it needs `pyarrow`, and each
tile's `.vrt` already carries its SRS and GeoTransform in the first 1.2 KB, so
ranged reads over all 520 tiles cost less than the 4.99 MB index.

## What this trusts about the mirror, and what it does not

`source.coop` is a third party. Running these scripts means letting a host we
do not control decide what bytes this machine parses, and the security review
of 2026-08-11 raised three Low findings that all rest on that one precondition.
Naming the assumption is the point of this section: **the mirror is trusted to
serve the dataset it publishes, and nothing here assumes it is trusted to
decide where else this machine connects, or how much it downloads.**

**Where a VRT points is checked before anything is opened.** GDAL follows a VRT's
sources wherever they lead — reproduced here, not taken from a report: a VRT
naming `/vsicurl/http://127.0.0.1:<port>/x.tif` made GDAL issue two real
requests to that host. So steps 2 and 3 fetch each VRT and refuse it unless
every source sits under `/vsis3/us-west-2.opendata.source.coop/tge-labs/aef/`.

**But that check is not what bounds the damage, and two rounds of review are
how we learned it.** Every version of the guard that reasoned about **names**
was bypassed by something GDAL decides by **content**:

1. Element names were matched case-sensitively; GDAL matches them with
   `EQUAL()`, so `<sourcefilename>` was followed and never seen.
2. Refusing a source whose name ends in `.vrt` refuses a *name*. The VRT driver
   identifies a VRT by its header, so a hostile mirror serves the nested VRT
   called `.tiff` — which is what every real source is called.
3. The element allowlist bounds nothing either: `<GDAL_WMS>` names its target
   in `<ServerUrl>` and `GDALTileIndexDataset` in `<IndexDataset>`, both
   dispatched on content, with a decoy `<SourceFilename>` under the prefix to
   satisfy the rule.

All three were verified end to end, and 1 and 2 were shipped as fixed before
the next review found them still open.

**So the fix is structural, not a better parser.** GDAL now opens **exactly one
document per tile, with its driver pinned**: the `.tiff`, as `driver="GTiff"`.
There is no second open for a nested document to hijack, and no sniffing for a
disguised one to win. Measured, one process per case:

| hostile body served as `.tiff` | requests to the attacker's host |
|---|---|
| nested VRT, driver not pinned | 1 |
| `GDAL_WMS`, driver not pinned | 1 |
| nested VRT, **driver pinned** | **0** |
| `GDAL_WMS`, **driver pinned** | **0** |

**And that trade has a cost, which is the trap this screening exists to avoid.**
The `.tiff` is stored bottom-up, so reading it directly is exactly the mirrored
read that would hand every AGEB the embedding of the wrong place.
`comun.leer_ventana_north_up` handles both row orders explicitly, and it is
tested in both — against the `.vrt`'s own north-up reading of the same window,
at two overview levels, with a negative control confirming that an unflipped
read really does differ. The whole screening was then re-run: the regenerated
overview is byte-identical to the published intermediate in all five arrays.

**What is still not closed, stated first this time.** The mirror can tell this
check and GDAL apart trivially: the two requests carry different user agents
(`Python-urllib/…` versus `GDAL/…`), so a server can serve one body here and
another to GDAL. An earlier version of this section called that the expensive
attack while two one-line mutations were live; it is not expensive. What the
design buys is that a hostile body now has to arrive through the single
pinned-driver GTiff open, instead of through whatever document GDAL could be
led to open next.

**`CPL_VSIL_CURL_ALLOWED_EXTENSIONS` was measured and rejected** for the same
reason the `.vrt` rule failed — it is a rule about names. With `.vrt,.tiff`
allowed, a hostile source ending in `.tif` is blocked (0 requests) but one
ending in `.tiff` goes straight through (2 requests), and the pipeline needs
`.tiff`.

**Nothing here reads an unbounded body.** `Range:` is a request, not an
obligation: a server may answer `200` with a body of any size, so every read is
capped and every cap raises rather than truncating. Same for the two loops the
server steers — pagination stops at `MAX_PAGINAS`, and the key list is refused
past `MAX_TESELAS` before it becomes that many requests. GDAL gets
`GDAL_HTTP_TIMEOUT` and `GDAL_HTTP_CONNECTTIMEOUT`, because
`GDAL_HTTP_MAX_RETRY` bounds how many times it retries, not how long it waits;
and `GDAL_VRT_ENABLE_PYTHON` and `GDAL_VRT_ENABLE_RAWRASTERBAND` are pinned to
`NO` rather than inherited from the environment.

**What this is not.** These are one-off scripts run by hand on a laptop, and
the guards are sized for that: they keep a hostile mirror from steering this
machine's network stack or hanging it, and they are not a sandbox.

## Attribution

Required by the dataset's CC-BY 4.0 licence:

> The AlphaEarth Foundations Satellite Embedding dataset is produced by Google
> and Google DeepMind.

Citation: Brown, Kazmierski, Pasquarella et al. (2025), arXiv:2507.22291.
