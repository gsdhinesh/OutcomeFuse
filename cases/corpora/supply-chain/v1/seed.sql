-- Seed data for the supply-chain workload corpus, v1.
-- Hand-authored and deterministic. Each exception PO exhibits exactly one
-- classifiable condition under classification.sql, with enough surrounding
-- noise that the classification is not a single lookup.

INSERT INTO suppliers (supplier_id, name, country, on_time_rate_pct, committed_units_per_week) VALUES
    (1, 'Northwind Components', 'DE', 96,  800),
    (2, 'Kanto Precision',      'JP', 91,  300),
    (3, 'Aravalli Metals',      'IN', 78, 1200),
    (4, 'Cascade Polymer',      'US', 88,  600),
    (5, 'Baltic Fasteners',     'PL', 69, 2000);

INSERT INTO parts (part_id, sku, name, supplier_id, lead_time_days) VALUES
    (201, 'NC-BRG-08', 'Bearing 8mm',      1, 21),
    (202, 'KP-SNS-01', 'Sensor Module',    2, 35),
    (203, 'AM-PLT-04', 'Steel Plate 4mm',  3, 28),
    (204, 'CP-SEL-11', 'Polymer Seal',     4, 14),
    (205, 'BF-FST-M6', 'Fastener M6',      5, 10),
    (206, 'NC-BRG-12', 'Bearing 12mm',     1, 21),
    (207, 'KP-SNS-02', 'Sensor Module HD', 2, 42),
    (208, 'AM-PLT-06', 'Steel Plate 6mm',  3, 28);

INSERT INTO price_agreements (part_id, agreed_unit_cost_cents, effective_from) VALUES
    (201, 1250, '2026-01-01'),
    (202, 4400, '2026-01-01'),
    (203,  780, '2026-01-01'),
    (204,  235, '2026-01-01'),
    (205,   45, '2026-01-01'),
    (206, 1875, '2026-01-01'),
    (207, 6125, '2026-01-01'),
    (208, 1040, '2026-01-01');

INSERT INTO purchase_orders (po_id, part_id, ordered_qty, order_date, promised_date, buyer_region) VALUES
    (5001, 201,  400, '2026-01-06', '2026-02-03', 'EMEA'),
    (5002, 202,  120, '2026-01-08', '2026-02-19', 'APAC'),
    (5003, 203, 2000, '2026-01-12', '2026-02-16', 'EMEA'),
    (5004, 204,  900, '2026-01-15', '2026-02-05', 'AMER'),
    (5005, 205, 6000, '2026-01-19', '2026-02-02', 'EMEA'),
    (5006, 206,  350, '2026-01-22', '2026-02-19', 'AMER'),
    (5007, 207,   80, '2026-01-26', '2026-03-16', 'APAC'),
    (5008, 208, 1500, '2026-02-02', '2026-03-09', 'EMEA'),
    (5009, 201,  500, '2026-02-05', '2026-03-05', 'AMER'),
    (5010, 203, 3000, '2026-02-09', '2026-03-16', 'APAC'),
    (5011, 205, 9000, '2026-02-12', '2026-02-26', 'EMEA'),
    (5012, 202,  150, '2026-02-16', '2026-03-30', 'AMER'),
    (5013, 204, 1200, '2026-02-19', '2026-03-12', 'EMEA'),
    (5014, 206,  420, '2026-02-23', '2026-03-23', 'APAC'),
    (5015, 208, 1800, '2026-03-02', '2026-04-06', 'AMER'),
    (5016, 207,   60, '2026-03-05', '2026-04-23', 'EMEA'),
    (5017, 201,  300, '2026-03-09', '2026-03-12', 'APAC'),
    (5018, 205, 4000, '2026-03-12', '2026-03-26', 'AMER'),
    (5019, 203, 1000, '2026-03-16', '2026-04-20', 'EMEA'),
    (5020, 204,  600, '2026-03-19', '2026-04-09', 'APAC');

