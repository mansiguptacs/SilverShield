-- Phase 3: Base tables for the FDA SafetyNet lakehouse.
-- Run against the `safetynet` database.

CREATE DATABASE IF NOT EXISTS safetynet;

-- ---------------------------------------------------------------------------
-- fda_recalls: fed by the ingestion pipeline (PyAirbyte -> loader, or Airbyte
-- Cloud -> ClickHouse destination). One row per recalled product NDC.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safetynet.fda_recalls
(
    recall_number      String,
    product_ndc        String,
    reason_for_recall  String,
    classification     String,           -- Class I / II / III
    severity           String,           -- mapped: Lethal / Moderate / Minor
    status             String,
    recalling_firm     String,
    distribution_pattern String,
    report_date        String,           -- YYYYMMDD (openFDA format)
    source_url         String,
    ingested_at        DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (product_ndc, recall_number);

-- ---------------------------------------------------------------------------
-- pharmacies: static reference data (~5k rows), carries geography.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safetynet.pharmacies
(
    pharmacy_id  String,
    name         String,
    chain        String,
    state        String,
    state_name   String,
    zip          String,
    lat          Float64,
    lon          Float64
)
ENGINE = MergeTree
ORDER BY pharmacy_id;

-- ---------------------------------------------------------------------------
-- patient_ehr: ~1M synthetic customer-prescription rows. Keyed by NDC so the
-- recall join is fast.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safetynet.patient_ehr
(
    customer_id          String,
    name                 String,
    phone_number         String,
    pharmacy_id          String,
    state                String,
    prescribed_ndc_code  String
)
ENGINE = MergeTree
ORDER BY (prescribed_ndc_code, pharmacy_id);

-- ---------------------------------------------------------------------------
-- patient_alerts: target table fed by the materialized view when a recall
-- intersects a customer's prescription. This is the high-velocity trigger.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safetynet.patient_alerts
(
    recall_number  String,
    product_ndc    String,
    severity       String,
    customer_id    String,
    name           String,
    phone_number   String,
    pharmacy_id    String,
    state          String,
    reason_for_recall String,
    source_url     String,
    matched_at     DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (severity, state, recall_number);

-- ---------------------------------------------------------------------------
-- alert_geo_rollup: per-recall, per-state aggregate counts (no PII). Powers
-- the live US map + scale metrics.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safetynet.alert_geo_rollup
(
    recall_number       String,
    severity            String,
    state               String,
    affected_customers  AggregateFunction(count, UInt64),
    affected_pharmacies AggregateFunction(uniq, String)
)
ENGINE = AggregatingMergeTree
ORDER BY (recall_number, severity, state);
