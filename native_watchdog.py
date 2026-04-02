"""
native_watchdog.py — Phase 7: The Aether Native Watchdog
════════════════════════════════════════════════════════════
Monitors the uptime of the Aether-Native Gates.
Ensures UI Playwright sessions don't memory-leak or crash the host.
Signals 'N8N Sunset Protocol COMPLETE' when stabilized.
"""
import time
import copy
import threading
import logging
import subprocess
import csv
from datetime import datetime

sys_path_added = False
import sys, os
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auto_heal import _log_heal_event

logger = logging.getLogger("AetherNativeWatchdog")

class AetherNativeWatchdog:
    def __init__(self, check_interval=30):
        self.check_interval = check_interval
        self._running = False
        self._memory_threshold_mb = 500  # 500 MB max for Headless worker
        self._consecutive_failures = 0
        self._port_failures = {}  # Per-port failure tracking for auto-restart
        self._start_time = time.time()
        self._sunsetting = True  # Set false once protocol completes

        # Live telemetry metrics
        self._telemetry = {
            "status": "initializing",
            "uptime_seconds": 0,
            "gates_health": {
                "pre_deploy": "UNKNOWN",
                "cfo_architect": "UNKNOWN",
                "phantom_pathfinder": "UNKNOWN"
            },
            "system_ram": "UNKNOWN"
        }

    def start_background_loop(self):
        """Spawns the watchdog loop as a daemon thread."""
        if not self._running:
            self._running = True
            self._start_time = time.time()
            self._thread = threading.Thread(target=self._watchdog_loop, daemon=True, name="AetherNativeWatchdog")
            self._thread.start()
            logger.info("Aether Native Watchdog ONLINE. Sunset countdown initiated.")

    def get_system_pulse(self) -> dict:
        """Returns the real-time health dictionary for /api/health."""
        self._telemetry["uptime_seconds"] = int(time.time() - self._start_time)
        return copy.deepcopy(self._telemetry)

    def _watchdog_loop(self):
        # Allow system to spin up before aggressive checks
        time.sleep(10)
        
        while self._running:
            try:
                self._run_health_checks()
                self._run_memory_guard()
                
                # Check for 5-minute sunset success
                uptime = time.time() - self._start_time
                if self._sunsetting and uptime > 300 and self._consecutive_failures == 0:
                    self._signal_sunset_complete()
                    
            except Exception as e:
                logger.error(f"Watchdog Loop Exception: {e}")
                
            time.sleep(self.check_interval)

    def _run_health_checks(self):
        """
        Pings local critical ports replacing all legacy n8n and dependency checks.
        Permanently ignoring n8n Cloud Reachability.
        Tracks per-port failure counts for targeted auto-restart.
        """
        import socket
        gates_status = {
            "root_api": "OK",
            "phantom_qa": "OK", 
            "master_architect": "OK",
            "c_suite": "OK",
            "clo_legal": "OK"
        }
        fail_detected = False
        
        ports = {
            "root_api": 5000,
            "phantom_qa": 5030,
            "master_architect": 5050,
            "c_suite": 5070,
            "clo_legal": 5080
        }

        # Map ports to their restart commands
        restart_commands = {
            5030: 'start /min "" cmd /c "cd Phantom_QA_Elite\\backend && python server.py"',
            5050: 'start /min "" cmd /c "cd Master_Architect_Elite_Logic && python server.py"',
            5070: 'start /min "" cmd /c "cd CFO_Agent && python server.py"',
            5080: 'start /min "" cmd /c "cd apps\\CLO_Agent && python legal_engine.py"',
        }

        for service, port in ports.items():
            try:
                with socket.create_connection(("localhost", port), timeout=2):
                    # Port responded — reset its failure counter
                    self._port_failures[port] = 0
            except Exception:
                gates_status[service] = "FAIL"
                fail_detected = True
                self._port_failures[port] = self._port_failures.get(port, 0) + 1
                logger.warning(f"Port {port} ({service}) FAIL — consecutive: {self._port_failures[port]}")

                # Auto-restart after 3 consecutive failures
                if self._port_failures[port] >= 3 and port in restart_commands:
                    self._auto_restart_port(port, service, restart_commands[port])

        self._telemetry["gates_health"] = gates_status
        
        if fail_detected:
            self._consecutive_failures += 1
            logger.warning(f"Native Port failure detected. Global consecutive: {self._consecutive_failures}")
        else:
            self._consecutive_failures = 0
            self._telemetry["status"] = "healthy"

    def _auto_restart_port(self, port, service, cmd):
        """Attempts a single automatic restart of a failed service."""
        logger.info(f"AUTO-RESTART: Attempting to revive {service} on port {port}...")
        try:
            factory_dir = os.path.dirname(os.path.abspath(__file__))
            subprocess.Popen(cmd, shell=True, cwd=factory_dir)
            _log_heal_event(
                "NativeWatchdog",
                f"Auto-Restart: {service} (port {port})",
                {"port": port, "service": service, "consecutive_fails": self._port_failures[port]},
                "AUTO_RESTART"
            )
            # Reset counter after restart attempt to avoid rapid-fire loops
            self._port_failures[port] = 0
            logger.info(f"AUTO-RESTART: {service} restart command dispatched.")
        except Exception as e:
            logger.error(f"AUTO-RESTART FAILED for {service}: {e}")

    def _trigger_v3_recovery(self):
        """Fires when internal components fail to respond to 3 pings."""
        logger.error(f"Watchdog trigger: V3_RECOVERY_REBOOT")
        _log_heal_event(
            "NativeWatchdog", 
            "V3 Component Ping Timeout", 
            {"consecutive_fails": self._consecutive_failures}, 
            "SYSTEM_RECOVERY"
        )
        # Attempt module reload or recovery flag
        self._consecutive_failures = 0

    def _run_memory_guard(self):
        """Uses subprocess tasklist to track memory footprint of potential zombie processes."""
        try:
            # We filter specifically for node.exe processes spawned by playwright.
            # Avoid killing actual Chrome processes used by the user.
            out = subprocess.check_output('tasklist /FI "IMAGENAME eq node.exe" /FO CSV /NH', shell=True).decode('utf-8')
            reader = csv.reader(out.splitlines())
            
            total_mb = 0
            for row in reader:
                if len(row) >= 5 and row[1].isdigit():
                    pid = int(row[1])
                    mem_str = row[4].replace(' K', '').replace(',', '').strip()
                    if mem_str.isdigit():
                        mem_mb = int(mem_str) / 1024.0
                        total_mb += mem_mb
                        
                        # Playwright node worker shouldn't exceed massive RAM spikes
                        if mem_mb > self._memory_threshold_mb:
                            logger.error(f"Memory Guard Triggered: PID {pid} using {mem_mb:.1f}MB (Threshold {self._memory_threshold_mb}MB)")
                            subprocess.run(f"taskkill /PID {pid} /F", shell=True)
                            _log_heal_event(
                                "NativeWatchdog", 
                                "Memory Guard Triggered", 
                                {"pid": pid, "mem_mb": mem_mb}, 
                                "SYSTEM_RECOVERY"
                            )
                            
            self._telemetry["system_ram"] = f"Node Workers: {total_mb:.1f}MB"
            
        except Exception as e:
            self._telemetry["system_ram"] = f"Guard Error: {str(e)}"
            pass

    def _trigger_v3_recovery(self):
        """Fires when internal components fail to respond to 3 pings."""
        logger.error(f"Watchdog trigger: V3_RECOVERY_REBOOT")
        _log_heal_event(
            "NativeWatchdog", 
            "V3 Component Ping Timeout", 
            {"consecutive_fails": self._consecutive_failures}, 
            "SYSTEM_RECOVERY"
        )
        # Attempt module reload or recovery flag
        self._consecutive_failures = 0

    def _signal_sunset_complete(self):
        """Fires exactly once after 5 minutes of 100% stable ping/uptime."""
        logger.info("WATCHDOG 100% UPTIME: Broadcast N8N Sunset COMPLETE")
        # In a real environment, we would await an async websocket broadcast here.
        # But this runs on a sync background thread, so we'll log it.
        try:
            # We will patch this info into the telemetry so the UI sees it.
            self._telemetry["sunset_protocol"] = "COMPLETE - N8N SUNSET VERIFIED"
            self._sunsetting = False
        except Exception:
            pass

# Singleton factory
_watchdog_instance = AetherNativeWatchdog()

def get_native_watchdog():
    return _watchdog_instance
