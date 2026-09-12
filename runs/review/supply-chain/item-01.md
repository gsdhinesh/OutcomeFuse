# Item 1

## The task

Purchase order 5013 has been flagged for review. Classify the exception, identify its root cause, recommend a disposition, and cite the supplier policy clauses your recommendation rests on.


## The answer given

```json
{
  "alternatives": [
    "partial-release",
    "expedite",
    "resource-alternate-supplier"
  ],
  "est_delay_days": 14,
  "exception_type": "quality-hold",
  "impacted_orders": [
    5013
  ],
  "policy_refs": [
    {
      "id": "SP-7.1"
    }
  ],
  "recommended_action": "hold-for-quality",
  "root_cause_code": "rc-qc-defect"
}
```

## Your judgement

Does this answer the task, on its own terms? Record `accept` or
`reject` against this item number in answers.yaml. You are not
being asked whether it matches a key -- you have not been shown one.
