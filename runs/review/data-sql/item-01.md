# Item 1

## The task

What is the unit cost, in USD, of the product with SKU "AM-PLT-06"? Report the figure, its units, the SQL you ran, and the number of underlying rows the figure is computed over.


## The answer given

```json
{
  "assumptions": [],
  "result_value": 10.4,
  "row_count": 1,
  "sql": "SELECT sku, unit_cost_cents FROM products WHERE sku = 'AM-PLT-06'",
  "tables_used": [
    "products"
  ],
  "units": "usd"
}
```

## Your judgement

Does this answer the task, on its own terms? Record `accept` or
`reject` against this item number in answers.yaml. You are not
being asked whether it matches a key -- you have not been shown one.
