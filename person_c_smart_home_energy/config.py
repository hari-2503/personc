"""Central configuration for Person C's service (12-factor: env vars only)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "smart-home-energy-monitor")
    service_owner: str = "Person C - Hariharan S (23MID0182)"
    version: str = "1.1.0"
    app_port: int = _get_int("APP_PORT", 8003)

    # Deviation above this percent (vs actual) flags a month for investigation.
    deviation_threshold_percent: float = _get_float("DEVIATION_THRESHOLD_PERCENT", 10.0)

    # Tariff set name used by /bill/estimate (see GET /tariffs).
    default_tariff: str = os.getenv("DEFAULT_TARIFF", "TNEB-Domestic-Monthly-Seed")


settings = Settings()
