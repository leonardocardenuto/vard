# Inferência local: quedas e confrontos

Todos os parâmetros dos jobs de inferência vêm do `.env` da raiz do projeto
(ou das variáveis de ambiente exportadas no terminal). Os objetos antigos
`fall_monitor`, `armed_monitor` e `confrontation_monitor` em `cameras.metadata`
são ignorados, inclusive `enabled`. Não é necessário alterar ou limpar o banco.
O banco fornece a origem do vídeo, nome, workspace e estado ativo da câmera.

Configuração local atual:

```dotenv
CAMERA_MONITOR_AUTOSTART=false
FALL_MONITOR_ENABLED=true
CONFRONTATION_MONITOR_ENABLED=true
ARMED_MONITOR_ENABLED=false
FALL_MONITOR_CAPTURE_FPS=16
FALL_MONITOR_THRESHOLD=0.85
CONFRONTATION_MONITOR_THRESHOLD=0.12
CONFRONTATION_MONITOR_MIN_CONSECUTIVE_HITS=3
```

`CAMERA_MONITOR_AUTOSTART=false` impede que iniciar a API abra monitores.
Os flags `*_MONITOR_ENABLED` selecionam os modelos disponíveis nos jobs.
`--detector` restringe a execução a um desses modelos habilitados.
`FALL_MONITOR_CAPTURE_FPS` controla a captura para todos os detectores,
inclusive quando confrontos são executados sozinhos; cada modelo mantém seu
próprio `*_MONITOR_SAMPLE_FPS`. Os demais parâmetros estão em `.env.example`.
Reinicie os processos após editar o `.env`, pois ele é carregado na inicialização.

Os checkpoints locais são `var/streams/best_vjepa2_fall_classifier_combined.pt`
e `fall_detection/models/best_confrontation_classifier_head.pt`, fora do Git.
O `.env` local seleciona o dispositivo `mps` deste Mac.

Execute na raiz do repositório, em terminais separados.

API:

```bash
.venv/bin/python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Quedas na Ipcam1:

```bash
REDIS_URL='' PYTORCH_ENABLE_MPS_FALLBACK=1 OPENCV_FFMPEG_CAPTURE_OPTIONS='rtsp_transport;tcp|allowed_media_types;video' .venv/bin/python -m scripts.run_fall_monitor_jobs --camera-id 8d58e528-219c-4fbb-a570-e9e0234d4a02 --detector fall --show-preview --log-file var/logs/quedas.log
```

Confrontos na Ipcam1:

```bash
REDIS_URL='' PYTORCH_ENABLE_MPS_FALLBACK=1 OPENCV_FFMPEG_CAPTURE_OPTIONS='rtsp_transport;tcp|allowed_media_types;video' .venv/bin/python -m scripts.run_fall_monitor_jobs --camera-id 8d58e528-219c-4fbb-a570-e9e0234d4a02 --detector confrontation --show-preview --log-file var/logs/brigas.log
```

Para executar os dois juntos, remova `--detector`. Sem `--camera-id`, o supervisor
monitora todas as câmeras ativas; use o ID para limitar o teste à câmera desejada.
Para reduzir leituras duplicadas da câmera, prefira **Iniciar as duas** no
[launcher](inference_launcher.md): os modelos compartilham uma conexão e um preview.
O preview usa `FALL_MONITOR_PREVIEW_FPS=8` e `FALL_MONITOR_PREVIEW_MAX_WIDTH=960`;
esses valores não mudam os frames enviados aos modelos nem a resolução dos clipes.
`--show-preview` abre a janela mesmo com `FALL_MONITOR_SHOW_PREVIEW=false`.
Ctrl+C encerra o monitor; Q/Esc fecha somente o preview.

App no emulador Android:

```bash
cd app
npm run start:emulator
```

O monitor registra ocorrências e tenta enviar push pelo OneSignal para as
inscrições dos membros ativos do workspace. A câmera deve estar acessível pela
rede. O comando `scripts.run_fall_detection` é uma ferramenta separada de teste
local e não registra ocorrências no app.

## Diagnóstico

O preview mostra limiar, atraso, processamento e pausas de cada modelo.
Os resultados ficam nos arquivos escolhidos com `--log-file`, com rotação.
Cada linha `Resultado` inclui `detector`, `prob`, `media`, `hits`, `alerta`,
`limiar` e `atraso`. A confirmação temporal utiliza os acertos consecutivos ou
a média da janela completa de predições. A pausa após uma queda afeta apenas
esse detector.

No mesmo processo, os modelos compartilham a GPU em sequência. Em processos
separados, continuam disputando os recursos do computador. O intervalo de
1 segundo é o mínimo entre submissões, não uma garantia de uma predição por segundo.

## Aviso de queda no app

Uma nova ocorrência de queda mostra um popup vermelho nas telas da sessão
autenticada de acompanhamento. O botão **Ver ocorrência** abre a tela de
ocorrências da câmera responsável, onde também é possível abrir o trecho.
Quedas pelo celular abrem as ocorrências do workspace indicado na notificação,
incluindo os eventos sem câmera, sem oferecer um clipe de câmera para o sensor.

O app recebe eventos pelo OneSignal e consulta ocorrências a cada 4 segundos
enquanto está ativo, como alternativa ao push. O mesmo ID aparece uma única
vez por sessão, mesmo quando chega pelos dois caminhos. Ocorrências antigas
não disparam o popup ao entrar. Em segundo plano, a notificação do sistema
continua dependendo do OneSignal e das permissões do aparelho.
