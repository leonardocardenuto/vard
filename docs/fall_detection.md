# Deteccao de queda no VARD

Este documento descreve como a deteccao de queda funciona no codigo atual do projeto, cobrindo:

- treinamento e formato do modelo;
- pipeline de inferencia em arquivo, webcam e stream;
- suavizacao temporal e criterio de alerta;
- blocos prontos para exportar clipe e criar notificacao;
- integracao com backend e app;
- limites importantes do que ja esta conectado e do que ainda esta desacoplado.

## Resumo executivo

Hoje a deteccao de queda existe como um pipeline Python reutilizavel dentro de `fall_detection/` e um ponto de entrada de execucao em `scripts/run_fall_detection.py`.

O fluxo principal em tempo real e:

```text
fonte de video
-> CameraWorker
-> FrameBuffer
-> recorte temporal de uma janela
-> amostragem de 16 frames
-> AutoVideoProcessor
-> backbone V-JEPA 2 + classificador
-> probabilidade de "queda"
-> TemporalSmoother
-> alerta logico
```

Importante:

- o detector funciona hoje como script local/servico Python;
- o backend FastAPI ja possui cadastro de cameras, geracao de stream HLS e cadastro de notificacoes;
- existem modulos prontos para exportar clipe e enviar `fall_detected` para a API;
- porem, no estado atual do codigo, o script de deteccao continua ainda nao chama automaticamente `ClipExporter` nem `NotificationSender`;
- em outras palavras: a deteccao em si esta implementada, mas o disparo automatico do alerta dentro do produto ainda precisa de orquestracao adicional.

## Onde cada parte mora

### Nucleo da deteccao

- `fall_detection/config.py`: parametros centrais do pipeline.
- `fall_detection/camera_worker.py`: captura frames de arquivo, webcam ou stream RTSP/HTTP/HTTPS.
- `fall_detection/frame_buffer.py`: buffer circular com timestamp e amostragem temporal.
- `fall_detection/inference.py`: carregamento do modelo e inferencia.
- `fall_detection/temporal_smoother.py`: suavizacao e regra de disparo do alerta.
- `fall_detection/clip_exporter.py`: gera MP4 a partir dos frames do buffer.
- `fall_detection/notifications.py`: envia evento `fall_detected` para a API.

### Entrada de execucao

- `scripts/run_fall_detection.py`: CLI principal para modo `clip` e `stream`.
- `tests/smoke_fall_detection.py`: smoke test do fluxo de captura + buffer sem carregar modelo.

### Origem do modelo

- `tests/train_fall_classifier.py`: define classes, leitura de video, backbone e treino.

### Backend e app ligados ao dominio

- `api/routers/cameras.py`: CRUD de cameras e ping de conectividade.
- `api/services/camera_streams.py`: sobe `ffmpeg` para converter a camera em HLS.
- `api/routers/camera_streams.py`: endpoint para iniciar/parar stream HLS.
- `api/routers/notifications.py`: cria/lista notificacoes e envia push via OneSignal.
- `api/models/notifications.py`: persistencia das notificacoes.
- `app/src/views/settings/components/CameraSettingsPanel.tsx`: lista cameras e abre visualizacao ao vivo.
- `app/src/views/settings/pages/CameraLiveViewScreen.tsx`: exibe stream HLS ou webview local.
- `app/src/views/insights/pages/Insights.tsx`: agrega notificacoes por camera e periodo.

## Base de ML: como o modelo foi pensado

O ponto de partida esta em `tests/train_fall_classifier.py`.

### Classes

O problema e binario:

- `sem_queda`
- `queda`

O codigo assume essa ordem em `CLASS_NAMES = ["sem_queda", "queda"]`.

### Backbone

O backbone padrao e:

```text
facebook/vjepa2-vitl-fpc64-256
```

Esse backbone e carregado com `transformers.AutoModel` e processado com `AutoVideoProcessor`.

### Estrategia de treino

No treino, o V-JEPA 2 atua como encoder de video. Sobre a saida dele, o projeto aplica uma head rasa:

