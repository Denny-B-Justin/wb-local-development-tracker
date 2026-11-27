# wb-local-development-tracker

The **Local Development Tracker (LDT)** as a Python 3.11.9 Dash app: the pim-pam LDT design (formerly a Next.js app) rebuilt page for page, reading its data from **Azure Databricks Unity Catalog** (`prd_mega.sgpbpi163`) through an OAuth service principal, and deployable to **Posit Connect**.

- Public site: Home, Why LDT, Methodology, Resources, Release notes, About.
- Country workspace: Map, Compare, Local units, Unit profile, Planning brief (AI), Data & trust, Strategy inventory.
- Countries: Nepal, Serbia, Zambia, Vietnam, Guinea (see §8 for what is different about Vietnam, §12 for Guinea). English and French.

---

## 1. Quick start

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env            # fill in the DATABRICKS_* values
LDT_ENV=development python app.py   # http://127.0.0.1:8050/?page=home
```

Without Databricks credentials the app still runs from `data_snapshot/` (Nepal, Serbia and Zambia from the ldt-demo bundles; Vietnam and Guinea from their Unity Catalog tables).

## 2. URLs

Every screen is a query-string URL on `/`:

| URL | Page |
| --- | --- |
| `/?page=home` (or `/`) | Landing |
| `/?page=why-ldt`, `methodology`, `resources`, `release-notes`, `about` | Site pages |
| `/?page=map&country=nepal` | Workspace map |
| `/?page=compare&country=nepal&compare=<id>,<id>` | Compare (up to 5 units) |
| `/?page=municipalities&country=serbia&q=nis&sort=composite&dir=desc` | Local units table |
| `/?page=profile&country=zambia&unit=<id>&tab=drivers` | Unit profile |
| `/?page=brief&country=nepal&scope=<id>&score=prosperity` | Planning brief |
| `/?page=data&country=nepal` | Data & trust |
| `/?page=strategy-inventory&country=serbia` | Strategy inventory |

Shared parameters: `year`, the country's level keys (`province`, `district`, `region`, …) for the area filter, `pillar`, `indicator`, `selected`, `view`, `lang=fr`. Unknown parameters are dropped; every value is validated (§9). Unit ids are stable 12-hex hashes of `ISO3 + names`, so links survive data refreshes.

## 3. Layout

```
app.py                  Dash app, index template, router callback, security + API wiring
constants.py            Deployment constants: env vars, UC catalog/schema/tables, cache, AI, security
countries/              One module per country (levels, release, plans, table shape) + registry
pages/                  One module per page; pages_constants.py holds page copy/structure
utils/                  Design system: components.py (cards, badges, menus…), shell.py (headers, sidebar)
services/
  databricks.py         OAuth SP connection, parameterized SQL, IDENTIFIER(:table)
  assemble.py           UC tables → country bundle + boundary GeoJSON
  store.py              gz artifacts in .ldt_cache/ → data_snapshot/; background warm
  model.py              Ranking, filters, summaries, drivers, trends, peers, coverage
  state.py              URL ⇄ request state; security.py validation, headers, CORS, rate limits
  api.py                /api/geometry, CSV/MD exports, brief stages, /healthz, /api/admin/refresh
  plans.py, inventory.py, i18n.py, catalog.py, text.py, ai/
assets/                 styles.css, js/ (navigation, map, charts, hero, brief), fonts/, icons/, img/,
                        geo/context/ (map surroundings), vendor/maplibre/
