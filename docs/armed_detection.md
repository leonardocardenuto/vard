# Monitoramento de quedas e pessoas armadas

O supervisor em `api/services/fall_monitor.py` executa camadas independentes
por camera: queda, pessoa armada e [confronto](confrontation_detection.md).
Elas recebem frames RGB da mesma captura,
mas usam janelas, checkpoints, suavizacao e cooldowns proprios. A classificacao
de arma nao depende de uma queda nem transforma a classe `armado` em `queda`.

## Checkpoint

O carregador `fall_detection/armed_inference.py` aceita o formato de
`tests/train_gun_classifier_head.py`: `head_state_dict`, `model_name`,
`class_names`, `input_dim`, `hidden_dim`, `dropout`, `num_frames` e
`view_duration_seconds`. Reproduz o pooling medio dos tokens e a arquitetura
LayerNorm -> Linear -> GELU -> Dropout -> Linear. A probabilidade de arma e
extraida pelo nome `armado`, respeitando a ordem das classes do checkpoint.

O checkpoint final encontrado nesta maquina foi copiado de
`D:/backup/training_runs/gun_binary_head_final/best_gun_binary_classifier_head.pt`
para `fall_detection/models/best_gun_binary_classifier_head.pt`.
Arquivos `.pt` sao ignorados pelo Git: copie o arquivo separadamente ao instalar
em outra maquina, ou configure `ARMED_MONITOR_CHECKPOINT` com seu caminho.

Esse checkpoint usa `facebook/vjepa2-vitl-fpc64-256`, 16 frames em 3 segundos e
classes `sem_arma` / `armado`. No monitor, `(16 - 1) / 3 = 5` e o valor correto de
`sample_fps`. O provider rejeita uma taxa diferente da registrada no checkpoint;
o carregador rejeita quantidade de frames ou classes incompativeis. Cada
checkpoint/device e carregado uma vez e reutilizado entre cameras. As duas
camadas mantem seus proprios modelos; dimensione a memoria para ambos.

## Ativacao

Use o ambiente Python com as dependencias de ML ja instaladas, alem das
dependencias da API. A partir da raiz `vard/`, configure o `.env`:

```dotenv
ARMED_MONITOR_ENABLED=true
ARMED_MONITOR_CHECKPOINT=fall_detection/models/best_gun_binary_classifier_head.pt
ARMED_MONITOR_NUM_FRAMES=16
ARMED_MONITOR_SAMPLE_FPS=5
ARMED_MONITOR_THRESHOLD=0.85
ARMED_MONITOR_SMOOTHING_WINDOW=5
ARMED_MONITOR_MIN_CONSECUTIVE_HITS=2
ARMED_MONITOR_ALERT_COOLDOWN_SECONDS=60
```

Com isso, cameras ativas que ja possuem `metadata.fall_monitor.enabled=true`
recebem a segunda camada automaticamente. Para ativar somente armas em uma
camera, use o PATCH de cameras existente, preservando os demais metadados:

```json
{
  "metadata": {
    "armed_monitor": { "enabled": true }
  }
}
```

`metadata.armed_monitor.enabled=false` desabilita explicitamente essa camada
na camera. Dentro de `armed_monitor`, os campos `checkpoint`, `device`,
`num_frames`, `sample_fps`, `stride_seconds`, `threshold`, `smoothing_window`,
`min_consecutive_hits`, `buffer_seconds` e `alert_cooldown_seconds` sobrescrevem
os padroes globais. Em cameras com apenas armas, `capture_fps` e `show_preview`
tambem podem ser definidos nesse objeto. O restante dos parametros esta em
`.env.example`. Mudancas nos metadados reiniciam o job na proxima reconciliacao;
mudancas no `.env` exigem reinicio do processo.

Para executar junto da API, habilite `ARMED_MONITOR_ENABLED` ou
`FALL_MONITOR_ENABLED` e inicie o Uvicorn com um unico processo, ou execute o
supervisor dedicado:

```powershell
.venv/Scripts/python.exe -m scripts.run_fall_monitor_jobs
```

Execute apenas um supervisor por banco/conjunto de cameras para evitar alertas
duplicados. Ao usar o processo dedicado, deixe os tres flags globais como
`false` no processo da API. A camada de queda continua usando sua configuracao
existente. Nesta copia do projeto, o checkpoint de queda presente na raiz e
`best_vjepa2_fall_classifier.pt`; configure `FALL_MONITOR_CHECKPOINT` com esse
arquivo caso nao tenha instalado o checkpoint configurado. A main atualizada
em 03/10/2026 usa `var/best_vjepa2_fall_classifier_combined.pt` como padrao;
essa alteracao recebida do repositorio foi preservada.

## Confirmacao e notificacoes

O `TemporalSmoother` confirma um evento com duas probabilidades consecutivas
acima do limiar, ou com a media de cinco janelas acima dele. Os numeros sao
configuraveis. O limiar 0.85 e um padrao operacional, nao um limiar calibrado por
este trabalho. A camada de armas continua inferindo durante seu cooldown;
apenas novos alertas ficam suprimidos por 60 segundos. A pausa de queda afeta
somente a inferencia de queda, mantendo captura e deteccao de armas ativas.

O fluxo de evento confirmado e:

```text
armed_probability -> TemporalSmoother -> cooldown por camera/detector
-> Notification (armed_person_detected, critical)
-> membros ativos do workspace com assinatura OneSignal
-> push + listagem existente no app
```

O payload inclui camera, checkpoint, classe, probabilidades, limiar, media,
hits e `confidence` em porcentagem para o app. A origem tem suas credenciais
mascaradas. As telas Home e Alertas reconhecem o tipo como "Pessoa armada".
Nao ha necessidade de migration: `notification_type` e um campo textual livre.

`ONESIGNAL_APP_ID`, `ONESIGNAL_API_KEY` e assinaturas de usuarios precisam estar
configurados para entrega real. O envio usa o campo `data` para transportar os
identificadores ao SDK, conforme a [referencia oficial do OneSignal](https://documentation.onesignal.com/reference/push-notification).
Sem credenciais, o evento continua salvo e aparece na listagem. Erros HTTP ou
timeouts de push ficam no log e nao desfazem o evento; o servico atual nao tem
fila persistente de retentativas de push. Falhas ao salvar no banco permitem
nova tentativa na proxima janela, sem consumir o cooldown. Falha de inferencia
de uma camada pausa suas tentativas por 30 segundos e preserva a outra camada.

## Verificacao local sem enviar alertas

```powershell
.venv/Scripts/python.exe scripts/predict_armed_video.py --source caminho/video.mp4
.venv/Scripts/python.exe scripts/predict_armed_video.py --source caminho/video.mp4 --sliding-windows
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py' -v
```

O primeiro comando analisa a janela inicial de 3 segundos; o segundo percorre
o video. Eles nao acessam banco nem enviam notificacoes. O script antigo
`run_fall_detection.py` permanece uma ferramenta de teste de quedas; o fluxo
integrado de ambas as camadas e o supervisor de cameras.

Validacao realizada com o checkpoint final na GPU e backbone em cache:

- `No_Gun/N9_C2_P5_V3_HB_1`: `sem_arma`, probabilidade de arma 0.4029.
- `Handgun/PCH7_C2_P5_V2_HB_2`: `armado`, probabilidade de arma 0.7712.

Essas duas janelas verificam a execucao real, nao medem a qualidade do modelo.
A segunda fica abaixo do limiar padrao de notificacao 0.85. Os testes
automatizados exercitam a confirmacao temporal e os envios com probabilidades
controladas e servicos externos simulados. Nao foi enviado push real.
