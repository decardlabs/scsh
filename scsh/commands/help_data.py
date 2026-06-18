"""三层 Help 数据库。

每条命令的 help_data 包含三个信息层：
- apdu: 底层 GP 操作名、gp.jar 映射、APDU CLA/INS/P1P2 流程
- diagnostic: 常见 SW → 原因 → 修复建议
- usage: 用法 + 示例

v0.4.0 先覆盖高频命令，其余命令 help_data 留空（只显示 help_text）。
"""

from __future__ import annotations

from typing import Any


# ── card 子系统 ──

CARD_HELP: dict[str, dict[str, Any]] = {
    "list": {
        "apdu": {
            "gp_op": "GET STATUS",
            "gp_jar": "--list",
            "apdu_flow": [
                "1. SELECT ISD → CLA=00 INS=A4 P1=04 P2=00",
                "2. GET STATUS (card manager) → CLA=80 INS=F2 P1=80 P2=00 Le=00",
                "3. GET STATUS (applications) → CLA=80 INS=F2 P1=40 P2=00 Le=00",
            ],
        },
        "diagnostic": {
            "6A82": {"cause": "ISD 未找到", "fix": "检查卡片 AID 或执行 connect"},
            "6985": {"cause": "安全条件不满足", "fix": "需要先建立 SCP 通道（自动处理）"},
        },
        "usage": [
            "card list",
            "gp-list",
        ],
    },
    "info": {
        "apdu": {
            "gp_op": "GET DATA + GET STATUS（info/scp/status 三合一）",
            "gp_jar": "--info + --list",
            "apdu_flow": [
                "1. SELECT ISD → CLA=00 INS=A4 P1=04 P2=00",
                "2. GET DATA (CPLC) → CLA=80 INS=CA P1=9F P2=7F",
                "3. GET STATUS → CLA=80 INS=F2 P1=80/40 P2=00",
            ],
        },
        "diagnostic": {
            "6A82": {"cause": "ISD 未找到", "fix": "执行 connect 连接读卡器"},
        },
        "usage": [
            "card info",
            "gp-info（仅基本信息）",
            "gp-scp（仅安全通道）",
            "gp-status（仅生命周期）",
        ],
    },
    "lifecycle": {
        "apdu": {
            "gp_op": "SET STATUS",
            "gp_jar": "--initialize-card / --secure-card / --lock-card / --unlock-card / --terminate-card",
            "apdu_flow": [
                "card lifecycle init:      SET STATUS → CLA=80 INS=F0 P1=80 P2=00 Lc=01 <01>",
                "card lifecycle secure:    SET STATUS → CLA=80 INS=F0 P1=40 P2=00 Lc=01 <03>",
                "card lifecycle lock:      SET STATUS → CLA=80 INS=F0 P1=40 P2=00 Lc=01 <7F>",
                "card lifecycle unlock:    SET STATUS → CLA=80 INS=F0 P1=40 P2=00 Lc=01 <5F>",
                "card lifecycle terminate: SET STATUS → CLA=80 INS=F0 P1=40 P2=00 Lc=01 <FF> ⚠️不可逆",
            ],
        },
        "diagnostic": {
            "6985": {"cause": "状态转换不允许", "fix": "检查当前生命周期状态，部分转换不可逆"},
            "6A80": {"cause": "数据错误", "fix": "SET STATUS 参数不正确"},
        },
        "usage": [
            "card lifecycle          # 显示当前生命周期状态 + 状态机图",
            "card lifecycle init     # OP_READY → INITIALIZED",
            "card lifecycle secure   # INITIALIZED → SECURED",
            "card lifecycle lock     # SECURED → CARD_LOCKED",
            "card lifecycle unlock   # CARD_LOCKED → SECURED",
            "card lifecycle terminate # CARD_LOCKED → TERMINATED ⚠️不可逆",
        ],
    },
    "applet-state": {
        "apdu": {
            "gp_op": "SET STATUS (Applet 级)",
            "gp_jar": "无直接映射（通过 --secure-apdu 实现）",
            "apdu_flow": [
                "SET STATUS → CLA=80 INS=E6 P2=02 Lc=<AID_len+1> <AID> <01/02/03>",
                "  01 = SELECTABLE",
                "  02 = LOCKED",
                "  03 = BLOCKED",
            ],
        },
        "diagnostic": {
            "6985": {"cause": "Applet 状态转换不允许", "fix": "检查 Applet 当前状态和目标状态"},
        },
        "usage": [
            "card applet-state <AID>           # 查看当前状态",
            "card applet-state <AID> selectable # 设为可选",
            "card applet-state <AID> locked     # 锁定 Applet",
            "card applet-state <AID> blocked    # 阻塞 Applet",
        ],
    },
    "store-data": {
        "apdu": {
            "gp_op": "STORE DATA",
            "gp_jar": "--store-data <hex>",
            "apdu_flow": [
                "STORE DATA → CLA=80 INS=E2 P1=80 P2=00 Lc=<data_len> <data>",
            ],
        },
        "diagnostic": {
            "6985": {"cause": "STORE DATA 条件不满足", "fix": "需要 SCP 安全通道"},
        },
        "usage": [
            "card store-data <hex>",
            "gp-store-data <hex>",
        ],
    },
    "create-domain": {
        "apdu": {
            "gp_op": "INSTALL [for install] (SSD)",
            "gp_jar": "--domain <AID>",
            "apdu_flow": [
                "INSTALL → CLA=E6 INS=08 P1=02 P2=00 Lc=<AID+params>",
            ],
        },
        "diagnostic": {
            "6985": {"cause": "SSD 创建条件不满足", "fix": "需要 ISD 权限"},
        },
        "usage": [
            "card create-domain <AID>",
            "gp-create-domain <AID>",
        ],
    },
    "rename-isd": {
        "apdu": {
            "gp_op": "STORE DATA (rename)",
            "gp_jar": "--rename-isd <new_AID>",
        },
        "usage": [
            "card rename-isd <new_AID>",
            "gp-rename-isd <new_AID>",
        ],
    },
    "make-selectable": {
        "apdu": {
            "gp_op": "INSTALL [for make selectable]",
            "gp_jar": "通过 --secure-apdu 实现",
            "apdu_flow": [
                "INSTALL → CLA=84 INS=E6 P1=08 P2=00 Lc=<AID>",
            ],
        },
        "usage": [
            "card make-selectable <AID>",
            "gp-make-selectable <AID>",
        ],
    },
    "set-cplc": {
        "apdu": {
            "gp_op": "STORE DATA (CPLC 日期)",
            "gp_jar": "--set-pre-perso / --set-perso / --today",
        },
        "usage": [
            "card set-cplc --pre-perso <hex> --perso <hex>",
            "card set-cplc --today",
        ],
    },
}


