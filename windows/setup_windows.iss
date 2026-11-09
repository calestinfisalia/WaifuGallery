#define AppName "Waifu Gallery"
#ifndef AppVersion
  #define AppVersion "0.1.6"
#endif
#ifndef WindowsDistDir
  #define WindowsDistDir "dist\Waifu Gallery"
#endif
#ifndef OutputDir
  #define OutputDir "dist-release"
#endif

[Setup]
AppId={{92DCD184-6B4A-4B3E-B461-7A6E91F1B0D5}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Fisalia Cantarella
DefaultDirName={localappdata}\Programs\Waifu Gallery
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
UninstallDisplayIcon={app}\Waifu Gallery.exe
SetupIconFile=waifu_gallery\assets\waifugallery.ico
OutputDir={#OutputDir}
OutputBaseFilename=WaifuGallery-Setup-x64
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
CloseApplications=yes
CloseApplicationsFilter=Waifu Gallery.exe
RestartApplications=no
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
Uninstallable=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#WindowsDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\Waifu Gallery.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Waifu Gallery.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Waifu Gallery.exe"; Description: "Launch Waifu Gallery"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ExistingVersion: String;
  UninstallKey: String;
begin
  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{92DCD184-6B4A-4B3E-B461-7A6E91F1B0D5}_is1';
  if RegQueryStringValue(HKCU, UninstallKey, 'DisplayVersion', ExistingVersion) then
  begin
    Result := MsgBox(
      'Waifu Gallery ' + ExistingVersion + ' is already installed.' + #13#10 + #13#10 +
      'Continue to update the existing installation? App settings and downloaded files will be kept.',
      mbConfirmation, MB_YESNO) = IDYES;
  end
  else
    Result := True;
end;