locales/                en.json, fr.json
scripts/                build_snapshot.py, check_country.py, build_map_context.py, uc_tables.sql
data_snapshot/          Shipped fallback artifacts (deployed with the app)
```

Rendering model: one `dcc.Location` + one callback renders the whole page from `?…`. Internal links are plain anchors that `assets/js/ldt-1-core.js` turns into client-side navigation (no full reloads, back button works). The map (MapLibre, vendored, no tiles fetched), charts and hero animation are small JS widgets mounted from `data-widget` attributes, so the browser draws them directly instead of round-tripping figures through Python.

## 4. Data flow

```
Unity Catalog tables ──(SQL warehouse, OAuth SP)──► services/assemble.py ──► .ldt_cache/*.json.gz
                                                                          └─► data_snapshot/ (fallback)
request ──► services/store.py (memory → cache → snapshot) ──► services/model.py ──► pages/*
```

Databricks is never queried on a page request. Artifacts are rebuilt in a background thread at startup when missing or older than `LDT_DATA_MAX_AGE_SECONDS` (6 h), or on demand:

```bash
curl -X POST -H "Authorization: Bearer $LDT_REFRESH_TOKEN" https://<connect-host>/<app>/api/admin/refresh
```

Before a deploy, refresh the shipped fallback so a cold start never shows stale numbers:

```bash
python scripts/build_snapshot.py                          # from Databricks
python scripts/build_snapshot.py --from-legacy <ldt-demo>/assets/data   # offline, from demo bundles
```

## 5. Databricks setup

1. **Service principal.** In the Azure Databricks account console create (or reuse) a service principal, generate an OAuth secret, and note the *Application (client) ID* and secret.
2. **SQL warehouse.** Give the principal *Can use* on a SQL warehouse; copy its *Server hostname* and *HTTP path* (Connection details).
3. **Grants** (run as a schema owner):
   ```sql
   GRANT USE CATALOG ON CATALOG prd_mega TO `<application-id>`;
   GRANT USE SCHEMA, SELECT ON SCHEMA prd_mega.sgpbpi163 TO `<application-id>`;
   GRANT READ VOLUME ON VOLUME prd_mega.sgpbpi163.vgpbpi163 TO `<application-id>`;          -- inventory fallback
   GRANT MODIFY ON TABLE prd_mega.sgpbpi163.ldt_ai_stage_cache TO `<application-id>`;       -- optional brief cache
   ```
4. **Environment**: `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET` (and optionally `LDT_CATALOG`, `LDT_SCHEMA`). Connections use TLS (HTTPS) end to end; the secret never leaves the server.
5. Check a country: `python scripts/check_country.py NPL`.

## 6. Unity Catalog tables

### Current tables (read today)

| Role | Nepal | Serbia | Zambia | Vietnam | Guinea |
| --- | --- | --- | --- | --- | --- |
| indicators | `ldt_gpbp_ldt_npl_admin_2_demo` | `ldt_gpbp_ldt_srb_admin_2_demo` | `ldt_gpbp_ldt_zmb_admin_2_demo` | `ldt_indicators_vietnam` | `ldt_indicators_guinea` |
| scores | `ldt_gpbp_ldt_npl_scores_admin_2_demo` | `ldt_gpbp_ldt_srb_scores_admin_2_demo` | `ldt_gpbp_ldt_zmb_scores_admin_2_demo` | `ldt_scores_vietnam` | `ldt_scores_guinea` |
| boundaries | `ldt_boundaries_admin2_nepal` | `ldt_boundaries_admin2_serbia` | `ldt_boundaries_admin2_zambia` | `ldt_boundaries_admin2_vietnam` | `ldt_boundaries_admin2_guinea` |

Shared (all optional — a missing table only empties that feature): `ldt_plan_document_sources`, `ldt_strategy_inventory_documents`, `ldt_ai_stage_cache`.

Every name is overridable without code changes: `LDT_<ISO3>_INDICATORS_TABLE`, `LDT_<ISO3>_SCORES_TABLE`, `LDT_<ISO3>_BOUNDARIES_TABLE`, `LDT_PLAN_SOURCES_TABLE`, `LDT_STRATEGY_INVENTORY_TABLE`, `LDT_AI_STAGE_CACHE_TABLE`.

### Recommended names (new loads and re-loads)

Lower-case, ISO3-first, level-explicit, no `demo`/`gpbp` noise (`constants.UC_TABLE_NAMING`):

| Role | Pattern | Example |
| --- | --- | --- |
| Indicator panel | `ldt_{iso3}_admin2_indicators` | `ldt_gin_admin2_indicators` |
| Score panel | `ldt_{iso3}_admin2_scores` | `ldt_gin_admin2_scores` |
| Boundaries | `ldt_{iso3}_admin2_boundaries` | `ldt_gin_admin2_boundaries` |
| Plan documents | `ldt_plan_document_sources` | one table, `country_code` column |
| Strategy inventory | `ldt_strategy_inventory_documents` | one table, `country_code` column |
| Brief cache | `ldt_ai_stage_cache` | one table |

When existing countries are re-loaded, move them to the pattern (e.g. `ldt_npl_admin2_scores`) and point the env overrides at the new names; no code changes are needed. Full DDL with column types: `scripts/uc_tables.sql`.

### Data contract

- **Scores**: one row per local unit per year; a year column (`Year`/`year`), the hierarchy name columns named in the country module, the three pillar scores (`Prosperity Score`, `Infrastructure Score`, `Livability Score`) and the 18 component scores, all 0–100. Column matching ignores case, spaces and punctuation, so `prosperity_score` also works.
- **Indicators**: same keys plus `Population` and `Total Land Area (km2)` (context) and raw indicators.
- **Boundaries**: admin-1 and admin-2 names spelled as in the score table, and a geometry column (`geometry_wkt`, WKB or GeoJSON) in EPSG:4326 (or set `Source.crs`). Names are matched after accent/case folding; unmatched polygons are listed on Data & trust as boundary gaps.

## 7. Migrating data into Unity Catalog

**Is a NoSQL database in use?** No dedicated NoSQL store (no MongoDB, Firestore, Redis, DynamoDB). The Next.js app used **Supabase Postgres** (relational, `analytics` schema), but with document-style parts that need flattening:

- **JSONB columns** — `municipality_boundaries.raw_properties`, `boundary_ingest_issues.details`, `ai_document_contexts.passages/chunks/extraction_metadata`, `ai_stage_cache.structured_output/source_references`, `ai_stage_runs.model_settings/token_usage/…`.
- **JSON/GeoJSON file blobs** — the ldt-demo shipped `analytics-data.json` + `municipalities.geojson` per country; Next built `public/geo/context/*.json`.

| Source (Supabase `analytics.*` / files) | Unity Catalog target | How |
| --- | --- | --- |
| `municipalities` + `municipality_score_values` + `municipality_score_component_values` (long: one row per unit × score) | `ldt_{iso3}_admin2_scores` (wide) | Pivot to one row per unit × year, one column per score (SQL below) |
| `municipality_indicator_values` + `municipality_context_values` + `indicators` | `ldt_{iso3}_admin2_indicators` | Pivot by indicator name |
| `municipality_boundaries` (PostGIS `geometry`) | `ldt_{iso3}_admin2_boundaries` | Export `ST_AsText(geom)` as `geometry_wkt`; drop `raw_properties` or keep it as a `STRING` of JSON |
| `plan_document_sources`, `province_plan_sources` | `ldt_plan_document_sources` | Union; `province_plan_sources` rows get `plan_level='province'` |
| `strategy_inventory_documents` | `ldt_strategy_inventory_documents` | Copy as-is |
| `ai_stage_cache` (JSONB payload) | `ldt_ai_stage_cache` | Serialise JSONB to a JSON `STRING` column `payload`; read back with `from_json`/`:` path syntax |
| `ai_document_contexts`, `ai_stage_runs` | not needed | The Dash app extracts text on demand and keeps run counts locally |
| `analytics-data.json` / `municipalities.geojson` blobs | the three per-country tables | `python scripts/build_snapshot.py --from-legacy …` reads them directly, or load them with the notebook steps below |
| `dataset_releases`, `countries`, `score_definitions`, `score_components` | code (`countries/*.py`, `services/catalog.py`) | Static metadata; versioned with the app |

Steps:

1. **Export** from Supabase (`psql`): `\copy (SELECT …) TO 'scores_long.csv' CSV HEADER` for each table, with `ST_AsText(geom) AS geometry_wkt` for boundaries and `payload::text` for JSONB.
2. **Upload** the CSVs to the Volume: `/Volumes/prd_mega/sgpbpi163/vgpbpi163/LDT/import/`.
3. **Create** the tables: run `scripts/uc_tables.sql`.
4. **Load and pivot** in a Databricks SQL editor or notebook, for example:
   ```sql
   CREATE OR REPLACE TEMP VIEW scores_long AS
   SELECT * FROM read_files('/Volumes/prd_mega/sgpbpi163/vgpbpi163/LDT/import/scores_long.csv', format => 'csv', header => true);

   INSERT OVERWRITE prd_mega.sgpbpi163.ldt_npl_admin2_scores
   SELECT * FROM scores_long
   PIVOT (first(score_value) FOR score_label IN ('Prosperity Score', 'Infrastructure Score', 'Livability Score' /* , the 18 components */));
   ```
   JSON documents (e.g. a GeoJSON FeatureCollection) can be flattened with `read_files(..., format => 'json', multiLine => true)` + `explode(features)` and `to_json(feature.geometry)` into the geometry column.
5. **Verify**: `python scripts/check_country.py NPL` (row counts, years, missing columns, boundary match rate).
6. **Switch** the app by setting the `LDT_NPL_*_TABLE` overrides, then `POST /api/admin/refresh` and rebuild `data_snapshot/`.

## 8. Vietnam is different

- **Two levels, not three.** The July 2025 reform abolished districts: 34 provinces/centrally-run cities sit directly above ~3,300 communes, wards and special zones. The country module declares `Province → Commune`; the area filter has a single level and the UI says "communes & wards".
- **snake_case tables.** `ldt_indicators_vietnam` / `ldt_scores_vietnam` use `year`, `land_area_km2`, `*_pct` instead of the GPBP CSV headers. `Source.year_candidates` and `Source.column_aliases` in `countries/vnm.py` map them; column matching is punctuation-insensitive.
- **Diacritics.** Vietnamese names (Đà Nẵng, Thừa Thiên Huế) are folded for search, slugs and matching; `đ/Đ` is handled explicitly because Unicode NFD does not decompose it. Self-hosted fonts include the Vietnamese subsets.
- **Map.** ~3,300 polygons: a coarser simplification (`simplify_tolerance=0.0015`), deeper `map_max_zoom`, and its own surroundings file `assets/geo/context/vietnam.json`.
- **Plans** are filed by province (`plan_source_level="top"`), not per commune.

## 9. Security

- **SQL**: only parameterized statements; table names go through `IDENTIFIER(:table)` after allowlist validation (`^[A-Za-z_][A-Za-z0-9_]{0,127}$`); no user input ever reaches SQL. Read-only grants for the principal.
- **Input**: every query parameter is allow-listed, length-capped, control-character-stripped and pattern-checked (unit ids `[a-f0-9]{12}`, slugs, metric ids, enums); the query string is capped at 2 KB (414 otherwise). Text is rendered through Dash components (escaped), never as raw HTML.
- **XSS / headers**: strict Content-Security-Policy with hashes for Dash's inline scripts, `frame-ancestors 'self'` / `X-Frame-Options: SAMEORIGIN` (Connect's own viewer can still frame it), `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, HSTS over HTTPS.
- **CORS**: same-origin only, plus explicit `LDT_ALLOWED_ORIGINS`; POST endpoints reject cross-origin requests.
- **Debug off**: Dash debug runs only when `LDT_ENV=development` **and** `DASH_DEBUG=1`; errors show a generic page, details go to the server log.
- **Secrets**: all keys come from environment variables (`.env` locally, Connect *Vars* in production); `.env` is git-ignored and excluded from `manifest.json`.
- **Admin routes**: `/api/admin/refresh` and the detailed `/healthz` need `LDT_REFRESH_TOKEN` (constant-time compare); preview countries need `LDT_PREVIEW_TOKEN`. No login exists in LDT, so there are no user roles to separate.
- **Exposed files**: source, `.env`, `.git`, caches, snapshots, locales, scripts, `manifest.json`, `requirements.txt`, `*.py/.gz/.map` return 404. Only `assets/` is static.
- **Abuse**: per-client rate limits on `/api/*` and the AI brief (hourly per visitor, daily overall); CSV exports neutralise spreadsheet formulas; plan downloads for the brief refuse private/loopback addresses (SSRF) and cap size.
- **Fonts**: Inter and Fira Sans are self-hosted WOFF2 subsets (OFL) — no Google Fonts request, nothing third-party loaded by the browser.

