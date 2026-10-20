# Vard

Monorepo com:

- app mobile em Expo/React Native 
- API em FastAPI

## Requisitos

- Node.js 20+
- npm
- Python 3.11+
- Android Studio e SDK Android se for rodar no Android
- `adb` configurado no PATH para instalar no device/emulador

## Rodar o app

Instale as dependências do app:

```bash
cd /Users/leonardocardenuto/projects/vard/app
npm install
```

Suba o Metro:

```bash
npm start
```

No emulador Android, configure `app/.env.local` com
`EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:8000`. Esse endereço aponta para a
API no computador e não depende de `adb reverse`. `127.0.0.1` aponta para o
próprio Android, a menos que a porta 8000 tenha sido encaminhada por ADB.
O arquivo `.env.local` tem prioridade sobre `.env`; reinicie o Metro com
`npm start -- --clear --android` após mudar o endereço. Para iOS Simulator/web,
use `http://127.0.0.1:8000`; para celular físico pela rede, use o IP do computador.

Para usar o emulador sem depender do IP do Wi-Fi, execute
`npm run start:emulator -- --clear`. Esse comando seleciona `10.0.2.2:8000`
somente para o Metro dessa execução e mantém os `.env` com o endereço de rede
usado no APK/celular físico. Requisições à API têm limite de espera de 15 segundos.

Rodar no Android:

```bash
npm run android
```

Para selecionar automaticamente um JDK 17/21 compatível (incluindo o Java do
Android Studio), use `npm run android`. O Java 26 não é compatível com o build
atual. O development client usa `exp+com.vard.app` para não abrir instalações
antigas que compartilham o esquema `exp+vard`.

Rodar no iOS:

```bash
npx expo run:ios
```

Rodar no web:

```bash
npm run web
```

Se o Android estiver com cache visual antigo:

```bash
adb uninstall com.vard.app
npx expo run:android
```

## Rodar a API

Crie e ative um ambiente virtual:

```bash
cd /Users/leonardocardenuto/projects/vard
python3 -m venv .venv
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements-api.txt
```

Configure o ambiente:

```bash
cp .env.example .env
```

Rode as migrations:

```bash
python -m scripts.migrate
```

Suba a API:

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Healthcheck:

```bash
curl http://localhost:8000/health
```

Swagger:

[http://localhost:8000/docs](http://localhost:8000/docs)

## Rodar Postgres e Redis com Docker Compose

Suba Postgres e Redis:

```bash
docker compose up -d
```

Com os containers ativos, rode as migrations e a API localmente:

```bash
python -m scripts.migrate
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

- API: [http://localhost:8000](http://localhost:8000)
- Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
- Postgres: `localhost:5432` (`vard` / `vard` / `vard`)
- Redis: `localhost:6379`

### Cache de resposta

Os endpoints `GET` autenticados usam Redis para cache por usuário, sem expiração por tempo por padrão. A invalidação acontece automaticamente por tags quando dados relacionados são alterados no banco. Em desenvolvimento, as respostas incluem:

- `X-Response-Cache: HIT` ou `MISS`
- `X-Response-Cache-Key`

## Inferência de queda

O fluxo de inferência contínua com vídeo local, webcam ou câmera RTSP/IP está documentado em `docs/fall_detection.md`.

Os parâmetros e a habilitação dos detectores vêm somente do `.env`; os valores
antigos em `cameras.metadata` são ignorados. Para monitorar uma câmera cadastrada,
use `python -m scripts.run_fall_monitor_jobs --camera-id UUID_DA_CAMERA`. A opção
`--camera-id` pode ser repetida para selecionar mais de uma câmera. Sem ela, o
supervisor considera todas as câmeras ativas e os detectores habilitados no `.env`.
Use `--detector fall` ou `--detector confrontation` para separar os modelos.

Para visualizar o vídeo e também registrar as quedas e notificações no app, use
`python -m scripts.run_fall_monitor_jobs --camera-id UUID_DA_CAMERA --show-preview`.
Essa opção abre o preview mesmo com `FALL_MONITOR_SHOW_PREVIEW=false`,
sem alterar o banco. Ctrl+C encerra o monitoramento; Q/Esc fecha apenas a janela.
O script `scripts.run_fall_detection` é uma ferramenta de inferência local: seus
alertas aparecem no terminal/preview e não são gravados no app. Ao usar jobs separados,
use `CAMERA_MONITOR_AUTOSTART=false` para evitar inferência duplicada na API.
Reinicie os jobs após editar o `.env`; veja [configuração local](docs/local_inference.md).

### Demo com webcam local

O CLI de jobs mantém o comportamento normal por padrão: ele monitora somente as
câmeras ativas já cadastradas. Para preparar uma demonstração local com webcam,
use o modo explícito `--demo`:

```bash
python -m scripts.run_fall_monitor_jobs --demo
```

Ele cria, ou reaproveita, uma conta demo (`demo.webcam@example.com` / `VardDemo2026!`),
um workspace e a câmera **Webcam de demonstração** com a origem OpenCV `0`. A webcam
é usada apenas nesse modo. O comando também prepara a chave de recuperação usada
para descriptografar os eventos e clipes dessa conta no aplicativo.

Para criar os dados sem ligar a webcam, use:

```bash
python -m scripts.run_fall_monitor_jobs --demo --demo-seed-only
```

`--webcam-source` ajusta a origem da câmera demo. Configure checkpoint e limiar
com `FALL_MONITOR_CHECKPOINT` e `FALL_MONITOR_THRESHOLD` no `.env`; as antigas
opções `--demo-checkpoint` e `--demo-threshold` foram removidas.

O monitor integrado agora inclui uma segunda camada para pessoas armadas, com
checkpoint binario, notificacoes e push. Veja [ativacao e validacao](docs/armed_detection.md).

A terceira camada detecta `confronto` / `nao_confronto` com um checkpoint
treinado em SCFD, AIRTLab e VID domestico. Veja [treinamento, resultados e ativacao](docs/confrontation_detection.md).

## Estrutura

```text
vard/
├── app/          # Expo / React Native
├── api/          # FastAPI
├── sql/          # schema e scripts SQL
├── scripts/      # utilitários e migration runner
└── tests/        # testes e utilitários de ML
```

## Testes automatizados do app (Maestro)

Com o emulador Android e o development build instalados:

```sh
cd app
npm run test:e2e
```

A suíte prepara uma API e um banco descartáveis, executa autenticação, cadastro,
navegação e criação de workspace e salva relatórios JUnit. Consulte
[pré-requisitos, casos e relatórios](app/maestro/README.md).
