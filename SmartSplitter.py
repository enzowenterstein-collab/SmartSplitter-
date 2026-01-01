import wx
import os
import sys
import threading
import re
import winsound
import json
import logging
import urllib.request
import webbrowser
from audio_separator.separator import Separator 
from multiprocessing import freeze_support

# --- CONFIGURATION ---
APP_NAME = "SmartSplitter"
VERSION = "1.0"
UPDATE_URL = "https://raw.githubusercontent.com/Enzo-SmartSplitter/SmartSplitter/main/version.txt"
RELEASE_PAGE = "https://github.com/Enzo-SmartSplitter/SmartSplitter/releases"

MODELS_PRESETS = {
    "1. ULTRA INSTRUMENTAL (MDX23C)": "MDX23C-8KFFT-InstVoc_HQ.ckpt",
    "2. Top Qualité VOIX (BS-Roformer)": "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
    "3. Top Qualité DÉTAILS (Mel-Band)": "model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt",
    "4. Top Qualité INSTRUMENTAL (UVR-MDX)": "UVR-MDX-NET-Inst_HQ_3.onnx",
    "5. Standard Rapide (Kim Vocal 2)": "Kim_Vocal_2.onnx",
    "6. --- AUTRE (Manuel) ---": "MANUAL_INPUT"
}

OUTPUT_MODES = {
    "Tout garder": None,
    "Juste la VOIX": "vocals",
    "Juste la MUSIQUE": "instrumental"
}

AVAILABLE_FORMATS = ["WAV", "MP3", "FLAC", "M4A"]
AUDIO_EXT = ('.mp3', '.wav', '.flac', '.m4a', '.ogg')

