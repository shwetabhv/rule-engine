class RuleEngineError(Exception):
    """Base class for all rule-engine errors."""


class RuleValidationError(RuleEngineError):
    """Raised when a rule file, rule, or condition tree fails validation."""


class UnknownOperatorError(RuleEngineError):
    """Raised when a condition references an operator that isn't registered."""
