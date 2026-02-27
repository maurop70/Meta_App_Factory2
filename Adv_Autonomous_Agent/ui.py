import tkinter as tk
import threading
import shutil
import os
import sys
import queue
import time
import json as _json
from datetime import datetime
from tkinter import scrolledtext, filedialog, messagebox, ttk
from bridge import call_app, get_last_prompt, call_for_plan, revise_plan, execute_plan_step
from action_plan import ActionPlan, PlanStep, parse_gemini_response, execute_plan, build_revision_prompt, apply_revision
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
        self.root.title("Meta_App_Factory - Elite Council Edition")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1e1e1e")
        
        # CLI Project Init
        self.initial_project = sys.argv[1] if len(sys.argv) > 1 else "General_Consulting"
        if self.initial_project != "General_Consulting":
             self.root.title(f"Meta_App_Factory - {self.initial_project}")
             threading.Thread(target=self._init_cloud_project, daemon=True).start()

        # Atomizer Instance
        self.atomizer = Atomizer() if Atomizer else None

        # Telemetry Observer
        self.observer = None
        if SentryObserver:
            from bridge import CACHE_FILE
            self.observer = SentryObserver("Meta_App_Factory", cache_file=CACHE_FILE)
            self.observer.start()

        # Styles
        self.bg_color = "#1e1e1e"
        self.fg_color = "#d4d4d4"
        self.accent_color = "#007acc"
        self.sentry_active = False

        # === ACTION PLAN STATE ===
        self.current_plan = None  # ActionPlan instance
        self.plan_mode = False    # True when Action Plan panel is visible

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

        # Shared container for console AND plan panel (fixed pack position)
        self.content_container = tk.Frame(self.main_frame, bg=self.bg_color)
        self.content_container.pack(fill=tk.BOTH, expand=True)

        self._build_console()
        self._build_action_plan_panel()  # NEW: Action Plan display
        self._build_input_area()
        self._build_plan_controls()      # NEW: Feedback + Execute buttons
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
                    if is_triad:
                        # NEW: Triad Execute launches the Action Plan flow
                        task_text = current_text if current_text else command_text
                        self._triad_execute(task_text)
                        return
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
        self.console = scrolledtext.ScrolledText(self.content_container, wrap=tk.WORD, font=("Consolas", 11), bg="#252526", fg="#d4d4d4", insertbackground="white")
        self.console.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.console.insert(tk.END, ">>> ELITE SYSTEM INITIALIZED...\n>>> CONNECTED TO N8N BRIDGE.\n")
        self.console.see(tk.END)

    # ═══════════════════════════════════════════════════
    #   ACTION PLAN PANEL
    # ═══════════════════════════════════════════════════

    def _build_action_plan_panel(self):
        """Build the Action Plan display panel (hidden by default)."""
        self.plan_panel = tk.Frame(self.content_container, bg="#1a1a2e")
        # Not packed yet — shown when a plan is active

        # Header
        self.plan_header = tk.Label(self.plan_panel, text="ACTION PLAN", font=("Consolas", 16, "bold"), bg="#1a1a2e", fg="#9D4EDD")
        self.plan_header.pack(fill=tk.X, pady=(10, 5), padx=10)

        self.plan_status_lbl = tk.Label(self.plan_panel, text="Status: DRAFT", font=("Consolas", 10), bg="#1a1a2e", fg="#888888")
        self.plan_status_lbl.pack(fill=tk.X, padx=10)

        # Scrollable steps area
        canvas_container = tk.Frame(self.plan_panel, bg="#1a1a2e")
        canvas_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.plan_canvas = tk.Canvas(canvas_container, bg="#1a1a2e", highlightthickness=0)
        self.plan_scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=self.plan_canvas.yview)
        self.plan_steps_frame = tk.Frame(self.plan_canvas, bg="#1a1a2e")

        self.plan_steps_frame.bind("<Configure>", lambda e: self.plan_canvas.configure(scrollregion=self.plan_canvas.bbox("all")))
        self._plan_window_id = self.plan_canvas.create_window((0, 0), window=self.plan_steps_frame, anchor="nw")
        self.plan_canvas.configure(yscrollcommand=self.plan_scrollbar.set)

        # CRITICAL: Make the inner frame expand to fill the canvas width
        def _on_canvas_configure(event):
            self.plan_canvas.itemconfig(self._plan_window_id, width=event.width)
        self.plan_canvas.bind("<Configure>", _on_canvas_configure)

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            self.plan_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.plan_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.plan_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.plan_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Artifacts tray (below canvas, inside plan_panel)
        self.artifacts_frame = tk.LabelFrame(self.plan_panel, text="ARTIFACTS", font=("Consolas", 9, "bold"), bg="#1a1a2e", fg="#00ccff", bd=1)
        self.artifacts_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        self.artifacts_list = tk.Listbox(self.artifacts_frame, height=2, font=("Consolas", 9), bg="#0d0d1a", fg="#d4d4d4", bd=0)
        self.artifacts_list.pack(fill=tk.X, padx=5, pady=2)

    def _build_plan_controls(self):
        """Build the feedback bar and execution controls (hidden by default)."""
        self.plan_controls = tk.Frame(self.main_frame, bg="#2d2d4e")
        # Not packed yet

        # Feedback input
        feedback_lbl = tk.Label(self.plan_controls, text="FEEDBACK:", font=("Consolas", 10, "bold"), bg="#2d2d4e", fg="#9D4EDD")
        feedback_lbl.pack(side=tk.LEFT, padx=(10, 5))

        self.feedback_field = tk.Entry(self.plan_controls, font=("Consolas", 10), bg="#3e3e5e", fg="white", insertbackground="white")
        self.feedback_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.feedback_field.bind("<Return>", lambda e: self._submit_feedback())

        self.feedback_btn = tk.Button(self.plan_controls, text="Submit Feedback", command=self._submit_feedback, font=("Consolas", 9, "bold"), bg="#4B0082", fg="white", bd=0, padx=10)
        self.feedback_btn.pack(side=tk.LEFT, padx=5)

        self.approve_btn = tk.Button(self.plan_controls, text="Approve Plan", command=self._approve_plan, font=("Consolas", 9, "bold"), bg="#006600", fg="white", bd=0, padx=10)
        self.approve_btn.pack(side=tk.LEFT, padx=5)

        self.execute_btn = tk.Button(self.plan_controls, text="Execute", command=self._execute_plan, font=("Consolas", 10, "bold"), bg="#333333", fg="#666666", bd=0, padx=15, state=tk.DISABLED)
        self.execute_btn.pack(side=tk.LEFT, padx=5)

        self.cancel_plan_btn = tk.Button(self.plan_controls, text="X", command=self._close_plan_panel, font=("Consolas", 10, "bold"), bg="#660000", fg="white", bd=0, padx=8)
        self.cancel_plan_btn.pack(side=tk.RIGHT, padx=10)

    def _show_plan_panel(self):
        """Show the Action Plan panel, hide the console."""
        # Both live inside content_container — just swap visibility
        self.console.pack_forget()
        self.plan_panel.pack(in_=self.content_container, fill=tk.BOTH, expand=True)
        self.plan_controls.pack(fill=tk.X, pady=(0, 5), before=self.input_field.master)
        self.plan_mode = True
        print(">>> [UI] Action Plan panel shown.", flush=True)

    def _close_plan_panel(self):
        """Hide the Action Plan panel, show the console."""
        self.plan_panel.pack_forget()
        self.plan_controls.pack_forget()
        self.console.pack(in_=self.content_container, fill=tk.BOTH, expand=True, pady=(0, 10))
        self.plan_mode = False
        self.current_plan = None
        self.execute_btn.config(state=tk.DISABLED, bg="#333333", fg="#666666")
        print(">>> [UI] Plan panel closed, console restored.", flush=True)

    def _render_plan(self):
        """Render the current ActionPlan as step cards in the panel."""
        if not self.current_plan:
            return

        # Clear existing cards
        for widget in self.plan_steps_frame.winfo_children():
            widget.destroy()

        plan = self.current_plan

        # Update header
        self.plan_header.config(text=f"ACTION PLAN: {plan.task[:60]}")
        status_colors = {"draft": "#ffcc00", "reviewing": "#ff8800", "approved": "#00ff00", "executing": "#00ccff", "complete": "#00ff00", "failed": "#ff0000"}
        self.plan_status_lbl.config(text=f"Status: {plan.status.upper()} | Steps: {len(plan.steps)} | Revision: #{plan.revision_count}", fg=status_colors.get(plan.status, "#888888"))

        for step in plan.steps:
            card = tk.Frame(self.plan_steps_frame, bg="#16213e", bd=1, relief=tk.RIDGE, padx=10, pady=8)
            card.pack(fill=tk.X, pady=3, padx=5)

            # Row 1: Step number + Agent badge + Status
            row1 = tk.Frame(card, bg="#16213e")
            row1.pack(fill=tk.X)

            tk.Label(row1, text=f"{step.status_icon} Step {step.step_number}", font=("Consolas", 11, "bold"), bg="#16213e", fg="white").pack(side=tk.LEFT)
            tk.Label(row1, text=f"{step.agent_badge} {step.agent}", font=("Consolas", 10, "bold"), bg="#16213e", fg="#9D4EDD").pack(side=tk.LEFT, padx=10)
            tk.Label(row1, text=step.risk_icon, font=("Consolas", 10), bg="#16213e").pack(side=tk.RIGHT)

            # Row 2: Description
            tk.Label(card, text=step.description, font=("Consolas", 9), bg="#16213e", fg="#cccccc", wraplength=500, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(4, 0))

            # Row 3: Tools (if any)
            if step.tools:
                tk.Label(card, text=f"Tools: {', '.join(step.tools)}", font=("Consolas", 8), bg="#16213e", fg="#666666").pack(fill=tk.X)

            # Triad notes (pushback)
            if step.triad_notes:
                notes_frame = tk.Frame(card, bg="#2a1a3e", padx=5, pady=3)
                notes_frame.pack(fill=tk.X, pady=(4, 0))
                tk.Label(notes_frame, text=f"Triad: {step.triad_notes}", font=("Consolas", 8, "italic"), bg="#2a1a3e", fg="#cc99ff", wraplength=480, justify=tk.LEFT).pack(fill=tk.X)

            # User notes
            if step.user_notes:
                tk.Label(card, text=f"Your Notes: {step.user_notes}", font=("Consolas", 8), bg="#16213e", fg="#ffcc00").pack(fill=tk.X)

            # Output preview (if done)
            if step.output and step.status == "done":
                out_preview = step.output[:120].replace('\n', ' ')
                tk.Label(card, text=f"Output: {out_preview}...", font=("Consolas", 8), bg="#16213e", fg="#00ff00", wraplength=500, justify=tk.LEFT).pack(fill=tk.X, pady=(2, 0))

            # Error
            if step.error:
                tk.Label(card, text=f"Error: {step.error}", font=("Consolas", 8), bg="#16213e", fg="#ff4444").pack(fill=tk.X)

            # Per-step controls (only in draft/reviewing mode)
            if plan.status in ("draft", "reviewing", "approved"):
                ctrl_frame = tk.Frame(card, bg="#16213e")
                ctrl_frame.pack(fill=tk.X, pady=(4, 0))

                step_ref = step  # Capture for closure

                def make_skip_handler(s):
                    def handler():
                        s.skipped = not s.skipped
                        self._render_plan()
                    return handler

                def make_pause_handler(s):
                    def handler():
                        s.pause_after = not s.pause_after
                        self._render_plan()
                    return handler

                skip_text = "Unskip" if step.skipped else "Skip"
                skip_color = "#666600" if step.skipped else "#333333"
                tk.Button(ctrl_frame, text=skip_text, command=make_skip_handler(step_ref), font=("Consolas", 7), bg=skip_color, fg="white", bd=0, padx=5).pack(side=tk.LEFT, padx=2)

                pause_text = "Unpause" if step.pause_after else "Pause After"
                pause_color = "#664400" if step.pause_after else "#333333"
                tk.Button(ctrl_frame, text=pause_text, command=make_pause_handler(step_ref), font=("Consolas", 7), bg=pause_color, fg="white", bd=0, padx=5).pack(side=tk.LEFT, padx=2)

        # Update artifacts tray
        self.artifacts_list.delete(0, tk.END)
        if plan.artifacts:
            for a in plan.artifacts:
                self.artifacts_list.insert(tk.END, f"  {a}")

    # ═══════════════════════════════════════════════════
    #   TRIAD EXECUTE — Action Plan Flow
    # ═══════════════════════════════════════════════════

    def _triad_execute(self, task_text):
        """Launch the Triad Protocol: generate an Action Plan."""
        if not task_text.strip():
            self.console.insert(tk.END, "\n>>> Enter a task in the input field, then press Triad Execute.\n")
            return

        self.status_label.config(text="TRIAD: Generating Plan...", fg="#9D4EDD")
        self.console.insert(tk.END, f"\n>>> TRIAD EXECUTE: {task_text}\n>>> Generating Action Plan...\n")

        def plan_thread():
            try:
                response = call_for_plan(task_text)
                plan = parse_gemini_response(response, task_text)

                if plan and plan.steps:
                    self.current_plan = plan
                    self.root.after(0, self._show_plan_panel)
                    self.root.after(0, self._render_plan)
                    self.root.after(0, lambda: self.status_label.config(text="TRIAD: Plan Ready", fg="#00ff00"))
                    print(f"\n>>> ACTION PLAN generated with {len(plan.steps)} steps.\n", flush=True)
                else:
                    print(f"\n>>> TRIAD: Could not parse plan from response.\n", flush=True)
                    print(f">>> Raw response: {str(response)[:300]}\n", flush=True)
                    self.root.after(0, lambda: self.status_label.config(text="SYSTEM READY", fg="#00ff00"))
            except Exception as e:
                print(f"\n>>> TRIAD ERROR: {e}\n", flush=True)
                self.root.after(0, lambda: self.status_label.config(text="SYSTEM READY", fg="#00ff00"))

        threading.Thread(target=plan_thread, daemon=True).start()

    def _submit_feedback(self):
        """Send user feedback to Gemini for plan revision."""
        feedback = self.feedback_field.get().strip()
        if not feedback or not self.current_plan:
            return

        self.feedback_field.delete(0, tk.END)
        self.current_plan.status = "reviewing"
        self.status_label.config(text="TRIAD: Revising Plan...", fg="#ff8800")
        self._render_plan()

        plan = self.current_plan

        def revise_thread():
            try:
                response = revise_plan(plan.to_context_json(), feedback)
                success = apply_revision(plan, response)
                if success:
                    plan.status = "draft"
                    self.root.after(0, self._render_plan)
                    self.root.after(0, lambda: self.status_label.config(text=f"TRIAD: Plan Revised (v{plan.revision_count})", fg="#00ff00"))
                    print(f"\n>>> Plan revised to v{plan.revision_count}.\n", flush=True)
                else:
                    plan.status = "draft"
                    self.root.after(0, self._render_plan)
                    print("\n>>> TRIAD: Revision could not be parsed. Plan unchanged.\n", flush=True)
                    self.root.after(0, lambda: self.status_label.config(text="TRIAD: Plan Ready", fg="#00ff00"))
            except Exception as e:
                print(f"\n>>> REVISION ERROR: {e}\n", flush=True)
                self.root.after(0, lambda: self.status_label.config(text="TRIAD: Plan Ready", fg="#00ff00"))

        threading.Thread(target=revise_thread, daemon=True).start()

    def _approve_plan(self):
        """Approve the plan and enable the Execute button."""
        if not self.current_plan:
            return
        self.current_plan.status = "approved"
        self.execute_btn.config(state=tk.NORMAL, bg="#009900", fg="white")
        self._render_plan()
        self.status_label.config(text="TRIAD: Plan APPROVED", fg="#00ff00")

    def _execute_plan(self):
        """Execute the approved Action Plan."""
        if not self.current_plan or self.current_plan.status != "approved":
            return

        self.execute_btn.config(state=tk.DISABLED, bg="#333333", fg="#666666")
        self.approve_btn.config(state=tk.DISABLED)
        self.feedback_btn.config(state=tk.DISABLED)
        self.status_label.config(text="TRIAD: Executing...", fg="#00ccff")

        plan = self.current_plan

        def progress_callback(p):
            self.root.after(0, self._render_plan)
            idx = p.current_step_index
            if idx >= 0:
                step = p.steps[idx]
                self.root.after(0, lambda: self.status_label.config(
                    text=f"Executing Step {step.step_number}/{len(p.steps)}: {step.agent}", fg="#00ccff"))
                self.root.after(0, lambda: self.progress.configure(maximum=len(p.steps), value=step.step_number))

        def exec_thread():
            try:
                execute_plan(plan, execute_plan_step_wrapper, progress_callback=progress_callback)

                # Generate Mission Report
                report = plan.generate_mission_report()

                # Show report in console AND enter iteration mode
                def enter_iteration():
                    # Close plan cards panel
                    self.plan_panel.pack_forget()
                    # Show console with report
                    self.console.pack(in_=self.content_container, fill=tk.BOTH, expand=True, pady=(0, 10))
                    self.console.insert(tk.END, report + "\n")
                    self.console.see(tk.END)

                    status_text = "TRIAD: COMPLETE — Review & Iterate" if plan.status == "complete" else "TRIAD: FAILED — Review & Iterate"
                    status_color = "#00ff00" if plan.status == "complete" else "#ff0000"
                    self.status_label.config(text=status_text, fg=status_color)

                    # Reconfigure plan_controls as iteration controls
                    self._show_iteration_controls()

                self.root.after(200, enter_iteration)

            except Exception as e:
                print(f"\n>>> EXECUTION ERROR: {e}\n", flush=True)
                self.root.after(0, lambda: self.status_label.config(text="SYSTEM READY", fg="#00ff00"))
                self.root.after(0, lambda: self.approve_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.feedback_btn.config(state=tk.NORMAL))

        def execute_plan_step_wrapper(payload):
            """Wrapper that routes based on step context."""
            prompt = payload.get("prompt", "")
            # Extract agent from prompt if available
            if "YOUR ROLE:" in prompt:
                try:
                    agent = prompt.split("YOUR ROLE:")[1].split("\n")[0].strip()
                    return execute_plan_step(agent, prompt)
                except:
                    pass
            return call_app(payload)

        threading.Thread(target=exec_thread, daemon=True).start()

    def _show_iteration_controls(self):
        """Show iteration controls (Request Changes / Finalize) after execution."""
        # Reconfigure the plan_controls bar for iteration mode
        for widget in self.plan_controls.winfo_children():
            widget.pack_forget()

        # Iteration feedback label
        iter_lbl = tk.Label(self.plan_controls, text="ITERATE:", font=("Consolas", 10, "bold"), bg="#2d2d4e", fg="#00ccff")
        iter_lbl.pack(side=tk.LEFT, padx=(10, 5))

        # Reuse feedback field
        self.feedback_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.feedback_field.delete(0, tk.END)
        self.feedback_field.config(state=tk.NORMAL)
        self.feedback_field.bind("<Return>", lambda e: self._request_changes())

        # Request Changes button
        changes_btn = tk.Button(self.plan_controls, text="Request Changes", command=self._request_changes,
                                font=("Consolas", 9, "bold"), bg="#cc6600", fg="white", bd=0, padx=10)
        changes_btn.pack(side=tk.LEFT, padx=5)

        # Finalize button
        finalize_btn = tk.Button(self.plan_controls, text="✓ Finalize", command=self._finalize_plan,
                                 font=("Consolas", 10, "bold"), bg="#006600", fg="white", bd=0, padx=15)
        finalize_btn.pack(side=tk.LEFT, padx=5)

        # Close button
        close_btn = tk.Button(self.plan_controls, text="X", command=self._close_plan_panel,
                              font=("Consolas", 10, "bold"), bg="#660000", fg="white", bd=0, padx=8)
        close_btn.pack(side=tk.RIGHT, padx=10)

        # Make sure the controls bar is visible
        self.plan_controls.pack(fill=tk.X, pady=(0, 5), before=self.input_field.master)

    def _request_changes(self):
        """User requests changes — generate a revised plan and re-execute."""
        feedback = self.feedback_field.get().strip()
        if not feedback:
            self.console.insert(tk.END, "\n>>> Enter your feedback before requesting changes.\n")
            self.console.see(tk.END)
            return

        if not self.current_plan:
            self.console.insert(tk.END, "\n>>> No active plan to iterate on.\n")
            self.console.see(tk.END)
            return

        plan = self.current_plan
        self.status_label.config(text="TRIAD: Revising Plan...", fg="#ff8800")
        self.console.insert(tk.END, f"\n>>> REQUEST CHANGES: {feedback}\n>>> Generating revised plan...\n")
        self.console.see(tk.END)

        def revise_and_replan():
            try:
                # Build revision prompt that includes what was done and what needs changing
                revision_prompt = (
                    f"SYSTEM OVERRIDE: ITERATION MODE.\n"
                    f"The user has reviewed the execution results and wants changes.\n\n"
                    f"ORIGINAL TASK: {plan.task}\n"
                    f"PREVIOUS EXECUTION: {plan.progress} steps completed.\n\n"
                    f"USER FEEDBACK:\n\"{feedback}\"\n\n"
                    f"PREVIOUS PLAN CONTEXT:\n{plan.to_context_json()}\n\n"
                    f"INSTRUCTIONS:\n"
                    f"1. Review what was done and the user's feedback.\n"
                    f"2. Create a NEW revised plan that addresses the feedback.\n"
                    f"3. Keep steps that worked well, modify or add steps as needed.\n"
                    f"4. Return ONLY a JSON with a 'steps' array.\n"
                    f"5. Each step: agent, description, tools (list).\n"
                )

                response = call_for_plan(revision_prompt)
                revised = parse_gemini_response(response, plan.task)

                if revised and revised.steps:
                    # Update the plan
                    revised.revision_count = plan.revision_count + 1
                    revised.revision_history = plan.revision_history
                    revised.artifacts = plan.artifacts  # Carry forward artifacts
                    self.current_plan = revised

                    # Switch to plan panel for review
                    self.root.after(0, lambda: self.plan_controls.pack_forget())
                    self.root.after(0, self._rebuild_plan_controls)
                    self.root.after(0, self._show_plan_panel)
                    self.root.after(0, self._render_plan)
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"TRIAD: Revised Plan (#{revised.revision_count})", fg="#ff8800"))
                    print(f"\n>>> Revised plan generated with {len(revised.steps)} steps.\n", flush=True)
                else:
                    print(f"\n>>> Could not parse revised plan. Try more specific feedback.\n", flush=True)
                    self.root.after(0, lambda: self.status_label.config(
                        text="TRIAD: Revision Failed", fg="#ff0000"))
            except Exception as e:
                print(f"\n>>> REVISION ERROR: {e}\n", flush=True)
                self.root.after(0, lambda: self.status_label.config(
                    text="TRIAD: Revision Error", fg="#ff0000"))

        threading.Thread(target=revise_and_replan, daemon=True).start()

    def _rebuild_plan_controls(self):
        """Rebuild the plan controls bar to its original state (for re-entering plan review)."""
        for widget in self.plan_controls.winfo_children():
            widget.pack_forget()

        # Feedback input
        feedback_lbl = tk.Label(self.plan_controls, text="FEEDBACK:", font=("Consolas", 10, "bold"), bg="#2d2d4e", fg="#9D4EDD")
        feedback_lbl.pack(side=tk.LEFT, padx=(10, 5))

        self.feedback_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.feedback_field.delete(0, tk.END)
        self.feedback_field.config(state=tk.NORMAL)
        self.feedback_field.bind("<Return>", lambda e: self._submit_feedback())

        self.feedback_btn = tk.Button(self.plan_controls, text="Submit Feedback", command=self._submit_feedback,
                                     font=("Consolas", 9, "bold"), bg="#4B0082", fg="white", bd=0, padx=10)
        self.feedback_btn.pack(side=tk.LEFT, padx=5)

        self.approve_btn = tk.Button(self.plan_controls, text="Approve Plan", command=self._approve_plan,
                                     font=("Consolas", 9, "bold"), bg="#006600", fg="white", bd=0, padx=10)
        self.approve_btn.pack(side=tk.LEFT, padx=5)

        self.execute_btn = tk.Button(self.plan_controls, text="Execute", command=self._execute_plan,
                                     font=("Consolas", 10, "bold"), bg="#333333", fg="#666666", bd=0, padx=15, state=tk.DISABLED)
        self.execute_btn.pack(side=tk.LEFT, padx=5)

        cancel_btn = tk.Button(self.plan_controls, text="X", command=self._close_plan_panel,
                               font=("Consolas", 10, "bold"), bg="#660000", fg="white", bd=0, padx=8)
        cancel_btn.pack(side=tk.RIGHT, padx=10)

    def _finalize_plan(self):
        """User is satisfied — finalize the creation and save state."""
        if not self.current_plan:
            return

        plan = self.current_plan
        plan.status = "finalized"

        # Save final plan state to disk
        import json as _json
        state_dir = os.path.dirname(os.path.abspath(__file__))
        finalized_dir = os.path.join(state_dir, ".Gemini_state", "finalized_plans")
        os.makedirs(finalized_dir, exist_ok=True)

        safe_name = plan.task[:40].replace(" ", "_").replace("/", "_").replace("\\", "_")
        plan_file = os.path.join(finalized_dir, f"{safe_name}.json")

        plan_data = {
            "task": plan.task,
            "status": "finalized",
            "revision_count": plan.revision_count,
            "created_at": plan.created_at,
            "finalized_at": datetime.now().isoformat(),
            "artifacts": plan.artifacts,
            "steps": [
                {
                    "step": s.step_number,
                    "agent": s.agent,
                    "description": s.description,
                    "status": s.status,
                    "output_preview": (s.output[:200] if s.output else ""),
                    "elapsed_seconds": s.elapsed_seconds
                }
                for s in plan.steps
            ]
        }

        with open(plan_file, "w", encoding="utf-8") as f:
            _json.dump(plan_data, f, indent=2)

        # Write finalization summary to console
        self.plan_controls.pack_forget()
        self.console.insert(tk.END,
            f"\n{'=' * 60}\n"
            f"  ✓ FINALIZED: {plan.task}\n"
            f"  Revisions: {plan.revision_count} | Artifacts: {len(plan.artifacts)}\n"
            f"  Saved to: {plan_file}\n"
            f"{'=' * 60}\n"
            f"\n>>> You can always come back and iterate on this by running\n"
            f">>> Triad Execute with a new prompt referencing this task.\n\n"
        )
        self.console.see(tk.END)

        self.status_label.config(text="SYSTEM READY", fg="#00ff00")
        self.plan_mode = False
        self.current_plan = None
        print(f">>> Plan finalized and saved: {plan_file}", flush=True)

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
            try:
                result = call_app({"prompt": cmd, "suite_command": True})
                if result:
                    print(f"\n>>> SUITE RESPONSE:\n{result}\n", flush=True)
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
                    result = call_app({"prompt": user_input})
                    if result:
                        print(f"\n>>> COUNCIL RESPONSE:\n{result}\n", flush=True)
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
