from typing import Literal

from mock_client.client import get_json
from mock_client.schemas.alert import Alert

Severity = Literal["low", "medium", "high", "critical"]


def parse_alerts(items: list) -> list[Alert]:
    return [Alert.model_validate(item) for item in items]


async def get_alerts(site_id: str | None = None, severity: Severity | None = None) -> list[Alert]:
    """Alertes de consommation actives (liste vide possible)."""
    params = {
        key: value
        for key, value in {"site_id": site_id, "severity": severity}.items()
        if value
    }
    return parse_alerts(await get_json("/alerts", params))
