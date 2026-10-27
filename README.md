# ⚠️ 禁止商业使用 / NO COMMERCIAL USE

## Qing Audio 非商业源码共享许可证 1.0

### 本项目源码公开，但不属于 OSI 认可的开源软件

> **禁止任何商业使用。** 仅允许个人、学习、教育、研究、评估、爱好及其他非商业用途。发布原版、二进制版或修改版时，必须同时免费公开完整对应源代码，保留作者、版权和许可证声明，醒目标明原项目名称、作者、来源链接、修改者、修改日期及修改内容，并使整个修改版继续采用同一许可证。完整条款见 [LICENSE](LICENSE)。
>
> **NO COMMERCIAL USE.** Use is permitted only for personal, educational, research, evaluation, hobby, charitable, and other non-commercial purposes. Any distributed original, binary, or modified version must provide the complete corresponding source without charge, preserve authorship, copyright, and license notices, prominently identify the original project, author, source URL, modifier, date, and changes, and license the entire modified work under the same terms. See [LICENSE](LICENSE).
>
> 许可证政策变更与后续 AI 维护说明见 [LICENSE_POLICY_CHANGE.md](LICENSE_POLICY_CHANGE.md)。 / See [LICENSE_POLICY_CHANGE.md](LICENSE_POLICY_CHANGE.md) for the policy record and future AI maintenance instructions.

# QQDeBreathTool
<img width="1182" height="592" alt="image" src="https://github.com/user-attachments/assets/74673a30-7c39-4179-95f8-e00ee704d3d6" />



QQDeBreathTool is a waveform-editing tool for separating and editing vocal
Breath / Noise regions. It loads an audio file, analyzes Breath regions,
supports manual Breath / Noise editing, lets the user monitor Voice / Breath /
Noise combinations, and exports aligned `Vocal Only`, `Breath`, and `Noise`
WAV stems.

> QQ group: 692973169. Previously released versions remain under the license terms that applied when they were released.

## 下载 / Download

