# Testes mobile com Maestro

Segue o padrão de `geoescala/scala-app/maestro`: YAML por domínio, seletores
estáveis, preparação da massa, verificações do resultado e limpeza ao terminar.
O runner Android usa o app e a API FastAPI reais, sem mocks ou credenciais reais.

## Preparar uma vez

- Instale Maestro (`maestro --version`; validado com 2.10.0), Docker, Android SDK
  e `adb` no PATH.
- Na raiz do repositório, crie `.venv` e instale `requirements-api.txt`.
- Em `app/`, execute `npm ci` e instale o development build com
  `npx expo run:android`. O emulador deve estar ligado.

O runner procura Docker, Maestro e Android SDK também nos diretórios padrão
de instalação quando o terminal que executa `npm` tem um `PATH` reduzido.
O Docker Desktop precisa estar aberto. `ANDROID_HOME` e `ANDROID_SDK_ROOT`
podem indicar uma instalação personalizada do SDK; ferramentas já presentes
no `PATH` continuam tendo prioridade. Isso não altera a configuração do shell.

## Executar

Dentro de `app/`:

```sh
npm run test:e2e
npm run test:e2e -- email
npm run test:e2e -- login
npm run test:e2e -- signup
npm run test:e2e -- navigation
npm run test:e2e -- workspace
```

`MAESTRO_DEVICE` seleciona o Android (padrão `emulator-5554`). `MAESTRO_PYTHON`
permite usar outro Python com as dependências da API instaladas.

O runner sobe um Postgres temporário em memória, aplica as migrations, inicia
uma API na porta 18000 e um Metro exclusivo na 18081. A porta 55432 é reservada
para o banco de teste. Portas ocupadas fazem o comando abortar antes da criação
dos recursos. Não execute duas instâncias simultaneamente.

O Metro inicia com cache limpo. `VARD_MAESTRO=1` impede que o módulo de
ambiente do Expo SDK 54 sobrescreva a URL de teste com valores dos arquivos
`.env`; a configuração normal do app permanece igual.

A URL da API é definida apenas no Metro de testes; integrações OneSignal,
SendGrid, Redis e o monitor de quedas ficam desabilitados nesse processo.
A conta `maestro.login@example.com`, senha `MaestroLocal123!`, e o workspace
`Casa Maestro` existem somente no banco descartável. O cadastro usa
`maestro.signup@example.com`. O banco inteiro de teste é removido ao terminar,
inclusive quando há falha ou interrupção normal (Ctrl+C).

O Development Build preserva sua conexão com o Metro entre os fluxos. O runner
abre `vard://expo-development-client/` e trata o tutorial inicial do Expo.
Após testar, abra novamente o development build pelo seu Metro habitual.
Não é necessário limpar os dados ou reinstalar o app entre execuções.

## Cobertura

| Caso | Resultado verificado |
| --- | --- |
| email | Campo obrigatório, email inválido rejeitado pela API, correção e retorno preservando email |
| login | Senha obrigatória, credenciais incorretas, recuperação e entrada na home com OneSignal desabilitado |
| signup | Senha curta, confirmação divergente, termos obrigatórios, cadastro e login; persistência conferida pela API |
| navigation | Home sem incidentes, workspace da fixture, análises, dispositivos vazios e logout |
| workspace | Nome obrigatório, criação pela interface e persistência associada ao usuário pela API |

Relatórios JUnit, logs da API/Metro e evidências de falhas do Maestro ficam em
`results/<data-hora-pid>/` (ignorado pelo Git). O runner interrompe no primeiro
cenário que falhar e preserva o código de saída para integração em CI.

Os fluxos usam `testID` e textos; evite coordenadas e esperas fixas. Helpers
ficam em `shared/` e não devem ser executados como casos independentes.
O runner automatiza Android; execução iOS não foi validada.
Notificações push, vídeo ao vivo e chamadas de emergência não fazem parte desta suíte.

Referência: [comandos do Maestro](https://docs.maestro.dev/api-reference/commands/launchapp).
