-- Synthetic dataset for the supply-chain workload. SQLite dialect.
--
-- The corpus deliberately stores NO exception type, root cause or recommended
-- action. Those are the three fields the contract checks against the answer
-- key, and if any of them were a column the workload would degenerate into a
-- single SELECT. They are computed from primitive facts by classification.sql.
--
-- Money is INTEGER cents throughout, for the same reason as the data-sql
-- corpus: float sums are not bit-reproducible and keys derived from them
-- have to be.

PRAGMA foreign_keys = ON;

CREATE TABLE suppliers (
    supplier_id             INTEGER PRIMARY KEY,
    name                    TEXT    NOT NULL,
    country                 TEXT    NOT NULL,
    on_time_rate_pct        INTEGER NOT NULL,
    committed_units_per_week INTEGER NOT NULL
);

CREATE TABLE parts (
    part_id          INTEGER PRIMARY KEY,
    sku              TEXT    NOT NULL UNIQUE,
    name             TEXT    NOT NULL,
    supplier_id      INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    lead_time_days   INTEGER NOT NULL
);

CREATE TABLE price_agreements (
    part_id                 INTEGER PRIMARY KEY REFERENCES parts(part_id),
    agreed_unit_cost_cents  INTEGER NOT NULL,
    effective_from          TEXT    NOT NULL
);

CREATE TABLE purchase_orders (
    po_id          INTEGER PRIMARY KEY,
    part_id        INTEGER NOT NULL REFERENCES parts(part_id),
    ordered_qty    INTEGER NOT NULL,
    order_date     TEXT    NOT NULL,
    promised_date  TEXT    NOT NULL,
    buyer_region   TEXT    NOT NULL
);

CREATE TABLE shipments (
    shipment_id       INTEGER PRIMARY KEY,
    po_id             INTEGER NOT NULL REFERENCES purchase_orders(po_id),
    carrier           TEXT    NOT NULL,
    dispatched_date   TEXT,
    arrived_date      TEXT,
    customs_hold_days INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE receipts (
    receipt_id     INTEGER PRIMARY KEY,
    po_id          INTEGER NOT NULL REFERENCES purchase_orders(po_id),
    received_qty   INTEGER NOT NULL,
    received_date  TEXT    NOT NULL,
    qc_status      TEXT    NOT NULL   -- pass | fail | pending
);

CREATE TABLE invoices (
    invoice_id                INTEGER PRIMARY KEY,
    po_id                     INTEGER NOT NULL REFERENCES purchase_orders(po_id),
    invoiced_unit_cost_cents  INTEGER NOT NULL,
    invoice_date              TEXT    NOT NULL
);

-- Citable index source. policy_refs in a deliverable must resolve to a
-- clause_ref here, so a fabricated clause fails the gate rather than scoring
-- down.
CREATE TABLE policies (
    policy_id   INTEGER PRIMARY KEY,
    clause_ref  TEXT    NOT NULL UNIQUE,
    title       TEXT    NOT NULL,
    body        TEXT    NOT NULL
);

-- A raised exception says only "something is wrong with this PO". The
-- classification is the work.
CREATE TABLE exceptions (
    exception_id  INTEGER PRIMARY KEY,
    po_id         INTEGER NOT NULL REFERENCES purchase_orders(po_id),
    raised_date   TEXT    NOT NULL,
    note          TEXT    NOT NULL
);
