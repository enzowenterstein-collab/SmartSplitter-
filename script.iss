; Script d'installation SmartSplitter - Version Finale V1.0 (Corrigé)
; Configuration : Enzo | Mode : CPU Portable

[Setup]
; --- IDENTITÉ ---
AppName=SmartSplitter
AppVersion=1.0
AppPublisher=Enzo

; --- FICHIER DE SORTIE ---
; Nom de l'installateur créé
OutputBaseFilename=Setup_SmartSplitter

; --- INSTALLATION ---
; Installation dans "Program Files"
DefaultDirName={autopf}\SmartSplitter
; Droits admin requis
PrivilegesRequired=admin
; Pas de choix de dossier (plus simple)
DisableDirPage=no
; Nom du groupe Menu Démarrer
DefaultGroupName=SmartSplitter

; --- PERFORMANCE & LOOK ---
Compression=lzma2/ultra64
SolidCompression=yes
; Icône de désinstallation
UninstallDisplayIcon={app}\SmartSplitter.exe
WizardStyle=modern

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
; Case pour l'icône Bureau
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; --- LE PROGRAMME ---
; On pointe directement vers le fichier SmartSplitter.exe
Source: "SmartSplitter.exe"; DestDir: "{app}"; Flags: ignoreversion

; --- LES MODÈLES IA ---
Source: "models\*"; DestDir: "{app}\models"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 1. Raccourci Menu Démarrer
Name: "{group}\SmartSplitter"; Filename: "{app}\SmartSplitter.exe"
; 2. Raccourci Bureau
Name: "{autodesktop}\SmartSplitter"; Filename: "{app}\SmartSplitter.exe"; Tasks: desktopicon

[Run]
; Lancer l'application après l'installation
Filename: "{app}\SmartSplitter.exe"; Description: "{cm:LaunchProgram,SmartSplitter}"; Flags: nowait postinstall skipifsilent