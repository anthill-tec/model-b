"""Neutral hook-definition schema validation (CR-MDB-015 §S2).

Validates a parsed schema instance (one TOML table -> ``dict``) against
``hooks-src/schema.md`` v1: the six portable fields (``event``, ``matcher``,
``command``, ``tier``, ``timeout``, ``fail_direction``), the universal event
set, and the security-class rule — a hook whose ``command`` targets a
``block-*`` guard script MUST declare ``fail_direction``.

Stdlib only (pure runtime path).
"""

SCHEMA_VERSION = "v1"

VALID_EVENTS = frozenset({
    "pre-tool-use",
    "post-tool-use",
    "session-start",
    "turn-stop",
    "prompt-submit",
    "pre-compact",
})

VALID_TIERS = frozenset({"core", "extended", "harness-specific"})

VALID_FAIL_DIRECTIONS = frozenset({"open", "closed"})

#: schema.md v1 security-class signal: the command targets a blocking guard.
_SECURITY_CLASS_PREFIX = "block-"


def is_security_class(command: str) -> bool:
    """True when ``command`` targets a blocking (``block-*``) guard script.

    Per schema.md v1 the ``command`` field is a bare protocol-script name,
    but a defensive basename split keeps a pathy value classified correctly.
    """
    name = command.rsplit("/", 1)[-1]
    return name.startswith(_SECURITY_CLASS_PREFIX)


def validate_schema(instance: dict) -> list[str]:
    """Validate one neutral hook-schema instance against schema.md v1.

    Returns an empty list for a valid instance; otherwise one error string
    per problem, each prefixed ``"<field>: "`` naming the offending field.
    """
    errors: list[str] = []

    event = instance.get("event")
    if event is None:
        errors.append("event: required field is missing")
    elif not isinstance(event, str) or event not in VALID_EVENTS:
        errors.append(
            f"event: {event!r} is not in the universal event set "
            f"{sorted(VALID_EVENTS)}"
        )

    matcher = instance.get("matcher")
    if matcher is not None and (not isinstance(matcher, str) or not matcher):
        errors.append(f"matcher: must be a non-empty string, got {matcher!r}")

    command = instance.get("command")
    if command is None:
        errors.append("command: required field is missing")
    elif not isinstance(command, str) or not command:
        errors.append(f"command: must be a non-empty string, got {command!r}")

    tier = instance.get("tier")
    if tier is not None and (not isinstance(tier, str) or tier not in VALID_TIERS):
        errors.append(f"tier: {tier!r} is not one of {sorted(VALID_TIERS)}")

    timeout = instance.get("timeout")
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, int)
        or timeout <= 0
    ):
        errors.append(
            f"timeout: must be a positive integer (seconds), got {timeout!r}"
        )

    fail_direction = instance.get("fail_direction")
    if fail_direction is not None and fail_direction not in VALID_FAIL_DIRECTIONS:
        errors.append(
            f"fail_direction: {fail_direction!r} is not one of "
            f"{sorted(VALID_FAIL_DIRECTIONS)}"
        )
    elif (
        fail_direction is None
        and isinstance(command, str)
        and is_security_class(command)
    ):
        errors.append(
            "fail_direction: required for a security-class hook (command "
            f"{command!r} targets a block-* guard script; see schema.md v1)"
        )

    return errors