## 10. Deploying to Posit Connect

```bash
pip install rsconnect-python
rsconnect add --server https://<connect-host> --name ldt --api-key <key>
python scripts/build_snapshot.py               # optional: fresh fallback data
rsconnect write-manifest dash . --entrypoint app:app --exclude ".env" --exclude ".ldt_cache/**" --overwrite
rsconnect deploy manifest manifest.json -n ldt --title "Local Development Tracker"
```

`manifest.json` in the repo is ready to use (`python-dash`, entrypoint `app:app`, Python 3.11.9); regenerate it with `write-manifest` whenever files change. In Connect → *Vars*, set the `DATABRICKS_*` values, `LDT_REFRESH_TOKEN`, and (optionally, for the planning brief) `MAI_BASE_URL`, `MAI_ENDPOINT` and `MAI_MODEL` (see §11). Leave *Integrations* empty. Connect serves the app under a sub-path and sets Dash's path prefix itself; the app's own links, API calls and asset URLs are relative, so nothing needs configuring. Set *Min processes* to 1 so the warm cache stays hot.

## 11. Planning brief (optional AI)

All AI code lives in `ai/`. The brief reads the unit's plans (from `ldt_plan_document_sources`), extracts text (pypdf), picks the plan passages relevant to the score theme, optionally searches the web, and calls the **Posit mAI Gateway** through the OpenAI Responses API (`ai/client.py`). It runs on one model, `gpt-6-luna` by default (`MAI_MODEL`; `gpt-5.6-luna` also works). These are the allowed models with web search, which the brief uses by default; `gpt-6-luna` also has file search, needed for document upload. Web search uses the model's own search tool, so there is no separate search key.

