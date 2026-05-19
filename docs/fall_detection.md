# Inferencia de queda em camera RTSP/IP

Esta arquitetura reaproveita o pipeline atual em `tests/train_fall_classifier.py` e
`tests/predict_fall_video.py`, mas separa a inferencia continua em modulos reutilizaveis:

```text
Camera RTSP/IP ou video local
-> CameraWorker
-> FrameBuffer
-> janela amostrada com num_frames
-> FallClassifier / AutoVideoProcessor / VJEPA2Classifier
-> probabilidade de queda
-> TemporalSmoother
-> alerta
```

## Dependencias

Crie um ambiente Python e instale as dependencias de ML:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r tests/requirements.txt
```

Se for usar GPU, instale a build do PyTorch compativel com a sua versao de CUDA antes
de instalar o restante das dependencias.

## Checkpoint

O checkpoint esperado continua sendo o mesmo:

```text
best_vjepa2_fall_classifier.pt
```

Ele deve ser compativel com:

- `MODEL_NAME = "facebook/vjepa2-vitl-fpc64-256"`
- `CLASS_NAMES = ["sem_queda", "queda"]`
- `VJEPA2Classifier` definido em `tests/train_fall_classifier.py`

## Rodar com video local

Para testar o fluxo unico de uma vez, em modo clip:

```bash
python scripts/run_fall_detection.py ^
  --mode clip ^
  --source caminho\para\video.mp4 ^
  --checkpoint best_vjepa2_fall_classifier.pt ^
  --num-frames 16 ^
  --device cuda
```

Esse modo:

- abre o video;
- corta/amostra `num_frames` frames ao longo do clipe;
- passa os frames para o `AutoVideoProcessor`;
- roda a classificacao;
- imprime a classe e as probabilidades.

Se quiser avaliar apenas um trecho do video:

```bash
python scripts/run_fall_detection.py ^
  --mode clip ^
  --source caminho\para\video.mp4 ^
  --checkpoint best_vjepa2_fall_classifier.pt ^
  --num-frames 16 ^
  --start-frame 120 ^
  --end-frame 300 ^
  --device cuda
```

Para rodar inferencia continua em janelas sobre o video local:

```bash
python scripts/run_fall_detection.py ^
  --mode stream ^
  --source caminho\para\video.mp4 ^
  --checkpoint best_vjepa2_fall_classifier.pt ^
  --num-frames 16 ^
  --sample-fps 6 ^
  --stride-seconds 1 ^
  --threshold 0.75 ^
  --smoothing-window 5
```

Para validar o fluxo de captura, buffer e amostragem sem carregar o modelo:

```bash
python tests/smoke_fall_detection.py --source caminho\para\video.mp4
```

## Rodar com RTSP/IP camera

```bash
python scripts/run_fall_detection.py ^
  --mode stream ^
  --source rtsp://usuario:senha@192.168.0.10:554/stream1 ^
  --checkpoint best_vjepa2_fall_classifier.pt ^
  --num-frames 16 ^
  --sample-fps 6 ^
  --stride-seconds 1 ^
  --threshold 0.75 ^
  --smoothing-window 5 ^
  --device cuda
```

## Rodar com webcam em tempo real

Para webcam local, use o indice da camera como `--source`. Na maioria dos casos, a webcam principal e `0`.

```bash
python scripts/run_fall_detection.py ^
  --mode stream ^
  --source 0 ^
  --checkpoint best_vjepa2_fall_classifier.pt ^
  --num-frames 16 ^
  --sample-fps 6 ^
  --stride-seconds 0.5 ^
  --threshold 0.75 ^
  --smoothing-window 5 ^
  --show-preview ^
  --device cuda
```

Com `--show-preview`, a interface mostra:

- frame atual da webcam;
- classe prevista;
- probabilidade de queda;
- media movel;
- estado de alerta.

Para encerrar, pressione `q` ou `ESC` na janela.

Se a webcam nao abrir no Windows, teste explicitamente um backend:

```bash
python scripts/run_fall_detection.py ^
  --mode stream ^
  --source 0 ^
  --checkpoint best_vjepa2_fall_classifier.pt ^
  --device cuda ^
  --webcam-backend dshow
```

Ou:

```bash
python scripts/run_fall_detection.py ^
  --mode stream ^
  --source 0 ^
  --checkpoint best_vjepa2_fall_classifier.pt ^
  --device cuda ^
  --webcam-backend msmf
```

Se `--device` for omitido, o script usa CUDA quando disponivel e CPU como fallback.

## Parametros recomendados para baixo custo

- `--num-frames 16`: preserva o formato usado no treino.
- `--sample-fps 5` ou `--sample-fps 6`: reduz frames processados sem perder muita dinamica temporal.
- `--stride-seconds 1`: uma inferencia por segundo.
- `--threshold 0.75`: ponto inicial conservador para alerta.
- `--smoothing-window 5`: media movel das ultimas cinco janelas.
- `--min-consecutive-hits 2`: exige duas janelas consecutivas acima do threshold.

Em CPU, comece com `--sample-fps 5 --stride-seconds 1 --device cpu`. Em GPU, `6 FPS`
e stride de `0.5s` podem deixar o alerta mais responsivo.

## Logs

O script registra:

- conexao e reconexao da fonte de video;
- quantidade de frames capturados;
- inferencia realizada por janela;
- probabilidades por classe;
- `ALERTA_QUEDA_PROVAVEL` quando a suavizacao temporal dispara.
