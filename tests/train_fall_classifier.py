import argparse
import csv
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

import cv2
import kagglehub
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoVideoProcessor


MODEL_NAME = "facebook/vjepa2-vitl-fpc64-256"
CLASS_NAMES = ["sem_queda", "queda"]
CLASS_TO_ID = {name: idx for idx, name in enumerate(CLASS_NAMES)}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
DEFAULT_SEED = 42

# Ajuste estes aliases se o dataset do Kaggle usar nomes de pasta diferentes.
CLASS_ALIASES = {
    "queda": {
        "queda",
        "quedas",
        "fall",
        "falls",
        "falling",
        "falldown",
        "fall_down",
        "fall-detection",
    },
    "sem_queda": {
        "sem_queda",
        "semqueda",
        "no_fall",
        "nofall",
        "nonfall",
        "non_fall",
        "non-fall",
        "normal",
        "negative",
        "adl",
        "activities",
        "walking",
        "standing",
    },
}


def log(message: str):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


@dataclass(frozen=True)
class VideoSample:
    # Cada amostra representa um trecho anotado de um video, nao o video inteiro.
    video_path: str
    label: int
    start_frame: int | None = None
    end_frame: int | None = None
    group_id: str | None = None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Treina um classificador V-JEPA 2 para detectar quedas a partir de um dataset do Kaggle."
    )
    parser.add_argument(
        "--kaggle",
        required=True,
        help="URL do Kaggle ou slug no formato owner/dataset-name.",
    )
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--val-size", type=float, default=0.2)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--max-samples",
        type=int,
        default=64,
        help="Limita o total de amostras carregadas para testes rapidos. Use 0 para desabilitar.",
    )
    parser.add_argument(
        "--log-every",
        type=int,
        default=10,
        help="Mostra log a cada N batches durante treino e validacao.",
    )
    parser.add_argument(
        "--output",
        default="best_vjepa2_fall_classifier.pt",
        help="Arquivo do checkpoint salvo.",
    )
    return parser.parse_args()


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def extract_kaggle_handle(kaggle_value: str) -> str:
    kaggle_value = kaggle_value.strip()
    if re.fullmatch(r"[\w-]+/[\w-]+", kaggle_value):
        return kaggle_value

    match = re.search(r"kaggle\.com/datasets/([\w-]+/[\w-]+)", kaggle_value)
    if not match:
        raise ValueError(
            "Nao consegui extrair o dataset do Kaggle. Use uma URL valida ou owner/dataset-name."
        )
    return match.group(1)


def sample_frame_indices(start_frame: int, end_frame: int, num_frames: int) -> List[int]:
    total_frames = end_frame - start_frame + 1
    if total_frames <= 0:
        raise ValueError("Video sem frames.")

    if total_frames < num_frames:
        # Se a janela for curta, repetimos o ultimo frame para manter shape fixo.
        indices = np.linspace(start_frame, end_frame, total_frames).astype(int).tolist()
        while len(indices) < num_frames:
            indices.append(indices[-1])
        return indices[:num_frames]

    return np.linspace(start_frame, end_frame, num_frames).astype(int).tolist()


