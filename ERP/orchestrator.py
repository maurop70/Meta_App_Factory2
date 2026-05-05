import customtkinter as ctk
import subprocess
import threading

# Configuration
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class OrbitalCommander(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Orbital Deployment Commander - MWO Phase 43")
        self.geometry("900x600")
        
        # Grid layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)

        # Left Frame: Controls
        self.control_frame = ctk.CTkFrame(self, corner_radius=10)
        self.control_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        self.label_title = ctk.CTkLabel(self.control_frame, text="ACTUATION MATRIX", font=ctk.CTkFont(size=16, weight="bold"))
        self.label_title.pack(pady=(20, 30))

        self.btn_frontend = ctk.CTkButton(
            self.control_frame, 
            text="[Deploy Frontend Matrix]", 
            command=self.deploy_frontend,
            height=40,
            fg_color="#3b82f6",
            hover_color="#2563eb"
        )
        self.btn_frontend.pack(pady=15, padx=20, fill="x")

        self.btn_backend = ctk.CTkButton(
            self.control_frame, 
            text="[Deploy Backend Matrix]", 
            command=self.deploy_backend,
            height=40,
            fg_color="#10b981",
            hover_color="#059669"
        )
        self.btn_backend.pack(pady=15, padx=20, fill="x")

        # Right Frame: Console Output
        self.console_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#0f172a")
        self.console_frame.grid(row=0, column=1, padx=(0, 20), pady=20, sticky="nsew")
        
        self.console_label = ctk.CTkLabel(self.console_frame, text="EXECUTION TELEMETRY", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94a3b8")
        self.console_label.pack(pady=(10, 5), padx=10, anchor="w")

        self.console_text = ctk.CTkTextbox(
            self.console_frame, 
            fg_color="#1e293b", 
            text_color="#34d399", 
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word"
        )
        self.console_text.pack(expand=True, fill="both", padx=10, pady=(0, 10))
        self.console_text.configure(state="disabled")

    def log_message(self, message):
        """Thread-safe logging to the UI console."""
        self.console_text.configure(state="normal")
        self.console_text.insert("end", message + "\n")
        self.console_text.see("end")
        self.console_text.configure(state="disabled")

    def run_subprocess_and_log(self, cmd_str, cwd=None):
        """Executes a subprocess and streams output to the console."""
        self.log_message(f"[SYSTEM] Executing: {cmd_str}")
        try:
            process = subprocess.Popen(
                cmd_str,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                text=True,
                cwd=cwd,
                bufsize=1,
                universal_newlines=True
            )
            
            for line in iter(process.stdout.readline, ''):
                if line:
                    # Use after() to schedule GUI updates from the worker thread
                    self.after(0, self.log_message, line.strip())
            
            process.stdout.close()
            return_code = process.wait()
            
            if return_code == 0:
                self.after(0, self.log_message, f"[SUCCESS] Process completed with code 0.")
            else:
                self.after(0, self.log_message, f"[FATAL] Process failed with exit code {return_code}.")
                
        except Exception as e:
            self.after(0, self.log_message, f"[ERROR] Execution failed: {str(e)}")

    def deploy_frontend_task(self):
        self.log_message("\n=== INITIATING FRONTEND COMPILATION & TRANSMISSION ===")
        frontend_dir = r"C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\maintenance_frontend"
        
        # Phase 2.A: Compile
        self.run_subprocess_and_log("npm run build", cwd=frontend_dir)
        
        # Phase 2.B: Transmit
        scp_cmd = r"scp -o StrictHostKeyChecking=no -i C:\Users\mpetr\.ssh\id_rsa -r C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\maintenance_frontend\dist\* root@68.183.30.128:/opt/erp/frontend/"
        self.run_subprocess_and_log(scp_cmd)
        
        self.log_message("=== FRONTEND MATRIX DEPLOYMENT CYCLE COMPLETE ===")
        self.after(0, lambda: self.btn_frontend.configure(state="normal"))

    def deploy_frontend(self):
        self.btn_frontend.configure(state="disabled")
        threading.Thread(target=self.deploy_frontend_task, daemon=True).start()

    def deploy_backend_task(self):
        self.log_message("\n=== INITIATING BACKEND TRANSMISSION & ACTUATION ===")
        
        # Phase 3.A: Transmit
        scp_cmd = r"scp -o StrictHostKeyChecking=no -i C:\Users\mpetr\.ssh\id_rsa -r C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Maintenance_Work_Order\* root@68.183.30.128:/opt/erp/backend/"
        self.run_subprocess_and_log(scp_cmd)
        
        # Phase 3.B: Cycle Daemon
        ssh_cmd = r'ssh -o StrictHostKeyChecking=no -i C:\Users\mpetr\.ssh\id_rsa root@68.183.30.128 "systemctl restart erp-backend erp-auth"'
        self.run_subprocess_and_log(ssh_cmd)
        
        self.log_message("=== BACKEND MATRIX DEPLOYMENT CYCLE COMPLETE ===")
        self.after(0, lambda: self.btn_backend.configure(state="normal"))

    def deploy_backend(self):
        self.btn_backend.configure(state="disabled")
        threading.Thread(target=self.deploy_backend_task, daemon=True).start()

if __name__ == "__main__":
    app = OrbitalCommander()
    app.mainloop()
