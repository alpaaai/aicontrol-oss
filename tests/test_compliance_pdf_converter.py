"""Tests for compliance report PDF converter.

These tests require weasyprint system libraries (libpangoft2-1.0-0, libpangocairo-1.0-0).
They pass in the Docker container (which has those libs) and are skipped on host machines
that lack them.
"""
import pytest


def _weasyprint_available() -> bool:
    import ctypes.util
    return ctypes.util.find_library("pangoft2-1.0-0") is not None


if not _weasyprint_available():
    pytest.skip(
        "weasyprint system libraries not installed on this host "
        "(confirmed working in Docker — see Task 2 Docker verification)",
        allow_module_level=True,
    )

from enterprise.compliance.pdf_converter import convert_to_pdf  # noqa: E402

SAMPLE_MARKDOWN = """# AIControl Compliance Report

## Executive Summary

During the period 2026-01-01 to 2026-03-31, AIControl intercepted 847 calls.

## Agent Inventory

| Agent Name | Total Calls | Denied Calls |
|------------|-------------|--------------|
| loan-underwriting-agent | 412 | 8 |
| customer-support-agent | 312 | 4 |

## Interception Statistics

| Metric | Value |
|--------|-------|
| Total intercepts | 847 |
| Denial rate | 1.4% |

## Attestation of Technical Controls

Scope limitation: AIControl attests to the technical enforcement layer only.

_Report ID: test-report-id-123_
"""


def test_convert_returns_bytes():
    result = convert_to_pdf(SAMPLE_MARKDOWN)
    assert isinstance(result, bytes)


def test_pdf_starts_with_pdf_header():
    result = convert_to_pdf(SAMPLE_MARKDOWN)
    assert result[:4] == b"%PDF", f"Expected %PDF header, got {result[:4]!r}"


def test_pdf_length_exceeds_minimum():
    result = convert_to_pdf(SAMPLE_MARKDOWN)
    assert len(result) > 1000, f"PDF too small: {len(result)} bytes"


def test_convert_minimal_markdown():
    result = convert_to_pdf("# Test\n\nSimple paragraph.")
    assert result[:4] == b"%PDF"
