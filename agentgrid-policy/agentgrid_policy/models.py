from enum import StrEnum


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    ASK_USER = "ASK_USER"
    DENY = "DENY"
