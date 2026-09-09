-- Synthetic dataset for the data-sql workload. SQLite dialect.
--
-- Money is INTEGER cents throughout. Floating point sums are not
-- bit-reproducible across platforms or across summation orders, and the answer
-- keys derived from this data have to be, so no monetary column is REAL.
-- Cases that ask for USD are answered by converting exact cents at the edge.

PRAGMA foreign_keys = ON;

CREATE TABLE suppliers (
    supplier_id  INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    country      TEXT    NOT NULL,
    tier         INTEGER NOT NULL
);

CREATE TABLE products (
    product_id       INTEGER PRIMARY KEY,
    sku              TEXT    NOT NULL UNIQUE,
    name             TEXT    NOT NULL,
    category         TEXT    NOT NULL,
    unit_cost_cents  INTEGER NOT NULL,
    supplier_id      INTEGER NOT NULL REFERENCES suppliers(supplier_id)
);

CREATE TABLE orders (
    order_id         INTEGER PRIMARY KEY,
    order_date       TEXT    NOT NULL,          -- ISO-8601 date
    customer_region  TEXT    NOT NULL,          -- EMEA | AMER | APAC
    status           TEXT    NOT NULL           -- released | closed | cancelled | on_hold
);

CREATE TABLE order_lines (
    line_id           INTEGER PRIMARY KEY,
    order_id          INTEGER NOT NULL REFERENCES orders(order_id),
    product_id        INTEGER NOT NULL REFERENCES products(product_id),
    quantity          INTEGER NOT NULL,
    unit_price_cents  INTEGER NOT NULL
);

CREATE TABLE shipments (
    shipment_id     INTEGER PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(order_id),
    shipped_date    TEXT,                       -- NULL while unshipped
    delivered_date  TEXT,                       -- NULL while in transit
    carrier         TEXT    NOT NULL,
    status          TEXT    NOT NULL            -- in_transit | delivered | lost
);

CREATE TABLE returns (
    return_id    INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(order_id),
    product_id   INTEGER NOT NULL REFERENCES products(product_id),
    quantity     INTEGER NOT NULL,
    reason_code  TEXT    NOT NULL,              -- damaged | wrong_item | quality | late
    return_date  TEXT    NOT NULL
);
