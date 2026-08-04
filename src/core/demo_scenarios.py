SCENARIOS = (
    "normal",
    "memory_warning",
    "os_warning",
    "memory_os_warning",
    "tempspace_warning",
    "log_write_warning",
    "tempspace_log_write_warning",
    "mixed_warning",
)

DB_SCENARIO_MAP = {
    "TESTDB": "mixed_warning",
    "APPDB": "normal",
    "PAYDB": "memory_os_warning",
    "DWDB": "tempspace_log_write_warning",
}


def select_demo_scenario(db_name: str, run_id: str | None = None) -> str:
    """Select a demo scenario for placeholder data.

    Set DA_OPS_DEMO_SCENARIO to one of SCENARIOS to force a scenario.
    Without an environment override, known demo DB names map to fixed scenarios.
    Unknown DB names default to normal.
    """
    import os

    forced_scenario = os.getenv("DA_OPS_DEMO_SCENARIO")

    if forced_scenario in SCENARIOS:
        return forced_scenario

    return DB_SCENARIO_MAP.get(db_name.upper(), "normal")


def scenario_has_warning(scenario: str, domain: str) -> bool:
    """Return whether a scenario includes a warning for the given domain."""
    warning_domains = {
        "memory_warning": {"memory"},
        "os_warning": {"os"},
        "memory_os_warning": {"memory", "os"},
        "tempspace_warning": {"tempspace"},
        "log_write_warning": {"log_write"},
        "tempspace_log_write_warning": {"tempspace", "log_write"},
        "mixed_warning": {"memory", "os", "tempspace", "log_write"},
    }

    return domain in warning_domains.get(scenario, set())
