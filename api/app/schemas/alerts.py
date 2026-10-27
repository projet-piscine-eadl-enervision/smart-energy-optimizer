from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AlertStatus = Literal["active", "resolved"]


class Alert(BaseModel):
    """Alerte d'un site.

    timestamp : heure de l'alerte donnée par sa source (le mock, ou une règle de l'ETL).
    received_at : dernier tour de collecte où l'alerte a été vue ; c'est le curseur de `since`.
    status : `active` si elle a été vue il y a moins de 15 minutes et n'est pas résolue.
    """

    alert_id: str
    timestamp: datetime
    received_at: datetime
    site_id: str
    site_name: str
    severity: str
    alert_type: str
    alert_label: str
    message: str | None
    value: float | None
    threshold: float | None
    origin: Literal["api", "rule"]
    status: AlertStatus