# ── deploy 子系统 ──

DEPLOY_HELP: dict[str, dict[str, Any]] = {
    "install": {
        "apdu": {
            "gp_op": "LOAD + INSTALL [for install and make selectable]",
            "gp_jar": "--install <cap> --applet <aid> [--params] [--privs] [--default] [-f]",
            "apdu_flow": [
                "1. INSTALL [for load]  → CLA=E6 INS=08 P1=02 P2=00",
                "2. LOAD data blocks    → CLA=E8 INS=C0 P1=P2=00",
                "3. INSTALL [for install and make selectable] → CLA=E6 INS=08 P1=04 P2=00",
            ],
        },
        "diagnostic": {
            "9000": {"cause": "成功", "fix": "—"},
            "6985": {"cause": "使用条件不满足", "fix": "先 deploy delete 删除已有包再重装，或用 --force"},
            "6438": {"cause": "包依赖未找到", "fix": "卡片缺少 javacard.security 等基础包"},
            "6A82": {"cause": "AID 未找到", "fix": "检查 AID 是否正确"},
            "6A80": {"cause": "安装参数错误", "fix": "检查 --params 格式"},
        },
        "usage": [
            "deploy install <CAP路径>",
            "deploy install <CAP路径> --params <hex> --privs <privs> --default",
            "deploy install <CAP路径> --force          # 强制重装（先删除再装）",
            "deploy install <CAP路径> --step           # 分步模式（每步暂停确认）",
            "deploy install <CAP路径> --load-only       # 仅加载不安装",
            "deploy install <CAP路径> --install-only --applet <AID>  # 仅安装（包已加载）",
            "gp-install <CAP路径> [--params] [--privs] [--default] [-f]",
        ],
    },
    "delete": {
        "apdu": {
            "gp_op": "DELETE",
            "gp_jar": "--delete <AID>",
            "apdu_flow": [
                "DELETE → CLA=E6 INS=08 P1=01 P2=00 Lc=<AID_len+1> 00<AID>",
            ],
        },
        "diagnostic": {
            "6985": {"cause": "删除条件不满足", "fix": "先删除 Applet 再删除 Package"},
            "6A82": {"cause": "AID 未找到", "fix": "检查 AID 是否正确"},
        },
        "usage": [
            "deploy delete <AID>",
            "gp-delete <AID>",
        ],
    },
    "load": {
        "apdu": {
            "gp_op": "LOAD (仅加载，不 INSTALL)",
            "gp_jar": "--load <cap>",
            "apdu_flow": [
                "1. INSTALL [for load] → CLA=E6 INS=08 P1=02 P2=00",
                "2. LOAD data blocks   → CLA=E8 INS=C0 P1=P2=00",
            ],
        },
        "usage": [
            "deploy load <CAP路径>",
            "gp-load <CAP路径>",
        ],
    },
    "provision": {
        "apdu": {
            "gp_op": "按 Profile 蓝图编排多条 INSTALL/DELETE",
            "gp_jar": "无直接映射（scsh 编排层）",
            "apdu_flow": [
                "1. 读取 scsh.toml Profile",
                "2. card list 获取当前状态",
                "3. diff: Profile vs 卡片 → 安装计划",
                "4. 逐个 deploy install",
            ],
        },
        "diagnostic": {
            "6438": {"cause": "包依赖未找到", "fix": "检查 Profile 中定义的包是否依赖卡片缺失的基础包"},
        },
        "usage": [
            "deploy provision              # 按 scsh.toml 自动编排",
            "deploy provision --dry-run    # 只显示计划不执行",
            "deploy provision --step       # 每步暂停确认",
        ],
    },
    "plan": {
        "apdu": {
            "gp_op": "Profile vs 卡片状态差异计算（只读，不执行）",
            "gp_jar": "--list（获取卡片状态）",
        },
        "diagnostic": {
            "N/A": {"cause": "plan 不执行任何写操作", "fix": "用 deploy provision 执行安装"},
        },
        "usage": [
            "deploy plan  # 显示 Profile vs 卡片差异",
            "  + 需安装的包",
            "  = 已存在跳过",
            "  ? 卡上有但 Profile 中没有",
        ],
    },
}


