# Disponibilidade das câmeras

Execute o SQL de `sql/013_camera_availability_checks.sql` no banco da API. A
migration não foi aplicada automaticamente. A tabela e o índice usam `IF NOT
EXISTS`, permitindo executar o SQL manualmente e depois usar o runner normal
de migrations sem conflito.

Com a API rodando, o coletor verifica as câmeras ativas a cada 60 segundos.
`CAMERA_AVAILABILITY_ENABLED=false` desliga a coleta;
`CAMERA_AVAILABILITY_INTERVAL_SECONDS` aceita intervalos de 15 a 60 segundos.
O coletor reconhece a criação da tabela na próxima passagem, sem reiniciar a API.

Quando existe um job de monitoramento, a medição usa a recepção de um frame nos
últimos dez segundos. Para câmeras HTTP/HTTPS, usa uma resposta HTTP bem-sucedida;
para RTSP, testa a conexão TCP com o endpoint. O gráfico representa essa
conectividade, não a qualidade do vídeo. A máquina da API precisa alcançar a
câmera na rede. Uma webcam local sem agente de monitoramento disponível fica
sem dados; seu status salvo não é tratado como uma medição.

O endpoint autenticado `GET /insights/camera-availability?camera_id=...` exige
participação no workspace da câmera e retorna as últimas 24 horas em segmentos
`online`, `offline` e `unknown`. A tela consulta os dados novamente a cada minuto
enquanto está aberta e também ao atualizar a página.

Cada verificação tem validade máxima de três minutos. Sem nova medição, o
restante do intervalo aparece em cinza como **Sem dados**. Não há preenchimento
retroativo: antes da primeira verificação e durante pausas da API, o histórico
permanece desconhecido. O horário do eixo acompanha as últimas 24 horas, no
fuso do dispositivo.

- **Disponibilidade:** tempo online dividido pelo tempo efetivamente medido.
- **Cobertura:** tempo medido dividido pelas 24 horas.
- Sem medições, a disponibilidade aparece como `—`, não como 0% ou 100%.

Sem a tabela, a API e o restante das análises continuam funcionando. A seção
de disponibilidade informa que aguarda a atualização do banco.