mAI needs no API key: requests carry `X-Posit-App-Id` from `CONNECT_CONTENT_GUID` (set by Posit Connect) and are accepted only from apps running on Connect, so generation is unavailable locally (cached briefs still show). Set `MAI_BASE_URL` and `MAI_ENDPOINT` for QA or Production as listed in `.env.sample`.

Results are cached on disk and, when the table exists, in `ldt_ai_stage_cache` so all instances share them. Change `AI_PROMPT_VERSION` whenever `ai/prompt.py` changes. Set `AI_GENERATION_DISABLED=1` to serve cached briefs only.

## 12. Onboarding a new country (worked example: Guinea, GIN)

Guinea is onboarded: 8 regions (admin-1, incl. Conakry) → 342 communes (rural communes and urban communes, `CU …`), two levels, French names with accents and apostrophes (N'Zérékoré). It comes from the same pipeline as Vietnam, so the steps below use its real values.

**1. Check the tables in Unity Catalog.** The Vietnam/Guinea pipeline writes `ldt_indicators_<country>`, `ldt_scores_<country>` and `ldt_boundaries_admin2_<country>` (country name in lowercase). Guinea's tables:

| Table | Rows | Columns that matter |
| --- | --- | --- |
| `ldt_indicators_guinea` | 342 per year, 2021–2025 | `NAM_1`, `NAM_2`, `year`, `population`, `total_land_area_km2`, snake_case measures |
| `ldt_scores_guinea` | 342 per year, 2021–2025 | `NAM_1`, `NAM_2`, `year`, `*_score` (no flood scores), `infrastructure_score`, `livability_score`, `prosperity_score` |
| `ldt_boundaries_admin2_guinea` | 342 | `NAM_1`, `NAM_2`, `geometry_wkb` (EPSG:4326) |

Names must be spelled identically in all three. Unlike Vietnam (`Province`, `Municipality`), Guinea's score and indicator tables use `NAM_1`/`NAM_2`. Do not use `ldt_boundaries_guinea` (38 prefecture polygons, unaccented names) for the local level.

**2. Register the tables** in `constants.py` (`UC_COUNTRY_TABLES["GIN"]`, each overridable with `LDT_GIN_*_TABLE`).

**3. Describe the country** in `countries/gin.py`:
- `hierarchy={"province": "NAM_1", "district": "NAM_1", "municipality": "NAM_2"}`: the score/indicator column for each of the app's three roles; with two levels, `district` repeats the admin-1 column.
- `levels`: `Level("region", "province", …)` and `Level("commune", "municipality", …)`. Level keys become URL parameters (`&region=conakry`) and must not clash with reserved ones.
- `column_aliases` is only needed when population or land area use another spelling (Vietnam: `land_area_km2`); Guinea's `population` and `total_land_area_km2` are matched by default. Score columns match regardless of case and punctuation (`broadband_internet_score` = "Broadband Internet Score"; `emissions_normalized_score` = Emissions per Area).
- `national_plan` is optional and left unset until an official plan link is confirmed.
- `validate()` runs at import and refuses an inconsistent entry with a readable message.

**4. Add it to the registry** in `countries/__init__.py` (tuple order = display order).

**5. Translations** in `locales/en.json` and `locales/fr.json`: `data.countries.GIN`, `data.levels.region`, `data.landingMeta.GIN`, `data.aiMessage.GIN`. Missing keys fall back to the English strings in the country module.

**6. Map surroundings** (neighbours and sea, drawn offline):

```bash
curl -L -o /tmp/ne10.geojson https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson
python scripts/build_map_context.py /tmp/ne10.geojson --only GIN    # writes assets/geo/context/guinea.json
```

**7. Validate and build**:

```bash
python scripts/check_country.py GIN      # columns, years, units, boundary matches (Guinea: 342 of 342)
python scripts/build_snapshot.py         # writes country_GIN / geometry_GIN to data_snapshot/
```

**8. Publish.** `status="preview"` hides a country from everyone except reviewers who open `/api/preview?token=<LDT_PREVIEW_TOKEN>` once (sets a cookie); `status="draft"` hides it fully while tables load. Guinea is `published`. Regenerate `manifest.json` and redeploy.

## 13. Adding a language

Copy `locales/en.json` to `locales/<code>.json`, translate the values (keep keys and `{placeholders}`), and add the code to `LOCALES` and `LOCALE_NAMES` in `constants.py`. Plural forms use `one`/`other` keys.
