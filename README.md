# Smart Card Shell (scsh)
# scsh (original)
# scsh
=======
# Smart Card Shell (scsh)

统一的 REPL 交互式智能卡测试工具。一个 shell 内完成读卡器管理、APDU 收发、GlobalPlatform 管理和脚本批处理。

## 安装

```bash
git clone <repo-url>
cd scsh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 依赖

| 组件 | 用途 | 说明 |
|------|------|------|
| Python 3.13+ | 运行环境 | |
| pyscard | PC/SC 智能卡通信 | macOS 需要 ad-hoc 签名 |
| prompt_toolkit | REPL 交互界面 | |
| rich | 美化输出 | |
| Java (可选) | gp.jar GP 管理 | 安装 JDK 8+ 并设 `JAVA_HOME` |
| gp.jar (可选) | GlobalPlatform 命令 | 首次运行自动搜索 `gp.jar` |

## 快速开始

```bash
source .venv/bin/activate
scsh
```

### 连接卡片

```
[scsh:N] > readers
找到 3 个读卡器:
  [0] ACS ACR1581 1S Dual Reader SAM  ✅ 有卡
  [1] ACS ACR1581 1S Dual Reader PICC  ✅ 有卡
  [2] ACS ACR1581 1S Dual Reader ICC   空槽

[scsh:N] > connect 1
已连接到: ACS ACR1581 1S Dual Reader PICC
ATR: 3B8F80018665FF0B080118000000000000900098
协议: T=1
```

提示符变为 `[scsh:1] >` 表示已连接 1 号读卡器。

## 命令参考

### 硬件管理 (M1)

| 命令 | 功能 |
|------|------|
| `readers` | 列出所有读卡器及插卡状态 |
| `connect <N>` | 连接指定编号的读卡器 |
| `reconnect` | 断开并重连 |
| `info` | 显示卡片信息（ATR、协议） |
| `reset` | 卡片冷复位 |

### APDU 通信 (M2)

| 命令 | 功能 |
|------|------|
| `send <hex>` | 发送原始 APDU |
| `select <AID>` | SELECT AID 快捷命令 |
| `get-response <Le>` | GET RESPONSE |
| `send-file <path>` | 从文件读取 APDU 并逐条发送 |

### GP 管理 (M3-M4)

| 命令 | 功能 |
|------|------|
| `gp-list` | 列出已安装的 ISD/Package/Applet |
| `gp-info` | 显示 GP 详细信息 |
| `gp-install <cap>` | 安装 CAP 文件 |
| `gp-delete <aid>` | 删除 Applet/Package |
| `gp-lock <aid>` | 锁定 Applet |
| `gp-unlock <aid>` | 解锁 Applet |
| `gp-create <aid>` | 创建 Applet 实例 |
| `gp-key <hex>` | 设置 GP 密钥 |
| `gp-aid <alias> <AID>` | 注册 AID 别名 |
| `gp-scp` | 查看安全通道信息 |
| `gp-status` | 查询卡片生命周期 |

> **注意**: GP 命令需要安装 Java 并配置 `JAVA_HOME` 环境变量。系统自带 gp.jar 时自动使用。

### 辅助功能 (M5)

| 命令 | 功能 |
|------|------|
| `repeat [N]` | 重复上一条 APDU 指定次数 |
| `timing [on\|off]` | 切换 APDU 耗时显示 |
| `config` | 查看/设置配置 |
| `record <path>` | 录制当前会话到文件 |

### 内置命令

| 命令 | 功能 |
|------|------|
| `help` | 列出所有命令 |
| `help <cmd>` | 查看命令详情 |
| `exit` / `quit` | 退出 |

### 非交互模式

```bash
# 单次命令
scsh --command "select A0000006472F0001"

# 执行脚本文件
scsh --file test.scsh
```

## 脚本示例

创建一个 `test.scsh`：

```bash
# 连接卡片并选择 Applet
readers
connect 1
info
select A0000006472F0001
gp-list
```

执行：

```bash
scsh --file test.scsh
```

## 开发

### 运行测试

```bash
pytest tests/
```

### 项目结构

```
scsh/
├── scsh/
│   ├── main.py              # 入口 + 参数解析
│   ├── repl.py              # prompt_toolkit REPL
│   ├── exceptions.py        # 统一异常层级
│   ├── commands/
│   │   ├── __init__.py      # CommandRegistry
│   │   ├── hardware.py      # 硬件命令
│   │   ├── apdu.py          # APDU 命令
│   │   └── gp.py            # GP 命令
│   ├── transport/
│   │   └── pcsc.py          # pyscard 封装
│   ├── bridge/
│   │   └── gp_jar.py        # gp.jar 桥接
│   └── formats/
│       ├── apdu.py          # APDU 解析/格式化
│       ├── tlv.py           # BER-TLV 编解码
│       └── sw.py            # SW 状态字数据库
├── tests/                   # 172 个测试
├── gp.jar                   # GlobalPlatformPro
└── pyproject.toml
```

## 架构

```
REPL Layer (prompt_toolkit)
    │
    ├── 硬件命令 ── PC/SC Transport (pyscard)
    ├── APDU 命令 ── PC/SC Transport (pyscard)
    └── GP 命令 ──── gp.jar Bridge (subprocess)
                          │
                     Hardware (PCSC.framework / pcsc-lite / winscard)
```

## 许可证

MIT
