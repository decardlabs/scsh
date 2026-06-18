"""APDU 历史记录管理。

v0.7.0 新增：
  apdu history     — 显示 APDU 历史记录
  apdu replay      — 重放指定编号的 APDU
  apdu search      — 搜索 APDU 历史
"""

from __future__ import annotations

import time
from typing import Any

from scsh.session import Session, ApduRecord


# ── apdu history ──

def cmd_apdu_history(args: str, session: Session) -> None:
    """apdu history — 显示 APDU 历史记录。"""
    history = session.apdu_history
    if not history:
        print("APDU 历史为空。")
        return

    # 解析参数
    stripped = args.strip()
    if stripped == "--all":
        show_count = len(history)
    elif stripped and stripped.isdigit():
        show_count = min(int(stripped), len(history))
    else:
        show_count = min(20, len(history))

    # 显示最近 N 条
    recent = history[-show_count:]
    print(f"APDU 历史（最近 {len(recent)} 条，共 {len(history)} 条）:")
    print(f"  {'#':>4s}  {'APDU':<32s}  {'Response':<16s}  {'Context'}")
    for rec in recent:
        # 截断过长的 APDU/Response
        apdu_short = rec.apdu[:30] + "…" if len(rec.apdu) > 30 else rec.apdu
        resp_short = rec.response[:14] + "…" if len(rec.response) > 14 else rec.response
        print(f"  {rec.index:>4d}  {apdu_short:<32s}  {resp_short:<16s}  {rec.context}")


# ── apdu replay ──

def cmd_apdu_replay(args: str, session: Session) -> None:
    """apdu replay — 重放指定编号的 APDU。"""
    history = session.apdu_history
    if not history:
        print("APDU 历史为空，无法重放。")
        return

    stripped = args.strip()
    if not stripped:
        print("用法: apdu replay <编号> | last")
        return

    if stripped == "last":
        target = history[-1]
    elif stripped.isdigit():
        idx = int(stripped)
        target = None
        for rec in history:
            if rec.index == idx:
                target = rec
                break
        if not target:
            print(f"编号 {idx} 不存在于历史记录中。")
            return
    else:
        print(f"无效参数: {stripped}")
        print("用法: apdu replay <编号> | last")
        return

    print(f"重放 #{target.index}: {target.apdu}")
    print(f"  上下文: {target.context}")

    # 通过 apdu send 重新发送
    from scsh.commands.apdu import cmd_send
    cmd_send(target.apdu, session)


# ── apdu search ──

def cmd_apdu_search(args: str, session: Session) -> None:
    """apdu search — 搜索 APDU 历史。"""
    history = session.apdu_history
    if not history:
        print("APDU 历史为空。")
        return

    keyword = args.strip().upper()
    if not keyword:
        print("用法: apdu search <关键词>")
        return

    results = []
    for rec in history:
        if keyword in rec.apdu.upper() or keyword in rec.response.upper() or keyword in rec.context.upper():
            results.append(rec)

    if not results:
        print(f"未找到包含 '{keyword}' 的 APDU 记录。")
        return

    print(f"搜索 '{keyword}' 匹配 {len(results)} 条:")
    print(f"  {'#':>4s}  {'APDU':<32s}  {'Response':<16s}  {'Context'}")
    for rec in results:
        apdu_short = rec.apdu[:30] + "…" if len(rec.apdu) > 30 else rec.apdu
        resp_short = rec.response[:14] + "…" if len(rec.response) > 14 else rec.response
        print(f"  {rec.index:>4d}  {apdu_short:<32s}  {resp_short:<16s}  {rec.context}")


# ── 记录辅助函数 ──

def record_apdu(
    session: Session,
    apdu_hex: str,
    response_hex: str,
    context: str = "",
) -> None:
    """记录一条 APDU 到 session.apdu_history。

    供 apdu send/select/repeat 等命令在发送后调用。
    """
    idx = len(session.apdu_history) + 1
    rec = ApduRecord(
        index=idx,
        apdu=apdu_hex,
        response=response_hex,
        context=context,
        timestamp=time.time(),
    )
    session.apdu_history.append(rec)
