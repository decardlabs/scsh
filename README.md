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

启动后自动检查运行环境，缺失依赖时会给出明确的安装指引。

### 依赖

| 组件 | 用途 | 说明 |
|------|------|------|
| Python 3.13+ | 运行环境 | |
| pyscard | PC/SC 智能卡通信 | macOS 需要 ad-hoc 签名 |
| prompt_toolkit | REPL 交互界面 | |
| rich | 美化输出 | |
| Java Runtime (可选) | gp.jar GP 管理 | 安装 JDK 8+ |
| gp.jar (可选) | GlobalPlatform 命令 | 自动搜索 PATH → `tools/` → 当前目录 |

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

### 系统命令 (M0)

| 命令 | 功能 |
|------|------|
| `version` | 显示 scsh/Python/pyscard 版本 |
| `version -v` | 详细模式（额外显示 gp.jar / Java 版本） |

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

### GP 查询 (M3)

| 命令 | 功能 |
|------|------|
| `gp-list` | 列出已安装的 ISD/Package/Applet（含 ISD 状态） |
| `gp-info` | 显示 GP 详细信息（SCP、CPLC 厂商名翻译、Card Data OID 表、密钥能力） |
| `gp-aid <alias> <AID>` | 注册 AID 别名 |
| `gp-scp` | 查看安全通道信息 |
| `gp-status` | 查询卡片生命周期 |

### GP 操作 (M4)

| 命令 | 功能 |
|------|------|
| `gp-install <cap>` | 安装 CAP 文件 |
| `gp-delete <aid>` | 删除 Applet/Package |
| `gp-lock <aid>` | 锁定 Applet |
| `gp-unlock <aid>` | 解锁 Applet |
| `gp-create <aid>` | 创建 Applet 实例 |
| `gp-key <hex>` | 设置 GP 密钥 |
| `gp-load <cap>` | 仅加载 CAP（不执行 INSTALL） |
| `gp-uninstall <aid>` | 卸载 CAP/Package |
| `gp-put-key <kv>` | 更新 SCP 密钥 |
| `gp-delete-key <kv>` | 删除指定版本密钥 |
| `gp-store-data <hex>` | 写入个人化数据 |
| `gp-set-default <aid>` | 设置默认 Applet（NFC） |
| `gp-lock-card` | 锁定卡片（TERMINATED） |
| `gp-unlock-card` | 解锁卡片 |
| `gp-init-card` | 初始化卡片（OP_READY → INITIALIZED） |
| `gp-secure-card` | 安全化卡片（INITIALIZED → SECURED） |
| `gp-create-domain <aid>` | 创建补充安全域（SSD） |
| `gp-rename-isd <aid>` | 重命名 ISD AID |
| `gp-set-cplc <date>` | 设置 CPLC 个人化日期 |
| `gp-secure-apdu <hex>` | 通过 SCP 安全通道发送 APDU |
| `gp-mode <mode>` | 设置 SCP 安全通道模式 |
| `gp-make-selectable <aid>` | 将已安装 Applet 设为可选 |

> **注意**: GP 命令需要安装 Java Runtime，scsh 会自动搜索 `gp.jar`（搜索顺序：PATH → tools/ → 当前目录）。

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
│   ├── __init__.py          # 版本号
│   ├── main.py              # 入口 + 环境预检 + 参数解析
│   ├── repl.py              # prompt_toolkit REPL
│   ├── session.py           # 会话状态（Session dataclass）
│   ├── exceptions.py        # 统一异常层级
│   ├── gp_fallback.py       # gp.jar 不可用时的 APDU 降级方案
│   ├── commands/
│   │   ├── __init__.py      # CommandRegistry
│   │   ├── hardware.py      # 硬件命令（M1）
│   │   ├── apdu.py          # APDU 命令（M2）
│   │   ├── gp.py            # GP 命令（M3-M4）
│   │   └── system.py        # 系统命令（version）
│   ├── transport/
│   │   └── pcsc.py          # pyscard 封装
│   ├── bridge/
│   │   └── gp_jar.py        # gp.jar 子进程桥接
│   └── formats/
│       ├── apdu.py          # APDU 解析/格式化
│       ├── tlv.py           # BER-TLV 编解码
│       └── sw.py            # SW 状态字数据库
├── tests/                   # 177 个测试
├── tools/
│   └── gp.jar               # GlobalPlatformPro
├── examples/                # APDU 脚本示例
├── CLAUDE.md                # AI 辅助开发指南
├── scshr                    # 入口 Shell 脚本
├── download-isoapplet.sh    # ISOApplet 下载脚本
└── pyproject.toml
```

## 架构

```
     REPL (prompt_toolkit)
          │
          ├── M0  系统命令 ──── version
          ├── M1  硬件命令 ──── PC/SC Transport (pyscard)
          ├── M2  APDU 命令 ─── PC/SC Transport (pyscard)
          ├── M3  GP 查询 ───── gp.jar Bridge (subprocess) / pyscard fallback
          ├── M4  GP 操作 ───── gp.jar Bridge (subprocess)
          └── M5  辅助命令 ──── repeat / timing / config / record
                                   │
          Session (dataclass) ──── 所有状态集中管理
                                   │
                              Hardware (PCSC.framework / pcsc-lite / winscard)
```

## 许可证

MIT
