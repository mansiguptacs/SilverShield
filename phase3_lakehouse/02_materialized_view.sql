-- Phase 3: Materialized views = the real-time matching engine.

-- ---------------------------------------------------------------------------
-- mv_patient_matches: fires on every INSERT into fda_recalls. For each newly
-- ingested recall it joins the FULL patient_ehr table on NDC and writes every
-- affected customer into patient_alerts. This is the automatic trigger.
-- (A ClickHouse MV sees only the newly inserted block of its FROM table, so
--  each recall insert emits just that recall's matches.)
-- ---------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS safetynet.mv_patient_matches
TO safetynet.patient_alerts
AS
SELECT
    r.recall_number       AS recall_number,
    r.product_ndc         AS product_ndc,
    r.severity            AS severity,
    p.customer_id         AS customer_id,
    p.name                AS name,
    p.phone_number        AS phone_number,
    p.pharmacy_id         AS pharmacy_id,
    p.state               AS state,
    r.reason_for_recall   AS reason_for_recall,
    r.source_url          AS source_url,
    now()                 AS matched_at
FROM safetynet.fda_recalls AS r
INNER JOIN safetynet.patient_ehr AS p
    ON r.product_ndc = p.prescribed_ndc_code;

-- ---------------------------------------------------------------------------
-- mv_alert_geo_rollup: fires on inserts into patient_alerts (including those
-- produced by mv_patient_matches). Maintains per-recall, per-state aggregate
-- counts with NO PII - powers the live US map + scale metrics.
-- ---------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS safetynet.mv_alert_geo_rollup
TO safetynet.alert_geo_rollup
AS
SELECT
    recall_number,
    severity,
    state,
    countState()                AS affected_customers,
    uniqState(pharmacy_id)      AS affected_pharmacies
FROM safetynet.patient_alerts
GROUP BY recall_number, severity, state;
