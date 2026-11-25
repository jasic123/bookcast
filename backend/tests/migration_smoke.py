"""Verify the existing SQLite library can migrate without touching the live database."""
import asyncio
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import httpx


async def main():
    source = Path(__file__).resolve().parents[1] / 'book_research.db'
    with tempfile.TemporaryDirectory(prefix='bookcast-migration-', ignore_cleanup_errors=True) as directory:
        target = Path(directory) / 'copy.db'
        with sqlite3.connect(source) as original, sqlite3.connect(target) as copy:
            original.backup(copy)
        os.environ['DATABASE_URL'] = f'sqlite+aiosqlite:///{target.as_posix()}'
        os.environ['AUTH_REGISTRATION_CODE'] = 'migration-smoke-only'
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from app.core.database import engine, init_db
        from app.main import app

        engine.echo = False

        await init_db()
        await init_db()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.post('/api/auth/register', json={
                'username': 'migrationtest', 'password': 'temporary-password-123',
                'registration_code': 'migration-smoke-only'})
            assert response.status_code == 200, response.text
            lists = (await client.get('/api/books/lists')).json()
            voices = (await client.get('/api/voices')).json()
            assert lists, 'No legacy library was assigned'
            assert voices, 'No old custom voice was imported'
            print(f'migrated copy: {len(lists)} legacy lists, {len(voices)} reusable voices')
        await engine.dispose()
        await asyncio.sleep(.1)


if __name__ == '__main__':
    asyncio.run(main())
