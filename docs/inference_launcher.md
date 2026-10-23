# Janela de controle de inferências

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
- **Iniciar as duas / Parar as duas / Reiniciar as duas** controla um processo compartilhado
  com os dois modelos, uma conexão de vídeo e uma janela de preview.
- Ao iniciar o segundo modelo na mesma câmera pelos botões individuais, o launcher
  substitui o processo anterior pelo compartilhado. Assim não duplica a leitura da câmera.
- Sozinhos, os modelos têm PID próprio. Juntos, os dois campos mostram o mesmo PID.
- Parar um dos modelos enquanto estão juntos encerra o PID compartilhado e retoma
  somente o modelo restante. Reiniciar um deles nesse modo reinicia o processo dos dois.
- A seleção de câmera e preview é salva localmente em `var/launcher/settings.json`.
- Parâmetros e habilitação dos modelos continuam no `.env`, lido por cada novo processo.
- A opção de vídeo pode ser desativada mesmo com preview habilitado no `.env`.
- Alterar câmera/preview enquanto um processo roda exige **Reiniciar** para aplicar.
- Fechar a janela encerra as instâncias que ela criou antes de sair.

O launcher usa `REDIS_URL=''`, `PYTORCH_ENABLE_MPS_FALLBACK=1` e
`OPENCV_FFMPEG_CAPTURE_OPTIONS='rtsp_transport;tcp|allowed_media_types;video'`.
Os processos individuais executam `scripts.run_fall_monitor_jobs --detector fall`
ou `--detector confrontation`. O compartilhado usa os dois argumentos no mesmo
comando, com os mesmos registros de ocorrências e notificações.

Para abrir a janela e iniciar os dois modelos na última câmera selecionada:

```bash
.venv/bin/python -m scripts.inference_launcher --start-both
```

O preview tem limite de `FALL_MONITOR_PREVIEW_FPS=8` e largura máxima de
`FALL_MONITOR_PREVIEW_MAX_WIDTH=960`, configuráveis no `.env`. O redimensionamento
acontece antes de desenhar e comprimir o vídeo, e a fila mantém a imagem mais recente.
Esses ajustes não alteram a captura, os frames analisados ou os clipes salvos.
No processo compartilhado, os modelos são executados em sequência na GPU; ainda
existe tempo de processamento e espera entre as análises.

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
var/logs/gui_both.log
var/logs/gui_fall_console.log
var/logs/gui_confrontation_console.log
var/logs/gui_both_console.log
```

Os arquivos `.log` sem `_console` têm rotação pelo monitor. Os arquivos de console
recebem stdout/stderr para diagnosticar falhas de importação ou bibliotecas nativas.
