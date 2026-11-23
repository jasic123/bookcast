import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from app.main import app


def test_deep_health_reports_missing_workers():
    async def check():
        with patch('app.main.Worker.all', return_value=[]), patch('app.main.redis_conn.ping', return_value=True):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                response = await client.get('/health/deep')
                assert response.status_code == 503
                checks = response.json()['checks']
                assert checks['database']['ok'] is True
                assert checks['redis']['ok'] is True
                assert checks['workers']['missing'] == ['audio', 'podcast', 'research']

    asyncio.run(check())


def test_deep_health_accepts_idle_workers_with_valid_heartbeat():
    async def check():
        worker = SimpleNamespace(
            key='rq:worker:idle',
            queues=[SimpleNamespace(name=name) for name in ('research', 'podcast', 'audio')],
        )
        with patch('app.main.Worker.all', return_value=[worker]), \
                patch('app.main.redis_conn.ping', return_value=True), \
                patch('app.main.redis_conn.ttl', return_value=200):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                response = await client.get('/health/deep')
                assert response.status_code == 200
                assert response.json()['checks']['workers']['ok'] is True

    asyncio.run(check())