**[QQDeBreathTool 1.12 Stable - 正式 Release / Latest release](https://github.com/Ziqing-Gu/QQDeBreathTool/releases/tag/v1.12)**

- Windows 10/11 x64 独立应用 / standalone app: [QQDeBreathTool-Windows-x64-1.12.zip](https://github.com/Ziqing-Gu/QQDeBreathTool/releases/download/v1.12/QQDeBreathTool-Windows-x64-1.12.zip)
- M 系列 Mac / Apple Silicon app: [QQDeBreathTool-macOS-Apple-Silicon-1.12.zip](https://github.com/Ziqing-Gu/QQDeBreathTool/releases/download/v1.12/QQDeBreathTool-macOS-Apple-Silicon-1.12.zip)
- Intel Mac 独立应用 / standalone app: [QQDeBreathTool-macOS-Intel-1.12.zip](https://github.com/Ziqing-Gu/QQDeBreathTool/releases/download/v1.12/QQDeBreathTool-macOS-Intel-1.12.zip)
- 中文安装说明 / Chinese installation: [QQDeBreathTool-1.12-INSTALL-ZH-CN.txt](https://github.com/Ziqing-Gu/QQDeBreathTool/releases/download/v1.12/QQDeBreathTool-1.12-INSTALL-ZH-CN.txt)
- 英文安装说明 / English installation: [QQDeBreathTool-1.12-INSTALL-EN.txt](https://github.com/Ziqing-Gu/QQDeBreathTool/releases/download/v1.12/QQDeBreathTool-1.12-INSTALL-EN.txt)
- 中文图文手册 · 8 页 / illustrated Chinese manual: [QQDeBreathTool-1.12-User-Manual-ZH-CN.pdf](https://github.com/Ziqing-Gu/QQDeBreathTool/releases/download/v1.12/QQDeBreathTool-1.12-User-Manual-ZH-CN.pdf)
- English illustrated manual · 8 pages: [QQDeBreathTool-1.12-User-Manual-EN.pdf](https://github.com/Ziqing-Gu/QQDeBreathTool/releases/download/v1.12/QQDeBreathTool-1.12-User-Manual-EN.pdf)
- 完整对应源码 / complete corresponding source: [QQDeBreathTool-1.12-Complete-Source.zip](https://github.com/Ziqing-Gu/QQDeBreathTool/releases/download/v1.12/QQDeBreathTool-1.12-Complete-Source.zip)

选择与你的系统/芯片对应的一个程序包。GitHub 自动生成的 Source code (zip)/(tar.gz) 是源码，不是可运行程序。

Choose one app package matching your system/chip. GitHub automatic Source code archives are not installable apps.

[1.11 历史版本 / Previous release](https://github.com/Ziqing-Gu/QQDeBreathTool/releases/tag/v1.11) · [全部版本 / All releases](https://github.com/Ziqing-Gu/QQDeBreathTool/releases)

## Version

Current Stable version: **1.12**, designated by the user on 2026-10-27.

## 1.12 Stable — 2026-10-27 — 分析加速 / Faster analysis

- 中文：减少 RMS、过零率和频谱分析的重复运算；只对严格为零的窗口复用静音统计。Windows x64 在滤波期间使用线程局部浮点控制，避免极小残余信号拖慢分析，并在退出时恢复原状态。修复分析进度窗口完成回调重入的问题。用户指定为 Stable。
- English: Avoid repeated work in RMS, zero-crossing and spectral analysis; reuse silence statistics only for exactly-zero windows. On Windows x64, temporary thread-local floating-point control avoids slow subnormal filter tails and restores the prior state on exit. Fix reentrant analysis-progress completion. User-designated Stable.
- 模型、阈值、区域规则和编辑操作不变。八份原始音频的完整检测区域与 1.11 相同；20 项合成数据检查、浮点状态恢复、离屏 GUI 分析与 Undo/Redo、Windows EXE CLI 检查通过。
- The model, thresholds, region rules and editing behavior are unchanged. Complete region results match 1.11 on eight original recordings. Twenty synthetic cases, FP-state restoration, offscreen GUI analysis/Undo/Redo and the Windows frozen CLI passed.
- Windows 实测例子：43.211→9.238 秒、36.498→8.976 秒、25.162→5.498 秒。不是所有素材都会同幅提速。Mac 使用跨平台运算优化，不包含 Windows 浮点辅助库；不把 Windows 测速结果当作 Mac 测速。
- Windows timing examples: 43.211→9.238 s, 36.498→8.976 s, 25.162→5.498 s. Gains depend on the material. Mac uses the portable analysis improvements without the Windows FP helper; these timings are not Mac benchmarks.
- 升级与限制：退出应用后替换整个程序目录/APP；保留用户设置。Mac 使用临时签名，未经 Developer ID 公证。构建与自动检查不代表真实桌面试听验收。无试用到期或功能限制。
- Upgrade and limitations: quit the app and replace the complete application folder/bundle, preserving user settings. Mac apps are ad-hoc signed, not Developer ID notarized. Builds and automated checks do not claim real desktop listening acceptance. No trial expiry or feature limits.


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
- Windows x64 and native macOS Apple Silicon / Intel standalone apps.
- Qing Audio / Gu Ziqing; GUI and CLI version 1.12.

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

## macOS builds / Mac 构建

Use Python 3.10 and `QQDeBreathTool-macos.spec` on a native Apple Silicon or Intel runner. The `release-standalone-112.yml` workflow builds both app architectures and checks versions, executable architectures, bundled model, signature and frozen CLI analysis. The Windows build is reused from the verified local 1.12 delivery. Existing contributor workflows remain unchanged; release commits skip push CI and the Mac release workflow is dispatched explicitly.

See [BUILD](BUILD.md) and the bilingual guides under [docs](docs). The Windows-only FP helper is intentionally absent on Mac. Performance gains on Mac have not been benchmarked on the private recordings. Verified dependency minimum macOS: arm64 12.3, x86_64 15.7. Developer ID signing/notarization and interactive Mac listening acceptance are not claimed.

## 许可证 / License

本项目第一方源码采用 **Qing Audio 非商业源码共享许可证 1.0**（`LicenseRef-Qing-Audio-NC-Source-Share-1.0`）。禁止任何商业使用。发布原版、二进制版或修改版时，必须同时免费公开完整对应源代码，保留作者、版权与许可证声明，注明原项目、作者、来源链接、修改者、修改日期及修改内容，并使整个修改版继续采用同一许可证。完整条款见 [LICENSE](LICENSE)。第三方组件继续适用其各自许可证。

This project's first-party source is licensed under the **Qing Audio Non-Commercial Source-Share License 1.0** (`LicenseRef-Qing-Audio-NC-Source-Share-1.0`). Commercial use is prohibited. Distribution of the original, binary, or modified version requires the complete corresponding source at no charge, preserved authorship, copyright, and license notices, prominent identification of the original project, author, source URL, modifier, date, and changes, and the same license for the entire modified work. See [LICENSE](LICENSE). Third-party components remain under their respective licenses.

Previously distributed copies retain rights already granted; this License applies to copies supplied with it.
