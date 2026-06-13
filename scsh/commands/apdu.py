"""APDU 层命令：send / select / get-response / send-file。"""

from __future__ import annotations

from typing import Any

from scsh.exceptions import CardDisconnectedError, TransportError
from scsh.formats.apdu import (
    apdu_summary,
    format_apdu,
    format_response,
    parse_apdu_hex,
)


def cmd_send(args: str, transport: Any) -> None:
    """发送原始 APDU。"""
    if not args:
        print("用法: send <十六进制APDU>")
        return

    # 移除空格
    hex_str = args.strip()
    try:
        parsed = parse_apdu_hex(hex_str)
    except ValueError as exc:
        print(f"无效十六进制: {exc}")
        return

    # 显示发送内容
    print(f"→ {format_apdu(hex_str)}")

    # 构造字节
    apdu = (
        bytes([parsed["cla"], parsed["ins"], parsed["p1"], parsed["p2"]])
    )
    if parsed["lc"] is not None and parsed["data"] is not None:
        apdu += bytes([parsed["lc"]]) + parsed["data"]
    elif parsed["lc"] is not None:
        apdu += bytes([parsed["lc"]])

    if parsed["le"] is not None:
        apdu += bytes([parsed["le"]])

    # 保存为"上一条 APDU"（供 repeat 使用）
    transport._last_apdu = apdu
    transport._last_apdu_label = hex_str

    try:
        data, sw = transport.send_apdu(apdu)
    except CardDisconnectedError:
        print("卡片未连接")
        return
    except TransportError as exc:
        print(f"发送失败: {exc}")
        return

    print(f"← {format_response(data, sw)}")

    # 如果 timing 启用，记录耗时
    if hasattr(transport, "_timing_enabled") and transport._timing_enabled:
        duration = getattr(transport, "_last_duration_ms", 0)
        if isinstance(duration, (int, float)):
            print(f"  ⏱ {duration:.1f} ms")

    # 如果 recording 启用，记录到文件
    if hasattr(transport, "_recording") and transport._recording:
        record_path = getattr(transport, "_record_path", None)
        if isinstance(record_path, str):
            record_apdu(record_path, f"send {hex_str}")

    # 如果 log 启用，记录到日志文件
    log_path = getattr(transport, "_log_path", None)
    if isinstance(log_path, str):
        from scsh.formats.apdu import log_apdu
        log_apdu(log_path, hex_str, data, sw)


def cmd_select(args: str, transport: Any) -> None:
    """SELECT AID 快捷命令。"""
    if not args:
        print("用法: select <AID十六进制>")
        return

    aid_hex = args.strip().replace(" ", "")
    try:
        aid = bytes.fromhex(aid_hex)
    except ValueError:
        print("无效 AID 十六进制")
        return

    # 构造 SELECT APDU: 00 A4 04 00 Lc AID
    apdu = b"\x00\xA4\x04\x00" + bytes([len(aid)]) + aid
    label = apdu_summary(apdu.hex().upper())
    print(f"→ {label}")

    try:
        data, sw = transport.send_apdu(apdu)
    except CardDisconnectedError:
        print("卡片未连接")
        return
    except TransportError as exc:
        print(f"SELECT 失败: {exc}")
        return

    print(f"← {format_response(data, sw)}")


def cmd_get_response(args: str, transport: Any) -> None:
    """GET RESPONSE 命令。"""
    le = 0x100  # 默认 256
    if args:
        try:
            le = int(args.strip(), 16)
        except ValueError:
            le = 0x100

    apdu = b"\x00\xC0\x00\x00" + bytes([le if le < 0x100 else 0x00])
    label = apdu_summary(apdu.hex().upper())

    print(f"→ {label}")
    try:
        data, sw = transport.send_apdu(apdu)
    except CardDisconnectedError:
        print("卡片未连接")
        return
    except TransportError as exc:
        print(f"GET RESPONSE 失败: {exc}")
        return

    print(f"← {format_response(data, sw)}")


