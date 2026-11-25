-- Unity Catalog DDL for the Local Development Tracker (catalog prd_mega, schema sgpbpi163).
-- Run in a Databricks SQL editor as a user who can create tables in the schema.
-- The per-country tables follow the naming in constants.UC_TABLE_NAMING; Guinea is the example.

USE CATALOG prd_mega;
USE SCHEMA sgpbpi163;

-- ---------------------------------------------------------------------------
-- Per country (example: Guinea, GIN). Columns mirror the GPBP datacube CSVs.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ldt_gin_admin2_indicators (
  Year INT NOT NULL,
  Province STRING NOT NULL,          -- admin-1 (Guinea: region)
  District STRING,                   -- optional middle level; repeat Province when there is none
  Municipality STRING NOT NULL,      -- admin-2 local unit (Guinea: prefecture)
  Population DOUBLE,
  `Total Land Area (km2)` DOUBLE
  -- + the raw indicator columns from GPBP_LDT_GIN_admin_2.csv (kept for provenance)
) COMMENT 'LDT indicator panel, one row per admin-2 unit per year';

CREATE TABLE IF NOT EXISTS ldt_gin_admin2_scores (
  Year INT NOT NULL,
  Province STRING NOT NULL,
  District STRING,
  Municipality STRING NOT NULL,
  `Prosperity Score` DOUBLE, `Infrastructure Score` DOUBLE, `Livability Score` DOUBLE,
  `Luminosity per Capita Score` DOUBLE, `Luminosity per Area Score` DOUBLE, `Built Area Development Score` DOUBLE,
  `Tourism Score` DOUBLE, `Agricultural Land Score` DOUBLE,
  `Broadband Internet Score` DOUBLE, `Mobile Internet Score` DOUBLE, `Key Structure Internet Access Score` DOUBLE,
  `Accessibility to Hospitals Score` DOUBLE, `Accessibility to Schools Score` DOUBLE,
  `Emissions Score` DOUBLE, `Air Quality Score` DOUBLE, `Deforestation Score` DOUBLE, `Emissions Normalized Score` DOUBLE,
  `Railway Heatwave Score` DOUBLE, `Road Heatwave Score` DOUBLE, `Road Flood Score` DOUBLE, `Railway Flood Score` DOUBLE
) COMMENT 'LDT 0-100 score panel, one row per admin-2 unit per year';

CREATE TABLE IF NOT EXISTS ldt_gin_admin2_boundaries (
  NAM_1 STRING NOT NULL,             -- admin-1 name, spelled exactly as in the score table
  NAM_2 STRING NOT NULL,             -- admin-2 name, spelled exactly as in the score table
  geometry_wkt STRING NOT NULL       -- EPSG:4326 WKT (WKB / GeoJSON also accepted)
) COMMENT 'LDT admin-2 boundaries';

-- ---------------------------------------------------------------------------
-- Shared tables (all countries). Optional: missing tables show empty states.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ldt_plan_document_sources (
  country_code STRING NOT NULL,      -- ISO3
  plan_level STRING NOT NULL,        -- 'national' | 'province' (area or local unit plans)
  province STRING,                   -- area / unit name the plan is filed under (matched case-insensitively)
  title STRING NOT NULL,
  link STRING NOT NULL,              -- public http(s) URL to the PDF or page
  document_type STRING,              -- e.g. local_development_plan, national_development_plan
  score_theme STRING,
  notes STRING,
  priority INT,
  is_active BOOLEAN NOT NULL
) COMMENT 'Plan documents used by Data & trust, profiles and planning briefs';

CREATE TABLE IF NOT EXISTS ldt_strategy_inventory_documents (
  country_code STRING NOT NULL, lsg_id STRING, lsg_name STRING NOT NULL, lsg_name_local STRING, region_name STRING,
  document_type STRING, document_title STRING, publication_year INT, valid_from_year INT, valid_to_year INT,
  source_url STRING, source_status STRING, language STRING, translation_status STRING, parsing_status STRING,
  ai_ready BOOLEAN, comprehensiveness_score DOUBLE, notes STRING, last_updated DATE, is_active BOOLEAN NOT NULL
) COMMENT 'Strategy inventory (Serbia, Zambia, ...)';

CREATE TABLE IF NOT EXISTS ldt_ai_stage_cache (
  cache_key STRING NOT NULL,         -- sha256 of scope + stage + prompt/invalidation versions
  country_code STRING NOT NULL, release_key STRING NOT NULL, municipality_key STRING NOT NULL,
  score_id STRING NOT NULL, stage STRING NOT NULL, prompt_version STRING,
  payload STRING NOT NULL,           -- JSON stage result (the Supabase jsonb columns, serialised)
  updated_at TIMESTAMP
) COMMENT 'Planning-brief stage cache shared across app instances';

-- The app's service principal needs:
--   GRANT USE CATALOG ON CATALOG prd_mega TO `<sp-application-id>`;
--   GRANT USE SCHEMA, SELECT ON SCHEMA prd_mega.sgpbpi163 TO `<sp-application-id>`;
--   GRANT MODIFY ON TABLE prd_mega.sgpbpi163.ldt_ai_stage_cache TO `<sp-application-id>`;   -- only if briefs are cached in UC
--   GRANT READ VOLUME ON VOLUME prd_mega.sgpbpi163.vgpbpi163 TO `<sp-application-id>`;      -- strategy inventory fallback