-- dispatched_date within 3 days of promised_date means the supplier dispatched
-- too late for any carrier to make the date; earlier dispatch that still
-- arrives late is a carrier problem.
INSERT INTO shipments (shipment_id, po_id, carrier, dispatched_date, arrived_date, customs_hold_days) VALUES
    (7001, 5001, 'DHL',   '2026-01-27', '2026-02-12', 0),
    (7002, 5002, 'FedEx', '2026-02-10', '2026-03-06', 0),
    (7003, 5003, 'DHL',   '2026-02-01', '2026-02-14', 0),
    (7004, 5004, 'UPS',   '2026-02-15', '2026-02-24', 0),
    (7005, 5005, 'DHL',   '2026-02-01', '2026-02-20', 0),
    (7006, 5006, 'FedEx', '2026-02-11', '2026-02-18', 0),
    (7007, 5007, 'UPS',   '2026-03-01', '2026-03-29', 9),
    (7008, 5008, 'DHL',   '2026-03-08', '2026-03-20', 0),
    (7009, 5009, 'FedEx', '2026-02-24', '2026-03-04', 0),
    (7010, 5010, 'UPS',   '2026-03-04', '2026-03-15', 0),
    (7011, 5011, 'DHL',   '2026-02-17', '2026-03-08', 0),
    (7012, 5012, 'FedEx', '2026-03-28', '2026-04-11', 0),
    (7013, 5013, 'UPS',   '2026-03-01', '2026-03-10', 0),
    (7014, 5014, 'DHL',   '2026-03-12', '2026-03-21', 0),
    (7015, 5015, 'FedEx', '2026-03-25', '2026-04-19', 6),
    (7016, 5016, 'UPS',   '2026-04-10', '2026-04-22', 0),
    (7017, 5017, 'DHL',   '2026-03-01', '2026-03-11', 0),
    (7018, 5018, 'FedEx', '2026-03-24', '2026-04-08', 0),
    (7019, 5019, 'UPS',   '2026-04-05', '2026-04-18', 0),
    (7020, 5020, 'DHL',   '2026-03-30', '2026-04-27', 0);

INSERT INTO receipts (receipt_id, po_id, received_qty, received_date, qc_status) VALUES
    (8001, 5001,  400, '2026-02-12', 'pass'),
    (8002, 5002,  120, '2026-03-06', 'pass'),
    (8003, 5003, 1400, '2026-02-14', 'pass'),
    (8004, 5004,  900, '2026-02-24', 'fail'),
    (8005, 5005, 6000, '2026-02-20', 'pass'),
    (8006, 5006,  350, '2026-02-18', 'pass'),
    (8007, 5007,   80, '2026-03-29', 'pass'),
    (8008, 5008, 1500, '2026-03-20', 'pass'),
    (8009, 5009,  500, '2026-03-04', 'pass'),
    (8010, 5010, 1900, '2026-03-15', 'pass'),
    (8011, 5011, 9000, '2026-03-08', 'pass'),
    (8012, 5012,  150, '2026-04-11', 'pass'),
    (8013, 5013, 1200, '2026-03-10', 'fail'),
    (8014, 5014,  420, '2026-03-21', 'pass'),
    (8015, 5015, 1800, '2026-04-19', 'pass'),
    (8016, 5016,   60, '2026-04-22', 'pass'),
    (8017, 5017,  250, '2026-03-11', 'pass'),
    (8018, 5018, 2600, '2026-04-08', 'pass'),
    (8019, 5019,  950, '2026-04-18', 'pass'),
    (8020, 5020,  600, '2026-04-27', 'pass');

