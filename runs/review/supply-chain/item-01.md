# Item 1

## The task

Purchase order 5004 has been flagged for review. Classify the exception, identify its root cause, recommend a disposition, and cite the supplier policy clauses your recommendation rests on.


## The answer given

```json
{
  "alternatives": [
    "escalate-to-buyer",
    "expedite",
    "partial-release"
  ],
  "est_delay_days": 7,
  "exception_type": "quality-hold",
  "impacted_orders": [
    5004
  ],
  "policy_refs": [
    {
      "id": "SP-7.1"
    },
    {
      "id": "SP-4.1"
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
