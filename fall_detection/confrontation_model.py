"""Cabeca binaria com a mesma arquitetura do classificador original de quedas."""
from torch import nn

CLASS_NAMES = ["nao_confronto", "confronto"]
MODEL_NAME = "facebook/vjepa2-vitl-fpc64-256"


class ConfrontationHead(nn.Sequential):
    def __init__(self, input_dim: int = 1024, hidden_dim: int = 512, dropout: float = 0.3):
        super().__init__(
            nn.Linear(input_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout), nn.Linear(hidden_dim, 2)
        )
