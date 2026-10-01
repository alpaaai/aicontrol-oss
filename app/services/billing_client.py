"""Server-to-server calls from this customer instance to billing-service
(plans/v4 task 18). Single place all outbound calls to billing.aictl.io go
through -- used by billing_usage() (task 19) and the daily license sync job
(task 20).
"""
from __future__ import annotations

import httpx

from app.core.config import settings

_TIMEOUT = httpx.Timeout(5.0, connect=5.0)


class BillingClientError(Exception):
    """Raised when billing-service is unreachable or returns an error
    response. Callers must catch this rather than letting a bare
    httpx.RequestError leak through."""
    pass


async def fetch_billing_urls(activation_code: str, plan: str) -> dict:
    """Manage-subscription URL for an existing billing-service customer,
    via POST /billing/portal keyed on the org's stored activation code.

    upgrade_url is only populated for a trial customer: billing-service's
    POST /billing/upgrade (added for mid-trial upgrades) requires the
    caller to already be on the "trial" plan and takes activation_code, not
    an email -- business/enterprise customers manage their subscription
    (including plan changes) through the portal URl above instead.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            portal_response = await client.post(
                f"{settings.AICONTROL_LICENSE_SYNC_URL}/billing/portal",
                json={"activation_code": activation_code},
            )
    except httpx.RequestError as exc:
        raise BillingClientError(f"billing-service unreachable: {exc}") from exc

    if portal_response.status_code != 200:
        raise BillingClientError(f"billing-service returned {portal_response.status_code}")

    upgrade_url = None
    if plan == "trial":
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                upgrade_response = await client.post(
                    f"{settings.AICONTROL_LICENSE_SYNC_URL}/billing/upgrade",
                    json={"activation_code": activation_code, "plan": "business"},
                )
        except httpx.RequestError as exc:
            raise BillingClientError(f"billing-service unreachable: {exc}") from exc
        if upgrade_response.status_code == 200:
            upgrade_url = upgrade_response.json()["url"]
        # A non-200 here (e.g. rate limited) isn't fatal to the overall
        # call -- the portal URL above still loaded fine, so degrade to no
        # upgrade link rather than raising.

    return {
        "manage_subscription_url": portal_response.json()["url"],
        "upgrade_url": upgrade_url,
    }


async def sync_license(activation_code: str) -> dict:
    """GET /license/sync, activation code as bearer token. Returns
    {"status": ..., "plan": ...}."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(
                f"{settings.AICONTROL_LICENSE_SYNC_URL}/license/sync",
                headers={"Authorization": f"Bearer {activation_code}"},
            )
    except httpx.RequestError as exc:
        raise BillingClientError(f"billing-service unreachable: {exc}") from exc

    if response.status_code != 200:
        raise BillingClientError(f"billing-service returned {response.status_code}")

    return response.json()
