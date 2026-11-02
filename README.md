# Aster
A desktop study workspace for Google Classroom, school email, documents, quizzes, study chat and research.

## Install
Download the Windows setup or the macOS archive for your processor from the same GitHub Releases page. Windows setup installs Microsoft WebView2. On macOS, extract Aster.app and move it to Applications. Initial Mac builds are not Apple-notarized; macOS may require an explicit Open Anyway action in Privacy & Security.

Open Settings, select a recommended local model and click Download. Aster downloads a verified private Ollama engine if necessary, downloads the model and activates it. Internet and sufficient disk space are required for the initial setup. Cloud AI is optional.

Windows automatically sets up LibreOffice when first opening an Office document. Mac releases include it. PDFs use the bundled PDF.js viewer.

## Google connection
The release contains no preconnected Google account, OAuth client, tokens, model, chats or school documents. Supply your own Desktop OAuth client JSON in Settings, enable the Google Classroom, Gmail and Drive APIs for that project, and sign in to your own school account. School administrators may restrict access. Google access is read-only. User data is stored separately in LocalAppData/Aster on Windows and Library/Application Support/Aster on macOS; credentials use Windows DPAPI or macOS Keychain.

## Build
Requires Python 3.11. Run `python -m pip install -r requirements.txt`, then `python packaging/build.py`. Windows also needs Inno Setup 6 for the installer. Build macOS on macOS; Windows executables cannot be used on a Mac. The GitHub workflow builds Windows and both Mac runner architectures and creates a draft release for version tags. Review and test artifacts before publishing. Mac packaging is prepared but must be validated on actual macOS hardware; signing with an Apple Developer identity and notarization are not configured.

## License and attribution
AGPL-3.0; see LICENSE. Aster was developed from school-focused additions to the open-source Odysseus project; retain upstream notices in the source. PDF.js is Apache-2.0, Marked is MIT, DOMPurify includes its license, Ollama is MIT, and LibreOffice has MPL/LGPL licensing. Third-party notices accompany their bundled files. No claim of endorsement by these projects is made.