def read_video_frames_opencv(
    video_path: str,
    num_frames: int,
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> List[np.ndarray]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir o video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        raise RuntimeError(f"Video invalido ou sem frames: {video_path}")

    start_idx = 0 if start_frame is None else max(0, start_frame)
    end_idx = total_frames - 1 if end_frame is None else min(total_frames - 1, end_frame)
    if end_idx < start_idx:
        cap.release()
        raise RuntimeError(f"Janela de frames invalida em: {video_path}")

    # Amostramos ao longo da janela anotada para representar o evento inteiro.
    target_indices = sample_frame_indices(start_idx, end_idx, num_frames)

    frames = []
    for frame_idx in target_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame_bgr = cap.read()
        if not ret:
            break
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frames.append(frame_rgb)

    cap.release()

    if not frames:
        raise RuntimeError(f"Nao foi possivel extrair frames: {video_path}")

    while len(frames) < num_frames:
        frames.append(frames[-1])

    return frames[:num_frames]


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def detect_label_from_path(video_path: Path) -> str | None:
    normalized_parts = [normalize_token(part) for part in video_path.parts]
    for label, aliases in CLASS_ALIASES.items():
        normalized_aliases = {normalize_token(alias) for alias in aliases}
        if any(part in normalized_aliases for part in normalized_parts):
            return label
    return None


def find_dataset_root(download_dir: Path) -> Path:
    # Alguns datasets do Kaggle criam niveis extras de pasta ao descompactar.
    # Aqui escolhemos a raiz mais profunda que realmente contem os videos.
    directories_with_videos = {}
    for video_path in download_dir.rglob("*"):
        if video_path.suffix.lower() not in VIDEO_SUFFIXES:
            continue
        parent = video_path.parent
        directories_with_videos[parent] = directories_with_videos.get(parent, 0) + 1

    if not directories_with_videos:
        raise RuntimeError("Nenhum video encontrado no dataset baixado.")

    best_root = max(
        directories_with_videos,
        key=lambda path: (len(path.relative_to(download_dir).parts), directories_with_videos[path]),
    )
    return best_root.parent if best_root.name.startswith("chute") else best_root


def find_metadata_csv(download_dir: Path) -> Path | None:
    preferred = [
        download_dir / "data_tuple3.csv",
        download_dir.parent / "data_tuple3.csv",
    ]
    for candidate in preferred:
        if candidate.exists():
            return candidate

    matches = list(download_dir.rglob("data_tuple3.csv"))
    if matches:
        return matches[0]
    return None


def normalize_mcfd_cam(chute: int, cam_raw: str, start_frame: int, end_frame: int) -> int:
    cam = int(float(cam_raw))
    if 1 <= cam <= 8:
        return cam

    # O CSV do MCFD tem pelo menos um typo conhecido.
    if chute == 23 and cam == 55 and start_frame == 1572 and end_frame == 1602:
        log("Corrigindo typo conhecido do CSV: chute23 cam55 -> cam3")
        return 3

    raise ValueError(
        f"Valor de camera invalido no CSV: chute={chute} cam={cam_raw} start={start_frame} end={end_frame}"
    )


def collect_samples(dataset_root: Path) -> List[VideoSample]:
    samples = []
    ignored = 0

    for file_path in dataset_root.rglob("*"):
        if file_path.suffix.lower() not in VIDEO_SUFFIXES:
            continue

        label_name = detect_label_from_path(file_path)
        if label_name is None:
            ignored += 1
            continue

        samples.append(VideoSample(str(file_path), CLASS_TO_ID[label_name], group_id=str(file_path)))

    if not samples:
        raise RuntimeError(
            "Nao encontrei videos rotulados como 'queda' ou 'sem_queda'. "
            "Ajuste os aliases em CLASS_ALIASES para casar com o dataset."
        )

    print(f"Videos aceitos: {len(samples)}")
    print(f"Videos ignorados por falta de alias: {ignored}")
    return samples


def load_mcfd_samples(dataset_root: Path, metadata_path: Path) -> List[VideoSample]:
    if not metadata_path.exists():
        raise FileNotFoundError(f"CSV de anotacao nao encontrado: {metadata_path}")

    samples = []
    with metadata_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            chute = int(float(row["chute"]))
            start_frame = int(float(row["start"]))
            end_frame = int(float(row["end"]))
            cam = normalize_mcfd_cam(chute, row["cam"], start_frame, end_frame)
            label = int(float(row["label"]))

            # O CSV aponta para uma janela especifica dentro de uma camera/cena.
            video_path = dataset_root / f"chute{chute:02d}" / f"cam{cam}.avi"
            if not video_path.exists():
                raise FileNotFoundError(f"Video anotado nao encontrado: {video_path}")

            samples.append(
                VideoSample(
                    video_path=str(video_path),
                    label=label,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    group_id=f"chute{chute:02d}",
                )
            )

    log(f"Amostras anotadas carregadas do CSV: {len(samples)}")
    return samples


def split_samples(samples: Sequence[VideoSample], val_size: float, seed: int):
    groups = [sample.group_id for sample in samples]
    labels = [sample.label for sample in samples]

    if all(group is not None for group in groups):
        # Evita colocar a mesma cena em treino e validacao ao mesmo tempo.
        splitter = GroupShuffleSplit(n_splits=1, test_size=val_size, random_state=seed)
        train_idx, val_idx = next(splitter.split(samples, labels, groups))
        train_samples = [samples[i] for i in train_idx]
        val_samples = [samples[i] for i in val_idx]
        log("Split feito com GroupShuffleSplit para evitar vazamento entre cenas relacionadas.")
        return train_samples, val_samples

    train_samples, val_samples = train_test_split(
        list(samples),
        test_size=val_size,
        random_state=seed,
        stratify=labels,
    )
    log("Split feito com train_test_split estratificado.")
    return train_samples, val_samples


def maybe_limit_samples(samples: Sequence[VideoSample], max_samples: int, seed: int) -> List[VideoSample]:
    if max_samples <= 0 or len(samples) <= max_samples:
        return list(samples)

    rng = random.Random(seed)
    # Mantemos uma amostra balanceada entre classes para testes rapidos.
    by_label = {}
    for sample in samples:
        by_label.setdefault(sample.label, []).append(sample)

    limited = []
    labels = sorted(by_label)
    per_label = max_samples // len(labels)
    remainder = max_samples % len(labels)

    for idx, label in enumerate(labels):
        label_samples = list(by_label[label])
        rng.shuffle(label_samples)
        take = per_label + (1 if idx < remainder else 0)
        limited.extend(label_samples[:take])

    rng.shuffle(limited)
    log(f"Limitando dataset para teste rapido: {len(limited)} amostras")
    return limited


class VideoClassificationDataset(Dataset):
    def __init__(self, samples: Sequence[VideoSample], processor, num_frames: int):
        self.samples = list(samples)
        self.processor = processor
        self.num_frames = num_frames

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        # Lemos apenas a janela anotada do evento, nao o arquivo inteiro como um unico exemplo.
        frames = read_video_frames_opencv(
            sample.video_path,
            self.num_frames,
            start_frame=sample.start_frame,
            end_frame=sample.end_frame,
        )
        # O processor aplica resize, crop e normalizacao no formato esperado pelo checkpoint.
        inputs = self.processor(frames, return_tensors="pt")
        pixel_values = inputs["pixel_values_videos"].squeeze(0)

        return {
            "pixel_values_videos": pixel_values,
            "labels": torch.tensor(sample.label, dtype=torch.long),
            "video_path": sample.video_path,
        }


def collate_fn(batch):
    return {
        "pixel_values_videos": torch.stack([item["pixel_values_videos"] for item in batch], dim=0),
        "labels": torch.stack([item["labels"] for item in batch], dim=0),
        "video_paths": [item["video_path"] for item in batch],
    }


class VJEPA2Classifier(nn.Module):
    def __init__(self, model_name: str, num_classes: int, freeze_backbone: bool = True):
        super().__init__()
        # O V-JEPA 2 entra como encoder de video; a classificacao vem da head abaixo.
        self.backbone = AutoModel.from_pretrained(model_name)
        hidden_size = self.backbone.config.hidden_size

        # Head pequena para transformar as features do backbone em logits binarios.
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes),
        )

        if freeze_backbone:
            for param in self.backbone.parameters():
                param.requires_grad = False

    def forward(self, pixel_values_videos):
        outputs = self.backbone(pixel_values_videos=pixel_values_videos, skip_predictor=True)
        # Fazemos media dos tokens para obter uma representacao unica do clipe.
        features = outputs.last_hidden_state.mean(dim=1)
        return self.classifier(features)


