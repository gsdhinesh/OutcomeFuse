# Item 2

## The task

How many shipments are currently in transit? Report the figure, its units, the SQL you ran, and the number of underlying rows the figure is computed over.


## The answer given

```json
{
  "assumptions": [
    "Defined 'currently in transit' as shipments with status = 'in_transit'; no date filters applied"
  ],
  "result_value": 3,
  "row_count": 3,
  "sql": "SELECT count(*) AS in_transit_count FROM shipments WHERE status = 'in_transit';",
  "tables_used": [
    "shipments"
  ],
  "units": "count"
}
```

## Your judgement

Does this answer the task, on its own terms? Record `accept` or
`reject` against this item number in answers.yaml. You are not
being asked whether it matches a key -- you have not been shown one.
