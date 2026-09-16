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

| script | what it does | transfer, measured 2026-09-16 |
|---|---|---|
| `00_sondear_bucket.py` | learns the mirror's layout | a few KB |
| `01_localizar_teselas.py` | finds the zone-14N tiles covering the project | 711 KB |
| `02_bajar_overview.py` | reads the 160 m overview over the extent | 25.1 MB, ~45 s |
| `03_verificar_overview.py` | checks unit norm and georeferencing | 77.0 MB, ~65 s |
| `04_agregar_ageb.py` | builds the 431 × 64 AGEB table | local |
| `05_tamizaje.py` | the two cosine questions, plus sensitivity | local |
| `comun.py` | guards shared by the steps that touch the network | — |

Total transfer is about **103 MB**. **This corrects a figure published here
and in `DATOS.md §3.6` for a month: "~4.4 MB", with ~3.8 MB and ~1 MB for
steps 2 and 3.** None of those was a transfer measurement. They match the
size of the arrays read (a 4.55 MB `int8` grid for step 2), and a COG cannot
be read by the pixel: each band of the level-3 overview is one compressed
block of ~200 KB, so step 2 has to fetch 64 of them per tile whatever
transport it uses, and step 3's 16 × 16 px at full resolution sits in 64
blocks of ~630 KB. Measured both ways — the old GDAL `/vsicurl/` path through
a byte-counting proxy, the current one at the opener:

| step | old `/vsicurl/` | current opener | bytes GDAL actually asked for |
|---|---|---|---|
| 2 | 39.8 MB | 25.1 MB | 25.1 MB |
| 3 | 78.8 MB | 77.0 MB | — |

The old path spent the difference on read-ahead. The output is unchanged:
the regenerated overview has the same SHA-256 as the published intermediate,
and step 3 reproduces cosine 0.999934 against the mirrored control's 0.460602.
The current path is slower (46 s against 8 s for step 2), because each range is
its own HTTPS request; for a one-off script that is the cheaper side of the
trade, and the reason is below.

## Three traps, and why the code asserts rather than assumes

1. **The COGs are stored bottom-up.** Opening a `.tiff` directly returns north
   and south swapped, which would hand every AGEB the embedding of its
   *mirrored* location with nothing downstream looking wrong. Step 1 reads the
   `.vrt` and refuses a non-negative y resolution; steps 2 and 3 read the
   `.tiff` and so must **handle** the flip instead of refusing it — see the
   security section below for why refusing stopped being an option.
2. **De-quantization is `((v/127.5)**2) * sign(v)`** — squared and
   sign-preserving, not a linear rescale. A linear one leaves the vectors off
   the unit sphere and distorts every cosine similarity computed from them.
3. **The VRTs reference their sources over `/vsis3/`**, which GDAL would open
   with S3 credentials and retry until it gave up. Nothing here opens it that
   way any more: steps 2 and 3 rewrite the source to its HTTPS URL and fetch
   the bytes themselves (`comun.a_https`, `comun.abrir_tesela`), and step 1
   reads VRT headers with urllib. The `AWS_*` keys left in `ENTORNO_GDAL` are
   inert today.

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

**So the fix is structural, not a better parser.** GDAL now opens the `.tiff`
with `driver="GTiff"`, which bounds the top-level open. Measured, one process
per case:

| hostile body served as `.tiff` | requests to the attacker's host |
|---|---|
| nested VRT, driver not pinned | 1 |
| `GDAL_WMS`, driver not pinned | 1 |
| nested VRT, **driver pinned** | **0** |
| `GDAL_WMS`, **driver pinned** | **0** |

**That was written up as "exactly one document", and a third review showed it
was false.** Pinning the driver bounds the top-level open and nothing after it:
GTiff honours the `OVERVIEWS/OVERVIEW_FILE` metadata item and carries that
domain **inside the file's own `GDAL_METADATA` tag**, so a hostile `.tiff` names
a second dataset from within itself, GDAL opens it **unpinned**, and the review
chained that to a third host and served the analysed pixels from it. It only
fires when the tile ships no internal overviews — which the attacker decides,
since the attacker publishes the file — and `GDAL_DISABLE_READDIR_ON_OPEN` does
not suppress it, because this is not a sibling probe.

`comun.abrir_tesela` refuses it, read off a flat open before any
`OVERVIEW_LEVEL` open, at no extra request. It is a rule about the content of
the one document we allow rather than about the name of a second one. It began
as a separate function each script had to remember to call first; a review
pointed out it was the one guard still left to memory, so it now lives inside
the only function that opens a tile:

| tile declaring an external overview | requests to the attacker's host |
|---|---|
| no guard, `OVERVIEW_LEVEL=3` | 3 at `open()`, 4 after `read()` — and the pixels come from there |
| **guard in place** | **0, and the run stops** |

