import tkinter as tk
import threading
import shutil
import os
import sys
import queue
import time
from tkinter import scrolledtext, filedialog, messagebox, ttk
from bridge import call_app, get_last_prompt
from flask import Flask, request, jsonify # Tunnel-Ready Endpoint

# Sentry Telemetry & Atomizer (Shared Utils)
# Adjust paths for the new app structure
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_UTILS = os.path.abspath(os.path.join(BASE_DIR, "..", "utils"))
SKILLS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "skills"))

if SHARED_UTILS not in sys.path: sys.path.append(SHARED_UTILS)
if SKILLS_DIR not in sys.path: sys.path.append(SKILLS_DIR)

try:
    from atomizer import Atomizer
except ImportError:
    print("WARNING: Atomizer not found in Shared Utils.")
    Atomizer = None
try:
    from sentry_telemetry.observer import SentryObserver
except ImportError:
    SentryObserver = None

class RedirectText(object):
    def __init__(self, out_queue):
        self.out_queue = out_queue
    def write(self, string):
        self.out_queue.put(string)
    def flush(self):
        pass

# --- RECURSIVE LEARNING: Tunnel-Ready Endpoint ---
app_flask = Flask(__name__)
log_queue_ref = None # Global reference for Flask to access

@app_flask.route('/api/hot_update', methods=['POST'])
def hot_update():
    try:
        data = request.json
        if log_queue_ref:
            log_queue_ref.put(f"\n>>> HOT UPDATE RECEIVED: {str(data)[:100]}...\n")
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def run_flask():
    try:
        app_flask.run(port=5000, debug=False, use_reloader=False)
    except: pass
# -------------------------------------------------