```text
Linear(hidden_size -> 512)
ReLU
Dropout(0.3)
Linear(512 -> 2)
```

No `forward`, o codigo faz media dos tokens temporais/espaciais:

```text
last_hidden_state.mean(dim=1)
```

Essa representacao agregada do clipe e a entrada da head classificadora.

### Como os frames de treino sao lidos

O treino usa `read_video_frames_opencv(...)`:

- abre o video com OpenCV;
- define uma janela entre `start_frame` e `end_frame`;
- escolhe `num_frames` indices igualmente espacados;
- le somente esses frames;
- converte BGR para RGB;
- repete o ultimo frame se a janela tiver menos frames que o esperado.

Isso e importante porque a inferencia online tenta reproduzir a mesma ideia: sempre entregar ao classificador um lote fixo de frames representando um trecho curto do movimento.

## Tipos de checkpoint aceitos na inferencia

O classificador em `fall_detection/inference.py` aceita dois formatos.

### 1. Checkpoint PyTorch `.pt`

Esse e o formato salvo pelo treino tradicional da head do classificador.

Fluxo:

- instancia `VJEPA2Classifier`;
- carrega `state_dict`;
- roda logits;
- aplica `softmax`.

### 2. Checkpoint `joblib`/scikit-learn `.pkl`

Tambem existe suporte a um pipeline baseado em embeddings.

Fluxo:

- carrega um dicionario via `joblib.load`;
- espera a chave `model`;
- carrega o backbone com `AutoModel`;
- extrai embeddings com `skip_predictor=True`;
- faz pooling `mean` ou `mean_std`;
- envia features para um pipeline sklearn.

O repositorio ja contem um checkpoint desse tipo:

```text
fall_detection/best_fall_embedding_classifier_all.pkl
```

Isso significa que o codigo atual de inferencia e mais flexivel do que a documentacao antiga sugeria: ele nao depende exclusivamente de `best_vjepa2_fall_classifier.pt`.

## Configuracao central do pipeline

`FallDetectionConfig`, em `fall_detection/config.py`, concentra os parametros mais importantes:

- `checkpoint`: arquivo do modelo.
- `num_frames`: quantidade de frames entregue por inferencia. Padrao `16`.
- `sample_fps`: taxa de amostragem logica do pipeline. Padrao `6.0`.
- `stride_seconds`: intervalo minimo entre inferencias consecutivas. Padrao `1.0`.
- `threshold`: limiar da probabilidade de queda. Padrao `0.75`.
- `smoothing_window`: tamanho da media movel. Padrao `5`.
- `min_consecutive_hits`: hits consecutivos acima do limiar para alertar. Padrao `2`.
- `buffer_seconds`: quantos segundos de historico manter no buffer. Padrao `8.0`.
- `device`: `cuda`, `cpu` ou autodetectado.

A propriedade `buffer_max_frames` calcula o tamanho do buffer circular:

```text
max(num_frames, int(buffer_seconds * sample_fps) + num_frames)
```

Isso garante historico suficiente para montar uma janela completa, mesmo enquanto o buffer ainda esta enchendo.

## Captura de video: `CameraWorker`

`CameraWorker` e o modulo de ingestao do video.

### Fontes aceitas

Ele aceita:

- caminho para arquivo local;
- indice numerico de webcam;
- URLs `rtsp://`, `rtmp://`, `http://` e `https://`.

Se a URL tiver usuario e senha com caracteres especiais, o pipeline normaliza essas credenciais antes de abrir o stream. Isso evita falhas com senhas contendo, por exemplo, `%`, `@`, espaco ou `^`.

### Comportamento por tipo de fonte

#### Arquivo local

- valida se o arquivo existe;
- abre com `cv2.VideoCapture`;
- le ate o fim;
- ao terminar, encerra o loop.

#### Webcam

Para webcam no Windows, o codigo tenta abrir na ordem:

1. `DirectShow`
2. `Media Foundation`
3. backend padrao do OpenCV

Tambem e possivel forcar `dshow` ou `msmf` pela CLI.

