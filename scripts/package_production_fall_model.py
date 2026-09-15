from __future__ import annotations

import argparse
import json
import pickle
import time
from pathlib import Path


DEFAULT_SOURCE = Path("fall_detection/models/vard_fall_window_production.pkl")
DEFAULT_OUTPUT = Path("fall_detection/models/vard_fall_window_production.pkl")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Atualiza metadados operacionais de um classificador ja escolhido para producao. "
            "Para treinar o artefato final calibrado, prefira scripts/build_production_fall_model_from_features.py."
        )
    )
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--production-window-seconds", type=float, default=5.0)
    parser.add_argument("--production-stride-seconds", type=float, default=1.0)
    parser.add_argument("--production-sample-fps", type=float, default=6.0)
    parser.add_argument("--smoothing-window", type=int, default=5)
    parser.add_argument("--min-consecutive-hits", type=int, default=2)
    return parser.parse_args()


def main():
    args = parse_args()
    source = Path(args.source)
    output = Path(args.output)
    if not source.exists():
        raise FileNotFoundError(f"Modelo fonte nao encontrado: {source}")

    with source.open("rb") as source_file:
        payload = pickle.load(source_file)

    metadata = dict(payload.get("metadata", {}))
    metadata.update(
        {
            "artifact_role": "production",
            "production_window_seconds": args.production_window_seconds,
            "production_stride_seconds": args.production_stride_seconds,
            "production_sample_fps": args.production_sample_fps,
            "production_smoothing_window": args.smoothing_window,
            "production_min_consecutive_hits": args.min_consecutive_hits,
            "packaged_from": str(source),
            "packaged_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "serving_notes": (
                "Use recent frames over production_window_seconds, split into subclips, "
                "aggregate V-JEPA2 embeddings with mean/max/std, then apply threshold."
            ),
        }
    )
    payload["metadata"] = metadata

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as output_file:
        pickle.dump(payload, output_file)
    output.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Modelo de producao salvo em: {output}")
    print(f"Metadata salva em: {output.with_suffix('.json')}")


if __name__ == "__main__":
    main()