def train_one_epoch(model, dataloader, optimizer, criterion, device, log_every: int):
    model.train()
    total_loss = 0.0
    total_correct = 0
    total_samples = 0

    for step, batch in enumerate(dataloader, start=1):
        pixel_values = batch["pixel_values_videos"].to(device)
        labels = batch["labels"].to(device)

        optimizer.zero_grad()
        logits = model(pixel_values)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * labels.size(0)
        preds = torch.argmax(logits, dim=1)
        total_correct += (preds == labels).sum().item()
        total_samples += labels.size(0)

        if step == 1 or step % log_every == 0 or step == len(dataloader):
            avg_loss = total_loss / total_samples
            avg_acc = total_correct / total_samples
            log(
                f"Treino batch {step}/{len(dataloader)} "
                f"loss={avg_loss:.4f} acc={avg_acc:.4f}"
            )

    return total_loss / total_samples, total_correct / total_samples


@torch.no_grad()
def evaluate(model, dataloader, criterion, device, class_names, log_every: int):
    model.eval()
    total_loss = 0.0
    total_correct = 0
    total_samples = 0
    all_labels = []
    all_preds = []

    for step, batch in enumerate(dataloader, start=1):
        pixel_values = batch["pixel_values_videos"].to(device)
        labels = batch["labels"].to(device)

        logits = model(pixel_values)
        loss = criterion(logits, labels)
        preds = torch.argmax(logits, dim=1)

        total_loss += loss.item() * labels.size(0)
        total_correct += (preds == labels).sum().item()
        total_samples += labels.size(0)
        all_labels.extend(labels.cpu().tolist())
        all_preds.extend(preds.cpu().tolist())

        if step == 1 or step % log_every == 0 or step == len(dataloader):
            avg_loss = total_loss / total_samples
            avg_acc = total_correct / total_samples
            log(
                f"Validacao batch {step}/{len(dataloader)} "
                f"loss={avg_loss:.4f} acc={avg_acc:.4f}"
            )

    print("\n=== Classification Report ===")
    print(classification_report(all_labels, all_preds, target_names=class_names, digits=4))
    print("=== Confusion Matrix ===")
    print(confusion_matrix(all_labels, all_preds))

    return total_loss / total_samples, total_correct / total_samples


