# QQDeBreathTool
![Uploading image.png…]()

QQDeBreathTool is a waveform-editing tool for separating and editing vocal
Breath / Noise regions. It loads an audio file, analyzes Breath regions,
supports manual Breath / Noise editing, lets the user monitor Voice / Breath /
Noise combinations, and exports aligned `Vocal Only`, `Breath`, and `Noise`
WAV stems.

> Non-commercial source release. QQ group: 692973169.

## Version

Current version: `1.11`

Version 1.11 keeps the 1.10 detector/model unchanged and focuses on UI
smoothness: cached waveform drawing, lighter playhead repainting, and finer
mouse-wheel zoom / Shift-wheel horizontal movement.

Version 1.10 retrains the Breath detector using the per-song `1.09.txt`
feedback files while preserving older feedback as anti-regression anchors. The
selected model uses Breath threshold `0.84`; final selection was based on both
frame-level metrics and a PASS/WARN/FAIL audit of the latest feedback notes.

Special thanks to Jason for contributing additional Vocal training samples,
which helped improve the Breath detector in the 1.10 model update.

Version 1.09 retrains the Breath detector using the per-song `1.08.txt`
feedback files. It keeps the original 11-song training set anchored while
folding in the newer sample notes, and selects a balanced Breath threshold of
`0.84` to recover older-song misses without taking the false-positive-heavy
low-threshold route.

Version 1.08 further retrains the Breath detector using the per-song `1.07.txt`
feedback files. It also scopes gender-section feedback such as `男:` / `女:` to
the matching vocal stem, avoiding cross-contamination in folders with multiple
vocal tracks.

Version 1.07 further retrains the Breath detector using the per-song `1.06.txt`
feedback files. These notes are treated as hard feedback for missed breaths,
false-positive consonants/noise/breathy syllable tails, and corrected region
boundaries.

Version 1.06 retrains the Breath detector with the expanded private sample set.
The training pipeline accepts both legacy `Noize` and current `Noise` stem
names, and incorporates `QQDebreathTool7没识别的部分.txt` feedback files as hard
Breath feedback.

Version 1.05 adds copyable current/selected-region timecodes and corrects the
visible Noise spelling while preserving compatibility with older saved data.

Version 1.04 fixes WAV stem export for MP3/OGG/other non-WAV inputs. The app now
uses a WAV-safe output subtype when exporting `Vocal Only`, `Breath`, and
`Noise`, so decoded MP3 input metadata is not reused as an invalid WAV encoding.

## About

QQDeBreathTool 是由混音师顾子青用 Codex 加载 ChatGPT 5.5 制作出来的分离呼吸声 /
噪音的软件，由程序员刁翔宇帮助编译修正。

QQDeBreathTool is a de-breath and noise separation utility developed by mixing
engineer Gu Ziqing, who built it by integrating ChatGPT 5.5 via Codex, with
compilation and bug fixes assisted by programmer Diao Xiangyu.

模型使用多首歌曲片段和多位歌手的人声样本训练，其中大部分是录音室录音，少部分是家庭环境录音，也包含了一些重呼吸、严重直流偏移等极端案例。

The current model has been trained on song excerpts and vocal samples from
multiple singers. Most recordings were captured in professional studios, a
smaller portion in home recording environments, and a subset of samples feature
edge cases including heavy breathiness and severe DC offset distortion.

特别感谢网友 Jason 提供新的 Vocal 训练样本，帮助改进 1.10 版 Breath 检测模型。

Special thanks to Jason for contributing additional Vocal training samples used
to improve the 1.10 Breath detector.

目前识别呼吸声的准确率已经显著高于其他同类插件软件。

Its current accuracy in detecting breath sounds far outperforms that of
comparable competing plugins and software.

## Features

- Drag/drop audio loading with waveform display.
- Automatic Breath region analysis.
- Breath / Noise / Vocal Only region editing.
- Shift-drag region creation and Delete removal.
- Region boundary editing.
- Right-click region toggle between Breath and Noise.
- Undo / Redo with `Ctrl+Z` and `Shift+Ctrl+Z`.
- Playback with Space play / stop.
- Voice / Breath / Noise monitor checkboxes.
- Monitor gain and meter.
- Optional Fade In / Fade Out for monitoring and export.
- Adjacent regions use shared visual and audio crossfade.
- Optional Breath normalization for export, monitoring, and Breath waveform
  display.
- Breath Adjust / Breath Gain for changing Breath stem level.
- Copyable current playhead timecode and selected region time range.
- Restores the last opened audio file and edited regions on launch.
- Windows PyInstaller build spec included.

## Repository Contents

- `debreath_tool_app.py` - app entry point and legacy compatibility facade.
- `qq_debreath/` - GUI, CLI, and core facade modules.
- `breath_frame_model.joblib` - trained Breath detection model bundled with the
  app.
- `QQDeBreathTool.spec` - Windows PyInstaller build spec.
- `requirements-qqdebreath.txt` - Python dependencies.
- `debreath_icon.*` - application icon assets.
- `make_debreath_icon.py` - icon generation helper.

Training audio, private evaluation reports, local build folders, and exported
WAV files are intentionally not included.

## Install Dependencies

Python 3.10 is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-qqdebreath.txt
```

## Run From Source

```powershell
python .\debreath_tool_app.py
```

CLI smoke test:

```powershell
python .\debreath_tool_app.py --analyze-only --input .\your_vocal.wav --out-dir .\out
```

Plugin JSON CLI:

```powershell
python .\debreath_tool_app.py analyze-for-plugin `
  --input .\your_vocal.wav `
  --output-json .\plugin_result.json `
  --out-dir .\plugin_out `
  --threshold 0.86 `
  --fade-ms 10 `
  --breath-target-db -6 `
  --breath-gain-db 0 `
  --detect-noize 0
```

## Build Windows App

```powershell
python -m PyInstaller --noconfirm --clean .\QQDeBreathTool.spec
```

The built app folder will be:

```text
dist\QQDeBreathTool
```

The main executable is:

```text
dist\QQDeBreathTool\QQDeBreathTool.exe
```

## macOS Notes

The source includes macOS-friendly settings and font handling, but the included
`.spec` is Windows-oriented. On macOS, use a macOS PyInstaller command or spec
and use `:` as the `--add-data` separator.

Example:

```bash
python3 -m PyInstaller --noconfirm --windowed --name QQDeBreathTool \
  --add-data "breath_frame_model.joblib:." \
  --add-data "debreath_icon.ico:." \
  -i debreath_icon.ico \
  debreath_tool_app.py
```

The macOS builder may need PortAudio available for `sounddevice`.

## License

This project is released under a non-commercial source license. See
[`LICENSE`](LICENSE).
