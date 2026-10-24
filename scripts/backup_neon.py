"""Save a consistent Neon backup locally without putting credentials in argv."""
from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    source = values.get('DATABASE_URL')
    if not source:
        parser.error('DATABASE_URL ausente no arquivo de ambiente.')
    url = make_url(source)
    if not url.host or not url.host.endswith('.neon.tech'):
        parser.error('O arquivo selecionado nao aponta para o Neon; nenhum backup foi iniciado.')
    binary = shutil.which('pg_dump')
    if not binary:
        binary = next((str(p) for p in (
            Path('/opt/homebrew/opt/libpq/bin/pg_dump'),
            Path('/usr/local/opt/libpq/bin/pg_dump'),
        ) if p.is_file()), None)
    if not binary:
        parser.error('Instale o cliente PostgreSQL: brew install libpq')
    output = args.output or ROOT / 'var' / 'backups' / f'neon-{datetime.now():%Y%m%d-%H%M%S}.dump'
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error('O destino ja existe; escolha outro nome para preservar o backup anterior.')
    partial = output.with_name(output.name + '.partial')
    # Exclusive creation prevents collisions and keeps database contents private.
    with partial.open('xb'):
        partial.chmod(0o600)
    env = os.environ.copy()
    env.update(PGHOST=url.host, PGPORT=str(url.port or 5432), PGUSER=url.username or '',
               PGPASSWORD=url.password or '', PGDATABASE=url.database or '',
               PGSSLMODE=str(url.query.get('sslmode', 'require')), PGCONNECT_TIMEOUT='15')
    if url.query.get('channel_binding'):
        env['PGCHANNELBINDING'] = str(url.query['channel_binding'])
    try:
        result = subprocess.run([binary, '--format=custom', '--no-owner', '--no-acl',
                                 '--file', str(partial)], env=env, capture_output=True, text=True)
        if result.returncode:
            message = result.stderr
            for private in (source, url.password, url.username, url.host):
                if private:
                    message = message.replace(private, '[oculto]')
            print('Nao foi possivel gerar o backup:\n' + message.strip(), file=sys.stderr)
            return result.returncode
        partial.rename(output)
        print(f'Backup salvo: {output}')
        print(f'Tamanho: {output.stat().st_size / 1024**2:.2f} MB')
        return 0
    finally:
        partial.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
