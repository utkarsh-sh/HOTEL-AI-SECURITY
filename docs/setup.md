# Local Setup

## 1. Prerequisites

Recommended local environment:

- Windows 10/11 for the current development workflow.
- Python 3.13 for the CI-tested dependency set.
- Git.
- A working Python virtual environment.
- Sufficient disk space for external model artifacts.
- Optional NVIDIA/CUDA environment if GPU inference is required.

The production ONNX adapters support CPU execution and prefer CUDA when an available CUDA execution provider is present.

## 2. Clone the repository

```powershell
git clone https://github.com/utkarsh-sh/HOTEL-AI-SECURITY.git
cd HOTEL-AI-SECURITY
```

If the repository is already present locally, do not clone it again.

## 3. Create and activate a virtual environment

Example:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell execution policy prevents activation, use the Python executable inside `.venv` directly rather than changing system-wide policy unnecessarily.

## 4. Install dependencies

For CI-equivalent validation:

```powershell
python -m pip install -r requirements-ci.txt
```

The CI dependency file is intended to provide a reproducible test environment; it is not necessarily a complete set of optional development dependencies.

## 5. Configure JWT authentication

Set a local secret before exercising authenticated functionality:

```powershell
$env:HOTEL_SECURITY_JWT_SECRET = "<your-strong-local-secret-at-least-32-characters>"
```

Never put a real secret into Git.

## 6. Acquire production model artifacts

The model binaries are intentionally not tracked in Git.

Follow `docs/model_acquisition.md`.

After placing the models at their required paths, run:

```powershell
python scripts\verify_model_artifacts.py
```

Do not skip checksum verification when preparing a production or evaluation environment.

## 7. Run the test suite

```powershell
python -m pytest -q
```

A successful local test run should be recorded before a milestone is considered complete.

## 8. Check the working tree

Before committing:

```powershell
git status --short
git diff --check
```

Review all changed files manually.

## 9. Windows-specific notes

The project contains Python and native computer-vision/ONNX Runtime components. If CUDA is being used, verify that ONNX Runtime actually reports the CUDA execution provider instead of assuming GPU inference is active.

To inspect available providers:

```powershell
@'
import onnxruntime as ort

for provider in ort.get_available_providers():
    print(provider)
'@ | python
```

The exact active provider is determined by the model adapter's runtime session.

## 10. Reproducibility principle

Model artifacts, secrets, runtime databases, generated evidence, and local caches are external/runtime state. Source code and configuration required to recreate the application belong in Git; large or generated runtime artifacts do not.

If an exact external model source is not recorded by the repository, do not invent a download URL or source revision. Verify the artifact by its pinned SHA-256 instead.
