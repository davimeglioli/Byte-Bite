import customtkinter as ctk
import subprocess
import threading
import webbrowser
import os
import sys
import queue
import time
import signal
import psutil
import shutil
import socket
import qrcode
from datetime import datetime
from PIL import Image, ImageTk

# ==================== Configurazione ====================

# Colori definiti in base al file style.css del progetto.
ACCENT_COLOR = "#FF006E"
HEADER_COLOR = "#000000"
BG_COLOR = "#FFFFFF"
TEXT_COLOR_HEADER = "#FFFFFF"
SIDEBAR_COLOR = "#FFFFFF"
CARD_COLOR = "#FFFFFF"

# Imposta il tema chiaro per customtkinter.
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

class ByteBiteLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configurazione base della finestra principale.
        self.title("Byte-Bite Launcher")
        self.geometry("1000x700")
        self.resizable(True, True)
        
        # Gestione dell'icona finestra per Windows e macOS/Linux.
        try:
            base_path = os.path.dirname(os.path.realpath(__file__))
            if os.name == 'nt':
                 # Su Windows si usa il file .ico.
                 icon_path = os.path.join(base_path, "static", "favicon.ico")
                 self.iconbitmap(icon_path)
            else:
                 # Su macOS e Linux si usa iconphoto con PNG.
                 icon_path = os.path.join(base_path, "static", "logo.png")
                 img = Image.open(icon_path)
                 self.iconphoto(True, ImageTk.PhotoImage(img))
        except Exception as e:
            print(f"Errore impostazione icona: {e}")
        
        # Definizione dei font utilizzati nell'interfaccia.
        self.font_title = ("Inter", 24, "bold")
        self.font_header = ("Inter", 18, "bold")
        self.font_body = ("Inter", 14)
        self.font_console = ("Consolas", 12)

        # Variabili di stato per il processo del server.
        self.process = None
        self.server_running = False
        self.log_queue = queue.Queue()

        # Inizializza l'interfaccia e il controllo dei log.
        self._init_ui()
        self._check_queue()

        # Gestisce la chiusura della finestra per terminare i processi.
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _init_ui(self):
        # Configura il grid layout principale (1 colonna, 2 righe).
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ==================== Header ====================
        
        # Frame dell'header nero in alto (altezza fissa 80px).
        self.header_frame = ctk.CTkFrame(self, fg_color=HEADER_COLOR, corner_radius=0, height=80)
        self.header_frame.grid(row=0, column=0, sticky="nsew")
        self.header_frame.grid_propagate(False)

        # Linea di bordo rosa posizionata in basso nell'header.
        self.header_border = ctk.CTkFrame(self.header_frame, fg_color=ACCENT_COLOR, corner_radius=0, height=2)
        self.header_border.place(relx=0, rely=1.0, anchor="sw", relwidth=1.0, y=0)

        # Layout interno dell'header per posizionare gli elementi.
        self.header_frame.grid_columnconfigure(1, weight=1)

        # Contenitore per il logo e il titolo a sinistra.
        self.branding_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.branding_frame.grid(row=0, column=0, padx=20, sticky="w", pady=20)
        
        # Caricamento e ridimensionamento del logo mantenendo l'aspect ratio.
        try:
            image_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "static", "logo.png")
            pil_image = Image.open(image_path)
            
            # Calcola le nuove dimensioni basate sull'altezza di 40px.
            target_height = 40
            aspect_ratio = pil_image.width / pil_image.height
            target_width = int(target_height * aspect_ratio)
            
            self.logo_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(target_width, target_height))
            
            # Mostra il logo nell'interfaccia.
            self.logo_label = ctk.CTkLabel(self.branding_frame, text="", image=self.logo_image)
            self.logo_label.pack(side="left", padx=(0, 20))
        except Exception as e:
            print(f"Errore caricamento logo: {e}")

        # Etichetta del titolo accanto al logo.
        self.title_label = ctk.CTkLabel(
            self.branding_frame, 
            text="Byte-Bite Launcher", 
            font=self.font_title,
            text_color=TEXT_COLOR_HEADER
        )
        self.title_label.pack(side="left")

        # Indicatore di stato (Online/Offline) a destra.
        self.status_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.status_frame.grid(row=0, column=2, padx=20, sticky="e", pady=20)
        
        # Punto colorato indicatore di stato.
        self.status_dot = ctk.CTkLabel(
            self.status_frame,
            text="●",
            font=("Inter", 24),
            text_color="gray",
        )
        self.status_dot.pack(side="left", padx=(0, 5))
        
        # Testo dello stato corrente.
        self.status_text = ctk.CTkLabel(
            self.status_frame,
            text="OFFLINE",
            font=("Inter", 14, "bold"),
            text_color="gray"
        )
        self.status_text.pack(side="left")

        # ==================== Main Content ====================

        # Area principale che contiene i controlli e la console.
        self.main_area = ctk.CTkFrame(self, fg_color=BG_COLOR, corner_radius=0)
        self.main_area.grid(row=1, column=0, sticky="nsew")
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(1, weight=1)
        
        # Container interno per gestire il padding.
        self.content_container = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.content_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(1, weight=3)
        self.content_container.grid_rowconfigure(0, weight=1)

        # Card di sinistra: Pannello di Controllo.
        self.controls_card = ctk.CTkFrame(
            self.content_container, 
            fg_color="white", 
            corner_radius=30,
            border_width=1,
            border_color="#E0E0E0"
        )
        self.controls_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
        
        # Titolo della sezione controlli.
        self.controls_label = ctk.CTkLabel(
            self.controls_card, 
            text="Pannello di Controllo", 
            font=self.font_header,
            text_color="black"
        )
        self.controls_label.pack(anchor="w", padx=25, pady=(25, 20))

        # Pulsante per avviare il server Flask.
        self.btn_start = ctk.CTkButton(
            self.controls_card,
            text="Start Server",
            command=self.start_server,
            fg_color=ACCENT_COLOR,
            hover_color="#D0005A",
            font=self.font_body,
            height=50,
            corner_radius=25, 
            width=200
        )
        self.btn_start.pack(pady=10, padx=20, fill="x")

        # Pulsante per arrestare il server.
        self.btn_stop = ctk.CTkButton(
            self.controls_card,
            text="Stop Server",
            command=self.stop_server,
            fg_color="gray",
            state="disabled",
            font=self.font_body,
            height=50,
            corner_radius=25,
            width=200
        )
        self.btn_stop.pack(pady=10, padx=20, fill="x")
        
        # Spaziatore visivo.
        ctk.CTkLabel(self.controls_card, text="").pack(pady=10)

        # Pulsante per aprire il browser.
        self.btn_browser = ctk.CTkButton(
            self.controls_card,
            text="Apri nel Browser",
            command=self.open_browser,
            fg_color="white",
            border_width=2,
            border_color="#333333",
            text_color="#333333",
            hover_color="#F0F0F0",
            font=self.font_body,
            height=50,
            corner_radius=25,
            width=200
        )
        self.btn_browser.pack(pady=10, padx=20, fill="x")

        # Pulsante per Backup DB.
        self.btn_backup = ctk.CTkButton(
            self.controls_card,
            text="Backup Database",
            command=self.backup_db,
            fg_color="white",
            border_width=2,
            border_color="#333333",
            text_color="#333333",
            hover_color="#F0F0F0",
            font=self.font_body,
            height=50,
            corner_radius=25,
            width=200
        )
        self.btn_backup.pack(pady=10, padx=20, fill="x")

        # Pulsante per Mostra QR Code.
        self.btn_qrcode = ctk.CTkButton(
            self.controls_card,
            text="Mostra QR Code",
            command=self.show_qr_code,
            fg_color="white",
            border_width=2,
            border_color="#333333",
            text_color="#333333",
            hover_color="#F0F0F0",
            font=self.font_body,
            height=50,
            corner_radius=25,
            width=200
        )
        self.btn_qrcode.pack(pady=10, padx=20, fill="x")

        # Card di destra: Console Log.
        self.console_card = ctk.CTkFrame(
            self.content_container, 
            fg_color="white", 
            corner_radius=30,
            border_width=1,
            border_color="#E0E0E0"
        )
        self.console_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)
        self.console_card.grid_columnconfigure(0, weight=1)
        self.console_card.grid_rowconfigure(1, weight=1)

        # Titolo della sezione console.
        self.console_header = ctk.CTkLabel(
            self.console_card, 
            text="Console Log", 
            font=self.font_header,
            text_color="black"
        )
        self.console_header.grid(row=0, column=0, sticky="w", padx=25, pady=(25, 10))

        # Textbox scorrevole per i log.
        self.console_box = ctk.CTkTextbox(
            self.console_card,
            font=self.font_console,
            text_color="#E0E0E0",
            fg_color="#1E1E1E",
            corner_radius=15,
            activate_scrollbars=True
        )
        self.console_box.grid(row=1, column=0, sticky="nsew", padx=25, pady=(0, 25))
        self.console_box.configure(state="disabled")

    def start_server(self):
        # Avvia il processo del server se non è già in esecuzione.
        if self.server_running:
            return

        self.log(">>> Avvio del server in corso...")
        
        # Identifica l'interprete Python corrente.
        python_exe = sys.executable
        
        try:
            # Lancia app.py come sottoprocesso, catturando stdout/stderr.
            # L'argomento -u forza l'output non bufferizzato per log in tempo reale.
            self.process = subprocess.Popen(
                [python_exe, "-u", "app.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                # Evita la creazione di una finestra console su Windows.
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Aggiorna lo stato dell'interfaccia.
            self.server_running = True
            self.update_ui_state(running=True)
            
            # Avvia un thread separato per leggere l'output senza bloccare la GUI.
            self.read_thread = threading.Thread(target=self._read_output, daemon=True)
            self.read_thread.start()
            
        except Exception as e:
            self.log(f"!!! Errore durante l'avvio: {e}")
            self.server_running = False

    def stop_server(self):
        # Ferma il server e tutti i processi figli.
        if not self.server_running or not self.process:
            return

        self.log(">>> Arresto del server in corso...")
        
        try:
            # Usa psutil per terminare l'intero albero dei processi.
            parent = psutil.Process(self.process.pid)
            children = parent.children(recursive=True)
            for child in children:
                child.terminate()
            parent.terminate()
            
            # Attende la terminazione dei processi.
            gone, alive = psutil.wait_procs(children + [parent], timeout=3)
            for p in alive:
                p.kill()
                
            self.process = None
            self.server_running = False
            self.update_ui_state(running=False)
            self.log(">>> Server arrestato.")
        except Exception as e:
            self.log(f"!!! Errore durante l'arresto: {e}")

    def open_browser(self):
        # Apre l'URL locale nel browser predefinito.
        webbrowser.open("http://localhost:8000")

    def backup_db(self):
        # Crea una copia di backup del database con timestamp.
        db_file = "db.sqlite3"
        if not os.path.exists(db_file):
            self.log("!!! Database non trovato: db.sqlite3")
            return

        # Crea la cartella backups se non esiste.
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # Genera il nome del file con data e ora corrente.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"db_backup_{timestamp}.sqlite3"
        backup_path = os.path.join(backup_dir, backup_filename)

        try:
            # Copia il file.
            shutil.copy2(db_file, backup_path)
            self.log(f">>> Backup creato con successo: {backup_path}")
        except Exception as e:
            self.log(f"!!! Errore durante il backup: {e}")

    def show_qr_code(self):
        # Genera e mostra un QR code con l'indirizzo IP locale.
        try:
            # Ottiene l'indirizzo IP locale della macchina.
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except Exception:
            ip_address = "127.0.0.1"

        url = f"http://{ip_address}:8000"
        self.log(f">>> Generazione QR Code per: {url}")

        # Genera il QR Code.
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        # Crea immagine PilImage e convertila esplicitamente in PIL.Image.Image.
        qr_pil = qr.make_image(fill_color="black", back_color="white").get_image()
        
        # Mostra il QR Code in una finestra popup (Toplevel).
        qr_window = ctk.CTkToplevel(self)
        qr_window.title("QR Code Accesso Mobile")
        qr_window.geometry("400x450")
        qr_window.resizable(False, False)
        
        # Assicura che la finestra sia in primo piano.
        qr_window.attributes("-topmost", True)

        # Titolo nel popup.
        label_title = ctk.CTkLabel(qr_window, text="Scansiona per accedere", font=("Inter", 18, "bold"))
        label_title.pack(pady=(20, 10))
        
        # Converti immagine per CTk usando l'oggetto PIL convertito.
        tk_img = ctk.CTkImage(light_image=qr_pil, dark_image=qr_pil, size=(300, 300))
        label_img = ctk.CTkLabel(qr_window, text="", image=tk_img)
        label_img.pack(pady=10)

        # Mostra l'URL testuale sotto.
        label_url = ctk.CTkLabel(qr_window, text=url, font=("Consolas", 14))
        label_url.pack(pady=(0, 20))

    def update_ui_state(self, running):
        # Aggiorna i pulsanti e l'indicatore di stato in base allo stato del server.
        if running:
            self.btn_start.configure(state="disabled", fg_color="#E0E0E0", text_color="gray")
            self.btn_stop.configure(state="normal", fg_color=ACCENT_COLOR, hover_color="#D0005A", text_color="white")
            self.status_text.configure(text="ONLINE", text_color="#00D000")
            self.status_dot.configure(text_color="#00D000")
        else:
            self.btn_start.configure(state="normal", fg_color=ACCENT_COLOR, hover_color="#D0005A", text_color="white")
            self.btn_stop.configure(state="disabled", fg_color="#E0E0E0", text_color="gray")
            self.status_text.configure(text="OFFLINE", text_color="gray")
            self.status_dot.configure(text_color="gray")

    def _read_output(self):
        # Legge l'output del processo riga per riga e lo mette in coda.
        if not self.process:
            return
            
        for line in iter(self.process.stdout.readline, ''):
            if line:
                self.log_queue.put(line)
        
        # Gestisce la fine del processo.
        if self.process:
            self.process.stdout.close()
            return_code = self.process.wait()
            if self.server_running: 
                # Se il server era marcato come running ma è terminato, notifica l'errore.
                self.log_queue.put(f"\n[Processo terminato con codice {return_code}]\n")
                self.after(0, lambda: self.update_ui_state(False))
                self.server_running = False

    def _check_queue(self):
        # Controlla periodicamente la coda per nuovi messaggi da stampare.
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log(msg, append=True)
        
        # Ripianifica il controllo tra 100ms.
        self.after(100, self._check_queue)

    def log(self, message, append=False):
        # Aggiunge un messaggio alla console box.
        self.console_box.configure(state="normal")
        if not append:
            message = message + "\n"
        self.console_box.insert("end", message)
        self.console_box.see("end")
        self.console_box.configure(state="disabled")

    def on_closing(self):
        # Gestisce la chiusura pulita dell'applicazione.
        if self.server_running:
            self.stop_server()
        self.destroy()

if __name__ == "__main__":
    app = ByteBiteLauncher()
    app.mainloop()
