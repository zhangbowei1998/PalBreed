"""PEP 420 兼容命名空间包 — 允许 pl_agent 跨多包分布."""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
