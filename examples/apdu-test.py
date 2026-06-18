#!/usr/bin/env python3
# ============================================================
# scsh 批量 APDU 测试脚本示例
# 文件名: examples/apdu-test.py
# 用途: 通过 subprocess 调用 scsh 进行批量 APDU 测试
# 依赖: pip install pyscard prompt_toolkit
# ============================================================

import subprocess
import sys
import time

SCSH = ["python3", "-m", "scsh"]


def run_scsh_command(cmd: str) -> str:
    """在 scsh REPL 中执行一条命令，返回输出。"""
    # 注意: 此为示例，实际应使用 pyscard 直接通信
    # 或通过 scsh 的 Python API 调用
    result = subprocess.run(
        SCSH + ["-c", cmd],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout + result.stderr


def test_fido2_applet():
    """测试 FIDO2 Applet 基本功能。"""
    print("=== FIDO2 Applet 功能测试 ===\n")

    tests = [
        ("选择 FIDO2 Applet", "apdu select A000000002000001"),
        ("获取版本号", "apdu send 00CB0000"),
        ("获取 AAGUID", "apdu send 80CB0000"),
    ]

    for desc, cmd in tests:
        print(f"测试: {desc}")
        print(f"  命令: {cmd}")
        output = run_scsh_command(cmd)
        print(f"  输出: {output[:200]}...")
        time.sleep(0.5)

    print("\n=== 测试完成 ===")


def test_hello_world():
    """测试 HelloWorld Applet。"""
    print("=== HelloWorld Applet 测试 ===\n")

    tests = [
        ("选择 Applet", "apdu select A000000001000001"),
        ("发送测试指令", "apdu send 0000000008"),
    ]

    for desc, cmd in tests:
        print(f"测试: {desc}")
        output = run_scsh_command(cmd)
        print(f"  结果: {output.strip()}")
        time.sleep(0.5)

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "fido2":
            test_fido2_applet()
        elif sys.argv[1] == "hello":
            test_hello_world()
        else:
            print(f"未知测试: {sys.argv[1]}")
            print("用法: apdu-test.py [fido2|hello]")
    else:
        test_hello_world()
        print()
        test_fido2_applet()