class ToolTip(object):
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.tw = None

    def enter(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert") or (0,0,0,0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tw, text=self.text, justify=tk.LEFT, background="#333333", fg="white", relief=tk.SOLID, borderwidth=1, font=("Consolas", 9))
        label.pack(ipadx=4, ipady=4)

    def leave(self, event=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None

class AppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Alpha_V2_Genesis - Elite Council Edition")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1e1e1e")
        
        # CLI Project Init
        self.initial_project = sys.argv[1] if len(sys.argv) > 1 else "General_Consulting"
        if self.initial_project != "General_Consulting":
             self.root.title(f"Alpha_V2_Genesis - {self.initial_project}")
             threading.Thread(target=self._init_cloud_project, daemon=True).start()

        # Atomizer Instance
        self.atomizer = Atomizer() if Atomizer else None

        # Telemetry Observer
        self.observer = None
        if SentryObserver:
            from bridge import CACHE_FILE
            self.observer = SentryObserver("Alpha_V2_Genesis", cache_file=CACHE_FILE)
            self.observer.start()

        # Styles
        self.bg_color = "#1e1e1e"
        self.fg_color = "#d4d4d4"
        self.accent_color = "#007acc"
        self.sentry_active = False

        # Main Layout
        self.main_container = tk.Frame(root, bg=self.bg_color)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.sidebar_frame = tk.Frame(self.main_container, bg="#1a1a1a", width=260)
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        
        self.main_frame = tk.Frame(self.main_container, bg=self.bg_color)
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Build UI Components
        self._build_header()
        self._build_command_palette()
        self._build_console()
        self._build_input_area()
        self._build_sentry_panel()
        self._build_agent_status_panel()
        self._build_atomizer_panel()
        self._build_telemetry_bar()

        # Queue for Thread-Safe UI Updates
        self.log_queue = queue.Queue()
        sys.stdout = RedirectText(self.log_queue)
        
        # Global Ref for Flask
        global log_queue_ref
        log_queue_ref = self.log_queue
        
        # Start Tunnel Endpoint
        threading.Thread(target=run_flask, daemon=True).start()
        
        # Start Polling Loops
        self.check_queue()
        self.heartbeat_loop()

    def _init_cloud_project(self):
        """Called on startup if CLI arg is provided"""
        try:
            from bridge import _check_project_switch
            _check_project_switch(self.initial_project)
            self.log_queue.put(f">>> CLOUD SYNC: Initialized Workspace for '{self.initial_project}'\n")
        except Exception as e:
            self.log_queue.put(f">>> CLOUD INIT ERROR: {e}\n")

    def _build_header(self):
        header_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        title = tk.Label(header_frame, text="ELITE COUNCIL TERMINAL", font=("Consolas", 24, "bold"), fg=self.accent_color, bg=self.bg_color)
        title.pack(side=tk.LEFT)
        
        self.status_label = tk.Label(header_frame, text="● SYSTEM READY", font=("Consolas", 12), fg="#00ff00", bg=self.bg_color)
        self.status_label.pack(side=tk.RIGHT, padx=10)

    def _build_command_palette(self):
        palette_title = tk.Label(self.sidebar_frame, text="COMMAND PALETTE", font=("Consolas", 14, "bold"), bg="#1a1a1a", fg="#00ccff", pady=10)
        palette_title.pack(fill=tk.X)

        commands_path = os.path.abspath(os.path.join(BASE_DIR, "..", "commands.json"))
        commands = []
        if os.path.exists(commands_path):
            try:
                import json
                with open(commands_path, "r", encoding="utf-8") as f:
                    commands = json.load(f)
            except Exception:
                pass
        
        visionary_names = ["Triad Execute", "Security Audit", "Twin Test", "Market Research"]
        
        vis_frame = tk.LabelFrame(self.sidebar_frame, text="The Visionary Suite", font=("Consolas", 10, "bold"), bg="#1a1a1a", fg="#9D4EDD", bd=2, highlightbackground="#4B0082", highlightthickness=1)
        vis_frame.pack(fill=tk.X, pady=(10, 20), padx=5, ipady=5)
        
        maint_frame = tk.LabelFrame(self.sidebar_frame, text="The Maintenance Suite", font=("Consolas", 10, "bold"), bg="#1a1a1a", fg="#4682B4", bd=2, highlightbackground="#2F4F4F", highlightthickness=1)
        maint_frame.pack(fill=tk.X, pady=(0, 20), padx=5, ipady=5)

        for cmd_info in commands:
            label_text = cmd_info.get("label", "Action")
            cmd = cmd_info.get("cmd", "")
            desc = cmd_info.get("desc", "")
            
            parent = maint_frame
            bg_color = "#2F4F4F"
            active_bg = "#4682B4"
            fg_color = "white"
            
            for vn in visionary_names:
                if vn in label_text:
                    parent = vis_frame
                    bg_color = "#4B0082"
                    active_bg = "#9D4EDD"
                    break
                    
            def make_handler(command_text, is_triad=False, is_flush=False):
                def handler():
                    if is_flush:
                        # Directly wipe sentry cache and stamp FRESH_BOOT
                        import json as _json
                        from datetime import datetime
                        cache_file = os.path.abspath(os.path.join(BASE_DIR, ".Gemini_state", ".sentry_cache.json"))
                        master_index = os.path.abspath(os.path.join(BASE_DIR, "..", "MASTER_INDEX.md"))
                        try:
                            with open(cache_file, "w") as cf:
                                _json.dump([], cf)
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            entry = f"\n## FRESH_BOOT\n- **Timestamp:** {timestamp}\n- **Reason:** Manual flush via UI button.\n- **Status:** FRESH_BOOT\n"
                            with open(master_index, "a", encoding="utf-8") as mf:
                                mf.write(entry)
                            self.console.insert(tk.END, f"\n>>> FLUSH COMPLETE: Sentry cache wiped. DCC reset to FRESH_BOOT at {timestamp}\n")
                            self.console.see(tk.END)
                            self.status_label.config(text="SYSTEM READY", fg="#00ff00")
                        except Exception as e:
                            self.console.insert(tk.END, f"\n>>> FLUSH ERROR: {e}\n")
                        return
                    # Standard handler
                    current_text = self.input_field.get("1.0", tk.END).strip()
                    self.input_field.delete("1.0", tk.END)
                    if is_triad and current_text:
                        self.input_field.insert(tk.END, f"{command_text}\n\nTASK: {current_text}")
                    else:
                        self.input_field.insert(tk.END, command_text)
                    self.send_prompt()
                return handler

            is_triad_btn = "Triad Execute" in label_text
            is_flush_btn = "Flush Memory" in label_text
            btn = tk.Button(parent, text=label_text, command=make_handler(cmd, is_triad=is_triad_btn, is_flush=is_flush_btn), font=("Consolas", 10, "bold"), bg=bg_color, fg=fg_color, activebackground=active_bg, activeforeground="white", bd=0, pady=6, cursor="hand2")
            btn.pack(fill=tk.X, padx=10, pady=5)
            
            if desc:
                ToolTip(btn, desc)


    def _build_console(self):
        self.console = scrolledtext.ScrolledText(self.main_frame, wrap=tk.WORD, font=("Consolas", 11), bg="#252526", fg="#d4d4d4", insertbackground="white")
        self.console.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        self.console.insert(tk.END, ">>> ELITE SYSTEM INITIALIZED...\n>>> CONNECTED TO N8N BRIDGE.\n")
        self.console.see(tk.END)

    def _build_input_area(self):
        input_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        self.input_field = scrolledtext.ScrolledText(input_frame, height=4, font=("Consolas", 12), bg="#333333", fg="white", insertbackground="white")
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.input_field.bind("<Control-Return>", self.send_prompt)
        self.input_field.bind("<Control-r>", self.recover_last_prompt)

        btn_frame = tk.Frame(input_frame, bg=self.bg_color)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        send_btn = tk.Button(btn_frame, text="SEND COMMAND", command=self.send_prompt, font=("Consolas", 12, "bold"), bg=self.accent_color, fg="white", width=15, height=2)
        send_btn.pack(pady=(0, 5))
        
        clear_btn = tk.Button(btn_frame, text="CLEAR", command=self.clear_console, font=("Consolas", 10), bg="#444444", fg="white", width=15)
        clear_btn.pack()

    def _build_sentry_panel(self):
        sentry_frame = tk.Frame(self.main_frame, bg="#2d2d2d", bd=1, relief=tk.SUNKEN)
        sentry_frame.pack(fill=tk.X, pady=(10, 0), ipady=5)
        
        lbl = tk.Label(sentry_frame, text="SUITE COMMAND CONSOLE (SENTRY BYPASS)", font=("Consolas", 10, "bold"), bg="#2d2d2d", fg="#ffcc00")
        lbl.pack(side=tk.LEFT, padx=10)
        
        self.suite_input = tk.Entry(sentry_frame, font=("Consolas", 10), bg="#3e3e3e", fg="#ffcc00", insertbackground="white")
        self.suite_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.suite_input.bind("<Return>", self.send_suite_command)
        
        run_btn = tk.Button(sentry_frame, text="RUN", command=self.send_suite_command, font=("Consolas", 9, "bold"), bg="#ffcc00", fg="black")
        run_btn.pack(side=tk.LEFT, padx=(0, 10))

        rec_btn = tk.Button(sentry_frame, text="RECOVER LAST", command=self.recover_last_prompt, font=("Consolas", 9), bg="#444444", fg="white")
        rec_btn.pack(side=tk.RIGHT, padx=10)
        
        upload_btn = tk.Button(sentry_frame, text="UPLOAD FILE", command=self.pasting_files, font=("Consolas", 9), bg="#444444", fg="white")
        upload_btn.pack(side=tk.RIGHT, padx=10)

    def _build_atomizer_panel(self):
        self.atomizer_frame = tk.Frame(self.main_frame, bg="#252526", bd=1, relief=tk.GROOVE)
        self.atomizer_frame.pack(fill=tk.X, pady=(10, 0))
        
        lbl = tk.Label(self.atomizer_frame, text="THE ATOMIZER: DECONSTRUCTION STATION", font=("Consolas", 10, "bold"), bg="#252526", fg="#00ccff")
        lbl.pack(anchor="w", padx=10, pady=5)
        
        self.chunk_list = tk.Listbox(self.atomizer_frame, height=4, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4", bd=0, highlightthickness=0)
        self.chunk_list.pack(fill=tk.X, padx=10, pady=(0,5))

    def _build_agent_status_panel(self):
        status_frame = tk.LabelFrame(self.main_frame, text="NEURAL NETWORK STATUS", font=("Consolas", 10, "bold"), bg="#1e1e1e", fg="#00ccff", bd=1, relief=tk.GROOVE)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.agent_labels = {}
        roles = ["CFO", "CMO", "HR", "CRITIC", "PITCH", "ATOMIZER", "ARCHITECT"]
        
        col = 0
        row = 0
        for role in roles:
            lbl = tk.Label(status_frame, text=f"● {role}", font=("Consolas", 9), bg="#1e1e1e", fg="#444444", width=15, anchor="w")
            lbl.grid(row=row, column=col, padx=5, pady=5)
            self.agent_labels[role] = lbl
            col += 1
            if col > 3:
                col = 0
                row += 1
                
        refresh_btn = tk.Button(status_frame, text="↻ SCAN", command=self.run_system_check, font=("Consolas", 8), bg="#333333", fg="white", bd=0)
        refresh_btn.grid(row=row+1, column=3, sticky="e", padx=10, pady=5)
        self.root.after(2000, self.run_system_check)

    def run_system_check(self):
        def check():
            from bridge import check_system_health
            report = check_system_health()
            self.root.after(0, lambda: self._update_status_ui(report))
        threading.Thread(target=check, daemon=True).start()
        
    def _update_status_ui(self, report):
        for role, is_online in report.items():
            key = role.upper()
            if key == "PRESENTATION_ARCHITECT": key = "ARCHITECT"
            lbl = self.agent_labels.get(key)
            if lbl:
                if is_online: lbl.config(fg="#00ff00")
                else: lbl.config(fg="#ff0000")

    def _build_telemetry_bar(self):
        self.telemetry_frame = tk.Frame(self.root, bg="#0e0e0e", height=25)
        self.telemetry_frame.pack(side=tk.BOTTOM, fill=tk.X)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("green.Horizontal.TProgressbar", foreground='green', background='green')
        self.progress = ttk.Progressbar(self.telemetry_frame, style="green.Horizontal.TProgressbar", orient="horizontal", length=300, mode="determinate")
        self.progress.pack(side=tk.LEFT, padx=20, pady=5)
        self.telemetry_lbl = tk.Label(self.telemetry_frame, text="TELEMETRY: OFF", font=("Consolas", 9), bg="#0e0e0e", fg="#555555")
        self.telemetry_lbl.pack(side=tk.RIGHT, padx=20)
        if self.observer: self.telemetry_lbl.config(text="TELEMETRY: INITIALIZING...", fg="#ffee00")

    def heartbeat_loop(self):
        if self.observer:
            self.observer.tick({"last_event": "ui_update"})
            status = self.observer.get_status()
            if status == "ACTIVE": self.telemetry_lbl.config(text="TELEMETRY: ACTIVE (PULSE OK)", fg="#00ff00")
            elif status == "WARNING": self.telemetry_lbl.config(text="TELEMETRY: UNSTABLE", fg="#ffcc00")
            elif status == "CRITICAL": self.telemetry_lbl.config(text="TELEMETRY: CRITICAL", fg="#ff0000")
        self.root.after(500, self.heartbeat_loop)

    def check_queue(self):
        while True:
            try:
                msg = self.log_queue.get_nowait()
                if isinstance(msg, bytes):
                    msg = msg.decode('utf-8', errors='replace')
                self.console.insert(tk.END, msg)
                self.console.see(tk.END)
                if "SENTRY ALERT" in msg:
                    self.status_label.config(text="● SENTRY: RECOVERING", fg="#ffcc00")
                    self.sentry_active = True
                elif "SENTRY RECOVERY" in msg:
                    self.status_label.config(text="● SENTRY: HEALING", fg="#ff0000")
                elif self.sentry_active and "Tool Success" in msg:
                    self.status_label.config(text="● SYSTEM READY", fg="#00ff00")
                    self.sentry_active = False
            except queue.Empty: break
        self.root.after(100, self.check_queue)
        
    def clear_console(self):
        self.console.delete(1.0, tk.END)
        try:
            from bridge import clear_memory
            clear_memory()
            self.console.insert(tk.END, ">>> MEMORY WIPED. READY FOR NEW CONTEXT.\n")
        except: pass
        
    def recover_last_prompt(self, event=None):
        last = get_last_prompt()
        if last:
            self.input_field.delete(1.0, tk.END)
            self.input_field.insert(tk.END, last)
            self.console.insert(tk.END, f"\n>>> SENTRY: RECOVERED LAST PROMPT.\n")
            self.console.see(tk.END)

    def pasting_files(self):
        file_path = filedialog.askopenfilename(title="Select File to Upload to Project Cloud")
        if file_path:
            filename = os.path.basename(file_path)
            user_input = self.input_field.get("1.0", tk.END).strip()
            project_name = "General_Consulting"
            if "Project:" in user_input:
                try: 
                    temp = user_input.split("Project:")[1].strip()
                    project_name = temp.split("\n")[0].split(":")[0].strip().replace(" ", "_")
                except: pass
            elif "Project " in user_input:
                try: 
                    temp = user_input.split("Project ")[1].strip()
                    candidate = temp.split("\n")[0].split(":")[0].strip()
                    # Heuristic for long prompt interpreted as name
                    if len(candidate) > 50:
                        candidate = "_".join(candidate.split()[:3])
                    project_name = candidate.replace(" ", "_").strip(".")
                except: pass
            
            try:
                from google_suite import GoogleSuiteManager
                mgr = GoogleSuiteManager(project_name)
                link = mgr.upload_file(file_path)
                if link: self.console.insert(tk.END, f"\n>>> CLOUD SYNC: Uploaded {filename} to {project_name}.\n>>> URL: {link}\n")
                else: self.console.insert(tk.END, f"\n>>> CLOUD SYNC FAILED. Check Console.\n")
            except Exception as e:
                self.console.insert(tk.END, f"\n>>> UPLOAD ERROR: {e}\n")

    def send_suite_command(self, event=None):
        cmd = self.suite_input.get().strip()
        if not cmd: return
        self.suite_input.delete(0, tk.END)
        self.console.insert(tk.END, f"\n>>> SUITE COMMAND: {cmd}\n")
        def run_thread():
            try: call_app({"prompt": cmd, "suite_command": True})
            except Exception as e: print(f"Suite Error: {e}")
        threading.Thread(target=run_thread, daemon=True).start()

    def send_prompt(self, event=None, override_text=None):
        if override_text: user_input = override_text
        else:
            user_input = self.input_field.get("1.0", tk.END).strip()
        if not user_input: return
        if not override_text: self.input_field.delete("1.0", tk.END)
        self.console.insert(tk.END, f"\n>>> USER: {user_input}\n")
        self.status_label.config(text="● PROCESSING...", fg="#00ccff")
        
        def run_thread():
            try:
                self.console.insert(tk.END, f">>> ATOMIZER: Scanning complexity...\n")
                chunks = self.atomizer.evaluate(user_input) if self.atomizer else []
                
                if chunks and len(chunks) > 0:
                    self.console.insert(tk.END, f">>> ATOMIZER: COMPLEXITY DETECTED. BREAKING DOWN {len(chunks)} PAYLOADS.\n")
                    self.chunk_list.delete(0, tk.END)
                    for c in chunks: self.chunk_list.insert(tk.END, f"• {c}")
                    self.progress["maximum"] = len(chunks)
                    self.progress["value"] = 0
                    results = []
                    for i, chunk in enumerate(chunks):
                        self.status_label.config(text=f"● ATOMIZER: EXECUTING CHUNK {i+1}/{len(chunks)}", fg="#ffcc00")
                        self.console.insert(tk.END, f"\n>>> ATOMIZER: Launching Chunk {i+1}...\n")
                        project_name = "General_Consulting"
                        if "Project:" in user_input:
                            try: 
                                temp = user_input.split("Project:")[1].strip()
                                project_name = temp.split("\n")[0].split(":")[0].strip().replace(" ", "_")
                            except: pass
                        elif "Project " in user_input:
                            try: 
                                temp = user_input.split("Project ")[1].strip()
                                candidate = temp.split("\n")[0].split(":")[0].strip()
                                # Heuristic for long prompt interpreted as name
                                if len(candidate) > 50:
                                    candidate = "_".join(candidate.split()[:3])
                                project_name = candidate.replace(" ", "_").strip(".")
                            except: pass
                        # [ACTION]: Execution Directive Wrapper
                        execution_prompt = (
                            f"DIRECTIVE: {chunk}\n"
                            f"CONTEXT: You are in AUTO-EXECUTION MODE. \n"
                            f"INSTRUCTION: Use your tools immediately to GENERATE the actual content for this step. \n"
                            f"Do not offer to do it. Do not plan. Do not summarize what you will do. \n"
                            f"If you need to search, partial search. If you need to calculate, calculate. \n"
                            f"OUTPUT: The actual result of the work."
                        )
                        res = call_app({"prompt": execution_prompt, "project_name": project_name})
                        results.append(res)
                        self.progress["value"] = i + 1
                        self.console.insert(tk.END, f">>> ATOMIZER: Chunk {i+1} Complete.\n")
                    self.status_label.config(text="● ATOMIZER: STITCHING...", fg="#00ff00")
                    final_report = self.atomizer.stitch(results)
                    self.console.insert(tk.END, f"\n{final_report}\n")
                else:
                    call_app({"prompt": user_input})
            except Exception as e:
                print(f"App Error: {e}")
                self.console.insert(tk.END, f">>> SYSTEM ERROR: {e}\n")
            finally:
                self.root.after(0, lambda: self.status_label.config(text="● SYSTEM READY", fg="#00ff00"))
                self.progress["value"] = 0
        threading.Thread(target=run_thread, daemon=True).start()
        return "break"

if __name__ == "__main__":
    root = tk.Tk()
    app = AppGUI(root)
    root.mainloop()
