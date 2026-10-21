# Push Android direto e comparação com OneSignal

O VARD pode enviar diretamente pela API FCM HTTP v1, sem passar pelo serviço
OneSignal ou pelo Expo Push Service. O OneSignal continua opcional para a
comparação e para a transição. Este fluxo novo é somente Android.

O padrão continua sendo OneSignal (`PUSH_PROVIDER=onesignal` no backend e
`EXPO_PUBLIC_PUSH_MODE=onesignal` no app). FCM direto é opcional. Nesse modo
padrão, um checkout novo não precisa de `google-services.json` para gerar a
configuração Expo. Para FCM/both, fornecer esse arquivo no diretório `app/` ou
informar seu caminho em `GOOGLE_SERVICES_JSON` (por exemplo, um segredo de arquivo EAS).

## Credenciais

- `app/google-services.json`: configuração Android do projeto Firebase, com o
  pacote `com.vard.app`. É ignorado pelo Git e necessário para compilar FCM.
- `var/secrets/firebase-service-account.json`: chave privada da conta de serviço.
  Somente no backend, com permissão de arquivo 600; nunca empacotar no app,
  registrar em logs ou adicionar ao Git. Configurar separadamente no servidor.

```dotenv
# .env da API: um provedor por evento, sem envio duplo automático.
PUSH_PROVIDER=fcm
FCM_SERVICE_ACCOUNT_FILE=var/secrets/firebase-service-account.json
PUSH_WORKER_ENABLED=true
```

```dotenv
# app/.env: both registra ambos para a comparação manual.
# fcm não inicializa nem chama o SDK OneSignal; onesignal mantém o caminho antigo.
EXPO_PUBLIC_PUSH_MODE=both
```

Ao mudar o backend, reiniciar a API. Ao mudar o modo do app, reiniciar o Metro
com `--clear` e reabrir o processo do aplicativo. O SDK OneSignal permanece como
dependência nesta fase de comparação; `fcm` desativa seu uso em tempo de execução.

## Preparação

```sh
.venv/bin/python -m scripts.migrate
cd app
npx expo prebuild --platform android --no-install
npm run android
```

As tabelas `push_devices` e `push_deliveries` são criadas pela migration 013.
Registro e revogação são vinculados à conta autenticada e à instalação. Trocar
de conta transfere a associação do token e impede o envio pendente à conta antiga.
Idosos não recebem os alertas de escalonamento dos espaços.

## Teste no próprio aparelho

Depois de entrar na conta, em Ajustes, usar **Testar notificações**:

1. OneSignal: título `VARD · Teste OneSignal`.
2. FCM direto: título `VARD · Teste FCM direto · sem OneSignal`.

Os testes só enviam para a instalação da própria conta. Não criam ocorrências
de queda/confronto. Há limite de cinco testes por minuto por conta.

Testar primeiro com o app aberto, depois com Home/tela bloqueada e tocar na
notificação. Forçar parada pelo Android não é equivalente a minimizar o app.
Sem conexão, o provedor pode entregar depois; não há promessa de entrega imediata.

## Fila, retentativas e confirmação

O evento e seus envios são persistidos na mesma transação. O worker da API usa
locks `SKIP LOCKED` para permitir múltiplos processos. A associação e as permissões
são conferidas de novo antes de enviar. Falhas transitórias de rede/HTTP 429/5xx
têm até oito tentativas com espera progressiva; eventos expiram após uma hora.
FCM `UNREGISTERED` desativa o token. Erros permanentes ficam como `failed`.

Novos envios emitem `pg_notify` na mesma transação da outbox. Um listener
PostgreSQL por worker acorda o processamento assim que o commit conclui, inclusive
entre processos distintos. A varredura a cada dois segundos permanece apenas como
recuperação de sinais perdidos, retentativas e indisponibilidade do listener.
Lotes cheios são drenados sem espera entre eles. Cada worker mantém uma conexão
adicional de banco para LISTEN e reutiliza uma sessão HTTP própria para evitar
refazer TCP/TLS a cada envio; a sessão é fechada na parada do worker.

`accepted` significa que o provedor aceitou, **não que o celular recebeu**.
`received` significa que o app confirmou ao receber em primeiro plano ou ao
usuário tocar na notificação. Isso não equivale a confirmação humana de socorro.
Enquanto o app estiver encerrado/offline, a confirmação pode não chegar.

OneSignal usa uma chave idempotente por envio. FCM não tem a mesma garantia:
uma resposta perdida pode ocasionar reenvio; a tag Android identifica o evento
para substituir sua notificação na bandeja. Isso não oferece entrega exatamente
uma vez, nem substitui uma estratégia de escalonamento de emergência.

Credenciais no servidor e uma nova versão Android são necessárias para ativar
em produção. Nenhum deploy/fetch/pull é necessário para o teste local.

## Medir latência

A migration 014 registra início da última tentativa, duração da chamada HTTP ao
provedor (relógio monotônico) e origem da confirmação (`foreground`, `tap` ou
`unknown` para clientes antigos). `accepted_at` marca o fim da resposta do provedor.
O painel de testes mostra os tempos. O total usa o relógio do servidor, da criação
na fila até receber o ACK do app: inclui fila, entrega, callback JS e rede de retorno.
Não é uma medida exata do instante em que o Android desenhou a notificação.

Com o app aberto e `EXPO_PUBLIC_PUSH_MODE=both`, executar:

```sh
.venv/bin/python -m scripts.benchmark_push \
  --email push.teste@example.com \
  --installation 03eaf7d4-2b4f-4349-98c1-e194ed7b6bef \
  --samples 20 --warmup 2
```

A senha é pedida sem eco. O script aquece ambos com envios reais (excluídos das
estatísticas), alterna pares AB/BA e usa título e corpo iguais. Respeita o limite
de cinco envios por minuto, sem criar ocorrências. Salva os tempos individuais,
média, mediana, p95 pelo método nearest-rank e mínimo/máximo em
`var/push-benchmark-warm.json`, sem tokens ou credenciais. Preserva o relatório
anterior e salva o progresso a cada envio; `complete` indica conclusão de toda a série.
O indicador principal é `send_to_confirmation`, entre o início do envio no backend
e a confirmação recebida do app, excluindo a espera na fila. Ainda inclui callback,
rede de retorno e eventual espera pelo commit da transação de envio; não isola
apenas a rede FCM ou o instante de exibição no Android. `provider_request` mede
somente a chamada ao provedor, não a entrega no aparelho. As chamadas usam o
mesmo adaptador e pool HTTP do envio normal, sem transporte exclusivo do benchmark.
O relatório anterior `push-benchmark-warm.json` foi medido antes das otimizações
de wake-up e reutilização HTTP; use outro `--output` para preservar a comparação.
Só confirmações em primeiro plano, na primeira tentativa, entram na média.
Toques, falhas, timeout e retentativas ficam separados no relatório.
Os resultados valem para este aparelho/rede/build; uma amostra pequena em emulador
não determina qual provedor é sempre mais rápido. Após comparar, voltar o app
para `EXPO_PUBLIC_PUSH_MODE=fcm` se não quiser inicializar o OneSignal.
