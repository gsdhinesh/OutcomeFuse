# Item 4

## The task

What is the total booked revenue, in USD, for EMEA orders placed in the first quarter of 2026, excluding cancelled orders? Report the figure, its units, the SQL you ran, and the number of underlying rows the figure is computed over.


## The answer given

```json
{
  "assumptions": [
    "Quarter defined as 2026-01-01 through 2026-03-31 (implemented as >= 2026-01-01 and < 2026-04-01).",
    "Booked revenue interpreted as the sum of quantity * unit_price across order lines for qualifying orders.",
    "Monetary values stored in integer cents are reported in whole USD by dividing by 100."
  ],
  "result_value": 8202,
  "row_count": 9,
  "sql": "SELECT \n  COALESCE(SUM(ol.quantity * ol.unit_price_cents),0) AS total_cents,\n  COUNT(*) AS row_count\nFROM order_lines ol\nJOIN orders o ON o.order_id = ol.order_id\nWHERE o.customer_region = 'EMEA'\n  AND o.status <> 'cancelled'\n  AND o.order_date >= '2026-01-01'\n  AND o.order_date < '2026-04-01';",
  "tables_used": [
    "orders",
    "order_lines"
  ],
  "units": "usd"
}
```

## Your judgement

Does this answer the task, on its own terms? Record `accept` or
`reject` against this item number in answers.yaml. You are not
being asked whether it matches a key -- you have not been shown one.
