import customtkinter as ctk
import subprocess
import threading
import os
import sys
import psutil
import time
import shutil
import webbrowser
import socket
import qrcode
from PIL import Image, ImageTk
from datetime import datetime
import io

# --- CONFIGURAZIONE ---
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")  # Base theme, will be overridden

# Colori Brand
COLOR_PRIMARY = "#FF006E"
COLOR_PRIMARY_HOVER = "#D6005C"
COLOR_BG = "#F5F5F7"
COLOR_WHITE = "#FFFFFF"
COLOR_TEXT = "#333333"
COLOR_SUCCESS = "#2ECC71"
COLOR_DANGER = "#E74C3C"

class ByteBiteLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Byte-Bite Launcher")
        self.geometry("1000x700")
        self.configure(fg_color=COLOR_BG)

        # Stato del Server
        self.server_process = None
        self.is_running = False
        self.log_queue = []

        # Layout Principale
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.create_sidebar()
        self.create_frames()
        self.show_dashboard()

        # Avvio thread monitoraggio
        self.monitoring = True
        threading.Thread(target=self.monitor_system, daemon=True).start()
        
        # Avvio loop controllo log
        self.check_log_queue()

    def create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=COLOR_WHITE)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        # Logo / Titolo
        self.logo_label = ctk.CTkLabel(
            self.sidebar, 
            text="Byte-Bite", 
            font=ctk.CTkFont(family="Inter", size=24, weight="bold"),
            text_color=COLOR_PRIMARY
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar, 
            text="Launcher Manager", 
            font=ctk.CTkFont(family="Inter", size=12),
            text_color="gray"
        )
        self.subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 20))

        # Pulsanti Navigazione
        self.btn_dashboard = ctk.CTkButton(
            self.sidebar, 
            text="Dashboard", 
            command=self.show_dashboard,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            font=ctk.CTkFont(family="Inter", size=14)
        )
        self.btn_dashboard.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.btn_tools = ctk.CTkButton(
            self.sidebar, 
            text="Strumenti Avanzati", 
            command=self.show_tools,
            fg_color="transparent",
            text_color=COLOR_TEXT,
            hover_color="#EEEEEE",
            font=ctk.CTkFont(family="Inter", size=14)
        )
        self.btn_tools.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        # Footer
        self.footer_label = ctk.CTkLabel(self.sidebar, text="v1.0.0", text_color="gray")
        self.footer_label.grid(row=5, column=0, padx=20, pady=20)

    def create_frames(self):
        # Container per le pagine
        self.container = ctk.CTkFrame(self, fg_color=COLOR_BG)
        self.container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        # Frame Dashboard
        self.dashboard_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.dashboard_frame.grid_columnconfigure(0, weight=1)
        self.dashboard_frame.grid_columnconfigure(1, weight=1)

        # Frame Tools
        self.tools_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.tools_frame.grid_columnconfigure(0, weight=1)

        self.setup_dashboard()
        self.setup_tools()

    def setup_dashboard(self):
        # --- Stato Server ---
        self.status_frame = ctk.CTkFrame(self.dashboard_frame, fg_color=COLOR_WHITE, corner_radius=10)
        self.status_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 20), ipady=10)
        
        self.lbl_status = ctk.CTkLabel(
            self.status_frame, 
            text="Status: OFFLINE", 
            text_color="gray",
            font=ctk.CTkFont(family="Inter", size=16, weight="bold")
        )
        self.lbl_status.pack(side="left", padx=20)

        self.btn_toggle_server = ctk.CTkButton(
            self.status_frame,
            text="AVVIA SERVER",
            command=self.toggle_server,
            fg_color=COLOR_SUCCESS,
            hover_color="#27AE60",
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
            width=150
        )
        self.btn_toggle_server.pack(side="right", padx=20)

        self.btn_open_browser = ctk.CTkButton(
            self.status_frame,
            text="Apri Browser",
            command=self.open_browser,
            fg_color="#3498DB",
            hover_color="#2980B9",
            state="disabled"
        )
        self.btn_open_browser.pack(side="right", padx=(0, 10))

        # --- Monitoraggio ---
        self.monitor_frame = ctk.CTkFrame(self.dashboard_frame, fg_color=COLOR_WHITE, corner_radius=10)
        self.monitor_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(0, 20))
        self.monitor_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.monitor_frame, text="Monitoraggio Sistema", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=10, padx=10, sticky="w")

        ctk.CTkLabel(self.monitor_frame, text="CPU").grid(row=1, column=0, padx=10, pady=5)
        self.cpu_bar = ctk.CTkProgressBar(self.monitor_frame, progress_color=COLOR_PRIMARY)
        self.cpu_bar.set(0)
        self.cpu_bar.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(self.monitor_frame, text="RAM").grid(row=2, column=0, padx=10, pady=5)
        self.ram_bar = ctk.CTkProgressBar(self.monitor_frame, progress_color=COLOR_PRIMARY)
        self.ram_bar.set(0)
        self.ram_bar.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        # --- Console Log ---
        self.log_frame = ctk.CTkFrame(self.dashboard_frame, fg_color=COLOR_WHITE, corner_radius=10)
        self.log_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.log_frame.grid_rowconfigure(1, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.log_frame, text="Console Log", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=10, padx=10, sticky="w")
        
        self.log_box = ctk.CTkTextbox(self.log_frame, font=("Consolas", 12), activate_scrollbars=True)
        self.log_box.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.log_box.configure(state="disabled")

    def setup_tools(self):
        # --- Backup ---
        self.backup_frame = ctk.CTkFrame(self.tools_frame, fg_color=COLOR_WHITE, corner_radius=10)
        self.backup_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(self.backup_frame, text="Database Backup", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        ctk.CTkButton(
            self.backup_frame, 
            text="Esegui Backup Ora", 
            command=self.backup_database,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER
        ).pack(pady=(0, 20))

        # --- QR Code ---
        self.qr_frame = ctk.CTkFrame(self.tools_frame, fg_color=COLOR_WHITE, corner_radius=10)
        self.qr_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(self.qr_frame, text="Connessione Dispositivi (QR Code)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        # Tabs per QR Code (Wi-Fi / App)
        self.qr_tabs = ctk.CTkTabview(self.qr_frame, width=400, height=350)
        self.qr_tabs.pack(pady=10, padx=10)
        
        # Tab 1: App Link
        self.tab_app = self.qr_tabs.add("Link App")
        self.qr_image_label = ctk.CTkLabel(self.tab_app, text="")
        self.qr_image_label.pack(pady=10)
        self.qr_info_label = ctk.CTkLabel(self.tab_app, text="Avvia il server per generare il QR", text_color="gray")
        self.qr_info_label.pack(pady=(0, 20))

        # Tab 2: Wi-Fi Login
        self.tab_wifi = self.qr_tabs.add("Wi-Fi Login")
        
        ctk.CTkLabel(self.tab_wifi, text="Genera QR per accesso rapido al Wi-Fi").pack(pady=5)
        
        self.wifi_ssid_entry = ctk.CTkEntry(self.tab_wifi, placeholder_text="Nome Rete (SSID)")
        self.wifi_ssid_entry.pack(pady=5, fill="x", padx=20)
        
        self.wifi_pass_entry = ctk.CTkEntry(self.tab_wifi, placeholder_text="Password", show="*")
        self.wifi_pass_entry.pack(pady=5, fill="x", padx=20)
        
        ctk.CTkButton(self.tab_wifi, text="Genera QR Wi-Fi", command=self.generate_wifi_qr, fg_color=COLOR_PRIMARY).pack(pady=10)
        
        self.wifi_qr_label = ctk.CTkLabel(self.tab_wifi, text="")
        self.wifi_qr_label.pack(pady=10)

        # --- Git Update ---
        self.git_frame = ctk.CTkFrame(self.tools_frame, fg_color=COLOR_WHITE, corner_radius=10)
        self.git_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(self.git_frame, text="Aggiornamenti", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        ctk.CTkButton(
            self.git_frame, 
            text="Scarica Aggiornamenti (git pull)", 
            command=self.git_pull,
            fg_color="#333", 
            hover_color="#000"
        ).pack(pady=(0, 20))

    # --- NAVIGAZIONE ---
    def show_dashboard(self):
        self.tools_frame.grid_forget()
        self.dashboard_frame.grid(row=0, column=0, sticky="nsew")
        self.btn_dashboard.configure(fg_color=COLOR_PRIMARY, text_color="white")
        self.btn_tools.configure(fg_color="transparent", text_color=COLOR_TEXT)

    def show_tools(self):
        self.dashboard_frame.grid_forget()
        self.tools_frame.grid(row=0, column=0, sticky="nsew")
        self.btn_dashboard.configure(fg_color="transparent", text_color=COLOR_TEXT)
        self.btn_tools.configure(fg_color=COLOR_PRIMARY, text_color="white")
        
        if self.is_running:
            self.generate_qr()
        else:
             # Reset se il server è spento
            self.qr_image_label.configure(image=None, text="")
            self.qr_info_label.configure(text="Avvia il server per generare il QR")

    # --- LOGICA SERVER ---
    def toggle_server(self):
        if self.is_running:
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
        if self.server_process is not None:
            return

        self.log("Avvio server in corso...", "INFO")
        try:
            # Esegue app.py con python corrente
            # Usa -u per unbuffered stdout
            cmd = [sys.executable, "-u", "app.py"]
            self.server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=os.getcwd()
            )
            
            self.is_running = True
            self.update_ui_state(running=True)
            
            # Thread lettura log
            self.log_thread = threading.Thread(target=self.read_server_output, daemon=True)
            self.log_thread.start()
            
            # Genera QR se siamo nel tab tools
            if self.tools_frame.winfo_viewable():
                self.generate_qr()

        except Exception as e:
            self.log(f"Errore avvio server: {e}", "ERROR")
            self.stop_server()

    def stop_server(self):
        if self.server_process:
            self.log("Arresto server...", "INFO")
            # Terminazione gentile
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            
            self.server_process = None
            self.is_running = False
            self.update_ui_state(running=False)
            self.log("Server arrestato.", "INFO")

    def update_ui_state(self, running):
        if running:
            self.lbl_status.configure(text="Status: ONLINE", text_color=COLOR_SUCCESS)
            self.btn_toggle_server.configure(text="FERMA SERVER", fg_color=COLOR_DANGER, hover_color="#C0392B")
            self.btn_open_browser.configure(state="normal")
        else:
            self.lbl_status.configure(text="Status: OFFLINE", text_color="gray")
            self.btn_toggle_server.configure(text="AVVIA SERVER", fg_color=COLOR_SUCCESS, hover_color="#27AE60")
            self.btn_open_browser.configure(state="disabled")

    def read_server_output(self):
        while self.is_running and self.server_process:
            line = self.server_process.stdout.readline()
            if not line:
                break
            self.log_queue.append(line)
        
        # Se esce dal loop, il processo è morto
        if self.is_running:
            self.after(0, lambda: self.stop_server())

    def check_log_queue(self):
        while self.log_queue:
            msg = self.log_queue.pop(0)
            self.append_log(msg)
        self.after(100, self.check_log_queue)

    def append_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.append_log(f"[{timestamp}] [{level}] {message}\n")

    def open_browser(self):
        # Cerca di indovinare l'IP locale come fa Flask
        ip = self.get_local_ip()
        webbrowser.open(f"http://{ip}:8000")

    # --- STRUMENTI ---
    def monitor_system(self):
        while self.monitoring:
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            
            # Aggiorna UI nel main thread
            self.after(0, lambda c=cpu, r=ram: self.update_bars(c, r))

    def update_bars(self, cpu, ram):
        self.cpu_bar.set(cpu / 100)
        self.ram_bar.set(ram / 100)

    def backup_database(self):
        db_file = "db.sqlite3"
        backup_dir = "backups"
        
        if not os.path.exists(db_file):
            self.log("Database non trovato!", "ERROR")
            return

        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"db_backup_{timestamp}.sqlite3")
        
        try:
            shutil.copy2(db_file, backup_file)
            self.log(f"Backup completato: {backup_file}", "SUCCESS")
        except Exception as e:
            self.log(f"Errore backup: {e}", "ERROR")

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def generate_qr(self):
        try:
            ip = self.get_local_ip()
            url = f"http://{ip}:8000"
            
            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill="black", back_color="white")
            
            # Fix per CustomTkinter: converte l'immagine QR in un oggetto PIL.Image standard
            # Salviamo in un buffer e ricarichiamo con PIL per essere sicuri del tipo
            buffer = io.BytesIO()
            qr_img.save(buffer, format="PNG")
            buffer.seek(0)
            img = Image.open(buffer)
            
            # Converti per CTk
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(200, 200))
            self.qr_image_ref = ctk_img # Mantieni riferimento
            
            self.qr_image_label.configure(image=ctk_img, text="")
            self.qr_info_label.configure(text=f"Scansiona per connetterti a:\n{url}")
        except Exception as e:
            self.log(f"Errore generazione QR: {e}", "ERROR")
            self.qr_info_label.configure(text=f"Errore QR: {e}")

    def generate_wifi_qr(self):
        ssid = self.wifi_ssid_entry.get()
        password = self.wifi_pass_entry.get()
        
        if not ssid:
            return

        # Formato WIFI:S:SSID;T:WPA;P:PASSWORD;;
        wifi_data = f"WIFI:S:{ssid};T:WPA;P:{password};;"
        
        try:
            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(wifi_data)
            qr.make(fit=True)
            qr_img = qr.make_image(fill="black", back_color="white")
            
            buffer = io.BytesIO()
            qr_img.save(buffer, format="PNG")
            buffer.seek(0)
            img = Image.open(buffer)
            
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(200, 200))
            self.wifi_qr_ref = ctk_img
            self.wifi_qr_label.configure(image=ctk_img, text="")
        except Exception as e:
            self.log(f"Errore QR Wi-Fi: {e}", "ERROR")

    def git_pull(self):
        self.log("Esecuzione git pull...", "INFO")
        try:
            result = subprocess.run(["git", "pull"], capture_output=True, text=True)
            if result.returncode == 0:
                self.log(f"Git Pull: {result.stdout}", "SUCCESS")
            else:
                self.log(f"Git Error: {result.stderr}", "ERROR")
        except FileNotFoundError:
            self.log("Git non trovato nel sistema.", "ERROR")
        except Exception as e:
            self.log(f"Errore git: {e}", "ERROR")

    def on_close(self):
        self.stop_server()
        self.monitoring = False
        self.destroy()

if __name__ == "__main__":
    app = ByteBiteLauncher()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