# ── config 子系统 ──

CONFIG_HELP: dict[str, dict[str, Any]] = {
    "key": {
        "apdu": {
            "gp_op": "设置本地连接密钥（注入到所有 GP 命令）",
            "gp_jar": "--key <hex>（通过 bridge.set_key() 注入）",
        },
        "diagnostic": {
            "6982": {"cause": "密钥不正确", "fix": "检查密钥值，确认与卡片 SCP 密钥一致"},
            "6985": {"cause": "安全条件不满足", "fix": "密钥可能已更改，用 key put 更新"},
        },
        "usage": [
            "config key <十六进制密钥>",
            "config key 404142434445464748494A4B4C4D4E4F",
            "gp-key <十六进制密钥>（别名）",
            "",
            "⚠️ 这是设置本地连接认证密钥，不是更新卡片上的密钥。",
            "更新卡片密钥用 key put。",
        ],
    },
    "aid": {
        "usage": [
            "config aid <别名> <AID>",
            "config aid isd A000000151000000",
            "gp-aid <别名> <AID>（别名）",
        ],
    },
    "mode": {
        "apdu": {
            "gp_op": "设置 SCP 安全通道模式",
            "gp_jar": "--mode <CLR/MAC/ENC/RMAC>",
        },
        "usage": [
            "config mode <模式>",
            "config mode MAC",
            "gp-mode <模式>（别名）",
            "模式: CLR, MAC, ENC, RMAC, 或组合如 MAC+ENC",
        ],
    },
    "show": {
        "usage": [
            "config show",
        ],
    },
    "set": {
        "usage": [
            "config set <key> <value>",
            "config set connection.key 404142434445464748494A4B4C4D4E4F",
            "config set connection.scp 02",
        ],
    },
    "get": {
        "usage": [
            "config get <key>",
            "config get connection.key",
        ],
    },
    "save": {
        "usage": [
            "config save          # 持久化到 ~/.scsh/config.toml",
        ],
    },
    "load": {
        "usage": [
            "config load          # 加载全局 + 项目配置",
            "config load /path    # 加载指定路径配置",
        ],
    },
}


