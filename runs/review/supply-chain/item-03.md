# Item 3

## The task

(unknown case)

## The answer given

```json
{
  "alternatives": [
    {
      "action": "accept-and-reschedule",
      "reason": "Rescheduling is the normal response for deliveries within 14 days (SP-4.1), but SP-8.1 requires escalation to the buyer where shipments are held at the border for documentation."
    },
    {
      "action": "expedite",
      "reason": "Expedited freight is authorised only where delay exceeds 14 days and the part is on a committed build (SP-4.2); current delay is 13 days, so expedite is not authorised per policy."
    }
  ],
  "est_delay_days": 13,
  "exception_type": "customs-hold",
  "impacted_orders": [
    5015
  ],
  "policy_refs": [
    {
      "id": "SP-8.1"
    },
    {
      "id": "SP-4.1"
    }
  ],
  "recommended_action": "escalate-to-buyer",
  "root_cause_code": "rc-customs-documentation"
}
```

## Your judgement

Does this answer the task, on its own terms? Record `accept` or
`reject` against this item number in answers.yaml. You are not
being asked whether it matches a key -- you have not been shown one.
