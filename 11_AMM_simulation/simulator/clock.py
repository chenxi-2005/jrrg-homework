"""Discrete simulation clock."""


class SimulationClock:
    """Monotonic step counter for the discrete-event simulation."""

    def __init__(self, start_step: int = 0):
        self._step: int = start_step
        self._paused: bool = False

    @property
    def step(self) -> int:
        return self._step

    @property
    def paused(self) -> bool:
        return self._paused

    def advance(self, steps: int = 1) -> int:
        """Advance the clock by `steps`. Returns the new step number."""
        if not self._paused:
            self._step += steps
        return self._step

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def reset(self, start_step: int = 0) -> None:
        self._step = start_step
        self._paused = False

    def __repr__(self) -> str:
        state = "paused" if self._paused else "running"
        return f"SimulationClock(step={self._step}, {state})"
