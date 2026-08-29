#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#ifndef SourceDir
  #error SourceDir must point to the portable ErgonoMouse-Setup directory
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

[Setup]
AppId={{D6A6C5D2-7E13-4CA7-B677-E215664B8D19}
AppName=ErgonoMouse Setup
AppVersion={#AppVersion}
AppPublisher=ErgonoMouse
DefaultDirName={localappdata}\Programs\ErgonoMouse Setup
DefaultGroupName=ErgonoMouse Setup
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=ErgonoMouse-Setup-{#AppVersion}-windows-x86_64-setup
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\ErgonoMouse-Setup.exe
WizardStyle=modern
LicenseFile={#SourceDir}\LICENSE
InfoBeforeFile={#SourceDir}\UNSIGNED_INSTALL.txt

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\ErgonoMouse Setup"; Filename: "{app}\ErgonoMouse-Setup.exe"
Name: "{autodesktop}\ErgonoMouse Setup"; Filename: "{app}\ErgonoMouse-Setup.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\ErgonoMouse-Setup.exe"; Description: "Open ErgonoMouse Setup"; Flags: nowait postinstall skipifsilent
