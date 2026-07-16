from unittest.mock import MagicMock, patch

import enterprise.compliance.service as service_module
from enterprise.compliance.service import ComplianceReportService


def test_service_uses_configured_reports_dir(tmp_path):
    configured_dir = tmp_path / "configured-reports"
    with patch.object(service_module.settings, "REPORTS_DIR", str(configured_dir)):
        with patch("enterprise.compliance.service.LocalFileStorage") as mock_cls:
            ComplianceReportService(db=MagicMock())
            mock_cls.assert_called_once_with(base_dir=str(configured_dir))
