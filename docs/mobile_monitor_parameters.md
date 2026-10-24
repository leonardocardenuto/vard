# Proteção do celular: localização e parâmetros

Aplicar `sql/014_mobile_monitor_settings.sql` antes de publicar a API e o novo APK.
A migração cria uma configuração global em `mobile_monitor_settings`, linha `id = 1`,
com os mesmos valores usados anteriormente no detector. É idempotente e não
sobrescreve os parâmetros existentes.

Ao ativar a proteção (inclusive ao reiniciar o serviço), o Android consulta
`GET /mobile-monitor/configuration` usando a credencial de monitoramento.
A API consulta o banco em cada requisição, valida os valores e devolve os
parâmetros. O sensor só começa após essa resposta. Sem conexão ou com
configuração inválida, a ativação falha com uma mensagem na tela; não usa
uma configuração antiga silenciosamente. Após ativado, o detector continua
localmente, inclusive sem rede. Mudanças no banco entram na próxima ativação.

Para ajustar a sensibilidade sem recompilar o aplicativo, por exemplo:

```sql
UPDATE mobile_monitor_settings
SET parameters = parameters || '{"impact_g": 3.0, "confirmation_timeout_ms": 25000}'::jsonb
WHERE id = 1;
```

Os campos e limites estão em `api/mobile_monitor_config.py`. O tempo imóvel
precisa ser menor que a janela de impacto; o limiar de impacto deve superar
a faixa usada para estimar a gravidade. A configuração é global; não há uma
nova tela de ajustes nem um endpoint público para alterar esses valores.

A localização é solicitada apenas durante a confirmação de uma possível queda.
“Estou bem” descarta o evento pendente e interrompe a captura de localização;
o cancelamento é processado na mesma thread do sensor e do temporizador.
Somente o evento que expira sem cancelamento entra na fila de alertas.
A localização acompanha esse evento, com um link para o mapa nos registros.
Permissão negada ou GPS indisponível não impede o envio de uma queda não cancelada.

A visão ao vivo não mostra controles de player. Os trechos gravados conservam
seus controles de reprodução.
