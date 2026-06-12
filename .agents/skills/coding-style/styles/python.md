# Python style

Non-negotiable rules (see [../SKILL.md](../SKILL.md)) for modern Python. Each rule is
tagged by how it is enforced:

- **[tool]** - `uv`, lockfiles, or package-index configuration catch it
- **[lint]** - Ruff catches it
- **[type]** - a type checker catches it (`pyright`, `basedpyright`, `mypy`, or `ty`)
- **[test]** - tests or smoke checks catch it
- **[review]** - human review; no common tool catches it reliably

## 1. Environments and dependencies - prefer uv

- **DO** use `uv` for new Python work: `uv init`, `uv add`, `uv sync --locked`,
  `uv run`, `uvx`, and `uv python pin`. Commit `pyproject.toml`, `uv.lock`, and any
  intentional `.python-version`. **[tool]**
- **DON'T** use `pip` directly when `uv` is available. If a project needs pip-style
  commands, use `uv pip ...`; use `python -m pip` only inside a legacy pip-managed
  environment or when upstream docs have no safe uv equivalent. **[tool]**
- **DO** declare dependencies in `pyproject.toml`: runtime deps under `[project]`,
  contributor-only deps under `[dependency-groups]`, and tool config under `[tool.*]`.
  Avoid ad hoc `requirements.txt` unless a deployment target requires an export. **[tool]**
- **DON'T** hand-edit `.venv` or install into the system interpreter. In uv projects,
  mutate dependencies with `uv add/remove`, then `uv sync`; for one-off scripts use
  `uv run --with ...` or PEP 723 inline script metadata. **[tool]**

## 2. Python version policy

- **DO** choose the Python minor version from the slowest native dependency, not from
  CPython's latest release. For pure Python, current stable Python is usually fine; for ML,
  CUDA, scientific, browser-automation, or database-driver stacks, check the wheel support
  matrix first. **[review]**
- **DON'T** assume Python 3.14 or free-threaded `3.14t` is safe for GPU/scientific stacks
  just because Python itself installed cleanly. Use 3.12 or 3.13 unless Torch, Triton,
  NumPy/SciPy, vLLM, and extension wheels all support the newer ABI you need. **[test]**
- **DO** record the decision in `requires-python`, `.python-version`, CI, and docs. A lockfile
  without a Python pin is not reproducible enough. **[tool]**

## 3. Torch, CUDA, and this Ubuntu workstation

On the inspected Ubuntu workstation (checked 2026-06-12): Ubuntu 24.04.4, 64 CPU threads,
125 GiB RAM, two NVIDIA RTX PRO 6000 Blackwell Workstation Edition GPUs (compute capability
12.0, about 98 GiB each), driver 590.44.01, CUDA Toolkit 13.1, system `python3` from pyenv is
3.14.2, and existing GPU venvs use uv-managed Python 3.12.13 with Torch `+cu130`.

- **DO** treat the Torch wheel's CUDA runtime (`torch.version.cuda`, e.g. `13.0`) as separate
  from `/usr/local/cuda` (`nvcc`, currently 13.1). The driver can run older CUDA-runtime
  wheels; local CUDA extension builds are the part that care about toolkit/header/compiler
  matching. **[test]**
- **DO** pin Torch-family packages together (`torch`, `torchvision`, `torchaudio`, Triton,
  xFormers/FlashAttention/vLLM when present) and choose the PyTorch index explicitly with
  `tool.uv.sources` / `tool.uv.index` (`explicit = true`). For quick diagnostics, the
  2026-era uv shortcut `UV_TORCH_BACKEND=auto uv pip install torch` can pick a backend, but
  committed projects should name the backend they intend. **[tool]**
- **DON'T** upgrade Python, Torch, CUDA, Triton, or vLLM independently on this box. Blackwell
  (`sm_120`) support landed later than generic CUDA 12.x support; verify
  `torch.cuda.is_available()`, `torch.version.cuda`, `torch.cuda.get_device_capability()`,
  and any custom kernels before trusting performance or correctness. **[test]**
- **DO** set `CUDA_DEVICE_ORDER=PCI_BUS_ID` and `CUDA_VISIBLE_DEVICES=...` for multi-GPU runs,
  and set `TORCH_CUDA_ARCH_LIST` to include `12.0` when building local CUDA extensions for
  these GPUs. **[test]**
- **DON'T** put `/usr/local/cuda/lib64` ahead of Torch wheel libraries at runtime unless you
  are intentionally building/debugging native extensions; it can shadow bundled CUDA/cuDNN
  libraries and create misleading import or kernel failures. **[review]**

## 4. Code shape

- **DO** keep module import side effects minimal; put CLI work in `main()` and guard it with
  `if __name__ == "__main__":`. **[review]**
- **DO** type public functions, dataclasses, config objects, and boundary data. Use `Any` only
  at audited interop seams; validate or narrow untyped data before use. **[type]**
- **DO** use `pathlib`, context managers, `tempfile`, `subprocess.run(..., check=True)`, and
  structured `logging`. **DON'T** use `shell=True` with untrusted data, bare `except`, mutable
  default arguments, hidden global state, or silent fallbacks around I/O/model loading.
  **[lint]** **[review]**
- **DO** make numerical and GPU code reproducible enough to debug: seed deliberately, log
  versions/devices, keep CPU fallbacks explicit, and add a tiny smoke test for tensor shapes,
  dtypes, and device placement. **[test]**

## 5. Enforcement

Use Ruff for formatting and linting. The reusable starter config is
[python.ruff.toml](python.ruff.toml); a host project can extend it from `pyproject.toml`:

```toml
[tool.ruff]
extend = "<path-to-skill>/styles/python.ruff.toml"
```

Run, at minimum:

```sh
uv run ruff format .
uv run ruff check .
uv run <type-checker> .
uv run pytest
```

For Torch/CUDA changes, also run a GPU smoke check that imports Torch and prints
`torch.__version__`, `torch.version.cuda`, `torch.cuda.is_available()`, and device capability.
