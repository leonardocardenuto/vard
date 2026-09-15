import argparse
import json
import pickle
import time
from pathlib import Path

import kagglehub
import numpy as np
import torch
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from transformers import AutoModel, AutoVideoProcessor

from train_fall_classifier import (
    CLASS_NAMES,
    CLASS_TO_ID,
    DEFAULT_MODEL_NAME,
    extract_kaggle_handle,
    get_torch_device,
    load_samples_from_root,
    log,
    read_video_frames_opencv,
    set_seed,
    split_samples,
    summarize_samples,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Treina um detector de queda leve sobre embeddings congelados do V-JEPA 2."
    )
    parser.add_argument("--kaggle", action="append", default=[])
    parser.add_argument("--local-dataset", action="append", default=[])
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument("--val-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cache", default="fall_vjepa2_embeddings.npz")
    parser.add_argument(
        "--input-cache",
        action="append",
        default=[],
        help="Cache .npz de embeddings ja extraidos. Pode repetir para treinar combinando datasets.",
    )
    parser.add_argument("--output", default="best_fall_embedding_classifier.pkl")
    parser.add_argument("--threshold-min-recall", type=float, default=0.9)
    args = parser.parse_args()
    if not args.input_cache and not args.kaggle and not args.local_dataset:
        parser.error("Informe pelo menos um --input-cache, --kaggle ou --local-dataset.")
    return args


def load_all_samples(args):
    samples = []
    for kaggle_value in args.kaggle:
        kaggle_handle = extract_kaggle_handle(kaggle_value)
        log(f"[{kaggle_handle}] Baixando/carregando via kagglehub.")
        download_dir = Path(kagglehub.dataset_download(kaggle_handle))
        samples.extend(load_samples_from_root(download_dir, source=kaggle_handle))

    for local_value in args.local_dataset:
        samples.extend(load_samples_from_root(Path(local_value), source=local_value))

    summarize_samples(samples, "Dataset bruto")
    return samples


@torch.no_grad()
def embed_sample(model, processor, sample, num_frames: int, device: str) -> np.ndarray:
    frames = read_video_frames_opencv(
        sample.video_path,
        num_frames=num_frames,
        start_frame=sample.start_frame,
        end_frame=sample.end_frame,
    )
    inputs = processor(frames, return_tensors="pt")
    pixel_values = inputs["pixel_values_videos"].to(device)
    outputs = model(pixel_values_videos=pixel_values, skip_predictor=True)
    tokens = outputs.last_hidden_state
    mean_features = tokens.mean(dim=1)
    max_features = tokens.max(dim=1).values
    features = torch.cat([mean_features, max_features], dim=1)
    return features.squeeze(0).cpu().numpy().astype(np.float32)


def build_or_load_embeddings(args, train_samples, val_samples):
    if args.input_cache:
        train_features = []
        train_labels = []
        val_features = []
        val_labels = []
        for input_cache in args.input_cache:
            cache_path = Path(input_cache)
            cached = np.load(cache_path, allow_pickle=True)
            log(f"Embeddings carregados do cache de entrada: {cache_path}")
            train_features.append(cached["x_train"])
            train_labels.append(cached["y_train"])
            val_features.append(cached["x_val"])
            val_labels.append(cached["y_val"])
        return (
            np.concatenate(train_features, axis=0),
            np.concatenate(train_labels, axis=0),
            np.concatenate(val_features, axis=0),
            np.concatenate(val_labels, axis=0),
        )

    cache_path = Path(args.cache)
    if cache_path.exists():
        cached = np.load(cache_path, allow_pickle=True)
        log(f"Embeddings carregados do cache: {cache_path}")
        return (
            cached["x_train"],
            cached["y_train"],
            cached["x_val"],
            cached["y_val"],
        )

    device = get_torch_device()
    log(f"Usando device para embeddings: {device}")
    log(f"Carregando processor/modelo: {args.model_name}")
    processor = AutoVideoProcessor.from_pretrained(args.model_name)
    model = AutoModel.from_pretrained(args.model_name).to(device)
    model.eval()

    def embed_many(samples, title):
        embeddings = []
        labels = []
        for idx, sample in enumerate(samples, start=1):
            embeddings.append(embed_sample(model, processor, sample, args.num_frames, device))
            labels.append(sample.label)
            if idx == 1 or idx % 25 == 0 or idx == len(samples):
                log(f"{title}: embeddings {idx}/{len(samples)}")
        return np.stack(embeddings), np.array(labels, dtype=np.int64)

    x_train, y_train = embed_many(train_samples, "Treino")
    x_val, y_val = embed_many(val_samples, "Validacao")
    np.savez_compressed(
        cache_path,
        x_train=x_train,
        y_train=y_train,
        x_val=x_val,
        y_val=y_val,
    )
    log(f"Embeddings salvos em: {cache_path}")
    return x_train, y_train, x_val, y_val


