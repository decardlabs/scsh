"""状态字 (SW) 数据库。

包含常用 ISO 7816-4 和 GlobalPlatform 状态字及其人类可读描述。
"""

from __future__ import annotations

from enum import Enum


class SWClass(Enum):
    """SW 分类。"""
    SUCCESS = "正常处理"
    WARNING = "警告"
    ERROR = "执行错误"
    SECURITY = "安全检查错误"
    MEMORY = "内存问题"
    FILE = "文件问题"


SW_RANGES: dict[tuple[int, int], SWClass] = {
    (0x6100, 0x61FF): SWClass.WARNING,     # 61xx = 更多数据可用
    (0x6200, 0x62FF): SWClass.WARNING,     # 62xx = 状态警告
    (0x6300, 0x63FF): SWClass.WARNING,     # 63xx = 状态警告
    (0x6400, 0x64FF): SWClass.ERROR,       # 64xx = 执行错误
    (0x6500, 0x65FF): SWClass.ERROR,       # 65xx = 执行错误
    (0x6600, 0x66FF): SWClass.SECURITY,    # 66xx = 安全检查
    (0x6700, 0x67FF): SWClass.ERROR,       # 67xx = 长度错误
    (0x6800, 0x68FF): SWClass.ERROR,       # 68xx = CLA 不支持
    (0x6900, 0x69FF): SWClass.ERROR,       # 69xx = 命令不允许
    (0x6A00, 0x6AFF): SWClass.FILE,        # 6Axx = 参数/文件错误
    (0x6B00, 0x6BFF): SWClass.ERROR,       # 6Bxx = P1P2 错误
    (0x6C00, 0x6CFF): SWClass.ERROR,       # 6Cxx = Le 错误
    (0x6D00, 0x6DFF): SWClass.ERROR,       # 6Dxx = INS 不支持
    (0x6E00, 0x6EFF): SWClass.ERROR,       # 6Exx = CLA 不支持
    (0x6F00, 0x6FFF): SWClass.ERROR,       # 6Fxx = 未知错误
    (0x9000, 0x9000): SWClass.SUCCESS,     # 9000 = 成功
}


class SWDatabase:
    """状态字数据库。"""

    def __init__(self) -> None:
        self._map: dict[int, str] = {}

    def register(self, sw: int, description: str) -> None:
        """注册状态字描述。"""
        self._map[sw] = description

    def get(self, sw: int) -> str | None:
        """获取指定状态字的人类可读描述。"""
        return self._map.get(sw)

    def get_class(self, sw: int) -> str | None:
        """获取状态字所属分类。"""
        for (lo, hi), cls in SW_RANGES.items():
            if lo <= sw <= hi:
                return cls.value
        return None


# 全局单例
SW_DATABASE = SWDatabase()

# ── 注册常用状态字 ─────────────────────────────────────

# 成功
SW_DATABASE.register(0x9000, "SUCCESS (正常处理完成)")

# 61xx — 更多数据
SW_DATABASE.register(0x61FF, "更多数据可用 (Le 不够长)")

# 62xx — 状态警告
SW_DATABASE.register(0x6200, "无信息")
SW_DATABASE.register(0x6281, "回退到 T=0")
SW_DATABASE.register(0x6282, "文件结尾 (EOF)")
SW_DATABASE.register(0x6283, "所选文件无效")
SW_DATABASE.register(0x6284, "FCI 不支持所选格式")
SW_DATABASE.register(0x6285, "未包含足够的输入数据")
SW_DATABASE.register(0x6286, "不支持的文件位置")

# 63xx — 状态警告
SW_DATABASE.register(0x6300, "认证失败")
SW_DATABASE.register(0x6381, "填充的数据文件")
SW_DATABASE.register(0x6382, "文件已锁定")

# 64xx — 执行错误
SW_DATABASE.register(0x6400, "命令执行失败")
SW_DATABASE.register(0x6401, "立即复位")

# 65xx — 执行错误
SW_DATABASE.register(0x6500, "无信息")
SW_DATABASE.register(0x6581, "内存写入失败")
SW_DATABASE.register(0x6582, "内存写入成功但无响应")

# 66xx — 安全检查
SW_DATABASE.register(0x6600, "无信息")
SW_DATABASE.register(0x6620, "无附加安全环境建立")

# 67xx — 长度错误
SW_DATABASE.register(0x6700, "长度错误 (Lc/Le 不正确)")
SW_DATABASE.register(0x6713, "Lc 类型与 P1P2 不兼容")

# 68xx — CLA 不支持
SW_DATABASE.register(0x6800, "逻辑通道不支持")
SW_DATABASE.register(0x6881, "安全通道不支持")
SW_DATABASE.register(0x6882, "安全消息不支持")

# 69xx — 命令不允许
SW_DATABASE.register(0x6900, "命令不允许")
SW_DATABASE.register(0x6981, "命令与文件结构不兼容")
SW_DATABASE.register(0x6982, "安全状态不满足 (需要认证)")
SW_DATABASE.register(0x6983, "认证方法被锁定")
SW_DATABASE.register(0x6984, "引用的数据被锁定/无效")
SW_DATABASE.register(0x6985, "使用条件不满足")
SW_DATABASE.register(0x6986, "命令不允许 (无 EF 选择)")
SW_DATABASE.register(0x6987, "安全消息 MAC 不匹配")
SW_DATABASE.register(0x6988, "安全消息校验和不正确")
SW_DATABASE.register(0x6989, "Applet 已被选择")

# 6Axx — 参数/文件错误
SW_DATABASE.register(0x6A00, "参数错误")
SW_DATABASE.register(0x6A80, "数据字段参数不正确")
SW_DATABASE.register(0x6A81, "功能不支持")
SW_DATABASE.register(0x6A82, "文件未找到")
SW_DATABASE.register(0x6A83, "记录未找到")
SW_DATABASE.register(0x6A84, "文件中空间不足")
SW_DATABASE.register(0x6A85, "Lc 与 TLV 结构不匹配")
SW_DATABASE.register(0x6A86, "P1/P2 参数不正确")
SW_DATABASE.register(0x6A87, "Lc 与 P1/P2 不匹配")
SW_DATABASE.register(0x6A88, "引用的数据未找到")

# 6Bxx — P1P2 错误
SW_DATABASE.register(0x6B00, "引用 P1/P2 不正确")

# 6Cxx — Le 错误
SW_DATABASE.register(0x6C00, "Le 不正确")

# 6Dxx — INS 不支持
SW_DATABASE.register(0x6D00, "指令 INS 不支持")

# 6Exx — CLA 不支持
SW_DATABASE.register(0x6E00, "CLA 不支持")

# 6Fxx — 未知错误
SW_DATABASE.register(0x6F00, "未知错误 (诊断错误)")

# ── GP 特定状态字 ─────────────────────────────────────

SW_DATABASE.register(0x6985, "使用条件不满足 (GP 安全通道未建立)")
SW_DATABASE.register(0x6A88, "引用的数据未找到 (AID 未安装)")
SW_DATABASE.register(0x6A86, "P1/P2 参数不正确 (GP 阶段错误)")
