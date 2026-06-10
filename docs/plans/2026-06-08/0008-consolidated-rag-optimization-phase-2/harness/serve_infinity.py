#!/usr/bin/env python3
"""serve_infinity.py — Wave-3 GPU embed/rerank server (campaign-only).

Bypasses Infinity's `infinity_emb v2` CLI, which is broken under the installed
typer/click ("Secondary flag is not valid for non-boolean flag"), by calling the
Python factory `infinity_emb.create_server(engine_args_list=[...])` and running it
with uvicorn. Serves one or more NAS-staged models (embedders and/or rerankers) on
one OpenAI/Infinity-compatible port: `/embeddings` and `/rerank`.

Run from the infinity venv and pin the free GPU explicitly (GPU0 is the gemma-4
vLLM server):

  CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 \
  ~/developer/third-party/python_venvs/infinity_env/.venv/bin/python serve_infinity.py \
    --port 7997 \
    --model /mnt/nas/home/ml/model/reranker/bge-reranker-v2-m3 \
    --model /mnt/nas/home/ml/model/embedding/bge-base-en-v1.5

Served model name defaults to the directory basename; override with `path::name`.
This is CAMPAIGN infrastructure — never part of the portable CPU `setting-up-rag` default.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from infinity_emb import EngineArgs, create_server


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", action="append", required=True,
                    help="NAS model dir, optionally path::served_name (repeatable)")
    ap.add_argument("--port", type=int, default=7997)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--dtype", default="auto")
    ap.add_argument("--engine", default="torch", help="torch | optimum | ...")
    ap.add_argument("--trust-remote-code", action="store_true",
                    help="needed for some decoder embedders/rerankers (e.g. Qwen3)")
    args = ap.parse_args()

    eargs = []
    for spec in args.model:
        path, _, name = spec.partition("::")
        name = name or Path(path).name
        eargs.append(EngineArgs(
            model_name_or_path=path, served_model_name=name,
            engine=args.engine, device="cuda", batch_size=args.batch_size,
            dtype=args.dtype, trust_remote_code=args.trust_remote_code,
            model_warmup=True,
        ))
        print(f"serve_infinity: + {name}  <-  {path}")
    app = create_server(engine_args_list=eargs)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
