from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_trial_expiry_started_on_startup():
    import app.main as _main

    with patch("app.services.trial_expiry.TrialExpiry.start"):
        async with _main.lifespan(_main.app):
            assert _main.app.state.trial_expiry is not None
            assert _main.app.state.trial_expiry.status == "healthy"
