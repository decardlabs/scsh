"""不可逆操作保护。

对卡片终止、锁卡等不可逆操作要求用户二次确认。
显示操作后果警告，输入 'yes' 才执行。
"""

from __future__ import annotations

from scsh.session import Session


# ── 不可逆操作定义 ──

IRREVERSIBLE_OPERATIONS: dict[str, dict] = {
    "terminate": {
        "label": "卡片终止 (TERMINATED)",
        "warning": "⚠️ 此操作不可逆！卡片将永久无法使用，所有数据不可恢复。",
        "confirm_msg": "确认终止卡片？输入 'yes' 继续:",
    },
    "lock-card": {
        "label": "卡片锁定 (CARD_LOCKED)",
        "warning": "⚠️ 卡片将被锁定，只能通过 unlock 解锁。",
        "confirm_msg": "确认锁定卡片？输入 'yes' 继续:",
    },
}

# ── 安全确认 ──


def confirm_irreversible(action: str, session: Session) -> bool:
    """对不可逆操作进行安全确认。

    Returns:
        True: 用户确认执行
        False: 用户取消操作
    """
    op = IRREVERSIBLE_OPERATIONS.get(action)
    if not op:
        # 非预定义不可逆操作，默认不拦截
        return True

    print(op["warning"])
    print(op["confirm_msg"])

    # 在 REPL 上下文中用 input()，非交互模式直接拒绝
    try:
        answer = input("> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("操作已取消。")
        return False

    if answer != "yes":
        print("操作已取消。")
        return False

    return True


def is_irreversible(action: str) -> bool:
    """检查操作是否为不可逆操作。"""
    return action in IRREVERSIBLE_OPERATIONS


# ── 生命周期状态机 ──

LIFECYCLE_STATES = {
    "OP_READY": {
        "index": 0x01,
        "desc": "出厂就绪，可用默认密钥连接和管理",
        "allowed_next": ["INITIALIZED"],
    },
    "INITIALIZED": {
        "index": 0x03,
        "desc": "已初始化，LOAD/INSTALL 受限",
        "allowed_next": ["SECURED", "OP_READY"],
    },
    "SECURED": {
        "index": 0x5F,
        "desc": "安全状态，需要密钥认证才能管理",
        "allowed_next": ["CARD_LOCKED", "INITIALIZED"],
    },
    "CARD_LOCKED": {
        "index": 0x7F,
        "desc": "卡片已锁定，仅可解锁或终止",
        "allowed_next": ["SECURED", "TERMINATED"],
    },
    "TERMINATED": {
        "index": 0xFF,
        "desc": "已终止（不可逆）",
        "allowed_next": [],
    },
}

# action → 目标状态映射
LIFECYCLE_ACTION_MAP: dict[str, str] = {
    "init": "INITIALIZED",
    "secure": "SECURED",
    "lock": "CARD_LOCKED",
    "unlock": "SECURED",
    "terminate": "TERMINATED",
}


def validate_transition(current_state: str, action: str) -> tuple[bool, str]:
    """验证生命周期状态转换是否合法。

    Returns:
        (allowed, reason) — allowed=True 允许转换，reason 为拒绝原因。
    """
    target = LIFECYCLE_ACTION_MAP.get(action)
    if not target:
        return (False, f"未知操作: {action}")

    current = LIFECYCLE_STATES.get(current_state)
    if not current:
        # 未知当前状态，放行（卡片可能有非标准状态）
        return (True, "")

    allowed_next = current.get("allowed_next", [])
    if target not in allowed_next:
        return (
            False,
            f"状态转换不允许: {current_state} → {target}。"
            f"当前状态允许的转换: {', '.join(allowed_next) or '无（终态）'}",
        )

    return (True, "")


# ── Applet 状态 ──

APPLET_STATES: dict[str, int] = {
    "selectable": 0x01,
    "locked": 0x02,
    "blocked": 0x03,
}

APPLET_STATE_NAMES: dict[int, str] = {
    0x01: "SELECTABLE",
    0x02: "LOCKED",
    0x03: "BLOCKED",
}
