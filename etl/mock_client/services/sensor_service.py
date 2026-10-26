from mock_client.client import get_json
from mock_client.schemas.sensor import SiteSensors


def parse_sensors_status(data: dict) -> list[SiteSensors]:
    """Le mock renvoie un objet indexé par site_id."""
    return [SiteSensors(site_id=site_id, **info) for site_id, info in data.items()]


async def get_sensors_status() -> list[SiteSensors]:
    """État des capteurs de chaque site."""
    return parse_sensors_status(await get_json("/sensors/status"))