**Then the fix for redirects turned out to cover the wrong half.** A review
found urllib following a mirror's redirect to whatever host it named, so
`abrir_url` began refusing them before the connection. That covered the four
urllib calls — a few KB of XML. The raster's bytes were fetched by GDAL's
`/vsicurl/`, which follows redirects on its own, and the GDAL 3.12 build here
has no option to stop it: no `FOLLOWLOCATION` or `MAX_REDIRECTS` exists in the
library at all, and a review measured `GDAL_HTTP_MAX_REDIRECTS=0` doing nothing.
So **GDAL no longer touches the network for a tile.** `abrir_tesela` hands it a
bare name and a rasterio opener, and the opener fetches every byte range through
`abrir_url`. Each case below ran in its own process against local servers, and
each guard has a control showing the test can see the attack:

| case | requests to the attacker | result |
|---|---|---|
| mirror 302s the `.tiff`, old `/vsicurl/` path | 2 | the pixel read is the attacker's |
| mirror 302s the `.tiff`, **opener** | **0** | refused, naming the redirect |
| absolute `Location` with `/../` under the prefix, **opener** | **0** | refused |
| mirror serves the `.tiff` directly (control) | 0 | opens, correct pixel |
| sibling probing re-enabled, **opener** | **0** | GDAL asked for sidecar names (`.aux.xml`, `.aux`, `.msk`, `.xml`… four in one run, eight in the review's) — all answered "no such file" locally |
| server ignores `Range` and answers 200 | 0 | refused before reading a body |
| file changes size between two ranges | 0 | refused |

`abrir_url` now refuses **every** redirect rather than those that leave the
prefix. The narrower rule compared text, and an absolute `Location` with dot
segments starts with the prefix and resolves outside it. There was nothing for
the rule to decide: the mirror answers the VRT, the `.tiff` and the listing
directly (206, 206, 200) and redirects none of them.

**Also from that review, and both cheap:** the `..` rule was evaded with
`%2e%2e`, because curl percent-decodes before normalising dot segments — the
key is now matched against a conservative alphabet instead, which disposes of
`?`, `#`, `@` and `\` at the same time. And `leer_ventana_north_up` checked its
bounds in only one of its two branches, and would have flipped a degenerate
dataset silently; both are handled inside the function now rather than relying
on the caller having called `bordes_north_up` first.

**One config value earns a note:** `GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR` is
a security guard, not a performance one. Removing it, GDAL probes eight sibling
paths on open and a hostile `.ovr` next to a tile reaches a foreign host **even
with the driver pinned**. Measured both ways. Since the opener, a probe that
slips past it ends at the opener instead of on the network, so it is the first
of two layers rather than the only one.

**And the trade has a cost, which is the trap this screening exists to avoid.**
The `.tiff` is stored bottom-up, so reading it directly is exactly the mirrored
read that would hand every AGEB the embedding of the wrong place.
`comun.leer_ventana_north_up` handles both row orders explicitly, and it is
tested in both — against the `.vrt`'s own north-up reading of the same window,
at two overview levels, with a negative control confirming that an unflipped
read really does differ. The whole screening was then re-run: the regenerated
overview is byte-identical to the published intermediate in all five arrays.

**What is still not closed, stated first this time.** The mirror decides the
bytes: it can serve a VRT that passes every source rule and a `.tiff` whose
pixels are wrong, and nothing here can tell. That is the trust named at the top
of this section. What it can no longer do is make this machine connect anywhere
else, since urllib and GDAL now fetch through the same guard. This paragraph
used to say the mirror could serve one body to the check and another to GDAL by
their user agents; both requests now come from urllib, but a server can still
tell a VRT request from a tile request by the path. So that split is not closed
either, only no longer free. And the opener stops relative names, not absolute
ones: an absolute path GDAL decides to open goes around it, which is why the
external-overview rule stays.

**`CPL_VSIL_CURL_ALLOWED_EXTENSIONS` was measured and rejected** for the same
reason the `.vrt` rule failed — it is a rule about names. With `.vrt,.tiff`
allowed, a hostile source ending in `.tif` is blocked (0 requests) but one
ending in `.tiff` goes straight through (2 requests), and the pipeline needs
`.tiff`.

**Nothing here reads an unbounded body.** `Range:` is a request, not an
obligation: a server may answer `200` with a body of any size, so every read is
capped and every cap raises rather than truncating. Same for the two loops the
server steers — pagination stops at `MAX_PAGINAS`, and the key list is refused
past `MAX_TESELAS` before it becomes that many requests. A tile used to be
the exception, because GDAL read whatever the file's own offsets told it to:
one tile open may now fetch at most `LIMITE_TESELA` (128 MB, about 3× the
largest real read), every range must come back as exactly the range asked for,
and every request has urllib's timeout. `GDAL_HTTP_TIMEOUT` and
`GDAL_HTTP_CONNECTTIMEOUT` stay for any request GDAL still makes itself, and
`GDAL_VRT_ENABLE_PYTHON` and `GDAL_VRT_ENABLE_RAWRASTERBAND` are pinned to `NO`
rather than inherited from the environment.

**What this is not.** These are one-off scripts run by hand on a laptop, and
the guards are sized for that: they keep a hostile mirror from steering this
machine's network stack or hanging it, and they are not a sandbox.

## Attribution

Required by the dataset's CC-BY 4.0 licence:

> The AlphaEarth Foundations Satellite Embedding dataset is produced by Google
> and Google DeepMind.

Citation: Brown, Kazmierski, Pasquarella et al. (2025), arXiv:2507.22291.