# --- GESTION INTELLIGENTE DES CHEMINS (CORRECTIF V19) ---
def get_base_path():
    """Trouve le dossier d'installation (pour lire les modèles)"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_app_data_path():
    """Trouve le dossier AppData (pour ECRIRE les réglages sans erreur)"""
    app_data = os.getenv('APPDATA') # C:\Users\Nom\AppData\Roaming
    my_folder = os.path.join(app_data, APP_NAME)
    if not os.path.exists(my_folder):
        os.makedirs(my_folder)
    return os.path.join(my_folder, "settings.json")

# --- CLASSE DE REDIRECTION (Pour la barre de progression) ---
class RedirectText(object):
    def __init__(self, frame):
        self.frame = frame

    def write(self, string):
        # On capture les pourcentages venant de la console
        try:
            match = re.search(r'(\d+)%', string)
            if match:
                percent = int(match.group(1))
                wx.CallAfter(self.frame.update_progress, percent)
        except: pass
        
        # On loggue aussi les erreurs importantes
        if "error" in string.lower() or "warning" in string.lower():
             wx.CallAfter(self.frame.log_area.AppendText, string)

    def flush(self): pass

class AudioSeparatorFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title=f"{APP_NAME} v{VERSION}", size=(750, 700))
        
        # Initialisation des chemins
        self.config_file = get_app_data_path()
        self.models_dir = os.path.join(get_base_path(), "models")
        
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # --- ONGLETS ---
        self.notebook = wx.Notebook(panel)
        self.tab_extract = wx.Panel(self.notebook)
        self.tab_options = wx.Panel(self.notebook)
        self.tab_logs = wx.Panel(self.notebook)
        
        self.notebook.AddPage(self.tab_extract, "1. Extraction")
        self.notebook.AddPage(self.tab_options, "2. Options")
        self.notebook.AddPage(self.tab_logs, "3. Journal")
        
        self.build_tab_extract()
        self.build_tab_options()
        self.build_tab_logs()
        
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

        # --- BARRE DE PROGRESSION ---
        prog_sizer = wx.StaticBoxSizer(wx.VERTICAL, panel, "État")
        self.gauge_label = wx.StaticText(panel, label="En attente...")
        prog_sizer.Add(self.gauge_label, 0, wx.ALL, 5)
        self.gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        prog_sizer.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(prog_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        self.Centre()
        self.load_settings()
        
        threading.Thread(target=self.check_update, daemon=True).start()

    def build_tab_extract(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self.tab_extract, label="Source :"), 0, wx.ALL, 10)
        self.radio_mode = wx.RadioBox(self.tab_extract, label="Mode", choices=["Fichier unique", "Dossier (Batch)"])
        self.radio_mode.Bind(wx.EVT_RADIOBOX, self.on_change_mode)
        sizer.Add(self.radio_mode, 0, wx.EXPAND | wx.ALL, 10)
        self.file_picker = wx.FilePickerCtrl(self.tab_extract, message="Choisir fichier", style=wx.FLP_USE_TEXTCTRL)
        sizer.Add(self.file_picker, 0, wx.EXPAND | wx.ALL, 10)
        self.dir_input_picker = wx.DirPickerCtrl(self.tab_extract, message="Choisir dossier source")
        sizer.Add(self.dir_input_picker, 0, wx.EXPAND | wx.ALL, 10)
        self.dir_input_picker.Hide()
        sizer.AddSpacer(20)
        self.btn_run = wx.Button(self.tab_extract, label="LANCER L'EXTRACTION")
        self.btn_run.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.btn_run.Bind(wx.EVT_BUTTON, self.on_run)
        sizer.Add(self.btn_run, 0, wx.EXPAND | wx.ALL, 20)
        self.tab_extract.SetSizer(sizer)

    def build_tab_options(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self.tab_options, label="Modèle IA :"), 0, wx.LEFT | wx.TOP, 10)
        self.model_choices = list(MODELS_PRESETS.keys())
        self.combo_model = wx.Choice(self.tab_options, choices=self.model_choices)
        self.combo_model.SetSelection(0)
        self.combo_model.Bind(wx.EVT_CHOICE, self.on_model_change)
        sizer.Add(self.combo_model, 0, wx.EXPAND | wx.ALL, 10)
        self.lbl_manual = wx.StaticText(self.tab_options, label="Nom manuel :")
        self.txt_manual = wx.TextCtrl(self.tab_options)
        sizer.Add(self.lbl_manual, 0, wx.ALL, 5)
        sizer.Add(self.txt_manual, 0, wx.EXPAND | wx.ALL, 5)
        self.lbl_manual.Hide(); self.txt_manual.Hide()
        sizer.Add(wx.StaticText(self.tab_options, label="Format sortie :"), 0, wx.LEFT, 10)
        self.combo_format = wx.Choice(self.tab_options, choices=AVAILABLE_FORMATS)
        self.combo_format.SetSelection(0)
        sizer.Add(self.combo_format, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(wx.StaticText(self.tab_options, label="Garder :"), 0, wx.LEFT, 10)
        self.output_choices = list(OUTPUT_MODES.keys())
        self.combo_output = wx.Choice(self.tab_options, choices=self.output_choices)
        self.combo_output.SetSelection(0)
        sizer.Add(self.combo_output, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(wx.StaticText(self.tab_options, label="Destination :"), 0, wx.LEFT, 10)
        default_path = os.path.expanduser("~\\Music")
        self.dir_picker = wx.DirPickerCtrl(self.tab_options, path=default_path, style=wx.DIRP_USE_TEXTCTRL)
        sizer.Add(self.dir_picker, 0, wx.EXPAND | wx.ALL, 10)
        self.tab_options.SetSizer(sizer)

    def build_tab_logs(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.log_area = wx.TextCtrl(self.tab_logs, style=wx.TE_MULTILINE | wx.TE_READONLY)
        sizer.Add(self.log_area, 1, wx.EXPAND | wx.ALL, 5)
        self.tab_logs.SetSizer(sizer)

    def on_change_mode(self, event):
        is_batch = self.radio_mode.GetSelection() == 1
        self.file_picker.Show(not is_batch)
        self.dir_input_picker.Show(is_batch)
        self.tab_extract.Layout()

    def on_model_change(self, event):
        if "AUTRE" in self.model_choices[self.combo_model.GetSelection()]:
            self.lbl_manual.Show(); self.txt_manual.Show()
        else:
            self.lbl_manual.Hide(); self.txt_manual.Hide()
        self.tab_options.Layout()

    def update_progress(self, percent):
        self.gauge.SetValue(percent)
        self.gauge_label.SetLabel(f"Traitement en cours : {percent}%")
        self.SetTitle(f"{percent}% - {APP_NAME}")

    def load_settings(self):
        # On charge depuis AppData (qui est autorisé en lecture/écriture)
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    s = json.load(f)
                    self.dir_picker.SetPath(s.get('out', os.path.expanduser("~\\Music")))
                    fmt = s.get('format_idx', 0)
                    if fmt < len(AVAILABLE_FORMATS): self.combo_format.SetSelection(fmt)
            except: pass

    def check_update(self):
        try:
            with urllib.request.urlopen(UPDATE_URL) as response:
                latest_version = response.read().decode('utf-8').strip()
            if latest_version != VERSION:
                wx.CallAfter(self.propose_update, latest_version)
        except: pass

    def propose_update(self, new_version):
        dlg = wx.MessageDialog(self, f"Nouvelle version {new_version} disponible !\nTélécharger ?", "Mise à jour", wx.YES_NO | wx.ICON_INFORMATION)
        if dlg.ShowModal() == wx.ID_YES: webbrowser.open(RELEASE_PAGE)
        dlg.Destroy()

    def on_run(self, event):
        files = []
        if self.radio_mode.GetSelection() == 0:
            p = self.file_picker.GetPath().replace('"', '').strip()
            if p: files.append(p)
        else:
            d = self.dir_input_picker.GetPath().replace('"', '').strip()
            if d:
                for f in os.listdir(d):
                    if f.lower().endswith(AUDIO_EXT): files.append(os.path.join(d, f))
        
        if not files:
            wx.MessageBox("Aucun fichier trouvé.", "Erreur")
            return

        # SAUVEGARDE DES REGLAGES (CORRIGÉ : Dans AppData)
        try:
            with open(self.config_file, 'w') as f:
                json.dump({'out': self.dir_picker.GetPath(), 'format_idx': self.combo_format.GetSelection()}, f)
        except Exception as e:
            # Si ça échoue, on continue quand même sans sauver (pas de crash)
            print(f"Erreur sauvegarde config: {e}")

        self.btn_run.Disable()
        self.gauge.SetValue(0)
        self.log_area.Clear()
        
        # Vérification critique : les modèles sont-ils là ?
        if not os.path.exists(self.models_dir):
            wx.MessageBox(f"Dossier 'models' introuvable dans :\n{self.models_dir}\n\nL'installation est incomplète.", "Erreur Fatale")
            self.btn_run.Enable()
            return
            
        self.log_area.AppendText(f"Dossier modèles détecté : {self.models_dir}\n")
        
        thread = threading.Thread(target=self.process_thread, args=(files, self.models_dir))
        thread.start()

    def process_thread(self, files, models_dir):
        output_dir = self.dir_picker.GetPath()
        choice_index = self.combo_model.GetSelection()
        model_filename = MODELS_PRESETS[self.model_choices[choice_index]]
        if model_filename == "MANUAL_INPUT":
            model_filename = self.txt_manual.GetValue().strip()
        single_stem = OUTPUT_MODES[self.output_choices[self.combo_output.GetSelection()]]
        selected_format = AVAILABLE_FORMATS[self.combo_format.GetSelection()]

        redirector = RedirectText(self)
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        sys.stdout = redirector
        sys.stderr = redirector

        try:
            for i, f_path in enumerate(files):
                file_name = os.path.basename(f_path)
                wx.CallAfter(self.gauge_label.SetLabel, f"Traitement {i+1}/{len(files)} : {file_name}")
                print(f"--- Démarrage : {file_name} ---")
                
                separator = Separator(
                    log_level=logging.WARNING,
                    log_formatter=None,
                    model_file_dir=models_dir,
                    output_dir=output_dir,
                    output_format=selected_format
                )
                
                separator.load_model(model_filename=model_filename)
                separator.separate(f_path)
                
        except Exception as e:
            wx.CallAfter(self.on_error, str(e))
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

        wx.CallAfter(self.on_success, output_dir)

    def on_success(self, output_dir):
        self.gauge.SetValue(100)
        self.gauge_label.SetLabel("Terminé.")
        self.SetTitle(f"{APP_NAME} - Prêt")
        winsound.MessageBeep()
        self.btn_run.Enable()
        wx.MessageBox("Terminé !", "Succès")
        try: os.startfile(output_dir)
        except: pass

    def on_error(self, msg):
        self.btn_run.Enable()
        self.gauge_label.SetLabel("Erreur.")
        wx.MessageBox(f"Erreur : {msg}", "Erreur")

if __name__ == '__main__':
    freeze_support()
    app = wx.App()
    frame = AudioSeparatorFrame()
    frame.Show()
    app.MainLoop()