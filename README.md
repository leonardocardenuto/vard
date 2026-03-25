# Vard

Monorepo com:

- app mobile em Expo/React Native em [`/Users/leonardocardenuto/projects/vard/app`](/Users/leonardocardenuto/projects/vard/app)
- API em FastAPI em [`/Users/leonardocardenuto/projects/vard/api`](/Users/leonardocardenuto/projects/vard/api)

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

Rodar no Android:

```bash
npx expo run:android
```

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
adb uninstall com.devsilogix.vard
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

## Estrutura

```text
vard/
├── app/          # Expo / React Native
├── api/          # FastAPI
├── sql/          # schema e scripts SQL
├── scripts/      # utilitários e migration runner
└── tests/        # testes e utilitários de ML
```
