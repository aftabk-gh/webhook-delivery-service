import asyncio
import sys
from typing import TypedDict

from app.database import AsyncSessionLocal, Base, engine
from app.queries.endpoint import add_endpoint, build_endpoint
from app.queries.tenant import add_tenant, build_tenant


class SeedEndpoint(TypedDict):
    url: str
    event_types: list[str]


class SeedTenant(TypedDict):
    name: str
    endpoints: list[SeedEndpoint]


# replace below urls with original ones from https://webhook.site/

WEBHOOK_URLS = [
    "https://webhook.site/2fd8a7d3-8e19-4991-8332-0b643ad70c91",
    "https://webhook.site/97fb8ddf-634c-47bf-9ff1-417b061cf6f3",
    "https://webhook.site/7339ed21-5feb-4c51-8727-3d54413fdbf2",
]

TENANTS: list[SeedTenant] = [
    {
        "name": "tenant-alpha",
        "endpoints": [
            {
                "url": WEBHOOK_URLS[0],
                "event_types": ["order.created", "order.cancelled"],
            },
            {
                "url": WEBHOOK_URLS[1],
                "event_types": ["order.created"],
            },
        ],
    },
    {
        "name": "tenant-beta",
        "endpoints": [
            {
                "url": WEBHOOK_URLS[2],
                "event_types": ["user.signup"],
            },
        ],
    },
]


async def reset_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    print("--- DB reset complete ---\n")


async def seed() -> None:
    should_reset = "--reset" in sys.argv

    if should_reset:
        await reset_db()

    async with AsyncSessionLocal() as session:
        for tenant_data in TENANTS:
            tenant = build_tenant(name=tenant_data["name"])
            add_tenant(session, tenant)
            await session.flush()

            for endpoint_data in tenant_data["endpoints"]:
                endpoint = build_endpoint(
                    tenant_id=tenant.id,
                    url=endpoint_data["url"],
                    event_types=endpoint_data["event_types"],
                )
                add_endpoint(session, endpoint)

            await session.commit()
            await session.refresh(tenant)

            endpoint_urls = [
                endpoint_data["url"] for endpoint_data in tenant_data["endpoints"]
            ]
            print(f"Tenant: {tenant.name}")
            print(f"  id:             {tenant.id}")
            print(f"  api_key:        {tenant.api_key}")
            print(f"  signing_secret: {tenant.signing_secret}")
            print(f"  endpoints:      {endpoint_urls}")
            print()


if __name__ == "__main__":
    asyncio.run(seed())
