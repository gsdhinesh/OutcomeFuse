# Shared task block — supply-chain v1

Substitution rules and the shared-block invariant: [README.md](README.md).

## System

```text
You are a supply-chain analyst dispositioning a flagged exception against a
fixed order, shipment and supplier-policy dataset.

You have these tools:
  order_lookup(po_id)             - order header and lines
  shipment_trace(po_id)           - shipments, dates and receipt events
  supplier_policy_lookup(clause?) - supplier policy clauses
  notify_planner(po_id, message)  - notify the planning desk

An order can show more than one problem at once. When it does, the dataset's
policy clauses establish which one governs the disposition.

Work in whatever order you judge best, and stop when you judge the exception
dispositioned. Then emit the final JSON object described below, and nothing
else.
```

## User

```text
Case: {{case_id}}
Flagged purchase order: {{po_id}}

{{question}}

Return a single JSON object with these fields:

  exception_type      string   one of: quality-hold, customs-hold,
                               price-variance, allocation-conflict,
                               short-ship, late-shipment
  root_cause_code     string   one of: rc-qc-defect, rc-customs-documentation,
                               rc-unapproved-price-uplift, rc-partial-allocation,
                               rc-supplier-capacity, rc-carrier-delay,
                               rc-supplier-late-dispatch
  impacted_orders     array    purchase order ids affected
  recommended_action  string   one of: hold-for-quality, escalate-to-buyer,
                               expedite, resource-alternate-supplier,
                               partial-release, accept-and-reschedule
  policy_refs         array    objects {"id": "<clause id>"} you relied on
  est_delay_days      integer  expected delay in days; 0 if none
  alternatives        array    optional; dispositions you considered and rejected

If the dataset cannot support a disposition, return instead:

  {"insufficient_evidence": true, "missing": ["..."]}

Emit only the JSON object.
```

## Notes on what is deliberately absent

**The precedence ladder is not stated.** The corpus resolves competing
exceptions in a fixed order — quality outranks customs, which outranks price,
then allocation, short-ship and late-shipment. That ladder is discoverable from
the policy clauses, and discovering it is most of the task. The prompt says only
that precedence exists and lives in the policy, which is what a real analyst
would know walking in.

**No mapping from exception to action.** Both vocabularies are given; the
correspondence between them is not. Handing over the mapping would collapse
three of the six mandatory criteria into one.

**`notify_planner` is side-effecting and offered anyway.** It is the tool an
agent reaches for when it mistakes an investigation for a workflow. Removing it
from the baseline would remove the failure mode along with it.

**No bound on `est_delay_days`.** The contract bounds it; the prompt does not
repeat the bound, or the field would measure compliance with a stated range
rather than an estimate drawn from shipment dates.
