"""Resolve a tool call to the business system it touches.

Resolution order (spec section 2.2):
  1. an explicit `system` parameter on the call
  2. a known SaaS domain in an http tool's URL
  3. a tool-name prefix matching a known connector
  4. UNKNOWN_SYSTEM

Stated fail-open: a policy bound to a system does not match a call whose
system could not be inferred. Mitigated by surfacing unresolved systems on
the agent (task 3.6) and by per-agent strict mode (task 7.1). Policies bound
only to agent + tool are unaffected.
"""
from typing import Any
from urllib.parse import urlparse

UNKNOWN_SYSTEM = "unknown"

HTTP_TOOLS = ("http_get", "http_post", "http_put", "http_delete", "http_patch")

# Domain suffix -> system name. Matched against the parsed netloc, lowercased.
DOMAIN_MAP: dict[str, str] = {
    "salesforce.com": "salesforce",
    "force.com": "salesforce",
    "netsuite.com": "netsuite",
    "guidewire.com": "guidewire",
    "workday.com": "workday",
    "servicenow.com": "servicenow",
    "atlassian.net": "jira",
    "zendesk.com": "zendesk",
    "hubspot.com": "hubspot",
    "stripe.com": "stripe",
    "epic.com": "epic",
    "cerner.com": "cerner",
}

# Tool-name prefix -> system name. Checked only when no URL resolved.
PREFIX_MAP: dict[str, str] = {
    "salesforce_": "salesforce",
    "netsuite_": "netsuite",
    "guidewire_": "guidewire",
    "workday_": "workday",
    "servicenow_": "servicenow",
    "jira_": "jira",
    "stripe_": "stripe",
}


def _system_from_url(url: str) -> str | None:
    netloc = urlparse(url).netloc.lower()
    if not netloc:
        return None
    host = netloc.split(":")[0]
    for suffix, system in DOMAIN_MAP.items():
        if host == suffix or host.endswith("." + suffix):
            return system
    return None


MAX_UNRESOLVED_TRACKED = 20


def merge_unresolved(existing: list[str] | None, tool_name: str) -> list[str]:
    """Append a tool whose system could not be inferred, distinct and bounded.

    This is the 2.2 fail-open mitigation: a policy bound to a system silently
    does not match a call whose system is unknown, so the unknowns have to be
    visible for an admin to correct the mapping.
    """
    current = list(existing or [])
    if tool_name in current:
        return current
    return (current + [tool_name])[-MAX_UNRESOLVED_TRACKED:]


def resolve_system(tool_name: str, tool_parameters: dict[str, Any]) -> str:
    """Return the business system this tool call touches, or UNKNOWN_SYSTEM."""
    explicit = tool_parameters.get("system")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().lower()

    if tool_name in HTTP_TOOLS:
        url = tool_parameters.get("url")
        if isinstance(url, str) and url:
            resolved = _system_from_url(url)
            if resolved:
                return resolved

    for prefix, system in PREFIX_MAP.items():
        if tool_name.startswith(prefix):
            return system

    return UNKNOWN_SYSTEM
