# Inferência local: quedas e confrontos

A câmera **cozinha**, no workspace **Casa de User teste**, está configurada no
banco para executar as duas camadas no mesmo monitor:

- Origem: `http://192.168.15.131:8080/video`.
- Captura compartilhada: 8 FPS.
- Quedas: 16 frames a 6 FPS, limiar 0,8.
- Confrontos físicos: 16 frames a 7,5 FPS (2 segundos), limiar 0,41.
- Confirmação temporal: janela de 5 predições e 2 acertos consecutivos.
- Alertas de confronto: intervalo mínimo de 60 segundos por câmera.
- Novos clipes de queda: 13 segundos antes da referência da detecção, sem os
  10 segundos adicionais após o resultado. Os frames anteriores são preservados durante a inferência.

Os checkpoints locais são `var/streams/best_vjepa2_fall_classifier_combined.pt`
e `fall_detection/models/best_confrontation_classifier_head.pt`. Ambos estão
fora do Git. O `.env` seleciona o dispositivo `mps` deste Mac; os metadados
da câmera também estão configurados para ele.

Execute os comandos a seguir na raiz do repositório, em terminais separados.

API:

```bash
.venv/bin/python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Monitor com vídeo, quedas, confrontos e notificações:

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 .venv/bin/python -m scripts.run_fall_monitor_jobs \
  --camera-id 221eacf3-8e94-4cb2-926c-03349d99f4b8 \
  --show-preview
```

App no emulador Android:

```bash
cd app
npm start -- --localhost --android
```

Os três sinalizadores globais `FALL_MONITOR_ENABLED`, `ARMED_MONITOR_ENABLED`
e `CONFRONTATION_MONITOR_ENABLED` ficam em `false` no `.env` local para que
iniciar a API não abra outros monitores ou a webcam. O comando de jobs acima
inicia explicitamente o supervisor e usa os dois detectores habilitados nos
metadados da câmera cozinha, mesmo com esses sinalizadores globais em `false`.

O monitor registra ocorrências e tenta enviar push pelo OneSignal para as
inscrições dos membros ativos do workspace. Os processos precisam estar usando
a configuração atual do `.env`. A câmera deve estar acessível pela mesma rede.
Ctrl+C encerra o monitor; Q/Esc fecha somente o preview. O comando
`scripts.run_fall_detection` é de teste local e não registra ocorrências no app.

## Diagnóstico

O preview mostra o limiar, o atraso entre a janela capturada e o resultado,
o processamento em andamento, a coleta do clipe e os tempos de pausa/intervalo
entre alertas. Erros de um modelo aparecem em laranja, com o tempo até a nova
tentativa. A pausa de 300 segundos após queda confirmada afeta somente quedas.

Os resultados e erros ficam também em `var/logs/camera_monitor.log`, com rotação
de arquivos. Para acompanhar:

```bash
tail -f var/logs/camera_monitor.log
```

Cada linha `Resultado` inclui `detector`, `prob`, `media`, `hits`, `alerta`,
`limiar` e `atraso`. O limiar é aplicado à confirmação temporal, não somente à
classe mais provável. Dois modelos compartilham a GPU em sequência; o intervalo
configurado de 1 segundo é o mínimo entre submissões, não uma garantia de uma
predição por segundo. O atraso observado deve ser avaliado antes de reduzir limiares.

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
