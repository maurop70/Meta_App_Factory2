---
name: sentry_telemetry
description: Asynchronous Health Monitoring & Direct Communication Channel (DCC) for Sentry.
---

# Sentry Telemetry (The Observer)

This skill implements an **Asynchronous Observer Pattern** to monitor application health without blocking the main execution thread.

## Core Capabilities

1. **Direct Communication Channel (DCC)**: A thread-safe `Queue` or shared state for real-time status updates.
2. **Heartbeat Monitor**: Checks for "Silent Failures" (freezes) by ensuring the main thread updates a timestamp every 5 seconds.
3. **Sentry Handshake**: Packages state (Snapshot) to `.sentry_cache.json` upon failure for auto-recovery.

## Usage

```python
from sentry_telemetry.observer import SentryObserver

# 1. Start Observer (Daemon Thread)
observer = SentryObserver(app_name="Adv_Autonomous_Agent", heartbeat_interval=5)
observer.start()

# 2. Main Thread Loop (Heartbeat)
def main_loop():
    while True:
        # processing...
        observer.tick() # Signal "I am alive"
        time.sleep(0.1)

# 3. Report Status
observer.set_status("PROCESSING") # Green
observer.set_status("ERROR")      # Amber
```

## Failure Logic

If `time.time() - last_tick > 5s`:

1. Observer flags `CRITICAL_TIMEOUT`.
2. Observer writes `SNAPSHOT` to disk.
3. Observer triggers `Sentry Recovery` (if configured).