def main():
    log("Iniciando script.")
    args = parse_args()
    log(f"Argumento --kaggle recebido: {args.kaggle}")
    set_seed(args.seed)
    log(f"Seed configurada: {args.seed}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    log(f"Usando device: {device}")

    kaggle_handle = extract_kaggle_handle(args.kaggle)
    log(f"Handle extraido do Kaggle: {kaggle_handle}")
    log("Iniciando download do dataset via kagglehub.")
    download_dir = Path(kagglehub.dataset_download(kaggle_handle))
    log(f"Download concluido. Arquivos em: {download_dir}")

    log("Procurando raiz com videos.")
    dataset_root = find_dataset_root(download_dir)
    log(f"Dataset localizado em: {dataset_root}")

    metadata_path = find_metadata_csv(download_dir)
    if metadata_path is not None and metadata_path.exists():
        log(f"CSV de anotacao encontrado: {metadata_path}")
        # Caminho principal para o MCFD: usar as janelas anotadas do CSV.
        log("Montando amostras a partir das janelas anotadas no CSV.")
        samples = load_mcfd_samples(dataset_root, metadata_path)
    else:
        # Fallback generico para datasets organizados por pasta/classe.
        log("CSV de anotacao nao encontrado. Voltando para inferencia por nome de pasta.")
        samples = collect_samples(dataset_root)
    samples = maybe_limit_samples(samples, args.max_samples, args.seed)
    train_samples, val_samples = split_samples(samples, val_size=args.val_size, seed=args.seed)
    log(f"Treino: {len(train_samples)} videos | Validacao: {len(val_samples)} videos")

    log(f"Carregando processor do modelo: {MODEL_NAME}")
    processor = AutoVideoProcessor.from_pretrained(MODEL_NAME)
    log("Processor carregado.")

    log("Montando datasets de treino e validacao.")
    train_dataset = VideoClassificationDataset(train_samples, processor, args.num_frames)
    val_dataset = VideoClassificationDataset(val_samples, processor, args.num_frames)
    log("Datasets montados.")

    log("Criando dataloaders.")
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        collate_fn=collate_fn,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        collate_fn=collate_fn,
    )
    log("Dataloaders prontos.")

    log(f"Carregando backbone: {MODEL_NAME}")
    model = VJEPA2Classifier(
        model_name=MODEL_NAME,
        num_classes=len(CLASS_NAMES),
        freeze_backbone=True,
    ).to(device)
    log("Modelo carregado.")

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr,
        weight_decay=1e-4,
    )
    log("Otimizador e criterio configurados.")

    best_val_acc = 0.0
    for epoch in range(args.epochs):
        log(f"Iniciando epoca {epoch + 1}/{args.epochs}")
        train_loss, train_acc = train_one_epoch(
            model, train_loader, optimizer, criterion, device, args.log_every
        )
        val_loss, val_acc = evaluate(
            model, val_loader, criterion, device, CLASS_NAMES, args.log_every
        )

        print(
            f"\n[Epoch {epoch + 1}/{args.epochs}] "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}",
            flush=True,
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), args.output)
            log(f"Melhor modelo salvo em: {args.output}")

    log("Treinamento concluido.")


if __name__ == "__main__":
    main()
