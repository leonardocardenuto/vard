# Detecção de confronto — checkpoint v1

Treino concluído em 12/09/2026 na RTX 3060. Saídas: `nao_confronto` (índice 0)
e `confronto` (índice 1). O modelo reconhece ações visuais de confronto; não
determina o vínculo entre pessoas nem caracteriza, por si só, violência doméstica.

## Bases selecionadas

| Base e fonte original | Seleção usada | Motivo |
| --- | --- | --- |
| [SCFD](https://github.com/seymanurakti/fight-detection-surv-dataset) | 300 vídeos, 150 por classe | Confrontos reais em câmeras de segurança, com origens para agrupar os recortes. |
| [AIRTLab](https://github.com/airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos) | 350 vídeos, 230 violentos e 120 normais | Câmeras fixas em ambiente interno; negativos com abraços, palmas e gesticulações. |
| [VID — Harvard Dataverse](https://doi.org/10.7910/DVN/N4LNZD) | 320 vídeos domésticos encenados + 320 normais sorteados com seed 42 | Complementa os ambientes internos com ações domésticas; usados somente RGB com rostos desfocados. |

O [artigo do VID](https://pmc.ncbi.nlm.nih.gov/articles/PMC11951989/) descreve a
coleta com atores. Os negativos selecionados vêm da classe normal geral do VID,
não de um subconjunto exclusivamente doméstico. Os vídeos com esqueletos/pose
sobrepostos não foram usados. AIRTLab é disponibilizado para pesquisa e
educação; o Dataverse declara CC0 para VID. SCFD não fornece uma licença explícita
no material baixado. Essas bases foram usadas neste experimento acadêmico;
o download não estabelece autorização comercial sobre todas as fontes.

O downloader guarda os manifestos e verifica SHA-1 de blobs GitHub e checksums
dos arquivos Dataverse. Versões GitHub utilizadas:

- SCFD: `ff83b7c521e5ca4eb67a212cc42dbc54f39d6290`.
- AIRTLab: `1f7747e104301ccaa82ef5a2f6804b51ced1c398`.

## Preparação e treinamento

Dos 1.290 vídeos selecionados, duas duplicatas exatas do VID foram removidas
(`v_d_b_287` e `v_d_b_54`). Quatro clipes SCFD com menos de 1,8 segundo foram
excluídos do slicing (`fi028`, `fi034`, `fi149`, `fi019`). Restaram 1.284 vídeos.

A divisão ocorreu antes dos recortes. SCFD é agrupado pelo URL de origem;
os intervalos CamNet/Synopsis são mantidos em um único grupo conservador.
No AIRTLab, `cam1` e `cam2` do mesmo evento ficam no mesmo split. No VID,
o agrupamento é por vídeo. Não há garantia de separação por ator, residência
ou sessão no VID, nem de separação por ambiente no AIRTLab.

| Divisão | Vídeos usados | Janelas |
| --- | ---: | ---: |
| Treino | 817 | 1.709 |
| Validação | 205 | 405 |
| Teste | 262 | 530 |

Cada janela cobre aproximadamente 2 segundos e contém 16 frames uniformemente
amostrados. Os recortes de treino são consecutivos, sem sobreposição, descartando
caudas curtas. Clipes inteiros entre 1,8 e 2 segundos são aceitos para tolerar
variações reais de FPS/duração. Os rótulos são herdados dos clipes, não são
anotações temporais quadro a quadro.

Foi reproduzida a arquitetura de `tests/train_fall_classifier.py`:

```text
RGB → AutoVideoProcessor → facebook/vjepa2-vitl-fpc64-256 congelado
→ média dos tokens → Linear(1024,512) → ReLU → Dropout(0.3)
→ Linear(512,2) → softmax
```

O maior lado dos frames é limitado a 960 antes do processor. Embeddings em
BF16 na GPU, head em FP32, CrossEntropy e AdamW (`lr=0.001`, `weight_decay=0.0001`).
O sampler equilibra dataset/classe e reduz o peso de vídeos com mais janelas.
Batch da head: 128. Seed: 42. Limite: 80 épocas; early stopping: 12 épocas.
Foram executadas 15 épocas e escolhida a época 3 pelo F1 médio entre as três
bases na validação. O limiar **0,41** foi escolhido exclusivamente na validação.

## Resultado no teste separado

Métricas por janela usando limiar 0,41, antes da confirmação temporal do monitor:

| Base | Janelas | Acurácia | F1 confronto | Precisão confronto | Recall confronto |
| --- | ---: | ---: | ---: | ---: | ---: |
| SCFD | 66 | 81,82% | 82,86% | 76,32% | 90,63% |
| AIRTLab | 166 | 87,35% | 91,36% | 87,40% | 95,69% |
| VID doméstico + normais | 298 | 97,65% | 97,32% | 95,49% | 99,22% |
| Total | 530 | **92,45%** | **93,03%** | **89,60%** | **96,74%** |

Matriz de confusão `[real][predito]`, ordem `nao_confronto`, `confronto`:
`[[223,31],[9,267]]`. São 31 falsos positivos e 9 falsos negativos.
Por média das probabilidades por vídeo: acurácia 91,22%, F1 92,26%.
Com argmax/limiar 0,5: acurácia 93,40%, F1 93,83%; essa observação no teste
não foi usada para substituir o limiar escolhido na validação.

Há diferença relevante de domínio: na validação, o SCFD teve acurácia 59,57%
e F1 66,67% com limiar 0,41. Os grupos CCTV são poucos e heterogêneos;
o resultado agregado, dominado por cenas encenadas, não é uma estimativa de
desempenho em novas câmeras residenciais. O checkpoint requer validação nas
câmeras de destino. As métricas acima não medem a taxa de alertas por hora
do pipeline contínuo nem a calibração probabilística do softmax.

## Arquivos e reprodução

- Checkpoint instalado: `fall_detection/models/best_confrontation_classifier_head.pt`.
- SHA-256: `4bcabd3c162d71f9181f95b4f6088fd5c0e89d49fa7f69d938ea7f097869d2a1`.
- Execução completa: `var/training_runs/confrontation_head_v1/`.
- Dados e proveniência: `var/datasets/confrontation/`.

Na pasta da execução estão `videos.json`, `slices.json`, rejeições, splits,
argumentos, cache de embeddings, histórico, seleção de limiar, métricas de
validação/teste, predições individuais, gráfico e verificação de inferência.
O checkpoint guarda arquitetura, classes, janela, época, limiar e hash do
manifesto. Ele depende do backbone V-JEPA2 disponível no cache Hugging Face.
Pesos, vídeos e `var/` são ignorados pelo Git; copie-os separadamente ao migrar.

```powershell
.venv/Scripts/python.exe scripts/download_confrontation_datasets.py
.venv/Scripts/python.exe tests/train_confrontation_classifier.py --feature-batch-size 8 --feature-workers 4
.venv/Scripts/python.exe scripts/predict_confrontation_video.py --source caminho/video.mp4
.venv/Scripts/python.exe scripts/predict_confrontation_video.py --source caminho/video.mp4 --sliding-windows
```

O treino retoma embeddings já salvos sem recalcular o backbone; a head tem
seed reinicializada independentemente da retomada. Use outro `--output-dir`
para mudar parâmetros/dados. Os comandos de predição não acessam banco ou push.

## Inferência, notificações e ativação

A terceira camada usa a mesma captura RGB das camadas de queda e armas,
com estado temporal e cooldown próprios. Ela funciona também sozinha. O fluxo é:

```text
16 frames / 2 segundos → ConfrontationClassifier → confrontation_probability
→ TemporalSmoother → cooldown por câmera/detector
→ Notification(confrontation_detected, critical)
→ OneSignal para membros ativos do workspace → Home e Alertas: “Confronto”
```

O monitor infere a cada segundo; confirma duas probabilidades consecutivas
acima do limiar ou uma média de cinco janelas acima dele. Após um alerta,
suprime novos alertas de confronto por 60 segundos, mantendo a inferência.
A pausa da camada de queda não pausa confronto. Erros de uma camada não
interrompem as demais. O provider rejeita `sample_fps` incompatível com o treino.

A integração com a main de 03/10/2026 preserva a inferência assíncrona, snapshots
e o preview em processo separado. A camada de queda mantém a gravação com
pré/pós-evento e o histórico criptografado recebidos da main. A coleta do clipe
de queda não pausa as camadas de armas e confronto; estas geram suas próprias
notificações, sem criar registros indevidos no histórico exclusivo de quedas.

No `.env`, para habilitar nas câmeras já monitoradas por queda ou armas:

```dotenv
CONFRONTATION_MONITOR_ENABLED=true
CONFRONTATION_MONITOR_CHECKPOINT=fall_detection/models/best_confrontation_classifier_head.pt
CONFRONTATION_MONITOR_NUM_FRAMES=16
CONFRONTATION_MONITOR_SAMPLE_FPS=7.5
CONFRONTATION_MONITOR_THRESHOLD=0.41
```

Reinicie a API para carregar as variáveis. Os demais parâmetros estão em
`.env.example`. Para uma câmera específica, use o PATCH de câmeras existente,
preservando seus outros metadados:

```json
{"metadata":{"confrontation_monitor":{"enabled":true}}}
```

`enabled=false` desabilita explicitamente a camada nessa câmera. Checkpoint,
device, janela, stride, threshold, smoothing, hits, buffer e cooldown podem
ser sobrescritos no mesmo objeto. Para monitoramento exclusivo de confronto,
esse objeto também aceita `capture_fps` e `show_preview`.

Execute um único supervisor: junto da API com um processo, ou usando
`.venv/Scripts/python.exe -m scripts.run_fall_monitor_jobs`. No modo dedicado,
deixe os três flags globais desabilitados no processo da API para evitar outro
supervisor. O processo dedicado pode usar os flags ou metadados específicos.

O payload persistido inclui câmera, checkpoint, probabilidades, classe, limiar,
média, hits e `confidence` em porcentagem. `predicted_class` usa argmax; a
decisão de alerta usa o limiar 0,41 e confirmação temporal, portanto podem
divergir para probabilidades entre 0,41 e 0,5. A UI reutiliza o tipo interno
`fight` e mostra “Confronto”. Não é necessária migration: `notification_type`
é textual. Cada camada mantém seu próprio modelo em memória.

Push exige credenciais OneSignal e assinaturas cadastradas. O evento fica no
banco mesmo sem entrega do push. O serviço existente registra falhas de envio
e não possui fila persistente de retentativas. Nesta execução não foram
alterados os flags do `.env`, iniciados monitores reais ou enviados pushes.

## Verificação da integração

- 29 testes Python aprovados: splits, equivalência de frames, carregamento,
  ordem das classes, roteamento, três camadas, cooldowns e persistência/push simulados.
- `npx tsc --noEmit` aprovado no app.
- Inferência real na GPU em seis janelas de teste, uma por classe/base,
  reproduziu as probabilidades do cache com diferença máxima inferior a 0,000001.
  A janela normal `vid:nv_b_158` foi um falso positivo (0,92196); está preservada
  no relatório, junto dos demais exemplos. A verificação confirma a execução
  do checkpoint, não substitui as métricas do teste completo.

Após integrar a main `8f1be17` em 03/10/2026, os testes Python executáveis
passaram, incluindo criptografia, clipe pré/pós-evento e a independência das
camadas durante essa coleta. Um teste de workspace depende de banco de teste
migrado e foi pulado. O import da API e a instalação do app passaram. A
checagem TypeScript da main recebida apresenta cinco erros em componentes
inalterados por esta integração: exports ausentes `buildWebSocketUrl` e
`acceptInvite`, além dos tipos de navegação de `AcceptInviteScreen`.

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py' -v
```
