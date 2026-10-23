# Janela de controle de inferências

Na branch `experiment/fall-angle-crop-gui`, a secao **Quedas - YOLO auxiliar**
permite selecionar recorte, modo de pose (desligada/observar/assistir JEPA), peso
maximo de 0 a 10% e checkpoint de pose. Os valores sao aplicados ao iniciar ou
reiniciar Quedas; Confrontos continua independente. Consulte
[o experimento de pose](person_crop_experiment.md) para limites e validacao.

No macOS, dê dois cliques em `Iniciar Inferencias.command` na raiz do projeto.
Alternativamente, execute na raiz:

```bash
.venv/bin/python -m scripts.inference_launcher
```

A interface usa Tkinter do Python já instalado. Não precisa instalar dependências
adicionais nem iniciar a API para abrir a janela. Os jobs continuam precisando
do banco e dos checkpoints, como os comandos de terminal existentes.

- Cole o `camera-id` ou clique em **Buscar câmeras** para escolher uma câmera ativa.
- **Iniciar / Parar / Reiniciar** controla cada detector individualmente.
- **Iniciar as duas / Parar as duas / Reiniciar as duas** controla os dois processos.
- Cada detector tem um PID separado, exibido na janela e no registro de ações.
- A seleção de câmera e preview é salva localmente em `var/launcher/settings.json`.
- Parâmetros e habilitação dos modelos continuam no `.env`, lido por cada novo processo.
- A opção de vídeo pode ser desativada mesmo com preview habilitado no `.env`.
- Alterar câmera/preview enquanto um processo roda exige **Reiniciar** para aplicar.
- Fechar a janela encerra as instâncias que ela criou antes de sair.

O launcher usa `REDIS_URL=''`, `PYTORCH_ENABLE_MPS_FALLBACK=1` e
`OPENCV_FFMPEG_CAPTURE_OPTIONS='rtsp_transport;tcp|allowed_media_types;video'`.
Os processos executam `scripts.run_fall_monitor_jobs --detector fall` e
`--detector confrontation`, com os mesmos registros de ocorrências e notificações.

Ao parar, o PID registrado recebe `SIGTERM`. O launcher aguarda até 20 segundos.
Se o processo não sair, sinaliza o grupo criado para aquela instância e depois
usa `SIGKILL` se necessário. Reiniciar só inicia o novo processo depois de
confirmar que o anterior terminou. A limpeza do grupo também encerra previews filhos.

São controlados apenas processos criados pela janela. Monitores iniciados em
outros terminais devem ser encerrados nesses terminais para evitar duplicação.
Uma segunda janela do launcher não é aberta enquanto a primeira estiver ativa.
"Processo ativo" indica que o Python está rodando; confirme a conexão com a câmera
e os resultados no preview/log. Isso não garante que o vídeo ou o modelo carregou.

Logs detalhados:

```text
var/logs/gui_fall.log
var/logs/gui_confrontation.log
var/logs/gui_fall_console.log
var/logs/gui_confrontation_console.log
```

Os dois primeiros têm rotação de arquivos pelo monitor. Os arquivos de console
recebem stdout/stderr para diagnosticar falhas de importação ou bibliotecas nativas.
