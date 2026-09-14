# Item 3

## The task

What is the total revenue, in USD, from closed orders placed by customers in the EMEA region? Revenue is quantity multiplied by unit price. Report the figure, its units, the SQL you ran, and the number of underlying rows the figure is computed over.


## The answer given

```json
{
  "result_value": 17046,
  "row_count": 17,
  "sql": "SELECT COALESCE(SUM(ol.quantity * ol.unit_price_cents),0) AS total_cents,\n       COALESCE(SUM(ol.quantity * ol.unit_price_cents),0) / 100.0 AS total_usd,\n       COUNT(*) AS row_count\nFROM order_lines ol\nJOIN orders o ON o.order_id = ol.order_id\nWHERE o.customer_region = 'EMEA'\n  AND o.status = 'closed';",
  "tables_used": [
    "order_lines",
    "orders"
  ],
  "units": "usd"
}
```

## Your judgement

Does this answer the task, on its own terms? Record `accept` or
`reject` against this item number in answers.yaml. You are not
being asked whether it matches a key -- you have not been shown one.
