import tkinter as tk
from tkinter import messagebox, scrolledtext
import subprocess
import threading
import sys
import os
import queue

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUPERVISOR_PATH = os.path.join(BASE_DIR, "supervisor.py")
BRIDGE_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "gemini-n8n", "bridge.py"))

# Import global bridge for prompt recovery
sys.path.append(os.path.dirname(BRIDGE_PATH))
try:
    from bridge import get_last_prompt
except ImportError:
    def get_last_prompt(): return None

# Sentry Telemetry Import
SKILLS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "skills"))
if SKILLS_DIR not in sys.path: sys.path.append(SKILLS_DIR)
try:
    from sentry_telemetry.observer import SentryObserver
except ImportError:
    SentryObserver = None

class MetaFactoryLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Meta App Factory - Interactive Builder")
        self.root.geometry("700x900")
        self.root.configure(bg="#1e1e1e")

        # Telemetry Observer
        self.observer = None
        if SentryObserver:
            self.observer = SentryObserver("Meta_App_Factory")
            self.observer.start()

        self.process = None

        # --- UI CONSTRUCTION ---
        
        # Title
        title_label = tk.Label(root, text="META APP FACTORY", font=("Consolas", 18, "bold"), fg="#00ccff", bg="#1e1e1e")
        title_label.pack(pady=10)

        # Status Label (Sentry L2 + Telemetry L3 Placeholder)
        self.status_frame = tk.Frame(root, bg="#1e1e1e", height=25)
        self.status_frame.pack(fill=tk.X)
        self.status_label = tk.Label(self.status_frame, text="● SYSTEM READY", font=("Consolas", 10), bg="#1e1e1e", fg="#00ff00")
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # Prompt Section
        tk.Label(root, text="APP SPECIFICATION:", font=("Consolas", 10, "bold"), fg="#bdc3c7", bg="#1e1e1e").pack(anchor="w", padx=20)
        self.prompt_input = scrolledtext.ScrolledText(root, height=5, width=70, font=("Consolas", 11), bg="#333333", fg="white", insertbackground="white")
        self.prompt_input.pack(pady=5, padx=20, fill=tk.X)
        self.prompt_input.insert(tk.END, "Describe your app here...")
        self.prompt_input.bind("<Control-Return>", lambda e: self.start_launch())
        self.prompt_input.bind("<Control-r>", lambda e: self.recover_last_prompt())

        # Main Action Buttons
        button_frame = tk.Frame(root, bg="#1e1e1e")
        button_frame.pack(pady=10)

        self.launch_button = tk.Button(button_frame, text="IGNITE FACTORY", command=self.start_launch, bg="#00ccff", fg="white", font=("Consolas", 12, "bold"), width=20)
        self.launch_button.pack(side=tk.LEFT, padx=5)

        self.recover_button = tk.Button(button_frame, text="RECOVER LAST", command=self.recover_last_prompt, bg="#444444", fg="white", font=("Consolas", 10), width=15)
        self.recover_button.pack(side=tk.LEFT, padx=5)

        self.abort_button = tk.Button(button_frame, text="ABORT", command=self.abort_process, bg="#e74c3c", fg="white", font=("Consolas", 10), width=10, state='disabled')
        self.abort_button.pack(side=tk.LEFT, padx=5)

        # Suite Command (Sentry Bypass)
        self.suite_frame = tk.Frame(root, bg="#2d2d2d", bd=1, relief=tk.SUNKEN)
        self.suite_frame.pack(padx=20, pady=10, fill=tk.X, ipady=5)
        
        tk.Label(self.suite_frame, text="SUITE COMMAND", font=("Consolas", 9, "bold"), bg="#2d2d2d", fg="#ffcc00").pack(side=tk.LEFT, padx=10)
        self.suite_entry = tk.Entry(self.suite_frame, font=("Consolas", 10), bg="#3e3e3e", fg="#ffcc00", insertbackground="white")
        self.suite_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.suite_entry.bind("<Return>", lambda e: self.send_suite_command())

        tk.Button(self.suite_frame, text="RUN", command=self.send_suite_command, bg="#ffcc00", fg="black", font=("Consolas", 8, "bold")).pack(side=tk.RIGHT, padx=10)

        # Output Area
        tk.Label(root, text="BOARDROOM STATUS & PROGRESS:", font=("Consolas", 10, "bold"), fg="#bdc3c7", bg="#1e1e1e").pack(anchor="w", padx=20)
        self.output_area = scrolledtext.ScrolledText(root, height=15, width=80, state='disabled', bg="#000000", fg="#2ecc71", font=("Consolas", 10))
        self.output_area.pack(pady=5, padx=20, fill=tk.BOTH, expand=True)

        # Interaction Section (Supervisor Feedback Loop)
        self.interaction_frame = tk.LabelFrame(root, text="INTERACTION LOOP", font=("Consolas", 10, "bold"), fg="#f1c40f", bg="#1e1e1e", padx=10, pady=10)
        self.interaction_frame.pack(pady=10, padx=20, fill=tk.X)

        self.feedback_input = tk.Entry(self.interaction_frame, font=("Consolas", 11), state='disabled', width=40, bg="#333333", fg="white")
        self.feedback_input.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.feedback_input.bind("<Return>", lambda e: self.send_feedback())

        self.send_button = tk.Button(self.interaction_frame, text="SEND", command=self.send_feedback, bg="#f39c12", fg="white", state='disabled')
        self.send_button.pack(side=tk.LEFT, padx=5)

        self.approve_button = tk.Button(self.interaction_frame, text="APPROVE #1", command=lambda: self.approve_build("1"), bg="#2980b9", fg="white", state='disabled')
        self.approve_button.pack(side=tk.LEFT, padx=5)

        self.finish_button = tk.Button(self.interaction_frame, text="FINISH", command=self.finish_build, bg="#16a085", fg="white", state='disabled')
        self.finish_button.pack(side=tk.LEFT, padx=5)

        # Telemetry Bar
        self._build_telemetry_bar()
        self.heartbeat_loop()

    # --- TELEMETRY LOGIC ---
    def _build_telemetry_bar(self):
        self.telemetry_frame = tk.Frame(self.root, bg="#0e0e0e", height=25)
        self.telemetry_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.telemetry_lbl = tk.Label(self.telemetry_frame, text="TELEMETRY: OFF", font=("Consolas", 9), bg="#0e0e0e", fg="#555555")
        self.telemetry_lbl.pack(side=tk.RIGHT, padx=20)
        if self.observer: self.telemetry_lbl.config(text="TELEMETRY: INIT...", fg="#ffee00")

    def heartbeat_loop(self):
        if self.observer:
            self.observer.tick({"last_event": "launcher_pulse"})
            status = self.observer.get_status()
            if status == "ACTIVE": self.telemetry_lbl.config(text="TELEMETRY: ACTIVE (PULSE OK)", fg="#00ff00")
            elif status == "WARNING": self.telemetry_lbl.config(text="TELEMETRY: UNSTABLE", fg="#ffcc00")
            elif status == "CRITICAL": self.telemetry_lbl.config(text="TELEMETRY: SILENT FAILURE", fg="#ff0000")
        self.root.after(500, self.heartbeat_loop)

    # --- LOGGING & UI HELPERS ---
    def log(self, text):
        self.output_area.configure(state='normal')
        if "SENTRY RECOVERY" in text: self.status_label.config(text="● SENTRY: SELF-HEALING...", fg="#f1c40f")
        elif "ALERT" in text or "ERROR" in text: self.status_label.config(text="● SENTRY: ALERT", fg="#e74c3c")
        elif "SUCCESS" in text or "READY" in text: self.status_label.config(text="● SYSTEM READY", fg="#00ff00")
        
        # Tags
        tag = None
        if "OPTION" in text: tag = "option"
        elif "Score:" in text: tag = "score"
        elif "ERROR" in text: tag = "error"
        
        if tag: self.output_area.insert(tk.END, text + "\n", tag)
        else: self.output_area.insert(tk.END, text + "\n")

        self.output_area.tag_config("option", foreground="#f1c40f", font=("Consolas", 10, "bold"))
        self.output_area.tag_config("score", foreground="#2ecc71", font=("Consolas", 10, "italic"))
        self.output_area.tag_config("error", foreground="#e74c3c", font=("Consolas", 10, "bold"))
        
        self.output_area.see(tk.END)
        self.output_area.configure(state='disabled')

    def recover_last_prompt(self, event=None):
        last = get_last_prompt()
        if last:
            self.prompt_input.delete("1.0", tk.END)
            self.prompt_input.insert("1.0", last)
            self.log(">>> SENTRY: Last prompt recovered.")
        else:
            self.log(">>> SENTRY: No prompt history found.")

    def clear_input(self):
        self.prompt_input.delete("1.0", tk.END)

    # --- INTERACTIVE PROCESS MANAGER ---
    def start_launch(self):
        prompt = self.prompt_input.get("1.0", tk.END).strip()
        if not prompt or prompt == "Describe your app here...":
            messagebox.showwarning("Warning", "Please describe your app first!")
            return

        self.launch_button.config(state='disabled')
        self.abort_button.config(state='normal')
        self.log(f">>> IGNITING FACTORY: {prompt}")
        
        thread = threading.Thread(target=self.run_supervisor, args=(prompt,))
        thread.daemon = True
        thread.start()

    def abort_process(self):
        if self.process:
            self.process.terminate()
            self.log(">>> PROCESS ABORTED.")
            self.reset_ui()

    def run_supervisor(self, prompt):
        try:
            self.process = subprocess.Popen(
                [sys.executable, SUPERVISOR_PATH, prompt],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                text=True, bufsize=1, universal_newlines=True, encoding='utf-8'
            )
            for line in self.process.stdout:
                clean = line.strip()
                if "WAITING_FOR_USER_INPUT" in clean:
                    self.enable_interaction(clean)
                    continue
                self.log(clean)
            
            self.process.wait()
            self.log(f">>> SESSION ENDED (Code: {self.process.returncode})")
        except Exception as e:
            self.log(f">>> CRITICAL ERROR: {e}")
        finally:
            self.root.after(0, self.reset_ui)

    def enable_interaction(self, signal):
        self.feedback_input.config(state='normal')
        self.send_button.config(state='normal')
        self.approve_button.config(state='normal')
        self.finish_button.config(state='normal')
        self.log("--- SYSTEM READY: Enter Option #, Feedback, or Click Approve ---")

    def disable_interaction(self):
        self.feedback_input.delete(0, tk.END)
        self.feedback_input.config(state='disabled')
        self.send_button.config(state='disabled')
        self.approve_button.config(state='disabled')
        self.finish_button.config(state='disabled')

    def send_feedback(self):
        feedback = self.feedback_input.get().strip()
        if not feedback: return
        self.log(f"User Input: {feedback}")
        if self.process:
            self.process.stdin.write(feedback + "\n")
            self.process.stdin.flush()
        self.disable_interaction()

    def approve_build(self, opt_num="1"):
        self.log(f"Approving Option {opt_num}")
        if self.process:
            self.process.stdin.write(f"{opt_num}\n")
            self.process.stdin.flush()
        self.disable_interaction()

    def finish_build(self):
        self.log("Finalizing...")
        if self.process:
            self.process.stdin.write("done\n")
            self.process.stdin.flush()
        self.disable_interaction()

    def reset_ui(self):
        self.launch_button.config(state='normal')
        self.abort_button.config(state='disabled')
        self.disable_interaction()
        self.process = None

    def send_suite_command(self):
        cmd = self.suite_entry.get().strip()
        if not cmd: return
        self.log(f">>> SUITE COMMAND: {cmd}")
        self.suite_entry.delete(0, tk.END)
        def run_thread():
            try:
                # Use sub-process to avoid blocking UI main thread
                # Also ensures it uses the Global Bridge
                res = subprocess.run(
                    [sys.executable, BRIDGE_PATH, "--prompt", cmd, "--suite_command"],
                    capture_output=True, text=True, encoding='utf-8'
                )
                self.log(f">>> SENTRY RESPONSE:\n{res.stdout.strip()}")
            except Exception as e:
                self.log(f">>> SENTRY ERROR: {e}")
        threading.Thread(target=run_thread, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = MetaFactoryLauncher(root)
    root.mainloop()