def cmd_send_file(args: str, transport: Any) -> None:
    """从文件读取 APDU 并逐条发送。
    
    支持格式：
    - 纯文本：每行一个 APDU 十六进制（支持 # 注释）
    - JSON：{"apdus": [{"apdu": "00A404...", "delay": 100}]}
    
    选项：
    --continue-on-error  遇到错误继续执行
    --delay <ms>         每条 APDU 之间延迟（毫秒）
    --output <file>       保存结果到文件
    """
    import re
    import json
    import time
    
    # 解析参数
    parts = args.strip().split()
    path = None
    continue_on_error = False
    delay_ms = 0
    output_file = None
    
    for i, part in enumerate(parts):
        if part == "--continue-on-error":
            continue_on_error = True
        elif part == "--delay":
            if i + 1 < len(parts):
                try:
                    delay_ms = int(parts[i + 1])
                except ValueError:
                    print(f"无效延迟值: {parts[i + 1]}")
                    return
        elif part == "--output":
            if i + 1 < len(parts):
                output_file = parts[i + 1]
        elif path is None:
            path = part
    
    if not path:
        print("用法: send-file <文件路径> [--continue-on-error] [--delay <ms>] [--output <file>]")
        return
    
    # 读取文件
    try:
        with open(path) as f:
            content = f.read()
    except FileNotFoundError:
        print(f"文件未找到: {path}")
        return
    except OSError as exc:
        print(f"读取文件失败: {exc}")
        return
    
    # 解析 APDU 列表
    apdu_list = []
    
    # 尝试解析 JSON 格式
    if content.strip().startswith("{"):
        try:
            data = json.loads(content)
            if "apdus" in data:
                for item in data["apdus"]:
                    apdu_hex = item["apdu"]
                    delay = item.get("delay", 0)
                    apdu_list.append((apdu_hex, delay))
        except json.JSONDecodeError as exc:
            print(f"JSON 解析失败: {exc}")
            return
    else:
        # 纯文本格式
        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # 支持 delay:100 语法
            delay = 0
            if stripped.startswith("delay:"):
                try:
                    delay = int(stripped.split(":")[1])
                    continue
                except (ValueError, IndexError):
                    pass
            apdu_list.append((stripped, delay))
    
    if not apdu_list:
        print("文件中没有找到有效的 APDU")
        return
    
    print(f"共 {len(apdu_list)} 条 APDU")
    
    # 打开输出文件
    output_handle = None
    if output_file:
        try:
            output_handle = open(output_file, "w")
            output_handle.write(f"# scsh send-file 结果: {path}\n")
            output_handle.write(f"# 共 {len(apdu_list)} 条 APDU\n\n")
        except OSError as exc:
            print(f"无法创建输出文件: {exc}")
            return
    
    # 逐条发送
    success_count = 0
    error_count = 0
    
    for i, (apdu_hex, item_delay) in enumerate(apdu_list, 1):
        # 显示进度
        progress = f"[{i}/{len(apdu_list)}]"
        print(f"{progress} {apdu_hex}")
        
        # 解析 APDU
        try:
            parsed = parse_apdu_hex(apdu_hex)
        except ValueError as exc:
            print(f"  ⚠️ 跳过: {exc}")
            error_count += 1
            if output_handle:
                output_handle.write(f"{progress} {apdu_hex} → 错误: {exc}\n")
            if not continue_on_error:
                break
            continue
        
        # 构造 APDU 字节
        apdu_bytes = bytes([parsed["cla"], parsed["ins"], parsed["p1"], parsed["p2"]])
        if parsed["data"] is not None:
            apdu_bytes += bytes([parsed["lc"]]) + parsed["data"]
        if parsed["le"] is not None:
            apdu_bytes += bytes([parsed["le"]])
        
        # 发送 APDU
        try:
            data, sw = transport.send_apdu(apdu_bytes)
            response = format_response(data, sw)
            print(f"  → {response}")
            success_count += 1
            
            if output_handle:
                output_handle.write(f"{progress} {apdu_hex}\n")
                output_handle.write(f"  → {response}\n\n")
                
        except CardDisconnectedError as exc:
            print(f"  → ❌ 卡片断开: {exc}")
            error_count += 1
            if output_handle:
                output_handle.write(f"{progress} {apdu_hex} → 错误: {exc}\n")
            if not continue_on_error:
                break
        except TransportError as exc:
            print(f"  → ❌ 传输错误: {exc}")
            error_count += 1
            if output_handle:
                output_handle.write(f"{progress} {apdu_hex} → 错误: {exc}\n")
            if not continue_on_error:
                break
        
        # 延迟
        actual_delay = max(delay_ms, item_delay)
        if actual_delay > 0:
            time.sleep(actual_delay / 1000.0)
    
    # 关闭输出文件
    if output_handle:
        output_handle.write(f"\n# 完成: 成功 {success_count}, 失败 {error_count}\n")
        output_handle.close()
        print(f"\n结果已保存到: {output_file}")
    
    print(f"\n完成: 成功 {success_count}, 失败 {error_count}")


# ── M5: 辅助命令 ──────────────────────────────────────────


def cmd_repeat(args: str, transport: Any) -> None:
    """重复上一条 APDU。"""
    last_apdu = getattr(transport, "_last_apdu", None)
    last_label = getattr(transport, "_last_apdu_label", "")

    if last_apdu is None:
        print("没有之前发送的 APDU")
        return

    count = 1
    if args:
        try:
            count = max(1, int(args.strip()))
        except ValueError:
            print("用法: repeat [次数]")
            return

    for i in range(count):
        try:
            data, sw = transport.send_apdu(last_apdu)
            label = f"[{i + 1}/{count}] " if count > 1 else ""
            print(f"{label}← {format_response(data, sw)}")
        except CardDisconnectedError as exc:
            print(f"卡片未连接: {exc}")
            break
        except Exception as exc:
            print(f"第 {i + 1} 次失败: {exc}")
            break


def cmd_timing(args: str, transport: Any) -> None:
    """切换 APDU 耗时显示。"""
    if not hasattr(transport, "_timing_enabled"):
        transport._timing_enabled = False

    if args:
        if args.strip().lower() in ("on", "1", "true"):
            transport._timing_enabled = True
        elif args.strip().lower() in ("off", "0", "false"):
            transport._timing_enabled = False
        else:
            print("用法: timing [on|off]")
            return

    status = "启用" if transport._timing_enabled else "关闭"
    print(f"APDU 耗时显示: {status}")


def cmd_record(args: str, transport: Any) -> None:
    """录制当前会话。"""
    if not args:
        print("用法: record <文件路径>")
        return

    path = args.strip()
    try:
        open(path, "w").close()
    except OSError as exc:
        print(f"无法创建录制文件: {exc}")
        return

    transport._recording = True
    transport._record_path = path
    print(f"开始录制会话到: {path}")


def record_apdu(record_path: str, command_line: str) -> None:
    """将一条命令追加到录制文件。"""
    try:
        with open(record_path, "a") as f:
            f.write(command_line + "\n")
    except OSError:
        pass
