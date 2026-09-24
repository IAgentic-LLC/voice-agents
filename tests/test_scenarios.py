"""Chapter 23: every registered scenario points at a real file that
actually exists, checked once here, before any of them are run
live."""

import os

from voicelab.scenarios import SCENARIOS


def test_every_scenario_question_file_exists():
    for name, s in SCENARIOS.items():
        assert os.path.exists(s.question), f"{name}: {s.question}"


def test_every_scenario_interrupt_file_exists_if_given():
    for name, s in SCENARIOS.items():
        if s.interrupt:
            assert os.path.exists(s.interrupt), f"{name}: {s.interrupt}"
