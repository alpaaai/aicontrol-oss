import pytest


def test_registry_registers_and_gets_adapter():
    from aicontrol_sdk.adapters import ADAPTER_REGISTRY, get, register

    class FakeAdapter:
        name = "fake"

        def is_available(self):
            return True

        def patch(self, client):
            pass

        def extract_usage(self, response):
            return {}

    register(FakeAdapter())
    assert get("fake").name == "fake"
    ADAPTER_REGISTRY.pop("fake", None)


def test_registry_get_unknown_raises_keyerror():
    from aicontrol_sdk.adapters import get

    with pytest.raises(KeyError):
        get("does-not-exist")


def test_builtin_adapters_registered_by_name():
    from aicontrol_sdk.adapters import get

    assert get("anthropic").name == "anthropic"
    assert get("openai_agents").name == "openai_agents"
    assert get("google_adk").name == "google_adk"
