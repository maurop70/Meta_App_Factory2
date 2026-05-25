# WarRoomMonitor Agent

## Role Summary
Monitors the health and operational status of the host system and all registered child agents. Provides real-time CPU/RAM metrics and asynchronous connectivity checks to ensure system stability and agent availability.

## Primary Capabilities
- Monitor host system CPU utilization
- Track host system RAM usage
- Asynchronously ping active child agents via HTTP
- Read agent registry for active agent information
- Provide a comprehensive system health status report
- Expose a detailed monitoring endpoint for specific agent status requests

## API Endpoints
- **GET /api/health** — Retrieves current system health including CPU, RAM, and child agent connectivity status. (ref: SystemHealthContract)
- **POST /api/v1/monitor/status** — Requests a detailed status report for specified agents or the entire system with configurable depth. (ref: DetailedMonitorRequestContract)