#### Stream RTSP/HTTP/HTTPS

Para streams, quando uma leitura falha:

- o worker nao termina imediatamente;
- ele faz `release()` da captura;
- espera `reconnect_delay`;
- tenta reconectar;
- opcionalmente para apos `max_reconnect_attempts`.

### Controle da taxa de captura

Mesmo que a fonte entregue muito mais frames, o worker so emite um frame quando respeita:

```text
min_interval = 1 / sample_fps
```

Na pratica:

- a camera pode estar em 25 FPS ou 30 FPS;
- o detector pode consumir so 6 FPS;
- isso reduz custo computacional sem quebrar a entrada esperada pelo modelo.

### Saida produzida

O generator `frames()` retorna:

- `frame_rgb`
- `timestamp` em `time.monotonic()`

O uso de `monotonic()` evita problemas se o relogio do sistema variar durante a execucao.

## Buffer temporal: `FrameBuffer`

`FrameBuffer` guarda os frames recentes junto com seus timestamps.

### Estrutura

Cada item armazenado e um `BufferedFrame`:

- `frame`
- `timestamp`

Internamente, o buffer usa `collections.deque(maxlen=...)`, entao ele funciona como uma fila circular:

- frames antigos sao descartados automaticamente;
- o uso de memoria fica limitado.

### Como a janela para inferencia e montada

O metodo `sample_window(num_frames, sample_fps, end_timestamp)`:

1. calcula quanto tempo a janela deve cobrir:

```text
window_seconds = (num_frames - 1) / sample_fps
```

2. define o inicio temporal:

```text
start_ts = end_ts - window_seconds
```

3. filtra os frames do buffer entre `start_ts` e `end_ts`;
4. reamostra esse subconjunto com distribuicao uniforme;
5. garante exatamente `num_frames` saidas.

### Por que isso importa

Se `num_frames = 16` e `sample_fps = 6`, cada inferencia representa aproximadamente:

```text
(16 - 1) / 6 = 2.5 segundos
```

Ou seja, cada predicao nao olha para um frame isolado, mas para cerca de 2,5 segundos de contexto visual.

## Inferencia: `FallClassifier`

`FallClassifier` e o coracao da previsao.

### Preparacao do ambiente

Antes de carregar o modelo, o codigo prepara um cache local em:

```text
.cache/huggingface
```

Isso evita depender do cache global do usuario e reduz problemas de permissao.

### Dependencia do treino

O arquivo de inferencia importa alguns simbolos do script de treino:

- `CLASS_NAMES`
- `MODEL_NAME`
- `VJEPA2Classifier`
- `read_video_frames_opencv`

Isso garante consistencia entre treino e inferencia, mas tambem cria um acoplamento importante:

- a inferencia depende da estrutura do script em `tests/train_fall_classifier.py`;
- se esse script mudar de forma incompatível, a inferencia pode quebrar.

### Fluxo de `predict_frames`

Quando recebe uma sequencia de frames:

1. valida que a lista nao esta vazia;
2. passa os frames para `AutoVideoProcessor`;
3. obtém `pixel_values_videos`;
4. executa o modelo, em um dos dois modos:
   - `torch_head`
   - `embedding_sklearn`
5. monta um dicionario `probabilities`;
6. extrai `fall_probability`;
7. retorna:
   - `predicted_class`
   - `probabilities`
   - `fall_probability`

### Como `fall_probability` e escolhido

O codigo primeiro tenta achar a classe chamada exatamente `queda`.

Se nao encontrar, faz fallback para a ultima probabilidade do vetor. Isso permite algum grau de tolerancia a checkpoints que tragam metadados diferentes, mas a expectativa real do projeto continua sendo o rotulo `queda`.

## Regra de alerta: `TemporalSmoother`

O objetivo do `TemporalSmoother` e evitar que uma unica predicao ruidosa gere um alerta falso.

### Estado interno

Ele mantem:

- uma deque com as ultimas probabilidades;
- um contador de hits consecutivos acima do limiar.

### Entrada