INSERT INTO invoices (invoice_id, po_id, invoiced_unit_cost_cents, invoice_date) VALUES
    (9001, 5001, 1250, '2026-02-04'),
    (9002, 5002, 4400, '2026-03-08'),
    (9003, 5003,  780, '2026-02-16'),
    (9004, 5004,  235, '2026-02-26'),
    (9005, 5005,   45, '2026-02-03'),
    (9006, 5006, 2110, '2026-02-20'),
    (9007, 5007, 6125, '2026-03-31'),
    (9008, 5008, 1040, '2026-03-09'),
    (9009, 5009, 1250, '2026-03-06'),
    (9010, 5010,  780, '2026-03-17'),
    (9011, 5011,   45, '2026-02-27'),
    (9012, 5012, 4400, '2026-04-13'),
    (9013, 5013,  235, '2026-03-12'),
    (9014, 5014, 1875, '2026-03-23'),
    (9015, 5015, 1040, '2026-04-21'),
    (9016, 5016, 7350, '2026-04-24'),
    (9017, 5017, 1250, '2026-04-06'),
    (9018, 5018,   45, '2026-04-10'),
    (9019, 5019,  780, '2026-04-20'),
    (9020, 5020,  235, '2026-04-09');

INSERT INTO policies (policy_id, clause_ref, title, body) VALUES
    (1, 'SP-4.1',  'Late delivery tolerance',
        'A delivery arriving more than fourteen days after its promised date is escalated; within fourteen days it is rescheduled.'),
    (2, 'SP-4.2',  'Expedite authority',
        'Expedited freight may be authorised where the delay exceeds fourteen days and the part is on a committed build.'),
    (3, 'SP-5.1',  'Short shipment handling',
        'Where the shortfall exceeds ten percent of the ordered quantity, alternate sourcing is considered before partial release.'),
    (4, 'SP-5.2',  'Supplier capacity limits',
        'A supplier may not be held to an order exceeding its committed weekly capacity for the part family.'),
    (5, 'SP-6.1',  'Price variance escalation',
        'Any invoiced unit cost above the agreed price is escalated to the buyer before payment.'),
    (6, 'SP-7.1',  'Quality hold',
        'Material failing incoming inspection is held and may not be released to production.'),
    (7, 'SP-8.1',  'Customs documentation',
        'Shipments held at the border for documentation are escalated to the buyer, who owns the broker relationship.'),
    (8, 'SP-9.1',  'Partial release',
        'A partial release is permitted where the received quantity covers the committed build and no alternate source exists.');

INSERT INTO exceptions (exception_id, po_id, raised_date, note) VALUES
    (6001, 5002, '2026-03-06', 'Flagged by receiving: PO 5002 needs review.'),
    (6002, 5003, '2026-02-14', 'Flagged by receiving: PO 5003 needs review.'),
    (6003, 5004, '2026-02-24', 'Flagged by receiving: PO 5004 needs review.'),
    (6004, 5006, '2026-02-20', 'Flagged by finance: PO 5006 needs review.'),
    (6005, 5007, '2026-03-29', 'Flagged by logistics: PO 5007 needs review.'),
    (6006, 5010, '2026-03-15', 'Flagged by receiving: PO 5010 needs review.'),
    (6007, 5012, '2026-04-11', 'Flagged by planning: PO 5012 needs review.'),
    (6008, 5013, '2026-03-10', 'Flagged by receiving: PO 5013 needs review.'),
    (6009, 5015, '2026-04-19', 'Flagged by logistics: PO 5015 needs review.'),
    (6010, 5016, '2026-04-24', 'Flagged by finance: PO 5016 needs review.'),
    (6011, 5018, '2026-04-08', 'Flagged by receiving: PO 5018 needs review.'),
    (6012, 5019, '2026-04-18', 'Flagged by planning: PO 5019 needs review.'),
    (6013, 5001, '2026-02-12', 'Flagged by planning: PO 5001 needs review.'),
    (6014, 5005, '2026-02-20', 'Flagged by planning: PO 5005 needs review.'),
    (6015, 5008, '2026-03-20', 'Flagged by planning: PO 5008 needs review.'),
    (6016, 5011, '2026-03-08', 'Flagged by planning: PO 5011 needs review.'),
    (6017, 5017, '2026-03-11', 'Flagged by planning: PO 5017 needs review.'),
    (6018, 5020, '2026-04-27', 'Flagged by planning: PO 5020 needs review.');
