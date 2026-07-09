import random


SCENARIOS = ("normal", "memory_warning", "os_warning", "mixed_warning")
_SCENARIO_CACHE: dict[str, str] = {}


def select_demo_scenario(db_name: str, run_id: str | None = None) -> str:
    """Select a demo scenario for placeholder data.

    Set DA_OPS_DEMO_SCENARIO to one of normal, memory_warning, os_warning,
    or mixed_warning to force a scenario. Otherwise, a scenario is selected
    randomly for each data fetch.
    """
    import os

    forced_scenario = os.getenv("DA_OPS_DEMO_SCENARIO")

    if forced_scenario in SCENARIOS:
        return forced_scenario

    cache_key = run_id or db_name

    if cache_key not in _SCENARIO_CACHE:
        _SCENARIO_CACHE[cache_key] = random.choice(SCENARIOS)

    return _SCENARIO_CACHE[cache_key]
