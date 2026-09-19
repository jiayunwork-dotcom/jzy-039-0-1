"""Service-wide constants."""

from __future__ import annotations

SERVICE_NAME = "normal-shock-service"
SERVICE_VERSION = "1.0.0"

# Specific gas constant for air [J/(kg·K)], used only when dimensional
# upstream conditions are supplied. Callers may override per request.
DEFAULT_GAS_CONSTANT = 287.053

# Hand-checkable seeded case: M1=2, gamma=1.4 (closed-form table values).
SEED_CASE_NAME = "seed-m2-g1.4"
SEED_CASE_CONDITION = {"mach1": 2.0, "gamma": 1.4}

MAX_CASE_NAME_LENGTH = 128
MAX_BATCH_SIZE = 1000
