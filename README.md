# QQDeBreathTool

QQDeBreathTool 是一个面向人声后期处理的呼吸声 / 噪音分离工具。它可以载入音频文件，自动分析 Breath 区块，并允许手动编辑、监听和导出对齐的 `Vocal Only`、`Breath`、`Noize` 三条音频。

> 禁止商用，加 Q 群 692973169 交流。

## About

QQDeBreathTool 是由混音师顾子青用 Codex 加载 ChatGPT 5.5 制作出来的分离齿音 / 噪音的软件，由程序员刁翔宇帮助编译修正。

QQDeBreathTool is a de-breath and noise separation utility developed by mixing engineer Gu Ziqing, who built it by integrating ChatGPT 5.5 via Codex, with compilation and bug fixes assisted by programmer Diao Xiangyu.

这款软件的模型截止目前(2026.06.29)是使用了11首歌曲案例、12个歌手(6男6女)样本训练出来的，其中大部分是录音室录音，少部分是家庭环境录音，一部分样本包含极端案例(大量气声的情况、直流偏移严重的情形)。

As of June 29, 2026, the model powering this software has been trained on a dataset consisting of 11 song excerpts and vocal samples from 12 singers (6 male, 6 female). Most recordings were captured in professional studios, a smaller portion in home recording environments, and a subset of samples feature extreme edge cases, including heavy breathiness and severe DC offset distortion.

目前识别呼吸声的准确率已显著高于其他同类插件软件。

Its current accuracy in detecting breath sounds far outperforms that of comparable competing plugins and software.


Current version: `1.02`

## Features

- Drag and drop audio loading with waveform display.
- Automatic Breath region analysis.
- Breath / Noize / Vocal Only region editing.
- Right-click region toggle between Breath and Noize.
- Undo / Redo with `Ctrl+Z` and `Shift+Ctrl+Z`.
- Playback with Space play / stop.
- Voice / Breath / Noize monitor checkboxes.
- Monitor gain and meter.
- Optional Fade In / Fade Out for monitoring and export.
- Adjacent Breath / Noize regions use shared visual and audio crossfade.
- Optional Breath normalization for export, monitoring, and Breath waveform display.
- Restores the last opened audio file and edited regions on launch.
- Windows PyInstaller build spec included.

## Repository Contents

- `debreath_tool_app.py` - main PyQt5 desktop application and CLI analyze/export entry point.
- `breath_frame_model.joblib` - trained Breath detection model bundled with the app.
- `QQDeBreathTool.spec` - Windows PyInstaller build spec.
- `requirements-qqdebreath.txt` - Python dependencies.
- `debreath_icon.*` - application icon assets.
- `make_debreath_icon.py` - icon generation helper.

Training audio, private evaluation reports, local build folders, and exported WAV files are intentionally not included.

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

## Build Windows App

```powershell
python -m PyInstaller --noconfirm --clean .\QQDeBreathTool.spec
```

The built app folder will be:

```text
dist\QQDeBreathTool
```

## macOS Notes

The source includes macOS-friendly settings and font handling, but the included `.spec` is Windows-oriented. On macOS, use a macOS PyInstaller command or spec and use `:` as the `--add-data` separator.

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

This project is released under a non-commercial source license. See [LICENSE](LICENSE).
