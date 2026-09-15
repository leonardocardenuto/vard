from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(description="Concatena caches de features alinhados ao mesmo manifesto.")
    parser.add_argument("--primary", required=True, help="Cache principal, normalmente V-JEPA.")
    parser.add_argument("--auxiliary", required=True, help="Cache auxiliar, normalmente YOLO/OBB.")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    primary = np.load(args.primary, allow_pickle=True)
    auxiliary = np.load(args.auxiliary, allow_pickle=True)

    x_primary = primary["x"]
    y_primary = primary["y"]
    x_aux = auxiliary["x"]
    y_aux = auxiliary["y"]

    if len(x_primary) != len(x_aux):
        raise RuntimeError(f"Caches desalinhados: primary={len(x_primary)} auxiliary={len(x_aux)}")
    if not np.array_equal(y_primary, y_aux):
        raise RuntimeError("Labels dos caches nao batem.")

    metadata = {
        "primary": args.primary,
        "auxiliary": args.auxiliary,
        "primary_shape": list(x_primary.shape),
        "auxiliary_shape": list(x_aux.shape),
        "combined_shape": [int(x_primary.shape[0]), int(x_primary.shape[1] + x_aux.shape[1])],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        x=np.concatenate([x_primary, x_aux], axis=1).astype(np.float32),
        y=y_primary.astype(np.int64),
        metadata=json.dumps(metadata),
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
