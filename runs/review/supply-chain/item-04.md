# Item 4

## The task

(unknown case)

## The answer given

```json
{
  "alternatives": [
    "partial-release (rejected: SP-5.1 directs consideration of alternate sourcing before partial release when shortfall >10%; partial release only if no alternate source exists per SP-9.1)",
    "accept-and-reschedule (rejected: leaves committed-build risk given >10% shortfall)",
    "expedite (rejected: shipment tardiness is within 14-day tolerance per SP-4.1; SP-4.2 expedite authority applies only when delay exceeds 14 days)"
  ],
  "est_delay_days": 7,
  "exception_type": "short-ship",
  "impacted_orders": [
    5018
  ],
  "policy_refs": [
    {
      "id": "SP-5.1"
    },
    {
      "id": "SP-5.2"
    },
    {
      "id": "SP-9.1"
    },
    {
      "id": "SP-4.1"
    }
  ],
  "recommended_action": "resource-alternate-supplier",
  "root_cause_code": "rc-supplier-capacity"
}
```

## Your judgement

Does this answer the task, on its own terms? Record `accept` or
`reject` against this item number in answers.yaml. You are not
being asked whether it matches a key -- you have not been shown one.
