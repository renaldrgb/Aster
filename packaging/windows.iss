[Setup]
AppName=Aster
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\Aster
DefaultGroupName=Aster
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=Aster-Windows-Setup
SetupIconFile=..\static\aster.ico
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\Aster.exe
[Files]
Source: "..\dist\Aster\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
[Icons]
Name: "{userdesktop}\Aster"; Filename: "{app}\Aster.exe"
Name: "{group}\Aster"; Filename: "{app}\Aster.exe"
[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Setting up Microsoft WebView2..."; Flags: waituntilterminated
Filename: "{app}\Aster.exe"; Description: "Open Aster"; Flags: postinstall nowait skipifsilent
