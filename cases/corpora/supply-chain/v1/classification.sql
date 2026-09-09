-- Deterministic classification for the supply-chain workload.
--
-- KEY-DERIVATION MATERIAL. Not agent-visible: the agent sees only the tools
-- the contract declares. This file is what makes exception_type,
-- root_cause_code and recommended_action *derived* rather than stored — no
-- column in the corpus holds any of them.
--
-- Precedence is fixed and total, because a purchase order can exhibit more
-- than one condition at once and a case with two defensible answers cannot
-- have one answer key. Safety outranks money; money outranks scheduling:
--
--   quality-hold > customs-hold > price-variance
--                > allocation-conflict > short-ship > late-shipment
--
-- Takes :po_id. Returns exactly one row of three values.

WITH po AS (
    SELECT
        p.po_id,
        p.part_id,
        p.ordered_qty,
        p.promised_date,
        pt.supplier_id,
        s.committed_units_per_week,
        pa.agreed_unit_cost_cents
    FROM purchase_orders p
    JOIN parts pt ON pt.part_id = p.part_id
    JOIN suppliers s ON s.supplier_id = pt.supplier_id
    JOIN price_agreements pa ON pa.part_id = p.part_id
    WHERE p.po_id = :po_id
),
facts AS (
    SELECT
        po.*,
        sh.dispatched_date,
        sh.arrived_date,
        sh.customs_hold_days,
        r.received_qty,
        r.qc_status,
        i.invoiced_unit_cost_cents,
        CAST(julianday(sh.arrived_date) - julianday(po.promised_date) AS INTEGER) AS days_late,
        po.ordered_qty - r.received_qty AS shortfall,
        -- A sibling order for the same part, received in full inside a
        -- fortnight, is what separates "the supplier could not make it" from
        -- "the supplier made it and allocated it elsewhere".
        (SELECT COUNT(*)
           FROM purchase_orders p2
           JOIN receipts r2 ON r2.po_id = p2.po_id
          WHERE p2.part_id = po.part_id
            AND p2.po_id <> po.po_id
            AND r2.received_qty >= p2.ordered_qty
            AND ABS(julianday(p2.promised_date) - julianday(po.promised_date)) <= 14
        ) AS satisfied_siblings
    FROM po
    JOIN shipments sh ON sh.po_id = po.po_id
    JOIN receipts  r  ON r.po_id  = po.po_id
    JOIN invoices  i  ON i.po_id  = po.po_id
),
classified AS (
    SELECT
        f.*,
        CASE
            WHEN f.qc_status = 'fail'                          THEN 'quality-hold'
            WHEN f.customs_hold_days > 0                       THEN 'customs-hold'
            WHEN f.invoiced_unit_cost_cents > f.agreed_unit_cost_cents
                                                               THEN 'price-variance'
            WHEN f.received_qty < f.ordered_qty
                 AND f.ordered_qty <= f.committed_units_per_week
                 AND f.satisfied_siblings > 0                  THEN 'allocation-conflict'
            WHEN f.received_qty < f.ordered_qty                THEN 'short-ship'
            WHEN f.days_late > 0                               THEN 'late-shipment'
            ELSE NULL
        END AS exception_type
    FROM facts f
)
SELECT
    exception_type,
    CASE exception_type
        WHEN 'quality-hold'        THEN 'rc-qc-defect'
        WHEN 'customs-hold'        THEN 'rc-customs-documentation'
        WHEN 'price-variance'      THEN 'rc-unapproved-price-uplift'
        WHEN 'allocation-conflict' THEN 'rc-partial-allocation'
        WHEN 'short-ship'          THEN
            CASE WHEN ordered_qty > committed_units_per_week
                 THEN 'rc-supplier-capacity' ELSE 'rc-partial-allocation' END
        WHEN 'late-shipment'       THEN
            CASE WHEN julianday(dispatched_date) > julianday(promised_date) - 3
                 THEN 'rc-supplier-late-dispatch' ELSE 'rc-carrier-delay' END
    END AS root_cause_code,
    CASE exception_type
        WHEN 'quality-hold'        THEN 'hold-for-quality'
        WHEN 'customs-hold'        THEN 'escalate-to-buyer'
        WHEN 'price-variance'      THEN 'escalate-to-buyer'
        WHEN 'allocation-conflict' THEN 'partial-release'
        WHEN 'short-ship'          THEN
            CASE WHEN (ordered_qty - received_qty) * 10 > ordered_qty
                 THEN 'resource-alternate-supplier' ELSE 'partial-release' END
        WHEN 'late-shipment'       THEN
            CASE WHEN days_late > 14
                 THEN 'expedite' ELSE 'accept-and-reschedule' END
    END AS recommended_action
FROM classified;
