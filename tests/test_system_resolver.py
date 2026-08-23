"""System inference from tool call parameters."""
import pytest

from app.services.system_resolver import UNKNOWN_SYSTEM, resolve_system


@pytest.mark.parametrize(
    "tool_name,params,expected",
    [
        ("http_post", {"url": "https://acme.my.salesforce.com/services/data"}, "salesforce"),
        ("http_get", {"url": "https://1234.suitetalk.api.netsuite.com/rest"}, "netsuite"),
        ("http_post", {"url": "https://acme.guidewire.com/cc/claims"}, "guidewire"),
        ("http_get", {"url": "https://internal.acme.corp/api"}, UNKNOWN_SYSTEM),
        ("salesforce_query", {"soql": "SELECT Id FROM Account"}, "salesforce"),
        ("db_query", {"table": "claims"}, UNKNOWN_SYSTEM),
        ("http_post", {}, UNKNOWN_SYSTEM),
    ],
)
def test_resolve_system(tool_name, params, expected):
    assert resolve_system(tool_name, params) == expected


def test_explicit_system_parameter_wins_over_domain():
    result = resolve_system(
        "http_post",
        {"url": "https://acme.my.salesforce.com/x", "system": "guidewire"},
    )
    assert result == "guidewire"


def test_resolution_is_case_insensitive_on_domain():
    assert resolve_system("http_get", {"url": "https://ACME.MY.SALESFORCE.COM/x"}) == "salesforce"
