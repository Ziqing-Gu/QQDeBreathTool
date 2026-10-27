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

Prior local checkpoint: Windows standalone 1.12 was delivered and validated before public release was requested. The plug-in line is separate.

Build from the current sources; no private diagnostic transformation scripts or source recordings are distributed.

## 2026-10-27 — User-designated 1.12 Stable; standalone Plan B/C/D

The user explicitly selected standalone 1.12 as Stable and authorized one new Plan B, followed by C/D. Reuse the completed Windows build, tests and installation. Publish the complete corresponding source and build the missing native Apple Silicon/Intel apps. The earlier no-publication/no-Stable status above describes the previous task checkpoint and is superseded by this request. Existing plugin releases are separate and complete. No product behavior changes are made for Stable designation.

## 2026-10-27 — Plan B complete and frozen

Standalone 1.12 Stable: 62 source files / 2121216 bytes; every copied file hash matched. The backup is frozen. Later stages inherit this record without opening or refreshing the snapshot.

## 2026-10-27 — Illustrated standalone manuals

User requested Chinese and English illustrated manuals for standalone 1.12. Each PDF has eight pages, with actual 1.12 widgets rendered offscreen using generated audio and manually placed regions. All 16 pages were rendered and visually reviewed. Manuals explicitly distinguish region Undo/Redo (up to 100 steps) from global parameters, startup session restoration from manually reopening a file, and monitoring controls from export processing. No product binary inputs changed. Formal Plan B remains frozen and is not refreshed for documentation. Mac workflow run 40512028581 succeeded for arm64 and x86_64 with architecture, version, model, ad-hoc signature and frozen CLI checks.

## 2026-10-27 — Standalone 1.12 Stable Plan B/C/D complete

Windows build, source-equivalence tests, GUI/CLI checks and installation were reused. One explicitly authorized Plan B completed and was frozen: 62 source files, 2,121,216 bytes, every copied hash matched. No later backup access or refresh was performed.

Public product source/tag: 609e42096e066c9906daee8f3044af88d1b603f5 / v1.12. Illustrated manuals and packaged-source documentation: b6807a784a35594ad369a22bf10f2aaf3297d0e9. Mac run 40512028581 passed for arm64 and x86_64; artifact digests, APP structure/version/architecture, bundled model, ad-hoc signature and frozen CLI analysis were checked. Verified dependency minima: Apple Silicon macOS 12.3; Intel macOS 15.7. These packages do not claim older-system compatibility or interactive Mac listening acceptance.

The Chinese and English illustrated PDFs each contain eight pages; all 16 pages were rendered and visually checked. The release has eight assets, all public downloads accessible with matching byte counts and SHA-256 digests. The complete desktop user package contains Windows, both Mac apps, bilingual installation guides and both manuals. A separate runnable Windows folder and both manuals were also delivered to the desktop.

Release: https://github.com/Ziqing-Gu/QQDeBreathTool/releases/tag/v1.12
Version coverage: previous public 1.11 to current 1.12; included version 1.12; no omissions. All requested stages are complete. Future plugin work remains separate in QQEasyTool; this standalone app is not frozen by that plugin maintenance decision.
