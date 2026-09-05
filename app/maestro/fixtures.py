"""Seed and verify only the disposable Maestro API; no real credentials."""
import json
import sys
from urllib.request import Request, urlopen

BASE_URL = 'http://127.0.0.1:18000'
EMAIL = 'maestro.login@example.com'
SIGNUP_EMAIL = 'maestro.signup@example.com'
PASSWORD = 'MaestroLocal123!'


def request(path, payload=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    data = json.dumps(payload).encode() if payload is not None else None
    with urlopen(Request(BASE_URL + path, data=data, headers=headers), timeout=15) as response:
        return json.load(response)


def login(email):
    return request('/auth/login', {'email': email, 'password': PASSWORD})['access_token']


if sys.argv[1] == 'seed':
    token = request('/auth/register', {
        'email': EMAIL, 'password': PASSWORD, 'full_name': 'Maestro Login',
    })['access_token']
    request('/workspaces', {'name': 'Casa Maestro', 'slug': 'casa-maestro'}, token)
    print('Fixture local criada.')
elif sys.argv[1] == 'verify':
    case = sys.argv[2]
    if case in ('all', 'signup'):
        me = request('/auth/me', token=login(SIGNUP_EMAIL))
        assert me['full_name'] == 'Maestro Cadastro', me
        print('Cadastro persistido e login confirmado pela API.')
    if case in ('all', 'workspace'):
        workspaces = request('/workspaces', token=login(EMAIL))
        assert sum(w['name'] == 'Espaco criado pelo Maestro' for w in workspaces) == 1, workspaces
        print('Workspace persistido e associado ao usuario correto.')
else:
    raise SystemExit('Use seed ou verify <caso>.')
