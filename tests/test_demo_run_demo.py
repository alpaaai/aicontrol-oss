"""CLI wiring test for scripts/demos/run_demo.py. Verifies the argparse
--scenario choices come from scenarios.SCENARIOS (so a new scenario added to
scenarios.py is automatically selectable) and that main() forwards parsed
args to engine.dispatch() unchanged."""
import sys
from unittest.mock import patch

from scripts.demos import run_demo
from scripts.demos.scenarios import SCENARIOS


def test_main_forwards_args_to_dispatch():
    test_args = ["run_demo.py", "--scenario", "lending", "--token", "tok123", "--mode", "fast"]
    with patch.object(sys, "argv", test_args), patch("scripts.demos.run_demo.dispatch") as mock_dispatch:
        run_demo.main()
        mock_dispatch.assert_called_once_with("lending", "tok123", "fast")


def test_main_defaults_mode_to_walkthrough():
    test_args = ["run_demo.py", "--scenario", "insurance", "--token", "tok123"]
    with patch.object(sys, "argv", test_args), patch("scripts.demos.run_demo.dispatch") as mock_dispatch:
        run_demo.main()
        mock_dispatch.assert_called_once_with("insurance", "tok123", "walkthrough")


def test_unknown_scenario_rejected_by_argparse():
    test_args = ["run_demo.py", "--scenario", "not_a_real_scenario", "--token", "tok123"]
    with patch.object(sys, "argv", test_args):
        try:
            run_demo.main()
            assert False, "expected SystemExit"
        except SystemExit as e:
            assert e.code == 2


def test_all_scenario_names_are_selectable():
    parser_choices = run_demo.build_parser().parse_args(["--scenario", "mcp_gateway", "--token", "t"]).scenario
    assert parser_choices == "mcp_gateway"
    assert set(SCENARIOS.keys()) == set(run_demo.build_parser()._option_string_actions["--scenario"].choices)
