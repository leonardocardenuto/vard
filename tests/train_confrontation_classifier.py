"""Treino V-JEPA 2 binario em SCFD, AIRTLab e VID domestico, com splits por origem."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CACHE = ROOT / ".cache/huggingface"
os.environ.setdefault("HF_HOME", str(CACHE))

import cv2
import numpy as np
import torch
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from torch import nn
from torch.utils.data import DataLoader, Dataset, TensorDataset, WeightedRandomSampler
from transformers import AutoModel, AutoVideoProcessor

from fall_detection.confrontation_model import CLASS_NAMES, MODEL_NAME, ConfrontationHead


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def save_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def save_torch(path, payload):
    temporary = path.with_suffix(".tmp")
    torch.save(payload, temporary)
    temporary.replace(path)


@dataclass
class Sample:
    path: str
    dataset: str
    label: int
    source_id: str
    video_id: str
    sha256: str = ""
    fps: float = 0
    total_frames: int = 0
    split: str = ""
    start_frame: int = 0
    end_frame: int = 0


def source_map(root):
    mapping, current = {}, None
    for line in (root / "scfd/videos.txt").read_text(encoding="utf-8-sig").splitlines():
        if line.strip().startswith("http"):
            current = line.strip()
        match = re.match(r"^(nofi\d+|fi\d+)\s*:", line.strip())
        if match and current:
            mapping[match[1]] = "scfd:" + current
    # A lista de origem fornece faixas agregadas para esses videos normais.
    for index in range(62, 92):
        mapping[f"nofi{index:03d}"] = "scfd:CamNet-Synopsis"
    return mapping


def collect_videos(root, seed):
    rows = []
    mapping = source_map(root)
    for path in sorted((root / "scfd").rglob("*.mp4")):
        if path.stem not in mapping:
            raise ValueError(f"Origem SCFD nao identificada: {path}")
        rows.append(Sample(str(path.resolve()), "scfd", int(path.parent.name == "fight"),
                           mapping[path.stem], "scfd:" + path.stem))
    for path in sorted((root / "airtlab").rglob("*.mp4")):
        label = int("violent" in path.parts and "non-violent" not in path.parts)
        source = f"airtlab:{label}:{path.stem}"
        rows.append(Sample(str(path.resolve()), "airtlab", label, source, source + ":" + path.parent.name))
    positives, negatives = [], []
    for path in sorted((root / "vid").rglob("*.mp4")):
        if path.stem.startswith("v_d_b_"):
            positives.append(path)
        elif path.stem.startswith("nv_b_"):
            negatives.append(path)
    if not positives or len(negatives) < len(positives):
        raise ValueError(f"VID incompleto: positivos={len(positives)}, negativos={len(negatives)}")
    # Subconjunto domestico balanceado, escolhido antes de gerar qualquer split.
    negatives = random.Random(seed).sample(negatives, len(positives))
    for label, paths in ((0, negatives), (1, positives)):
        for path in paths:
            identity = "vid:" + path.stem
            rows.append(Sample(str(path.resolve()), "vid_domestic", label, identity, identity))
    counts = Counter(row.dataset for row in rows)
    if counts["scfd"] != 300 or counts["airtlab"] != 350 or len(positives) != 320:
        raise ValueError(f"Contagens diferentes dos manifests esperados: {counts}; domesticos={len(positives)}")
    return rows


def audit_videos(rows, out):
    rejected, seen, kept = [], {}, []
    for index, row in enumerate(rows, 1):
        row.sha256 = hashlib.sha256(Path(row.path).read_bytes()).hexdigest()
        if row.sha256 in seen:
            other = seen[row.sha256]
            if row.label != other.label:
                raise ValueError(f"Duplicata com rotulos conflitantes: {row.path}")
            rejected.append({"path": row.path, "reason": "exact_duplicate", "duplicate_of": other.path})
            continue
        cap = cv2.VideoCapture(row.path)
        row.fps = float(cap.get(cv2.CAP_PROP_FPS))
        row.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        ok, _ = cap.read()
        cap.release()
        if not ok or row.fps <= 0 or row.total_frames < 16:
            rejected.append({"path": row.path, "reason": "unreadable_or_insufficient_frames"})
            continue
        seen[row.sha256] = row
        kept.append(row)
        if index % 200 == 0:
            log(f"Auditoria: {index}/{len(rows)} videos")
    save_json(out / "rejected_videos.json", rejected)
    return kept


def split_videos(rows, seed):
    # Escolha baseada somente na distribuicao de rotulos, nunca em desempenho.
    split_rows = []
    for dataset in sorted({row.dataset for row in rows}):
        subset = [row for row in rows if row.dataset == dataset]
        groups = [row.source_id for row in subset]
        best, best_cost = None, float("inf")
        for attempt in range(200):
            trainval, test = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed + attempt).split(subset, groups=groups))
            train_idx, val_idx = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed + 1000 + attempt).split(trainval, groups=[groups[i] for i in trainval]))
            splits = {"train": trainval[train_idx], "validation": trainval[val_idx], "test": test}
            if any(len({subset[i].label for i in indices}) < 2 for indices in splits.values()):
                continue
            ratio = np.mean([row.label for row in subset])
            cost = sum(abs(np.mean([subset[i].label for i in indices]) - ratio) +
                       abs(len(indices) / len(subset) - target)
                       for indices, target in zip(splits.values(), (0.64, 0.16, 0.2)))
            if cost < best_cost:
                best, best_cost = splits, cost
        if best is None:
            raise ValueError(f"Nao foi possivel separar as duas classes por origem em {dataset}")
        for split, indices in best.items():
            for i in indices:
                subset[i].split = split
                split_rows.append(subset[i])
    membership = defaultdict(set)
    for row in split_rows:
        membership[row.source_id].add(row.split)
    if any(len(splits) != 1 for splits in membership.values()):
        raise ValueError("Vazamento entre splits por origem")
    return split_rows


def slice_videos(rows, seconds):
    slices = []
    for row in rows:
        span = max(16, round(row.fps * seconds))
        # Recortes consecutivos, como no SCVD; caudas curtas nao viram janelas completas.
        # Pequenas diferencas de arredondamento/FPS sao toleradas em clipes de 2s.
        if row.total_frames < span:
            if row.total_frames / row.fps < seconds * 0.9:
                continue
            starts = [0]
        else:
            starts = list(range(0, row.total_frames - span + 1, span))
        for start in starts:
            values = asdict(row)
            values.update(start_frame=start, end_frame=min(row.total_frames - 1, start + span - 1))
            slices.append(Sample(**values))
    return slices


class VideoDataset(Dataset):
    def __init__(self, rows, processor, num_frames):
        self.rows, self.processor, self.num_frames = rows, processor, num_frames

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        indices = np.linspace(row.start_frame, row.end_frame, self.num_frames).astype(int)
        frames = []
        cap = cv2.VideoCapture(row.path)
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(indices[0]))
            next_index = 0
            for target in range(int(indices[0]), int(indices[-1]) + 1):
                ok = cap.grab()
                if not ok:
                    raise ValueError(f"Falha ao decodificar frame {target}: {row.path}")
                if target != indices[next_index]:
                    continue
                ok, frame = cap.retrieve()
                if not ok:
                    raise ValueError(f"Falha ao recuperar frame {target}: {row.path}")
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = frame.shape[:2]
                if max(h, w) > 960:
                    scale = 960 / max(h, w)
                    frame = cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
                frames.append(frame)
                next_index += 1
        finally:
            cap.release()
        return self.processor(frames, return_tensors="pt")["pixel_values_videos"][0]


def initialize_worker(_):
    cv2.setNumThreads(1)
    torch.set_num_threads(1)


@torch.inference_mode()
def extract_features(rows, args, out, device):
    fingerprint = hashlib.sha256(json.dumps({"samples": [asdict(row) for row in rows],
        "model": MODEL_NAME, "frames": args.num_frames}, sort_keys=True).encode()).hexdigest()
    cache_path = out / "features.pt"
    features = []
    if cache_path.exists():
        cached = torch.load(cache_path, weights_only=True, map_location="cpu")
        if cached["fingerprint"] != fingerprint:
            raise ValueError("Cache de embeddings nao corresponde ao manifesto atual; use outro output-dir.")
        features = [cached["features"]]
    done = sum(len(item) for item in features)
    if done == len(rows):
        return features[0]
    processor = AutoVideoProcessor.from_pretrained(MODEL_NAME, cache_dir=CACHE)
    backbone = AutoModel.from_pretrained(MODEL_NAME, cache_dir=CACHE).to(device).eval().requires_grad_(False)
    loader = DataLoader(VideoDataset(rows[done:], processor, args.num_frames),
                        batch_size=args.feature_batch_size, num_workers=args.feature_workers,
                        shuffle=False, worker_init_fn=initialize_worker,
                        pin_memory=device.type == "cuda", persistent_workers=args.feature_workers > 0)
    start = time.monotonic()
    for step, pixels in enumerate(loader, 1):
        with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
            outputs = backbone(pixel_values_videos=pixels.to(device), skip_predictor=True)
            features.append(outputs.last_hidden_state.mean(dim=1).float().cpu())
        if step == 1 or step % 20 == 0 or step == len(loader):
            complete = sum(len(item) for item in features)
            elapsed = time.monotonic() - start
            eta = elapsed / max(1, complete - done) * (len(rows) - complete)
            log(f"Embeddings: {complete}/{len(rows)} janelas; ETA {eta / 60:.1f} min")
            save_torch(cache_path, {"fingerprint": fingerprint, "features": torch.cat(features)})
    del backbone
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return torch.cat(features)


def metrics(labels, probabilities, threshold=0.5):
    predictions = (np.asarray(probabilities) >= threshold).astype(int)
    return {"accuracy": float(accuracy_score(labels, predictions)),
            "f1_confronto": float(f1_score(labels, predictions, zero_division=0)),
            "precision_confronto": float(precision_score(labels, predictions, zero_division=0)),
            "recall_confronto": float(recall_score(labels, predictions, zero_division=0)),
            "confusion_matrix": confusion_matrix(labels, predictions, labels=[0, 1]).tolist(),
            "classification_report": classification_report(labels, predictions, labels=[0, 1],
                target_names=CLASS_NAMES, output_dict=True, zero_division=0)}


@torch.inference_mode()
def predict(head, features):
    head.eval()
    return head(features).softmax(dim=1)[:, 1].cpu().numpy()


def summarize(rows):
    return {split: {dataset: dict(Counter(CLASS_NAMES[row.label] for row in rows
                if row.split == split and row.dataset == dataset))
            for dataset in sorted({row.dataset for row in rows})}
        for split in ("train", "validation", "test")}


def report_metrics(rows, probs, threshold):
    result = {"window": metrics([row.label for row in rows], probs, threshold), "per_dataset": {}}
    for dataset in sorted({row.dataset for row in rows}):
        indices = [i for i, row in enumerate(rows) if row.dataset == dataset]
        result["per_dataset"][dataset] = metrics([rows[i].label for i in indices], probs[indices], threshold)
    by_video = defaultdict(list)
    for row, probability in zip(rows, probs):
        by_video[row.video_id].append((row.label, float(probability)))
    result["video_mean"] = metrics([items[0][0] for items in by_video.values()],
                                    [np.mean([item[1] for item in items]) for items in by_video.values()], threshold)
    return result


def train(rows, features, args, out):
    # Embeddings congelados: a otimizacao da pequena head ocorre em CPU.
    # Reprodutivel tambem quando a extracao e retomada de um cache parcial.
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    by_split = {split: np.array([i for i, row in enumerate(rows) if row.split == split])
                for split in ("train", "validation", "test")}
    train_ids, val_ids = by_split["train"], by_split["validation"]
    source_counts = Counter(rows[i].video_id for i in train_ids)
    category_counts = Counter((row.dataset, row.label) for row in
                              {rows[i].video_id: rows[i] for i in train_ids}.values())
    weights = [1 / (source_counts[rows[i].video_id] * category_counts[(rows[i].dataset, rows[i].label)]) for i in train_ids]
    labels = torch.tensor([row.label for row in rows], dtype=torch.long)
    loader = DataLoader(TensorDataset(features[train_ids], labels[train_ids]), batch_size=128,
                        sampler=WeightedRandomSampler(weights, len(weights), replacement=True))
    head = ConfrontationHead(features.shape[1])
    optimizer = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()
    best, best_epoch, bad_epochs, history = -1.0, 0, 0, []
    selection = out / "best_confrontation_classifier_head.pt"
    for epoch in range(1, args.epochs + 1):
        head.train()
        total_loss = 0
        for x, y in loader:
            optimizer.zero_grad()
            loss = criterion(head(x), y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(y)
        val_probs = predict(head, features[val_ids])
        validation = report_metrics([rows[i] for i in val_ids], val_probs, 0.5)
        score = float(np.mean([item["f1_confronto"] for item in validation["per_dataset"].values()]))
        history.append({"epoch": epoch, "train_loss": total_loss / len(train_ids),
                        "validation_mean_dataset_f1": score, "validation": validation})
        log(f"Epoca {epoch:02d}: loss={history[-1]['train_loss']:.4f}; F1 medio validacao={score:.4f}")
        if score > best + 1e-6:
            best, best_epoch, bad_epochs = score, epoch, 0
            save_torch(selection, {"head_state_dict": head.state_dict(), "model_name": MODEL_NAME,
                "class_names": CLASS_NAMES, "input_dim": int(features.shape[1]), "hidden_dim": 512,
                "dropout": 0.3, "head_architecture": "fall_mlp_relu", "num_frames": args.num_frames,
                "view_duration_seconds": args.window_seconds, "sample_fps": (args.num_frames - 1) / args.window_seconds,
                "max_frame_side": 960, "selected_epoch": epoch, "best_val_mean_dataset_f1": score,
                "encoder_precision": "bfloat16_cuda_float32_cpu",
                "datasets": sorted({row.dataset for row in rows}), "seed": args.seed,
                "training_method": "frozen_vjepa2_mean_pool_fall_head", "manifest_sha256":
                    hashlib.sha256((out / "slices.json").read_bytes()).hexdigest()})
        else:
            bad_epochs += 1
            if bad_epochs >= args.patience:
                break
    checkpoint = torch.load(selection, weights_only=True, map_location="cpu")
    head.load_state_dict(checkpoint["head_state_dict"])
    val_probs = predict(head, features[val_ids])
    # Limiar escolhido exclusivamente na validacao: melhor F1 medio por dataset.
    val_rows = [rows[i] for i in val_ids]
    threshold_scores = [(float(t), float(np.mean([item["f1_confronto"] for item in
                        report_metrics(val_rows, val_probs, t)["per_dataset"].values()])))
                        for t in np.linspace(0.1, 0.95, 86)]
    threshold, _ = max(threshold_scores, key=lambda item: (item[1], item[0]))
    checkpoint["recommended_threshold"] = threshold
    save_torch(selection, checkpoint)
    save_json(out / "history.json", history)
    save_json(out / "threshold_selection.json", {"threshold": threshold, "scores": threshold_scores})
    save_json(out / "validation_metrics.json", report_metrics(val_rows, val_probs, threshold))
    test_ids = by_split["test"]
    test_rows = [rows[i] for i in test_ids]
    test_probs = predict(head, features[test_ids])
    test = report_metrics(test_rows, test_probs, threshold)
    save_json(out / "test_metrics.json", test)
    save_json(out / "test_metrics_argmax.json", report_metrics(test_rows, test_probs, 0.5))
    save_json(out / "test_predictions.json", [{**asdict(row), "confrontation_probability": float(prob)}
                                             for row, prob in zip(test_rows, test_probs)])
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot([item["epoch"] for item in history], [item["train_loss"] for item in history], label="Loss treino")
    axes[0].plot([item["epoch"] for item in history], [item["validation_mean_dataset_f1"] for item in history], label="F1 validacao")
    axes[0].legend()
    axes[0].set_xlabel("Epoca")
    matrix = np.array(test["window"]["confusion_matrix"])
    axes[1].imshow(matrix, cmap="Blues")
    for (i, j), value in np.ndenumerate(matrix):
        axes[1].text(j, i, str(value), ha="center", va="center", color="red")
    axes[1].set_xticks([0, 1], CLASS_NAMES)
    axes[1].set_yticks([0, 1], CLASS_NAMES)
    axes[1].set_xlabel("Predito")
    axes[1].set_ylabel("Real")
    figure.tight_layout()
    figure.savefig(out / "training_results.png", dpi=160)
    plt.close(figure)
    log(f"CONCLUIDO: epoca={best_epoch}; threshold={threshold:.2f}; teste={test['window']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=Path("var/datasets/confrontation"))
    parser.add_argument("--output-dir", type=Path, default=Path("var/training_runs/confrontation_head_v1"))
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument("--window-seconds", type=float, default=2.0)
    parser.add_argument("--feature-batch-size", type=int, default=4)
    parser.add_argument("--feature-workers", type=int, default=2)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.num_frames < 2 or args.window_seconds <= 0:
        raise ValueError("Janela de treinamento invalida")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(4)
    cv2.setNumThreads(1)
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    save_json(out / "last_execution_arguments.json", {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()})
    if (out / "slices.json").exists():
        rows = [Sample(**item) for item in json.loads((out / "slices.json").read_text(encoding="utf-8"))]
        saved_args = json.loads((out / "arguments.json").read_text(encoding="utf-8"))
        if any(saved_args[key] != getattr(args, key) for key in ("num_frames", "window_seconds", "seed")):
            raise ValueError("Parametros temporais/seed diferentes do manifesto existente")
    else:
        save_json(out / "arguments.json", {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()})
        videos = split_videos(audit_videos(collect_videos(args.dataset_root, args.seed), out), args.seed)
        rows = slice_videos(videos, args.window_seconds)
        save_json(out / "videos.json", [asdict(row) for row in videos])
        save_json(out / "slices.json", [asdict(row) for row in rows])
        save_json(out / "split_summary.json", {"videos": summarize(videos), "windows": summarize(rows)})
    log(f"Manifesto: {len(rows)} janelas; {summarize(rows)}")
    if args.prepare_only:
        return
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log(f"Device: {device}")
    train(rows, extract_features(rows, args, out, device), args, out)


if __name__ == "__main__":
    main()
