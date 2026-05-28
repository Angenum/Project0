"""Тесты conditional edges."""
from __future__ import annotations

import pytest

from src.routers import route_after_tester, route_after_critic
from src.state import PipelineState


def make_state(flags: dict, retries: dict) -> PipelineState:
    return {
        "goal": "",
        "requirements": None,
        "messages": [],
        "artifacts": {},
        "retry_counters": retries,
        "flags": flags,
        "metadata": {},
        "current_step": "",
        "error": None,
    }


@pytest.mark.parametrize("retries,expected", [
    ({"tester_builder": 0}, "builder"),
    ({"tester_builder": 1}, "builder"),
    ({"tester_builder": 2}, "critic"),
    ({"tester_builder": 5}, "critic"),
])
def test_route_after_tester_failed(retries, expected):
    state = make_state(flags={"tests_passed": False}, retries=retries)
    assert route_after_tester(state) == expected


def test_route_after_tester_passed():
    state = make_state(flags={"tests_passed": True}, retries={"tester_builder": 0})
    assert route_after_tester(state) == "critic"


@pytest.mark.parametrize("retries,expected", [
    ({"critic_builder": 0}, "builder"),
    ({"critic_builder": 2}, "security_auditor"),
    ({"critic_builder": 3}, "security_auditor"),
])
def test_route_after_critic_failed(retries, expected):
    state = make_state(flags={"critic_passed": False}, retries=retries)
    assert route_after_critic(state) == expected


def test_route_after_critic_passed():
    state = make_state(flags={"critic_passed": True}, retries={"critic_builder": 0})
    assert route_after_critic(state) == "security_auditor"
