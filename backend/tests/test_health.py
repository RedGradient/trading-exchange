import pytest
import httpx
from httpx import ASGITransport
from fastapi import status
from app.main import app

@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, 
        base_url="http://localhost:8000"
    ) as client:
        response = await client.get("/health")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}