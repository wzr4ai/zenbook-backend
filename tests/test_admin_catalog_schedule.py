import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from main import create_app
from src.core.database import get_db
from src.core.deps import require_admin
from src.modules.users.models import User
from src.shared.enums import UserRole


@pytest_asyncio.fixture
async def admin_client(db_session):
    app = create_app()
    admin_user = User(
        user_id="01ADMINUSER0000000000000000",
        wechat_openid="admin-openid",
        role=UserRole.ADMIN,
        is_active=True,
    )

    async def override_db():
        yield db_session

    async def override_admin():
        return admin_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_admin] = override_admin

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_admin_catalog_crud(admin_client):
    client: AsyncClient = admin_client

    loc_resp = await client.post(
        "/api/v1/admin/catalog/locations",
        json={"name": "HQ", "address": "Road 1", "city": "Shanghai"},
    )
    loc_resp.raise_for_status()
    location_id = loc_resp.json()["id"]

    svc_resp = await client.post(
        "/api/v1/admin/catalog/services",
        json={"name": "Foot", "default_duration_minutes": 30, "concurrency_level": 2},
    )
    svc_resp.raise_for_status()
    service_id = svc_resp.json()["id"]

    tech_resp = await client.post(
        "/api/v1/admin/catalog/technicians",
        json={"display_name": "Therapist A"},
    )
    tech_resp.raise_for_status()
    technician_id = tech_resp.json()["id"]

    offering_resp = await client.post(
        "/api/v1/admin/catalog/offerings",
        json={
            "technician_id": technician_id,
            "service_id": service_id,
            "location_id": location_id,
            "price": "168.00",
            "duration_minutes": 60,
        },
    )
    offering_resp.raise_for_status()
    offering_id = offering_resp.json()["id"]

    update_resp = await client.put(
        f"/api/v1/admin/catalog/offerings/{offering_id}",
        json={"price": "188.00"},
    )
    update_resp.raise_for_status()
    assert update_resp.json()["price"] == "188.00"

    list_resp = await client.get("/api/v1/admin/catalog/offerings")
    assert list_resp.status_code == 200
    assert any(item["id"] == offering_id for item in list_resp.json())


@pytest.mark.asyncio
async def test_admin_schedule_crud(admin_client):
    client: AsyncClient = admin_client

    technician_id = (
        await client.post("/api/v1/admin/catalog/technicians", json={"display_name": "Sched Therapist"})
    ).json()["id"]
    location_id = (
        await client.post("/api/v1/admin/catalog/locations", json={"name": "Sched Location"})
    ).json()["id"]

    hours_payload = [
        {
            "technician_id": technician_id,
            "location_id": location_id,
            "rule_date": "2024-05-21",
            "start_time_am": "09:00:00",
            "end_time_am": "12:00:00",
        }
    ]
    create_resp = await client.post("/api/v1/admin/schedule/business-hours", json=hours_payload)
    create_resp.raise_for_status()
    rule_id = create_resp.json()[0]["rule_id"]

    update_resp = await client.put(
        f"/api/v1/admin/schedule/business-hours/{rule_id}",
        json={"start_time_pm": "14:00:00", "end_time_pm": "18:00:00"},
    )
    update_resp.raise_for_status()
    body = update_resp.json()
    assert body["start_time_pm"] == "14:00:00"
    assert body["end_time_pm"] == "18:00:00"
    assert body["rule_date"] == "2024-05-21"

    exception_resp = await client.post(
        "/api/v1/admin/schedule/exceptions",
        json={
            "technician_id": technician_id,
            "location_id": location_id,
            "date": "2024-05-20",
            "is_available": False,
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "reason": "break",
        },
    )
    exception_resp.raise_for_status()
    exception_id = exception_resp.json()["exception_id"]

    exception_update = await client.put(
        f"/api/v1/admin/schedule/exceptions/{exception_id}",
        json={"reason": "off-site"},
    )
    exception_update.raise_for_status()
    assert exception_update.json()["reason"] == "off-site"

    list_resp = await client.get("/api/v1/admin/schedule/exceptions")
    assert list_resp.status_code == 200
    assert any(item["exception_id"] == exception_id for item in list_resp.json())
