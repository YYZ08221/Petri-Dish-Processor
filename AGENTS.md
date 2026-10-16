# CBL Agent Installation And Maintenance

This repository is a Python/PySide6 Windows desktop application, not an agent
plugin or a hosted service. Agents can install and verify it using a local shell.

## Install

1. Use Windows 10/11, Git, and 64-bit Python 3.11 or newer.
2. Clone `https://github.com/YYZ08221/CBL-Petri-Dish-Processor.git` into the user's
   chosen directory. Suggested location: `D:\程序\涂布处理系统\CBL`.
   If that directory already contains files, preserve them and use another directory.
3. From the repository root run:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -RunTests
   ```

4. Report the installation path, smoke-check result, pytest summary, and launch
   command. Reference-image tests may skip unless `CBL_REFERENCE_DIR` is provided.
5. To open the application in the user's interactive desktop:

   ```powershell
   .\.venv\Scripts\python.exe app.py
   ```

Do not change global execution policy. Do not install dependencies into global
Python. No API keys, paid services, GPU, or model weights are required. If Python
is missing, report the prerequisite rather than claiming installation succeeded.

## Verify And Develop

```powershell
.\.venv\Scripts\python.exe scripts/check_install.py
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m pytest -q
```

`scripts/check_install.py` uses synthetic data and temporary output only. For
real-image regression tests, set `CBL_REFERENCE_DIR` to a directory containing
the named reference JPEGs. Skipped real-image tests do not prove detection quality.

Application entry: `app.py`. Detection: `src/core/detection.py`. GUI:
`src/gui/main_window.py`. Export: `src/services/export_service.py`.

Preserve the original photos. Keep experimental data, reference images, exports,
backups, virtual environments, credentials, and machine-specific paths out of
commits. Do not change detection behavior during an installation task.
