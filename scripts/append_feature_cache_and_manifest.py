from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(description="Concatena manifesto/cache base com janelas adicionais.")
    parser.add_argument("--base-manifest", required=True)
    parser.add_argument("--base-features", required=True)
    parser.add_argument("--extra-manifest", required=True)
    parser.add_argument("--extra-features", required=True)
    parser.add_argument("--output-manifest", required=True)
    parser.add_argument("--output-features", required=True)
    return parser.parse_args()


def read_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    args = parse_args()
    base = np.load(args.base_features, allow_pickle=True)
    extra = np.load(args.extra_features, allow_pickle=True)
    x_base, y_base = base["x"], base["y"]
    x_extra, y_extra = extra["x"], extra["y"]
    if x_base.shape[1] != x_extra.shape[1]:
        raise RuntimeError(f"Dimensoes diferentes: base={x_base.shape} extra={x_extra.shape}")

    base_lines = read_lines(Path(args.base_manifest))
    extra_lines = read_lines(Path(args.extra_manifest))
    if len(base_lines) != len(x_base):
        raise RuntimeError("Base manifest/features desalinhados.")
    if len(extra_lines) != len(x_extra):
        raise RuntimeError("Extra manifest/features desalinhados.")

    output_manifest = Path(args.output_manifest)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text("\n".join(base_lines + extra_lines) + "\n", encoding="utf-8")

    metadata = {
        "base_manifest": args.base_manifest,
        "base_features": args.base_features,
        "extra_manifest": args.extra_manifest,
        "extra_features": args.extra_features,
        "base_shape": list(x_base.shape),
        "extra_shape": list(x_extra.shape),
        "combined_shape": [int(x_base.shape[0] + x_extra.shape[0]), int(x_base.shape[1])],
    }
    output_features = Path(args.output_features)
    output_features.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_features,
        x=np.concatenate([x_base, x_extra], axis=0).astype(np.float32),
        y=np.concatenate([y_base, y_extra], axis=0).astype(np.int64),
        metadata=json.dumps(metadata),
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