# ── key 子系统 ──

KEY_HELP: dict[str, dict[str, Any]] = {
    "put": {
        "apdu": {
            "gp_op": "PUT KEY（更新卡片上的 SCP 密钥）",
            "gp_jar": "--lock <master> / --lock-enc/mac/dek",
            "apdu_flow": [
                "PUT KEY → CLA=80 INS=D8 P1=<key_ver> P2=80 Lc=<key_data>",
            ],
        },
        "diagnostic": {
            "6985": {"cause": "密钥版本不匹配", "fix": "检查 --key-ver 参数"},
            "6A80": {"cause": "密钥格式错误", "fix": "密钥应为 16 字节十六进制"},
        },
        "usage": [
            "key put --master <hex>",
            "key put --enc <hex> --mac <hex> --dek <hex>",
            "key put --master <hex> --new-keyver <ver>",
            "gp-put-key ...（别名）",
            "",
            "⚠️ 这是更新卡片上的密钥（换锁），不是设置本地连接密钥。",
            "设置本地连接密钥用 config key。",
        ],
    },
    "delete": {
        "apdu": {
            "gp_op": "DELETE KEY",
            "gp_jar": "--delete-key <ver>",
        },
        "usage": [
            "key delete <版本号>",
            "gp-delete-key <版本号>（别名）",
        ],
    },
}


# ── apdu 子系统 ──

APDU_HELP: dict[str, dict[str, Any]] = {
    "send": {
        "apdu": {
            "gp_op": "直接发送 APDU 到卡片",
            "gp_jar": "无映射（pyscard 直接通信）",
        },
        "usage": [
            "apdu send <十六进制APDU>",
            "send <十六进制APDU>（别名）",
            "apdu send 00A4040000A000000151000000",
        ],
    },
    "select": {
        "apdu": {
            "gp_op": "SELECT AID",
            "apdu_flow": [
                "SELECT → CLA=00 INS=A4 P1=04 P2=00 Lc=<AID_len> <AID>",
            ],
        },
        "usage": [
            "apdu select <AID>",
            "select <AID>（别名）",
        ],
    },
    "get-response": {
        "apdu": {
            "gp_op": "GET RESPONSE",
            "apdu_flow": [
                "GET RESPONSE → CLA=00 INS=C0 P1=00 P2=00 Le=<length>",
            ],
        },
        "usage": [
            "apdu get-response [Le]",
            "get-response [Le]（别名）",
        ],
    },
    "secure-send": {
        "apdu": {
            "gp_op": "通过 SCP 安全通道发送 APDU",
            "gp_jar": "--secure-apdu <hex>",
        },
        "usage": [
            "apdu secure-send <hex>",
            "gp-secure-apdu <hex>（别名）",
        ],
    },
}


# ── session 子系统 ──

SESSION_HELP: dict[str, dict[str, Any]] = {
    "info": {
        "usage": [
            "session info",
            "info（别名）",
        ],
    },
    "readers": {
        "usage": [
            "session readers",
            "readers（别名）",
        ],
    },
    "connect": {
        "usage": [
            "session connect <编号>",
            "connect <编号>（别名）",
        ],
    },
    "reconnect": {
        "usage": [
            "session reconnect",
            "reconnect（别名）",
        ],
    },
    "reset": {
        "usage": [
            "session reset",
            "reset（别名）",
        ],
    },
    "record": {
        "usage": [
            "session record <文件路径>",
            "record <文件路径>（别名）",
        ],
    },
}
