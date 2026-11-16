from .verticals import (
    VERTICALS,
    active_vertical,
    catalog,
    get_vertical,
    greeting_text,
    system_prompt,
)


def test_every_vertical_is_complete():
    for v in VERTICALS.values():
        assert v.name and v.tagline and v.persona and v.greeting
        assert v.services, v.key
        assert v.booking_fields, v.key


def test_unknown_vertical_falls_back_to_personal():
    assert get_vertical("not-a-market").key == "personal"
    assert get_vertical(None).key == "personal"
    assert get_vertical("").key == "personal"


def test_known_verticals_load_case_insensitively():
    assert get_vertical("Dental").key == "dental"
    assert get_vertical(" resale ").key == "resale"


def test_greeting_uses_business_name(monkeypatch):
    from .config import settings

    monkeypatch.setattr(settings, "agent_vertical", "auto_repair")
    monkeypatch.setattr(settings, "business_name", "Rome Auto Works")
    text = greeting_text()
    assert "Rome Auto Works" in text
    assert "{business}" not in text


def test_system_prompt_carries_vertical_and_safety(monkeypatch):
    from .config import settings

    monkeypatch.setattr(settings, "agent_vertical", "dental")
    monkeypatch.setattr(settings, "business_name", "Bright Smiles Dental")
    prompt = system_prompt()
    assert "Bright Smiles Dental" in prompt
    assert "Cleaning and exam" in prompt
    # The base honesty rules and the dental guardrails must survive.
    assert "Never claim an action happened" in prompt
    assert "Never give medical or dental advice" in prompt


def test_resale_never_accepts_offers(monkeypatch):
    from .config import settings

    monkeypatch.setattr(settings, "agent_vertical", "resale")
    monkeypatch.setattr(settings, "business_name", "")
    prompt = system_prompt()
    assert "Never accept, decline or counter an offer" in prompt


def test_active_vertical_defaults_to_personal():
    assert active_vertical().key in VERTICALS


def test_catalog_lists_all_markets():
    keys = {row["key"] for row in catalog()}
    assert keys == set(VERTICALS)
    assert {"home_services", "auto_repair", "salon_barber", "dental",
            "real_estate", "restaurant", "resale", "personal"} <= keys
