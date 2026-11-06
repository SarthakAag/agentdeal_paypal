import threading

_engine = None
_init = threading.Lock()


def get_engine():
    """One shared LoRAEngine for negotiations and the assist features. Loads on first use."""
    global _engine
    with _init:
        if _engine is None:
            from .agents.lora_agent import LoRAEngine
            _engine = LoRAEngine()
        return _engine