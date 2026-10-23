# Experimento de recorte pela GUI

Branch: `experiment/fall-angle-crop-gui`, criada de `origin/parameters-test`
(base `d7a35cd`). O teste fica na janela nativa de preview do monitor.

## Executar

Neste computador, o checkout do experimento fica em
`/Users/leonardocardenuto/work_disk/vard-angle-crop`. O ambiente Python e o
`.env` local sao compartilhados por links; as alteracoes em andamento no outro
checkout foram preservadas. O checkpoint V-JEPA configurado usa caminho absoluto.

```bash
cd /Users/leonardocardenuto/work_disk/vard-angle-crop
REDIS_URL='' PYTORCH_ENABLE_MPS_FALLBACK=1 .venv/bin/python -m scripts.run_fall_monitor_jobs \
  --camera-id ID_DA_CAMERA --detector fall --show-preview \
  --person-crop-model var/models/yolo11n-pose.pt \
  --log-file var/logs/recorte-pessoa.log
```

Substitua `ID_DA_CAMERA` pelo UUID da camera de teste. Esse comando usa o monitor
real: pode registrar ocorrencias e enviar notificacoes ao workspace configurado.

O controle **Recorte pessoa** inicia em **0** (frame original). Mude para **1**
para ativar; volte a **0** para comparar. A escolha pertence a essa sessao de
preview e nao e persistida no banco ou no `.env`. Fechar o preview mantem a
ultima escolha enquanto o monitor continua; reiniciar o job volta a desativar.

O YOLO de pose foi baixado para `var/models/yolo11n-pose.pt` neste checkout,
fora do Git. Em outro computador, forneca um checkpoint YOLO COCO local com
classe pessoa `0`. O monitor nao baixa pesos automaticamente quando se ativa
o controle. Instale `requirements-ml.txt` e use OpenCV com suporte a GUI.

## Comportamento

- O detector YOLO recebe todos os frames da janela, na ordem original.
- As caixas de todas as pessoas de todos os frames formam uma unica area.
- Uma margem de 25% e adicionada, limitada aos contornos da imagem.
- O mesmo recorte e aplicado em toda a sequencia, sem seguir ou girar o corpo.
- A imagem e redimensionada proporcionalmente e recebe bordas para 256 x 256.
- A janela resultante entra no V-JEPA 2 e no classificador existentes.
- Sem deteccao de pessoa, usa-se o frame original. Falhas no recorte sao
  sinalizadas no preview e no log; a inferencia continua com o frame original.

A caixa desenhada no preview corresponde a ultima janela analisada, nao a uma
deteccao em tempo real no frame atual. A legenda distingue aguardando, ligado,
sem pessoa e erro. Os logs e o payload da ocorrencia incluem `person_crop`.

Ao alternar, a confirmacao temporal de quedas e reiniciada. Resultados em voo
do modo anterior sao descartados; clipes de alertas ja confirmados terminam
normalmente. O freezing, os cooldowns, os outros detectores e os videos
originais exportados nao mudam.

## Validacao

Compare os mesmos videos e intervalos com o controle em 0 e em 1. Registre
probabilidade, acertos consecutivos, falsos positivos, quedas perdidas e atraso
de processamento. Inclua pessoas caminhando, sentando e deitando, alem de
quedas, nas varias cameras. Use dados separados do treino.

Recortar pode reduzir interferencia do fundo, mas nao converte camera de teto
em camera frontal nem garante invariancia de perspectiva. Os keypoints nao
sao fundidos ao classificador neste experimento; o modelo de pose e usado
somente pelas caixas de pessoa. Homografia, rotacao automatica e retreino
nao fazem parte desta primeira comparacao.

```bash
.venv/bin/python -m pytest tests/test_person_crop.py tests/test_detection_pipeline.py \
  tests/test_temporal_smoother.py tests/test_fall_clip_roll.py -q
```
