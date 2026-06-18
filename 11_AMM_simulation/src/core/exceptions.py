"""Domain exceptions for the AMM simulation."""


class AMMException(Exception):
    """Base exception for all AMM-related errors."""
    pass


class InsufficientLiquidityError(AMMException):
    """Pool has insufficient reserves to execute the swap."""
    def __init__(self, pool_id: str, token: str, requested: str, available: str):
        self.pool_id = pool_id
        self.token = token
        self.requested = requested
        self.available = available
        super().__init__(
            f"Pool '{pool_id}': insufficient {token} liquidity. "
            f"Requested {requested}, available {available}"
        )


class SlippageExceededError(AMMException):
    """The actual output amount is less than the minimum specified."""
    def __init__(self, expected: str, minimum: str):
        self.expected = expected
        self.minimum = minimum
        super().__init__(
            f"Slippage exceeded: expected output {expected} < minimum {minimum}"
        )


class InvalidPoolError(AMMException):
    """The specified pool does not exist or is invalid."""
    def __init__(self, pool_id: str):
        self.pool_id = pool_id
        super().__init__(f"Pool '{pool_id}' not found or invalid")


class InsufficientBalanceError(AMMException):
    """User does not have enough balance to perform the operation."""
    def __init__(self, user_id: str, token: str, required: str, available: str):
        self.user_id = user_id
        self.token = token
        self.required = required
        self.available = available
        super().__init__(
            f"User '{user_id}': insufficient {token} balance. "
            f"Required {required}, available {available}"
        )


class InvalidOperationError(AMMException):
    """The requested operation is invalid in the current state."""
    pass


class RatioMismatchError(AMMException):
    """Liquidity deposit ratio does not match pool reserves."""
    def __init__(self, expected_ratio: str, provided_ratio: str):
        super().__init__(
            f"Liquidity ratio mismatch: pool ratio {expected_ratio}, "
            f"provided ratio {provided_ratio}"
        )
