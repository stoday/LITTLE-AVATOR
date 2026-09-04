from fastapi.testclient import TestClient

from p2026_little_avator.api import app


def test_running_little_avator_publishes_a_generic_a2a_agent_card() -> None:
    response = TestClient(app).get("/.well-known/agent-card.json")

    assert response.status_code == 200
    card = response.json()
    assert card["version"] == "0.1.0"
    assert card["supportedInterfaces"] == [
        {
            "protocolBinding": "HTTP+JSON",
            "protocolVersion": "1.0",
            "url": "http://127.0.0.1:8765/a2a",
        }
    ]
    assert [(skill["id"], skill["name"]) for skill in card["skills"]] == [
        ("natural-language-discussion", "Natural-language discussion")
    ]
    assert "calendar" not in str(card["skills"]).lower()
    assert card["securitySchemes"] == {
        "developmentBearer": {"httpAuthSecurityScheme": {"scheme": "Bearer"}}
    }
    assert card["securityRequirements"] == [{"schemes": {"developmentBearer": {}}}]
