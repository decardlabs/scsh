"""会话状态对象。

将原本动态附着在 PCSCTransport 上的会话状态（last_apdu, timing, recording,
aid_aliases, config 等）集中为 Session dataclass。命令 handler 接收 Session
而非 PCSCTransport，通过 session.transport 访问 PC/SC 通信层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    """scsh 会话状态。"""

    transport: Any  # PCSCTransport (import 推迟以避免循环依赖)
    gp_bridge: Any = None  # GPJarBridge | None
    config_manager: Any = None  # ConfigManager | None (v0.4.0 新增)
    last_apdu: bytes | None = None
    last_apdu_label: str = ""
    timing_enabled: bool = False
    last_duration_ms: float = 0.0
    recording: bool = False
    record_path: str | None = None
    log_path: str | None = None
    aid_aliases: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    gp_key: str | None = None
