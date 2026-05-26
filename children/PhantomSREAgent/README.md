# PhantomSREAgent Agent

## Role Summary
Monitors system health, manages incident lifecycles, and automates SRE tasks to ensure high availability and reliability of services.

## Primary Capabilities
- Monitor system metrics and logs for anomalies
- Detect and classify incidents automatically
- Trigger incident response workflows
- Provide real-time incident status updates
- Automate routine SRE operational tasks
- Integrate with alerting and paging systems

## API Endpoints
- **GET /api/sre/incidents** — Retrieve a list of active or recently closed SRE incidents. (ref: IncidentLogContract)
- **POST /api/sre/trigger** — Trigger a specific SRE action or incident response. (ref: TriggerActionContract)
