# Experimento de recorte pela GUI

Branch: `experiment/fall-angle-crop-gui`, atualizada com `origin/parameters-test`
(`43f02da`). O teste fica no launcher grafico e na janela nativa do monitor.

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
em camera frontal nem garante invariancia de perspectiva. Homografia, rotacao
automatica e retreino nao fazem parte deste experimento.

## Pose temporal auxiliar

Abra `Iniciar Inferencias.command` ou execute
`.venv/bin/python -m scripts.inference_launcher`. Na secao **Quedas - YOLO
auxiliar**, configure recorte, modelo de pose, modo e peso maximo.
As opcoes sao aplicadas ao iniciar/reiniciar o processo de quedas. O preview
permite alternar somente o recorte durante a execucao; o modo de pose continua
o escolhido no launcher. Confrontos nao recebem esses parametros.

- **Desligada**: apenas JEPA (e recorte, se ativado).
- **So observar**: calcula as medidas sem alterar a decisao do JEPA. Comece
  por esse modo para comparar os sinais.
- **Assistir JEPA**: ajusta o score de decisao em ate 0.10 (10 pontos
  percentuais), conforme o peso escolhido, usando a evidencia temporal.

O YOLO e executado uma vez por frame, compartilhado entre recorte e pose.
O recorte pode ficar desligado mesmo com a pose ligada. A probabilidade bruta
permanece em `fall_probability`; o score ajustado alimenta a confirmacao
temporal somente no modo `assist`. O ajuste e uma heuristica experimental,
nao uma probabilidade calibrada ou um classificador de pose treinado.

A pose exige ombros e quadris com confianca >= 0.5, ao menos quatro amostras,
75% de cobertura, duracao >= 0.5s e ausencia de lacunas grandes. Uma janela com
mais de uma pessoa nao recebe assistencia, pois o rastreamento de identidade
ainda nao foi validado. Mudancas excessivas de escala desativam o sinal.
YOLO sem keypoints serve ao recorte, mas nao a assistencia de pose.

As medidas sao descida e velocidade do quadril em comprimentos de tronco,
mudanca de orientacao do tronco e persistencia de postura baixa. A descida e
projetada no eixo inicial do tronco, reduzindo dependencia de rotacao fisica
da camera. Isso nao elimina os efeitos de perspectiva.

Em `assist`, o ajuste so ocorre quando o JEPA produz valor >= 0.5, < 0.95 e
esta a ate 0.15 do limiar configurado. As tres pistas precisam concordar para
produzir evidencia positiva forte. Evidencia fraca pode reduzir o score nessa
faixa: isso pode reduzir falsos alertas, mas tambem perder quedas. Valide com
videos anotados antes do uso habitual. Pose ausente, nao confiavel ou falha
no YOLO mantem o JEPA original.

O preview mostra pontos da ultima janela analisada (nao do frame ao vivo),
JEPA bruto, score de decisao e medidas. Logs e payload das ocorrencias incluem
`pose_assistance` com confiabilidade, motivo, medidas, peso e ajuste. Videos
originais e freezing permanecem inalterados.

Validacao local desta implementacao: testes sinteticos cobrem queda, sentar,
rotacao fisica da camera, escala, chaves ausentes, lacunas e limites do ajuste.
O launcher abriu com os controles dentro da janela. No video local
`chute22_fall_cam7.mp4`, a pose nao atingiu cobertura suficiente e a assistencia
foi desativada; isso nao demonstra ganho de precisao. A comparacao quantitativa
JEPA versus JEPA assistido em videos anotados ainda esta pendente.

```bash
.venv/bin/python -m scripts.run_fall_monitor_jobs --camera-id ID_DA_CAMERA \
  --detector fall --show-preview --person-crop \
  --person-crop-model var/models/yolo11n-pose.pt \
  --pose-mode observe --pose-weight 0.05
```

```bash
.venv/bin/python -m pytest tests/test_person_crop.py tests/test_pose_assistance.py \
  tests/test_detection_pipeline.py tests/test_inference_launcher.py \
  tests/test_temporal_smoother.py tests/test_fall_clip_roll.py -q
```
