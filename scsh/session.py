"""会话状态对象。

将原本动态附着在 PCSCTransport 上的会话状态（last_apdu, timing, recording,
aid_aliases, config 等）集中为 Session dataclass。命令 handler 接收 Session
而非 PCSCTransport，通过 session.transport 访问 PC/SC 通信层。

v0.7.0: 新增 apdu_history 记录所有 APDU 交互，支持 replay/search。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApduRecord:
    """单条 APDU 交互记录。

    v0.7.0 新增。
    """
    index: int        # 序号（从 1 开始）
    apdu: str         # 发送的 APDU（十六进制）
    response: str     # 响应（十六进制 + SW）
    context: str      # 命令上下文（如 "card list", "apdu send"）
    timestamp: float  # 时间戳（time.time()）


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
    apdu_history: list[ApduRecord] = field(default_factory=list)  # v0.7.0
