## 1.12 Stable — 2026-10-27 — 分析加速 / Faster analysis

- 中文：减少 RMS、过零率和频谱分析的重复运算；只对严格为零的窗口复用静音统计。Windows x64 在滤波期间使用线程局部浮点控制，避免极小残余信号拖慢分析，并在退出时恢复原状态。修复分析进度窗口完成回调重入的问题。用户指定为 Stable。
- English: Avoid repeated work in RMS, zero-crossing and spectral analysis; reuse silence statistics only for exactly-zero windows. On Windows x64, temporary thread-local floating-point control avoids slow subnormal filter tails and restores the prior state on exit. Fix reentrant analysis-progress completion. User-designated Stable.
- 模型、阈值、区域规则和编辑操作不变。八份原始音频的完整检测区域与 1.11 相同；20 项合成数据检查、浮点状态恢复、离屏 GUI 分析与 Undo/Redo、Windows EXE CLI 检查通过。
- The model, thresholds, region rules and editing behavior are unchanged. Complete region results match 1.11 on eight original recordings. Twenty synthetic cases, FP-state restoration, offscreen GUI analysis/Undo/Redo and the Windows frozen CLI passed.
- Windows 实测例子：43.211→9.238 秒、36.498→8.976 秒、25.162→5.498 秒。不是所有素材都会同幅提速。Mac 使用跨平台运算优化，不包含 Windows 浮点辅助库；不把 Windows 测速结果当作 Mac 测速。
- Windows timing examples: 43.211→9.238 s, 36.498→8.976 s, 25.162→5.498 s. Gains depend on the material. Mac uses the portable analysis improvements without the Windows FP helper; these timings are not Mac benchmarks.
- 升级与限制：退出应用后替换整个程序目录/APP；保留用户设置。Mac 使用临时签名，未经 Developer ID 公证。构建与自动检查不代表真实桌面试听验收。无试用到期或功能限制。
- Upgrade and limitations: quit the app and replace the complete application folder/bundle, preserving user settings. Mac apps are ad-hoc signed, not Developer ID notarized. Builds and automated checks do not claim real desktop listening acceptance. No trial expiry or feature limits.

# QQDeBreathTool standalone 1.12 - 2026-10-27

Optimize detection speed without changing the model, thresholds or region rules. Square sample data once for frame RMS, compare adjacent signs once for ZCR, and process spectra in bounded batches. Only exactly-zero frames reuse the original zero-frame statistics; quiet nonzero audio receives full analysis. A Windows x64 helper temporarily enables thread-local SSE FTZ/DAZ around sosfiltfilt and restores the exact prior floating-point state on exit, including exceptions. This avoids denormal filter-tail slowdown without changing global process state.

Fix the progress callback's reentrant modal-dialog access: update the label before setValue, because setValue can process completion and clear the window's dialog reference. Undo/Redo remains intact.

Validation: 20 synthetic frame/rate/silence cases, exact FP-state restoration, eight original WAV comparisons, source GUI/real AnalyzeThread completion and Undo/Redo offscreen, and frozen EXE CLI analysis. All eight inputs remain byte-identical; complete region dictionaries match 1.11. Model SHA-256 d655af2bfb260866de74319d179fda0b007e6539711c572967bc0fc709e42afe is unchanged. No real interactive desktop acceptance is claimed.

| Sample | 1.11 seconds | 1.12 seconds | Regions |
|---|---:|---:|---:|
| Everyday/Vocal L.wav | 19.740 | 11.561 | 72 |
| 今夜星辰/今夜星辰-Vocal女.wav | 25.162 | 5.498 | 12 |
| 今夜星辰/今夜星辰-Vocal男1.wav | 7.356 | 6.415 | 28 |
| 呼吸有害/呼吸有害 人声.wav | 8.068 | 6.579 | 54 |
| 大脑将我扼杀/人声1.wav | 22.284 | 9.077 | 60 |
| 小白兔/MixdownDN.wav | 1.366 | 1.172 | 3 |
| 阿那亚/Vocal1.wav | 43.211 | 9.238 | 12 |
| 阿那亚/Vocal2.wav | 36.498 | 8.976 | 19 |
