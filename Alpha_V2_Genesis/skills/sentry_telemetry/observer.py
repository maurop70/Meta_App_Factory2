import threading
import time
import json
import os
import sys
from datetime import datetime

class SentryObserver(threading.Thread):
    def __init__(self, app_name, cache_file=None, heartbeat_interval=1.0, failure_threshold=5.0):
        super().__init__()
        self.app_name = app_name
        self.heartbeat_interval = heartbeat_interval
        self.failure_threshold = failure_threshold
        
        # Paths
        if cache_file:
            self.cache_file = cache_file
        else:
            # Default to current dir
            self.cache_file = os.path.join(os.getcwd(), ".sentry_cache.json")
            
        # State
        self.daemon = True # Die when main thread dies
        self.running = True
        self.last_tick = time.time()
        self.status = "INITIALIZING" # STARTING, ACTIVE, WARNING, CRITICAL
        self.current_context = {} # Arbitrary data to dump on crash
        
        # Telemetry Data
        self.metrics = {
            "start_time": time.time(),
            "heartbeats": 0,
            "recoveries": 0
        }

    def run(self):
        """Main Observer Loop (Background Thread)"""
        print(f"--- SENTRY OBSERVER: WATCHING {self.app_name} [Threshold: {self.failure_threshold}s] ---")
        self.status = "ACTIVE"
        
        while self.running:
            time.sleep(self.heartbeat_interval)
            
            # 1. check heartbeat gap
            delta = time.time() - self.last_tick
            
            # 2. Logic
            if delta > self.failure_threshold:
                if self.status != "CRITICAL":
                    self.status = "CRITICAL"
                    self._on_silent_failure(delta)
            elif delta > (self.failure_threshold / 2):
                self.status = "WARNING"
            else:
                self.status = "ACTIVE"
                
    def tick(self, context=None):
        """Called by MAIN THREAD to say 'I am alive'"""
        self.last_tick = time.time()
        self.metrics["heartbeats"] += 1
        if context:
            self.current_context.update(context)
            
    def stop(self):
        self.running = False
        
    def _on_silent_failure(self, delta):
        """Handle Freeze"""
        print(f"\n--- SENTRY TELEMETRY: SILENT FAILURE DETECTED ({delta:.1f}s lag) ---")
        self.metrics["recoveries"] += 1
        
        # Snapshot State
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "status": "CRITICAL_FREEZE",
            "app": self.app_name,
            "metrics": self.metrics,
            "last_context": self.current_context
        }
        
        # Dump to Sentry Cache (Handshake)
        try:
            with open(self.cache_file, "w") as f:
                json.dump([snapshot], f, indent=2) # List format for legacy compatibility
            print("--- SENTRY: STATE SNAPSHOT SAVED TO CACHE ---")
        except Exception as e:
            print(f"--- SENTRY: FAILED TO SAVE SNAPSHOT: {e} ---")

    def get_status(self):
        return self.status
