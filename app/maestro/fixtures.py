"""Seed and verify only the disposable Maestro API; no real credentials."""
import json
import sys
from urllib.request import Request, urlopen

BASE_URL = 'http://127.0.0.1:18000'
EMAIL = 'maestro.login@example.com'
SIGNUP_EMAIL = 'maestro.signup@example.com'
INVITED_EMAIL = 'maestro.invited@example.com'
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
    workspace = request('/workspaces', {'name': 'Casa Maestro', 'slug': 'casa-maestro'}, token)
    request('/auth/register', {
        'email': INVITED_EMAIL, 'password': PASSWORD, 'full_name': 'Maestro Convidado',
    })
    request('/cameras', {
        'workspace_id': workspace['id'],
        'name': 'Camera Maestro',
        'connection_type': 'https',
        'stream_url': 'https://camera.test/live',
        'status': 'online',
        'metadata': {'location': 'Sala'},
    }, token)
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
    if case in ('all', 'invite'):
        workspaces = request('/workspaces', token=login(EMAIL))
        workspace_id = next(w['id'] for w in workspaces if w['name'] == 'Casa Maestro')
        invites = request(f'/invites?workspace_id={workspace_id}', token=login(EMAIL))
        matching = [invite for invite in invites if invite['email'] == 'maestro.invite@example.com']
        assert len(matching) == 1 and matching[0]['role'] == 'caregiver', invites
        print('Convite criado pela interface e persistido com o papel correto.')
    if case in ('all', 'camera'):
        workspaces = request('/workspaces', token=login(EMAIL))
        workspace_id = next(w['id'] for w in workspaces if w['name'] == 'Casa Maestro')
        cameras = request(f'/cameras?workspace_id={workspace_id}', token=login(EMAIL))
        assert any(camera['name'] == 'Camera Maestro' for camera in cameras), cameras
        print('Camera da fixture permaneceu acessivel pelo workspace.')
    if case in ('all', 'accept'):
        workspaces = request('/workspaces', token=login(INVITED_EMAIL))
        assert any(workspace['name'] == 'Casa Maestro' for workspace in workspaces), workspaces
        print('Convite aceito pela interface e workspace liberado para o convidado.')
else:
    raise SystemExit('Use seed ou verify <caso>.')
