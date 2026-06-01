# WarRoomMonitor Agent

## Role Summary
Monitors system health, CPU/RAM usage, and the operational status of all registered child agents by asynchronously pinging their health endpoints, providing a comprehensive system status.

## Primary Capabilities
- Monitor CPU utilization in real-time.
- Track RAM usage and availability.
- Read and parse the agent registry for active child agents.
- Asynchronously ping health endpoints of registered child agents.
- Aggregate and report a comprehensive system status.
- Expose a dedicated health check endpoint for external monitoring.

## API Endpoints
- **GET /api/health** — Provides a comprehensive system health report including CPU, RAM, and child agent statuses. (ref: SystemHealthContract)
- **POST /api/monitor/start** — Initiates continuous monitoring of system and child agent health, optionally sending reports to a specified destination. (ref: MonitorStartContract)
