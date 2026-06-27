# Pipeline 4 — Facebook Group CRM Router

> Awaiting Build Spec. Will be populated by a focused Claude Code session.

See `OPS-61_PLAN.md` "Pipeline 4 — Facebook Group Inbound CRM Router" for the full spec.

**Quick summary:**
- Chrome extension (read-only DOM scrape of FB Group pending members)
- POSTs structured JSON to n8n webhook → writes to `Inbound` Sheet tab
- Q3 (DM permission Y/N) drives operator action — n8n sets `operator_action` column
- Discord pings differentiate hot leads (Q3=Yes) from standard warm inbound

**Depends on:**
- FB Group Q3 configured to: *"Would you like me to reach out to discuss how we may be able to help you with that?"* (Jon, v0 setup)
