"""Les schémas de données sont documentés dans /docs : chaque champ a une description."""
import pytest

SCHEMAS = ["Prediction", "PeakHour", "ConsumptionPoint", "Recommendation"]


@pytest.mark.parametrize("name", SCHEMAS)
def test_every_field_has_a_description(client, name):
    schema = client.get("/openapi.json").json()["components"]["schemas"][name]

    assert schema.get("description")
    missing = [field for field, spec in schema["properties"].items() if not spec.get("description")]
    assert missing == []
