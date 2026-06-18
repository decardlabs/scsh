# scsh v0.7.0 用户手册

> Smart Card Shell — 智能卡管理命令行工具完整指南
> 版本：v0.7.0 | 语言：中文 | 适用人群：初学者 & 专家

---

## 目录

1. [简介](#1-简介)
2. [安装与配置](#2-安装与配置)
3. [初学者入门](#3-初学者入门)
4. [6 大子系统命令详解](#4-6-大子系统命令详解)
   - [card — 卡片管理](#41-card--卡片管理)
   - [deploy — 应用部署](#42-deploy--应用部署)
   - [config — 配置管理](#43-config--配置管理)
   - [key — 密钥管理](#44-key--密钥管理)
   - [apdu — APDU 通信](#45-apdu--apdu-通信)
   - [session — 会话管理](#46-session--会话管理)
5. [实战工作流](#5-实战工作流)
6. [案例文件](#6-案例文件)
7. [故障排除](#7-故障排除)
8. [附录](#8-附录)

---

## 1. 简介

scsh（Smart Card Shell）是一个基于 Python 的智能卡管理命令行工具，通过 pyscard 库与 PC/SC 读卡器通信，并调用 GlobalPlatformPro（gp.jar）完成 GlobalPlatform 规范操作。

**核心特性：**
- 🔌 自动检测 PC/SC 读卡器，支持多读卡器切换
- 📦 完整的 GP 操作：列表、安装、删除、密钥管理
- 🔐 SCP01/SCP02 安全通道支持
- 📝 APDU 历史记录、重放、搜索
- 🎯 Tab 自动补全（命令、AID、文件路径）
- ⚡ SW 状态字自动诊断提示
- 📄 Profile 蓝图驱动批量部署

**6 大子系统：**

| 子系统 | 功能 | 命令数 |
|--------|------|--------|
| `card` | 卡片生命周期、Applet 状态管理 | 9 |
| `deploy` | CAP 包安装、删除、批量部署 | 5 |
| `config` | 密钥、AID 别名、SCP 模式配置 | 8 |
| `key` | 卡片密钥更新、删除 | 2 |
| `apdu` | 原始 APDU 发送、历史管理 | 10 |
| `session` | 读卡器连接、会话录制 | 6 |

---

## 2. 安装与配置

### 2.1 环境要求

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Python | 3.10+ | 推荐 3.12+ |
| Java | 8+ | 运行 gp.jar 需要 |
| GlobalPlatformPro | 任意版本 | gp.jar 文件路径需在 `config.toml` 中配置 |
| pyscard | 2.0+ | PC/SC 智能卡通信库 |
| prompt_toolkit | 3.0+ | REPL 交互支持 |

### 2.2 安装步骤

```bash
# 克隆仓库
git clone https://github.com/decardlabs/scsh.git
cd scsh

# 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 验证安装
python -m scsh --version
```

### 2.3 配置文件

scsh 使用 TOML 格式配置文件，支持两级配置：

- **全局配置**：`~/.scsh/config.toml`
- **项目配置**：当前目录 `scsh.toml`（优先级更高）

首次运行会自动创建全局配置。参考案例文件 [`examples/scsh.toml`](examples/scsh.toml)。

### 2.4 连接真实读卡器

```bash
# 启动 scsh
python -m scsh

# 列出可用读卡器
session readers

# 连接读卡器（按编号）
session connect 1

# 查看卡片信息
card info
```

---

## 3. 初学者入门

### 3.1 第一次连接卡片

```bash
$ python -m scsh
scsh v0.7.0 — 输入 help 查看帮助，Tab 补全命令

>>> session readers
[1] ACS ACR39U ICC Reader 00 00
[2] Yubico YubiKey OTP+FIDO+CCID 01 00

>>> session connect 1
✓ 已连接到: ACS ACR39U ICC Reader 00 00
✓ ATR: 3B6F00...

>>> card info
ISD AID:          A000000003000000
GP Version:        2.2.1
JavaCard Version:  3.0.4
SCP Supported:     SCP02(i=55)
```

### 3.2 核心概念速查

| 概念 | 说明 | 示例 |
|------|------|------|
| **AID** | 应用标识符（Application ID），十六进制字符串 | `A000000003000000` |
| **ISD** | Issuer Security Domain，卡片发行安全域 | 每个 GP 卡片必有 |
| **Applet** | JavaCard 应用小程序 | FIDO2Applet |
| **CAP 文件** | 编译后的 JavaCard 应用包 | `build/libs/myapplet.cap` |
| **SCP** | Secure Channel Protocol，安全通道协议 | SCP02、SCP03 |
| **APDU** | Application Protocol Data Unit，智能卡通信指令 | `00A4040000` |
| **SW** | Status Word，APDU 响应状态字 | `9000` = 成功 |

### 3.3 第一个完整工作流：安装一个 Applet

```bash
# 1. 连接卡片
>>> session connect 1

# 2. 查看当前状态
>>> card list

# 3. 安装 CAP 包
>>> deploy install build/libs/HelloWorld.cap

# 4. 验证安装
>>> card list

# 5. 发送 APDU 测试
>>> apdu select A000000001000001
>>> send 00000000   # 发送自定义 APDU
```

---

## 4. 6 大子系统命令详解

---

### 4.1 `card` — 卡片管理

管理卡片生命周期、Applet 状态、安全域和数据存储。

#### `card list`
列出卡片上所有已安装的安全域、Package 和 Applet。

**语法：**
```
card list
gp-list          # 别名（直接调用 gp.jar）
```

**示例：**
```bash
>>> card list
ISD:
  A000000003000000  (GP v2.2.1)

Packages:
  A000000001        (JavaCard)

Applets:
  A000000001000001  HelloWorldApplet  [SELECTABLE]
```

**常见 SW 诊断：**
- `6A82` — ISD 未找到，检查卡片是否连接
- `6985` — 安全条件不满足，需要 SCP 安全通道

---

#### `card info`
显示卡片详细信息（ISD、GP 版本、CPLC 数据、SCP 支持）。

**语法：**
```
card info
gp-info         # 别名（仅基本信息）
gp-scp          # 别名（仅安全通道信息）
gp-status       # 别名（仅生命周期状态）
```

**示例：**
```bash
>>> card info
卡片信息:
  ISD AID:       A000000003000000
  GP Version:    2.2.1
  JC Version:     3.0.4
  Lifecycle:      OP_READY
  SCP Support:   SCP02(i=55), SCP03(i=15)
  CPLC:
    IC Fabricator: 4799
    IC Serial:     ...
```

---

#### `card lifecycle [状态]`
查看或变更卡片生命周期状态。

**生命周期状态机：**
```
OP_READY → INITIALIZED → SECURED → CARD_LOCKED → TERMINATED
             ↓              ↓
          (可回退)      (可回退)
```

**语法：**
```
card lifecycle                  # 显示当前状态 + 状态机图
card lifecycle init             # OP_READY → INITIALIZED
card lifecycle secure           # INITIALIZED → SECURED
card lifecycle lock             # SECURED → CARD_LOCKED
card lifecycle unlock           # CARD_LOCKED → SECURED
card lifecycle terminate        # CARD_LOCKED → TERMINATED ⚠️ 不可逆
```

**示例：**
```bash
>>> card lifecycle
当前状态: OP_READY
状态机: OP_READY → INITIALIZED → SECURED → CARD_LOCKED → TERMINATED

>>> card lifecycle init
✓ 卡片状态已变更为 INITIALIZED

>>> card lifecycle secure
✓ 卡片状态已变更为 SECURED
```

⚠️ **警告**：`terminate` 操作不可逆！卡片将永久报废。

---

#### `card applet-state <AID> [状态]`
查看或设置 Applet 的生命周期状态。

**语法：**
```
card applet-state <AID>                  # 查看状态
card applet-state <AID> selectable       # 设为可选（可被选中和调用）
card applet-state <AID> locked           # 锁定 Applet
card applet-state <AID> blocked          # 阻塞 Applet
```

**示例：**
```bash
>>> card applet-state A000000001000001
Applet A000000001000001 状态: SELECTABLE

>>> card applet-state A000000001000001 locked
✓ Applet 状态已变更为 LOCKED
```

---

#### `card store-data <hex>`
向卡片存储自定义数据（需 SCP 安全通道）。

**语法：**
```
card store-data <十六进制数据>
gp-store-data <hex>           # 别名
```

**示例：**
```bash
>>> card store-data 0001020304
✓ 数据已存储
```

---

#### `card create-domain <AID>`
创建辅助安全域（SSD）。

**语法：**
```
card create-domain <AID>
gp-create-domain <AID>        # 别名
```

---

#### `card rename-isd <new-AID>`
重命名 ISD 的 AID。

**语法：**
```
card rename-isd <新AID>
gp-rename-isd <新AID>         # 别名
```

---

#### `card make-selectable <AID>`
将已加载的 Package 设为可选状态（可被执行）。

**语法：**
```
card make-selectable <AID>
gp-make-selectable <AID>      # 别名
```

---

#### `card set-cplc [选项]`
设置卡片 CPLC 日期字段。

**语法：**
```
card set-cplc --pre-perso <hex> --perso <hex>
card set-cplc --today          # 自动填入今天日期
```

---

### 4.2 `deploy` — 应用部署

管理 CAP 包的安装、删除和批量部署。

#### `deploy install <CAP路径> [选项]`
安装 CAP 文件到卡片。

**语法：**
```
deploy install <CAP路径> [选项]
gp-install <CAP路径>           # 别名

选项:
  --params <hex>                # 安装参数（TLV 格式）
  --privs <privs>               # Applet 权限位
  --default                     # 设为默认选中 Applet
  -f, --force                  # 强制重装（先删除再安装）
  --step                        # 分步模式（每步暂停确认）
  --load-only                   # 仅加载，不安装
  --install-only --applet <AID> # 仅安装（包已加载）
```

**示例：**
```bash
# 基本安装
>>> deploy install build/libs/FIDO2Applet.cap

# 强制重装
>>> deploy install build/libs/FIDO2Applet.cap --force

# 带参数安装
>>> deploy install build/libs/MyApplet.cap --params 00C10101 --privs 02

# 分步模式（调试用）
>>> deploy install build/libs/MyApplet.cap --step
```

**APDU 流程：**
```
1. INSTALL [for load]  → CLA=E6 INS=08 P1=02 P2=00
2. LOAD data blocks    → CLA=E8 INS=C0 P1=P2=00 (可能多帧)
3. INSTALL [for install and make selectable] → CLA=E6 INS=08 P1=04 P2=00
```

**常见 SW 诊断：**
- `6985` — 已存在同名 Package，使用 `--force` 重装
- `6438` — 包依赖缺失（卡片 JavaCard 版本过低）
- `6A80` — 安装参数格式错误

---

#### `deploy delete <AID>`
从卡片删除 Applet 或 Package。

**语法：**
```
deploy delete <AID>
gp-delete <AID>                # 别名
```

**示例：**
```bash
>>> deploy delete A000000001000001
✓ Applet A000000001000001 已删除
```

⚠️ **注意**：删除 Package 前必须先删除其下所有 Applet。

---

#### `deploy load <CAP路径>`
仅加载 CAP 文件（不执行 INSTALL）。

**语法：**
```
deploy load <CAP路径>
gp-load <CAP路径>               # 别名
```

---

#### `deploy plan`
显示 Profile 蓝图与卡片当前状态的差异（只读，不执行）。

**语法：**
```
deploy plan
```

**输出示例：**
```bash
>>> deploy plan
Profile: scsh.toml

[+] A000000001000001  (需要安装)
[=] A000000003000000  (已存在，跳过)
[?] A000000005000001  (卡片上有但 Profile 未定义)
```

图例：
- `[+]` 需要安装
- `[=]` 已存在，跳过
- `[?]` 卡片上有但 Profile 未定义（孤立项）

---

#### `deploy provision [选项]`
按 Profile 蓝图自动编排安装计划并执行。

**语法：**
```
deploy provision
deploy provision --dry-run     # 只显示计划，不执行
deploy provision --step        # 每步暂停确认
```

**示例：**
```bash
>>> deploy provision --dry-run
Plan (3 actions):
  [1/3] INSTALL A000000001000001 from build/libs/app1.cap
  [2/3] INSTALL A000000002000001 from build/libs/app2.cap
  [3/3] SET DEFAULT A000000001000001

>>> deploy provision
Executing plan...
  [1/3] ✓ A000000001000001 installed
  [2/3] ✓ A000000002000001 installed
  [3/3] ✓ Default applet set
Done!
```

---

### 4.3 `config` — 配置管理

管理连接参数、密钥、AID 别名等配置。

#### `config key <hex>`
设置 GP 连接认证密钥（本地配置，非卡片密钥）。

**语法：**
```
config key <十六进制密钥>
gp-key <hex>                   # 别名
```

**示例：**
```bash
# 设置默认测试密钥（GlobalPlatform 标准默认值）
>>> config key 404142434445464748494A4B4C4D4E4F

# 验证密钥
>>> config show
```

⚠️ **注意**：此命令设置的是**连接认证密钥**（本地保存，用于连接卡片）。
更新卡片上的密钥用 `key put`。

---

#### `config aid <别名> <AID>`
注册 AID 别名，简化命令输入。

**语法：**
```
config aid <别名> <AID>
gp-aid <别名> <AID>            # 别名
```

**示例：**
```bash
>>> config aid isd A000000003000000
>>> config aid myapp A000000001000001

# 之后可以用别名代替 AID
>>> card applet-state myapp
>>> apdu select isd
```

---

#### `config mode <模式>`
设置 SCP 安全通道模式。

**语法：**
```
config mode <模式>
gp-mode <模式>                  # 别名

模式: CLR, MAC, ENC, RMAC, MAC+ENC
```

**示例：**
```bash
>>> config mode MAC+ENC
✓ SCP 模式已设为 MAC+ENC
```

---

#### `config show`
显示当前所有配置。

**语法：**
```
config show
```

**示例：**
```bash
>>> config show
connection:
  reader:     ACS ACR39U ICC Reader
  scp:        02
  key:        404142434445464748494A4B4C4D4E4F
  mode:       MAC+ENC
aid_aliases:
  isd   → A000000003000000
  myapp → A000000001000001
```

---

#### `config set <key> <value>`
设置指定配置项。

**语法：**
```
config set <key> <value>
```

**示例：**
```bash
>>> config set connection.scp 03
>>> config set connection.key 000102030405060708090A0B0C0D0E0F
```

---

#### `config get <key>`
读取指定配置项。

**语法：**
```
config get <key>
```

---

#### `config save`
将当前配置持久化到 `~/.scsh/config.toml`。

**语法：**
```
config save
```

---

#### `config load [路径]`
加载配置文件。

**语法：**
```
config load                      # 加载全局 + 项目配置
config load /path/to/config.toml # 加载指定文件
```

---

### 4.4 `key` — 密钥管理

管理卡片上的 GP 安全密钥（更新/删除）。

#### `key put [选项]`
更新卡片上的 SCP 密钥（**换锁**操作）。

**语法：**
```
key put --master <hex>          # 同时更新 ENC+MAC+DEK
key put --enc <hex> --mac <hex> --dek <hex>   # 分别指定
key put --master <hex> --new-keyver <ver>      # 指定新密钥版本
gp-put-key ...                  # 别名
```

**示例：**
```bash
# 使用主密钥同时更新三个密钥
>>> key put --master 000102030405060708090A0B0C0D0E0F

# 分别指定三个密钥
>>> key put --enc <enc_key> --mac <mac_key> --dek <dek_key>

# 更新到新版本号
>>> key put --master <new_key> --new-keyver 02
```

⚠️ **高风险操作**：密钥更新后，必须使用新密钥才能再次连接！
建议先记录新密钥，或在安全环境中操作。

**APDU 流程：**
```
PUT KEY → CLA=80 INS=D8 P1=<key_ver> P2=80 Lc=<key_data>
```

---

#### `key delete <版本号>`
删除指定版本的密钥。

**语法：**
```
key delete <版本号>
gp-delete-key <版本号>           # 别名
```

---

### 4.5 `apdu` — APDU 通信

直接发送 APDU 指令，管理 APDU 历史记录。

#### `apdu send <hex>`
发送原始 APDU 指令到卡片。

**语法：**
```
apdu send <十六进制APDU>
send <hex>                      # 别名
```

**示例：**
```bash
# SELECT ISD
>>> apdu send 00A4040000A000000003000000

# 带数据的 APDU
>>> apdu send 80E6010007A00000000100000100

# 使用 AID 别名
>>> apdu send "00A4040000$(config get aid.isd)"
```

---

#### `apdu select <AID>`
发送 SELECT 指令选中指定 AID。

**语法：**
```
apdu select <AID>
select <AID>                    # 别名
```

**示例：**
```bash
>>> apdu select A000000001000001
Response: 9000
Data: ...

# 使用别名
>>> config aid myapp A000000001000001
>>> apdu select myapp
```

---

#### `apdu get-response [Le]`
发送 GET RESPONSE 读取剩余响应数据。

**语法：**
```
apdu get-response [Le]
get-response [Le]               # 别名
```

---

#### `apdu secure-send <hex>`
通过 SCP 安全通道发送 APDU（自动加密/MAC）。

**语法：**
```
apdu secure-send <hex>
gp-secure-apdu <hex>            # 别名
```

---

#### `apdu repeat`
重复发送上一条 APDU（快速重测）。

**语法：**
```
apdu repeat
repeat                           # 别名
```

---

#### `apdu timing`
切换 APDU 耗时显示开关。

**语法：**
```
apdu timing
timing                          # 别名
```

**示例：**
```bash
>>> apdu timing
APDU 耗时显示: 已开启

>>> apdu send 00A4040000A000000003000000
→ 00 A4 04 00 08 A0 00 00 00 03 00 00 00
← 90 00  (12.3 ms)
```

---

#### `apdu send-file <文件路径>`
从文件批量发送 APDU（每行一条）。

**语法：**
```
apdu send-file <文件路径>
send-file <文件路径>             # 别名
```

**文件格式（参考 `examples/apdu-cmds.txt`）：**
```txt
# 这是注释行
00A4040000A000000003000000
80E6020007A00000000100000100
00A4040000A000000001000001
0000000008
```

---

#### `apdu history [选项]`
查看 APDU 发送历史。

**语法：**
```
apdu history          # 最近 20 条
apdu history --all    # 全部历史
apdu history <N>     # 最近 N 条
```

**示例：**
```bash
>>> apdu history
History (5 entries):
  [1] 00A4040000A000000003000000     → 9000  (12.3 ms)
  [2] 80E6010007A00000000100000100   → 9000  (8.7 ms)
  ...
```

---

#### `apdu replay <编号|last>`
重放历史记录中的 APDU。

**语法：**
```
apdu replay <编号>
apdu replay last      # 重放上一条
```

**示例：**
```bash
>>> apdu replay 1
Replaying [#1]: 00A4040000A000000003000000
→ 00 A4 04 00 08 A0 00 00 00 03 00 00 00
← 90 00  (12.1 ms)
```

---

#### `apdu search <关键词>`
搜索 APDU 历史记录。

**语法：**
```
apdu search <关键词>
```

**示例：**
```bash
>>> apdu search SELECT
Found 3 matches:
  [1] 00A4040000A000000003000000  (SELECT ISD)
  [5] 00A4040000A000000001000001  (SELECT Applet)
```

---

### 4.6 `session` — 会话管理

管理读卡器连接和会话录制。

#### `session info`
显示当前会话信息。

**语法：**
```
session info
info                            # 别名
```

**示例：**
```bash
>>> session info
Session Info:
  Reader:     ACS ACR39U ICC Reader 00 00
  ATR:        3B6F00...
  Connected:  Yes
  SCP:        Established (SCP02 i=55)
```

---

#### `session readers`
列出所有可用的 PC/SC 读卡器。

**语法：**
```
session readers
readers                         # 别名
```

---

#### `session connect <编号>`
连接指定读卡器。

**语法：**
```
session connect <读卡器编号>
connect <编号>                   # 别名
```

---

#### `session reconnect`
重新连接当前读卡器（卡片重置）。

**语法：**
```
session reconnect
reconnect                       # 别名
```

---

#### `session reset`
冷复位卡片（不重新连接读卡器）。

**语法：**
```
session reset
reset                           # 别名
```

---

#### `session record <文件路径>`
开始录制会话中的所有 APDU 通信到文件。

**语法：**
```
session record <文件路径>
record <文件路径>                # 别名
```

**示例：**
```bash
>>> session record session-20250618.txt
Recording to: session-20250618.txt

>>> apdu send 00A4040000A000000003000000
>>> card list

>>> session record off    # 停止录制（或 Ctrl+C）
```

录制文件格式参考 `examples/session-record.txt`。

---

## 5. 实战工作流

### 5.1 新卡片初始化流程

```bash
# 1. 连接卡片
>>> session connect 1

# 2. 查看初始状态
>>> card info
>>> card lifecycle

# 3. 初始化卡片（OP_READY → INITIALIZED）
>>> card lifecycle init

# 4. 设置安全通道（INITIALIZED → SECURED）
>>> card lifecycle secure

# 5. 更改默认密钥（推荐！）
>>> key put --master <新密钥>

# 6. 更新本地配置
>>> config key <新密钥>
>>> config save
```

### 5.2 应用开发调试流程

```bash
# 1. 编译 CAP 包（在 JavaCard 项目中）
$ gradle build

# 2. 安装到卡片
>>> deploy install /path/to/build/libs/MyApplet.cap --force

# 3. 测试 APDU 通信
>>> apdu select A000000001000001
>>> apdu send 0000000008  # 自定义指令

# 4. 查看 APDU 历史
>>> apdu history

# 5. 如果有问题，重放某条 APDU
>>> apdu replay 3
```

### 5.3 批量部署流程（Profile 驱动）

```bash
# 1. 编写 Profile 蓝图（参考 examples/profile.toml）
# 2. 预览部署计划
>>> deploy plan

# 3. 执行批量部署
>>> deploy provision

# 4. 验证结果
>>> card list
```

### 5.4 生产环境密钥轮换流程

```bash
# ⚠️ 高风险操作，需严格按流程执行

# 1. 确认当前密钥
>>> config show

# 2. 生成新密钥（记录在安全位置！）
# 新密钥: 00112233445566778899AABBCCDDEEFF

# 3. 更新卡片密钥
>>> key put --master 00112233445566778899AABBCCDDEEFF

# 4. 立即更新本地配置
>>> config key 00112233445566778899AABBCCDDEEFF
>>> config save

# 5. 验证新密钥可用
>>> session reconnect
>>> card list
```

---

## 6. 案例文件

以下案例文件随手册提供，位于 `examples/` 目录。

### 6.1 配置文件示例

**文件：`examples/scsh.toml`**

```toml
# scsh 项目配置文件
# 放置于项目根目录，优先级高于 ~/.scsh/config.toml

[connection]
reader = "ACS ACR39U ICC Reader 00 00"
scp = "02"
key = "404142434445464748494A4B4C4D4E4F"
mode = "MAC+ENC"

[aid_aliases]
isd = "A000000003000000"
myapp = "A000000001000001"
testapp = "A000000009000001"

[profile]
# 部署蓝图：定义卡片目标状态
[[profile.packages]]
aid = "A000000001000001"
cap = "build/libs/HelloWorld.cap"
default = true

[[profile.packages]]
aid = "A000000002000001"
cap = "build/libs/FIDO2Applet.cap"
params = "00C10101"
privs = "02"
```

### 6.2 APDU 脚本文件示例

**文件：`examples/apdu-cmds.txt`**

```txt
# APDU 批量脚本示例
# 用于 apdu send-file 命令
# 每行一条 APDU（十六进制），空行和 # 开头的行会被忽略

# === 选择 ISD ===
00A4040000A000000003000000

# === 查看 GP 状态 ===
80F2000000

# === 选择我的 Applet ===
00A4040000A000000001000001

# === 发送自定义指令（SELECTABLE 状态测试）===
0000000008

# === 读取 CPLC 数据 ===
80CA9F7F00
```

### 6.3 部署蓝图示例

**文件：`examples/profile.toml`**

```toml
# scsh 部署蓝图 Profile
# 用于 deploy provision / deploy plan 命令

[profile.meta]
name = "FIDO2 部署蓝图"
version = "1.0"
target_card = "JCOP v4"

[[profile.packages]]
aid = "A000000001000001"
cap = "build/libs/HelloWorld.cap"
default = true
description = "示例 HelloWorld Applet"

[[profile.packages]]
aid = "A000000002000001"
cap = "build/libs/FIDO2Applet.cap"
params = "00C10101"
privs = "02"
description = "FIDO2 认证 Applet"

# 需要预装的依赖包（如有）
[[profile.dependencies]]
aid = "A000000051000000"
description = "FIDO2 依赖库"
```

### 6.4 会话录制文件示例

**文件：`examples/session-record.txt`**

```txt
# scsh 会话录制
# 时间: 2026-06-18 15:22
# 读者: ACS ACR39U ICC Reader
# 卡片: NXP SmartMX2

>>> session connect 1
✓ 已连接

>>> card info
ISD AID: A000000003000000
...

>>> apdu select A000000001000001
→ 00 A4 04 00 08 A0 00 00 00 01 00 00 01
← 90 00  (8.5 ms)

>>> deploy install build/libs/Test.cap
...
```

---

## 7. 故障排除

### 7.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `未找到读卡器` | PC/SC 服务未启动 | macOS: `sudo launchctl start com.apple.pcscd` |
| `6A82` | ISD 未找到 | 检查卡片是否正确放置，尝试 `session reset` |
| `6982` | 密钥错误 | 确认 `config key` 与卡片密钥一致 |
| `6985` | 安全条件不满足 | 需要先建立 SCP 通道（通常自动处理） |
| `6438` | 包依赖缺失 | 卡片 JavaCard 版本过低，需升级卡片 |
| `6A80` | 数据格式错误 | 检查 APDU 或安装参数格式 |
| `connect` 后无响应 | 卡片与读卡器不兼容 | 检查卡片规范是否支持 |

### 7.2 SW 状态字典速查

| SW | 含义 | 处理建议 |
|----|------|----------|
| `9000` | 成功 | — |
| `6100`~`61FF` | 还有数据等待读取 | 发送 `GET RESPONSE` |
| `6C00`~`6CFF` | Le 错误，正确值为 XX | 重发，Le 设为 XX |
| `6A82` | 未找到（文件/DF）；多返回状态字 `6A82`，注意读卡器指令未找到 | 检查 AID 是否正确 |
| `6982` | 安全状态不满足（未认证） | 检查密钥配置 |
| `6985` | 使用条件不满足 | 检查当前卡片/Applet 状态 |
| `6A80` | 数据字段错误 | 检查命令参数格式 |
| `6438` | 不支持（包依赖问题） | 检查 JC 版本兼容性 |
| `6700` | 错误的长度 | 检查 Lc/Le 字段 |
| `6D00` | INS 不支持 | 检查 INS 字节 |
| `6E00` | CLA 不支持 | 检查 CLA 字节 |

### 7.3 调试技巧

```bash
# 1. 开启 APDU 耗时显示
>>> apdu timing

# 2. 查看 APDU 历史，定位失败指令
>>> apdu history --all

# 3. 重放某条 APDU 进行孤立测试
>>> apdu replay <编号>

# 4. 使用 --step 模式分步执行，观察每步结果
>>> deploy install app.cap --step

# 5. 查看详细帮助（三层帮助：命令层 + APDU 层 + 诊断层）
>>> help card install
```

---

## 8. 附录

### 8.1 命令全称索引

| 命令 |  subsystem | 功能 |
|------|-----------|------|
| `card list` | card | 列出所有应用 |
| `card info` | card | 显示卡片信息 |
| `card lifecycle` | card | 生命周期管理 |
| `card applet-state` | card | Applet 状态管理 |
| `card store-data` | card | 存储数据 |
| `card create-domain` | card | 创建安全域 |
| `card rename-isd` | card | 重命名 ISD |
| `card make-selectable` | card | 设为可选 |
| `card set-cplc` | card | 设置 CPLC |
| `deploy install` | deploy | 安装 CAP |
| `deploy delete` | deploy | 删除应用 |
| `deploy load` | deploy | 加载 CAP |
| `deploy plan` | deploy | 显示部署计划 |
| `deploy provision` | deploy | 执行批量部署 |
| `config key` | config | 设置连接密钥 |
| `config aid` | config | 注册 AID 别名 |
| `config mode` | config | 设置 SCP 模式 |
| `config show` | config | 显示配置 |
| `config set` | config | 设置配置项 |
| `config get` | config | 读取配置项 |
| `config save` | config | 保存配置 |
| `config load` | config | 加载配置 |
| `key put` | key | 更新卡片密钥 |
| `key delete` | key | 删除密钥 |
| `apdu send` | apdu | 发送 APDU |
| `apdu select` | apdu | SELECT 指令 |
| `apdu get-response` | apdu | 读取响应 |
| `apdu secure-send` | apdu | 安全通道发送 |
| `apdu repeat` | apdu | 重复上条 APDU |
| `apdu timing` | apdu | 切换耗时显示 |
| `apdu send-file` | apdu | 批量发送 |
| `apdu history` | apdu | 历史记录 |
| `apdu replay` | apdu | 重放 APDU |
| `apdu search` | apdu | 搜索历史 |
| `session info` | session | 会话信息 |
| `session readers` | session | 列出读卡器 |
| `session connect` | session | 连接读卡器 |
| `session reconnect` | session | 重新连接 |
| `session reset` | session | 复位卡片 |
| `session record` | session | 录制会话 |

### 8.2 GP 规范参考

- GlobalPlatform Card Specification v2.2.1
- GlobalPlatform Secure Channel Protocol v02 / v03
- Oracle JavaCard Runtime Environment Specification v3.0.4

### 8.3 相关工具

| 工具 | 用途 |
|------|------|
| [GlobalPlatformPro](https://github.com/martinpaljak/GlobalPlatformPro) | gp.jar 底层工具 |
| [pyscard](https://github.com/LudovicRousseau/pyscard) | Python PC/SC 库 |
| [JC SDK](https://www.oracle.com/java/technologies/javacard-sdk-downloads.html) | JavaCard 开发工具包 |

---

*手册版本：v0.7.0 | 最后更新：2026-06-18*