def candidate_models(seed: int):
    return {
        "logreg_balanced": make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=0.2,
                class_weight="balanced",
                max_iter=3000,
                random_state=seed,
            ),
        ),
        "svc_rbf_balanced": make_pipeline(
            StandardScaler(),
            SVC(
                C=1.0,
                gamma="scale",
                class_weight="balanced",
                probability=True,
                random_state=seed,
            ),
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=600,
            max_features="sqrt",
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=600,
            max_features="sqrt",
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=250,
            learning_rate=0.04,
            l2_regularization=0.1,
            random_state=seed,
        ),
    }


def predict_fall_prob(model, x):
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x)[:, CLASS_TO_ID["queda"]]
    scores = model.decision_function(x)
    return 1.0 / (1.0 + np.exp(-scores))


def find_threshold(y_true, fall_probs, min_recall: float):
    best = None
    for threshold in np.linspace(0.05, 0.95, 91):
        preds = np.where(fall_probs >= threshold, CLASS_TO_ID["queda"], CLASS_TO_ID["sem_queda"])
        report = classification_report(
            y_true,
            preds,
            target_names=CLASS_NAMES,
            output_dict=True,
            zero_division=0,
        )
        metrics = report["queda"]
        score = metrics["f1-score"]
        if metrics["recall"] < min_recall:
            score -= 1.0
        candidate = (
            score,
            metrics["f1-score"],
            metrics["precision"],
            metrics["recall"],
            float(threshold),
            preds,
            report,
        )
        if best is None or candidate[:4] > best[:4]:
            best = candidate
    return best


def main():
    args = parse_args()
    set_seed(args.seed)
    train_samples = []
    val_samples = []
    if not args.input_cache:
        samples = load_all_samples(args)
        train_samples, val_samples = split_samples(samples, val_size=args.val_size, seed=args.seed)
        summarize_samples(train_samples, "Treino")
        summarize_samples(val_samples, "Validacao")
    x_train, y_train, x_val, y_val = build_or_load_embeddings(args, train_samples, val_samples)
    log(
        "Embeddings finais: "
        f"treino={x_train.shape} classes={dict(zip(*np.unique(y_train, return_counts=True)))} | "
        f"validacao={x_val.shape} classes={dict(zip(*np.unique(y_val, return_counts=True)))}"
    )

    best_result = None
    for name, model in candidate_models(args.seed).items():
        log(f"Treinando classificador: {name}")
        model.fit(x_train, y_train)
        fall_probs = predict_fall_prob(model, x_val)
        result = find_threshold(y_val, fall_probs, args.threshold_min_recall)
        _, f1, precision, recall, threshold, preds, report = result
        print(f"\n=== {name} ===")
        print(f"threshold={threshold:.2f} precision={precision:.4f} recall={recall:.4f} f1={f1:.4f}")
        print(classification_report(y_val, preds, target_names=CLASS_NAMES, digits=4, zero_division=0))
        print(confusion_matrix(y_val, preds))
        comparable = (f1, recall, precision)
        if best_result is None or comparable > best_result["comparable"]:
            best_result = {
                "name": name,
                "model": model,
                "threshold": threshold,
                "report": report,
                "confusion_matrix": confusion_matrix(y_val, preds).tolist(),
                "comparable": comparable,
            }

    payload = {
        "model": best_result["model"],
        "metadata": {
            "model_type": "vjepa2_embedding_sklearn",
            "classifier": best_result["name"],
            "backbone": args.model_name,
            "num_frames": args.num_frames,
            "class_names": CLASS_NAMES,
            "threshold": best_result["threshold"],
            "metrics": best_result["report"]["queda"],
            "confusion_matrix": best_result["confusion_matrix"],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "kaggle": args.kaggle,
            "local_dataset": args.local_dataset,
            "input_cache": args.input_cache,
        },
    }
    with Path(args.output).open("wb") as f:
        pickle.dump(payload, f)
    metadata_path = Path(args.output).with_suffix(".json")
    metadata_path.write_text(json.dumps(payload["metadata"], indent=2), encoding="utf-8")
    log(f"Melhor classificador salvo em: {args.output}")
    log(f"Metadata salva em: {metadata_path}")


if __name__ == "__main__":
    main()
