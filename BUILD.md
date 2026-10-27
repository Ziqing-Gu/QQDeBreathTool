# QQDeBreathTool standalone 1.12 — Build

Python 3.10; dependencies in requirements-qqdebreath.txt. PyInstaller 6.21.0, NumPy 1.23.5, SciPy 1.10.1, scikit-learn 1.2.1, soundfile 0.12.1 and joblib 1.2.0. Qt, Pillow and miniaudio versions resolved by CI are recorded with the build evidence.

Windows: install MSVC x64 Build Tools, then `python -m PyInstaller --noconfirm --workpath <temporary-build> --distpath <output> QQDeBreathTool.spec`. The native helper is compiled by native/build_fp_control.py into the PyInstaller work directory. Keep the complete output directory and _internal. Windows GUI/CLI and PE versions are 1.12 (numeric 1.12.0.0).

Mac: use native Python 3.10 on the required architecture, install requirements, then `python -m PyInstaller --noconfirm QQDeBreathTool-macos.spec`. GUI/CLI and Info.plist versions are 1.12. The Windows-only floating-point helper is intentionally not built on Mac; portable frame-analysis improvements remain active. ZIP packaging must preserve symbolic links and execute bits (`ditto -c -k --sequesterRsrc --keepParent`).

Release CI: explicitly dispatch release-standalone-112.yml at the exact release tag. It builds only Apple Silicon and Intel apps. Windows release output is reused from the prior verified local build. Existing contributor workflows are preserved without edits; release commits contain [skip ci] to avoid redundant push builds.

Validation: Windows 1.11/1.12 comparison covered 20 synthetic cases and eight original audio files with identical final region dictionaries, plus exact FP-state restore, offscreen GUI analysis with Undo/Redo and frozen CLI. Private audio is not distributed. Mac CI checks architecture, bundle version/model/signature and runs frozen CLI on synthetic silence. These checks are not interactive desktop acceptance or Mac performance measurements.

Authoritative handoff: AI_DEVELOPMENT_HANDOFF.md. Current license: LICENSE and LICENSE_POLICY_CHANGE.md.