A cada nova inferencia, recebe `fall_probability`.

O valor e truncado para o intervalo `[0, 1]`.

### Condicoes de alerta

O alerta dispara se acontecer uma destas condicoes:

1. `consecutive_hits >= min_consecutive_hits`
2. a janela de suavizacao estiver cheia e a media movel estiver acima do `threshold`

Com os padroes atuais:

- `threshold = 0.75`
- `smoothing_window = 5`
- `min_consecutive_hits = 2`

isso significa que o sistema alerta quando:

- duas inferencias seguidas passam de `0.75`; ou
- as ultimas cinco inferencias, em media, passam de `0.75`.

### Efeito pratico

Essa combinacao tenta equilibrar:

- rapidez de resposta para uma queda clara;
- resistencia a ruído em movimentos bruscos isolados.

## Modos de execucao em `scripts/run_fall_detection.py`

O script principal oferece dois modos.

### Modo `clip`

Serve para processar um arquivo de video de forma pontual.

#### `clip` simples

O script:

- abre o arquivo;
- extrai `num_frames` igualmente espacados no intervalo informado;
- roda uma unica inferencia;
- imprime classe e probabilidades.

#### `clip` com janelas deslizantes

Com `--sliding-windows`, o script:

- le FPS real do video;
- define uma serie de janelas sobre o arquivo;
- roda uma inferencia para cada janela;
- passa cada `fall_probability` pelo `TemporalSmoother`;
- imprime tempo, frames, classe, probabilidade, media e estado de alerta.

Esse modo e util para auditar um video inteiro e entender em quais trechos o detector reagiu.

### Modo `stream`

Esse e o modo de deteccao continua.

Fluxo:

1. cria `CameraWorker`;
2. cria `FrameBuffer`;
3. cria `TemporalSmoother`;
4. entra num loop de captura;
5. adiciona cada frame ao buffer;
6. respeita `stride_seconds` para nao inferir toda hora;
7. pede ao buffer uma janela amostrada;
8. so infere quando existir uma janela completa;
9. roda o classificador;
10. atualiza a suavizacao;
11. registra o resultado em log;
12. se houver alerta, registra `ALERTA_QUEDA_PROVAVEL`.

### Preview visual

Com `--show-preview`, o script abre uma janela OpenCV com overlay contendo:

- status `Monitorando` ou `ALERTA: queda provavel`;
- classe prevista;
- probabilidade de queda;
- media movel;
- hits consecutivos.

## Como a janela deslizante e calculada

Ha dois mecanismos parecidos, mas em contextos diferentes.

### 1. Em arquivo de video com `predict_video_windows`

Nesse caso o codigo usa o FPS real do arquivo.

Ele calcula:

- `window_span_frames`: tamanho da janela no video real;
- `stride_frames`: salto entre janelas.

Assim, mesmo que o video original esteja em outra taxa de FPS, a janela final ainda tenta representar o equivalente temporal esperado por `num_frames` e `sample_fps`.

### 2. Em stream com `FrameBuffer.sample_window`

Nesse caso o pipeline nao depende do FPS real da camera. Ele trabalha sobre:

- frames efetivamente emitidos pelo `CameraWorker`;
- timestamps monotônicos desses frames;
- uma janela temporal de aproximadamente `2.5s` com os parametros padrao.

Esse desenho deixa o detector mais robusto a cameras com FPS variavel.

## Exportacao de clipe: bloco pronto, mas ainda nao ligado

`fall_detection/clip_exporter.py` existe para transformar os frames armazenados no buffer em um MP4.

### O que ele faz

`ClipExporter.export_mp4(...)`:

- recebe uma lista de `BufferedFrame`;
- cria um arquivo MP4 temporario;
- preserva o tamanho do primeiro frame;
- redimensiona frames divergentes, se necessario;
- converte RGB para BGR antes de escrever com OpenCV;
- devolve:
  - caminho do arquivo;
  - quantidade de frames;
  - duracao;
  - FPS;
  - MIME type.

### Payload pronto para API

`ClipExportResult.to_payload()` le o arquivo e devolve um dicionario com:

- `content_base64`
- `mime_type`
- `filename`
- `frame_count`
- `duration_seconds`
- `fps`
- `size_bytes`

Esse formato foi claramente preparado para ser embutido em `Notification.payload`.

### Estado atual

Apesar disso, nao ha chamada para `ClipExporter` em `scripts/run_fall_detection.py`.

Entao, hoje:

- o buffer guarda frames suficientes para gerar um clipe;
- o exportador existe;
- mas o clipe ainda nao e produzido automaticamente quando o alerta dispara.

## Envio de notificacao: bloco pronto, mas ainda nao ligado

`fall_detection/notifications.py` define:

- `NotificationConfig`
- `NotificationSender`

### Como o envio funciona

`send_fall_detected(payload)` monta um POST autenticado para a API com:

- `workspace_id`
- `camera_id`
- `notification_type = "fall_detected"`
- `severity = "critical"`
- `title`
- `body`
- `payload`
- `created_by`

Se a API responder com status 2xx, retorna `True`. Caso contrario, registra erro e retorna `False`.

### Estado atual

Esse modulo tambem nao esta sendo invocado pelo script principal de deteccao.

Logo, o sistema ja tem:

- formato de notificacao;
- endpoint de backend;
- push via OneSignal;

mas ainda falta conectar o momento do `smoothing.alert == True` ao envio automatico da notificacao.

## Backend: como cameras e notificacoes funcionam hoje

Mesmo que o detector ainda nao esteja embutido na API, o backend ja implementa o restante do fluxo operacional.

### Cameras

`api/routers/cameras.py` oferece:

- listar cameras por workspace;
- criar camera;
- obter camera;
- atualizar camera;
- remover camera;
- ping de conectividade.

O ping:

- usa HTTP para URLs `http/https`;
- usa `socket.create_connection` para RTSP e demais casos;
- atualiza `camera.status` para `online` ou `offline`.

### Stream ao vivo

`api/services/camera_streams.py` sobe um processo `ffmpeg` por camera para converter a origem em HLS.

O endpoint `POST /camera-streams/{camera_id}/hls`:

- garante que a camera existe;
- inicia ou reutiliza o processo `ffmpeg`;
- espera o playlist `index.m3u8` ficar disponivel;
- retorna `playlist_url`.

Isso nao e a deteccao de queda em si. E a infraestrutura de visualizacao ao vivo da camera.

### Notificacoes

`api/routers/notifications.py` recebe notificacoes e salva em banco.

Depois de persistir:

- busca membros ativos do workspace com `onesignal_subscription_id`;
- envia push via `send_push_to_subscription_ids(...)`.

Ou seja, se o detector chamar a API corretamente, o backend ja consegue:

- armazenar o incidente;
- alimentar a tela de insights;
- disparar push para os usuarios.

## App mobile/web: como isso aparece hoje

### Ajustes / cameras

Em `CameraSettingsPanel.tsx`, o app:

- resolve o workspace ativo;
- lista cameras;
- pinga cada camera;
- mostra status `Conectada` ou `Desconectada`;
- inicia a visualizacao ao vivo ao tocar na camera.

Se a camera usa RTSP/HTTP convertido para HLS:

- o app chama `startCameraHlsStream(...)`;
- navega para `CameraLiveViewScreen`;
- reproduz o `playlist_url`.

### Tela de visualizacao ao vivo

`CameraLiveViewScreen.tsx` so exibe o stream:

- via `expo-video` quando o protocolo e HLS;
- via `WebView` quando a camera e `local-webview`.

Nao ha overlay de deteccao nessa tela.

### Insights

`Insights.tsx` nao executa visao computacional.

Ela:

- lista cameras;
- lista notificacoes do workspace;
- filtra por periodo e camera;
- conta incidentes;
- agrega por sala/camera;
- exporta CSV.

Isso significa que a parte de analytics do app ja esta preparada para consumir notificacoes de queda, desde que elas sejam realmente criadas no backend.

## O que de fato acontece hoje em uma execucao completa

