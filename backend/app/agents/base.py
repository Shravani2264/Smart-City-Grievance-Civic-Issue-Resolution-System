import time
from dataclasses import dataclass, field


@dataclass
class AgentResult:
    agent: str
    output: dict
    reasoning: str
    mode: str = "rules"          # "rules" | "ai" | "ai+rules"
    ms: float = 0.0
    events: list = field(default_factory=list)

    def as_trace(self, step):
        return {"step": step, "agent": self.agent, "output": self.output, "reasoning": self.reasoning,
                "mode": self.mode, "ms": round(self.ms, 1)}


class Agent:
    name = "agent"

    def timed(self, fn, *args, **kwargs) -> AgentResult:
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        result.ms = (time.perf_counter() - t0) * 1000
        return result
