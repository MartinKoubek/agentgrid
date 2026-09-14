from agentgrid_policy import PolicyDecision, PolicyEngine


def test_policy_allows_safe_actions() -> None:
    assert PolicyEngine().decide("run unit tests") == PolicyDecision.ALLOW


def test_policy_asks_for_destructive_actions() -> None:
    assert PolicyEngine().decide("delete project directory") == PolicyDecision.ASK_USER


def test_policy_denies_force_push() -> None:
    assert PolicyEngine().decide("force-push protected branch") == PolicyDecision.DENY