Se voce rodar:

```bash
python scripts/run_fall_detection.py --mode stream --source 0 --checkpoint fall_detection/best_fall_embedding_classifier_all.pkl
```

o que acontece e:

1. a webcam/video/stream e aberta;
2. frames sao coletados em RGB numa taxa controlada;
3. o buffer circular guarda historico recente;
4. a cada `stride_seconds`, o sistema tenta montar uma janela completa;
5. quando consegue, roda inferencia;
6. o resultado vira `fall_probability`;
7. a suavizacao avalia se aquilo ja configura alerta;
8. o script escreve logs informativos;
9. se houver alerta, ele apenas registra `ALERTA_QUEDA_PROVAVEL` no log.

No estado atual, ele nao:

- cria notificacao automaticamente;
- exporta clipe automaticamente;
- altera estado de camera no backend;
- injeta resultado na UI em tempo real.

## Parametros padrao e sua interpretacao pratica

Com os valores padrao:

- `num_frames = 16`
- `sample_fps = 6`
- `stride_seconds = 1`
- `threshold = 0.75`
- `smoothing_window = 5`
- `min_consecutive_hits = 2`
- `buffer_seconds = 8`

temos aproximadamente:

- uma inferencia por segundo;
- cada inferencia olhando para cerca de `2.5s` de historico;
- buffer com historico suficiente para recuperar a janela recente;
- alerta rapido quando duas janelas seguidas passam de `0.75`;
- fallback mais conservador pela media movel das ultimas cinco janelas.

## Limites e pontos de atencao do desenho atual

### 1. O detector depende do script de treino

`inference.py` importa simbolos diretamente de `tests/train_fall_classifier.py`.

Isso e pratico para manter consistencia, mas ruim para isolamento de producao.

### 2. Nao existe servico daemon integrado ao backend

O detector roda como script/CLI. A API nao sobe automaticamente um worker de deteccao por camera.

### 3. Alerta ainda e local ao processo

O evento de alerta existe hoje como decisao logica em memoria e como mensagem de log.

### 4. Clip e notificacao ainda nao entram no fluxo principal

Os blocos estao prontos, mas faltam as chamadas no momento do alerta.

### 5. A UI so consome incidentes persistidos

O app mostra notificacoes e stream, mas nao exibe inferencia bruta nem probabilidade em tempo real.

## Como validar rapidamente o funcionamento

### Smoke test sem modelo

Valida captura e buffer:

```bash
python tests/smoke_fall_detection.py --source caminho\para\video.mp4
```

### Inferencia unica em arquivo

```bash
python scripts/run_fall_detection.py ^
  --mode clip ^
  --source caminho\para\video.mp4 ^
  --checkpoint fall_detection\best_fall_embedding_classifier_all.pkl
```

### Analise por janelas deslizantes

```bash
python scripts/run_fall_detection.py ^
  --mode clip ^
  --sliding-windows ^
  --source caminho\para\video.mp4 ^
  --checkpoint fall_detection\best_fall_embedding_classifier_all.pkl ^
  --sample-fps 6 ^
  --stride-seconds 1
```

### Deteccao continua com preview

```bash
python scripts/run_fall_detection.py ^
  --mode stream ^
  --source 0 ^
  --checkpoint fall_detection\best_fall_embedding_classifier_all.pkl ^
  --show-preview
```

## Conclusao

No codigo atual, a deteccao de queda do VARD ja possui um pipeline tecnico bem definido:

- captura controlada de frames;
- janela temporal fixa;
- backbone V-JEPA 2;
- classificacao binaria;
- suavizacao temporal para reduzir falsos positivos.

Ao mesmo tempo, o repositorio tambem ja possui as pecas necessarias para produto:

- cadastro e streaming de cameras;
- persistencia de notificacoes;
- envio de push;
- consumo de incidentes no app.

O principal gap atual nao esta no algoritmo base, mas na orquestracao entre esses dois mundos: o momento em que o alerta detectado localmente precisa virar clipe, notificacao persistida e atualizacao visivel no app.
