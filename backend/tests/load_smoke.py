"""Run a bounded local API smoke load against a disposable database."""
import asyncio
import os
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


async def main():
    with tempfile.TemporaryDirectory(prefix='bookcast-load-') as temporary:
        database = Path(temporary) / 'load.db'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = {**os.environ, 'DATABASE_URL': f'sqlite+aiosqlite:///{database.as_posix()}',
               'AUTH_REGISTRATION_CODE': 'load-test-only'}
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app',
                                   '--host', '127.0.0.1', '--port', str(port)],
                                  cwd=Path(__file__).resolve().parents[1], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', timeout=10) as client:
                for _ in range(50):
                    try:
                        if (await client.get('/health')).status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    await asyncio.sleep(.1)
                else:
                    raise RuntimeError('Disposable API did not start')
                registered = await client.post('/api/auth/register', json={
                    'username': 'loadtest', 'password': 'long-load-password',
                    'registration_code': 'load-test-only'})
                assert registered.status_code == 200, registered.text
                token = client.cookies.get('bookcast_session')
                assert token
                semaphore = asyncio.Semaphore(20)

                async def request(index):
                    async with semaphore:
                        started = time.perf_counter()
                        async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}',
                                                     cookies={'bookcast_session': token}, timeout=10) as one:
                            if index < 300:
                                response = await one.get('/api/books/lists')
                            else:
                                response = await one.post('/api/voices/pronunciations', json={
                                    'original': f'word{index}', 'spoken': f'word {index}'})
                        return response.status_code, time.perf_counter() - started

                results = await asyncio.gather(*(request(i) for i in range(320)))
                latencies = sorted(duration for _, duration in results)
                errors = [status for status, _ in results if status != 200]
                assert not errors, f'{len(errors)} requests failed: {errors[:10]}'
                assert len((await client.get('/api/voices/pronunciations')).json()) == 20
                print(f'320 requests, concurrency 20: errors=0, median={statistics.median(latencies):.3f}s, '
                      f'p95={latencies[int(.95 * len(latencies))]:.3f}s, max={max(latencies):.3f}s')
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == '__main__':
    asyncio.run(main())
