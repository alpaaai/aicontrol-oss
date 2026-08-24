"""CLI wiring test for scripts/demos/run_demo.py.

Rewritten for the phase-6 harness-driven CLI: --token is gone (the harness
self-registers its demo agent and issues its own token), and --scenario now
comes from the three harness scenarios (insurance, healthcare, gtm), not the
old scenarios.SCENARIOS dict.
"""
import sys
from unittest.mock import AsyncMock, patch

from scripts.demos import run_demo


def test_main_runs_the_harness_for_the_given_scenario():
    test_args = ["run_demo.py", "--scenario", "insurance", "--mode", "fast"]
    with patch.object(sys, "argv", test_args), \
         patch("scripts.demos.run_demo.DemoHarness") as mock_harness_cls, \
         patch("scripts.demos.run_demo.render"):
        mock_harness = mock_harness_cls.return_value
        mock_harness.run = AsyncMock(return_value=[])
        run_demo.main()
        mock_harness_cls.assert_called_once_with(scenario="insurance", live=False)


def test_live_flag_is_forwarded():
    test_args = ["run_demo.py", "--scenario", "insurance", "--live"]
    with patch.object(sys, "argv", test_args), \
         patch("scripts.demos.run_demo.DemoHarness") as mock_harness_cls, \
         patch("scripts.demos.run_demo.render"):
        mock_harness = mock_harness_cls.return_value
        mock_harness.run = AsyncMock(return_value=[])
        run_demo.main()
        mock_harness_cls.assert_called_once_with(scenario="insurance", live=True)


def test_main_defaults_mode_to_walkthrough():
    test_args = ["run_demo.py", "--scenario", "insurance"]
    with patch.object(sys, "argv", test_args), \
         patch("scripts.demos.run_demo.DemoHarness") as mock_harness_cls, \
         patch("scripts.demos.run_demo.render"):
        mock_harness = mock_harness_cls.return_value
        mock_harness.run = AsyncMock(return_value=[])
        run_demo.main()
        mock_harness.run.assert_awaited_once_with(mode="walkthrough")


def test_unknown_scenario_rejected_by_argparse():
    test_args = ["run_demo.py", "--scenario", "not_a_real_scenario"]
    with patch.object(sys, "argv", test_args):
        try:
            run_demo.main()
            assert False, "expected SystemExit"
        except SystemExit as e:
            assert e.code == 2


def test_all_scenario_names_are_selectable():
    parser_choices = run_demo.build_parser()._option_string_actions["--scenario"].choices
    assert set(parser_choices) == set(run_demo.SCENARIO_NAMES)
