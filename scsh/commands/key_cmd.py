"""key 子系统命令注册。

key — 密钥管理子系统
  put          更新卡片上的 SCP 密钥（换锁）
  delete       删除密钥版本

⚠️ config key 是"我手里的钥匙"（本地连接密钥），
  key put 是"换卡上的锁"（更新卡片密钥）。两者方向不同。
"""

from __future__ import annotations

from typing import Any

from scsh.commands.help_data import KEY_HELP


def register_key_subsystem(registry: Any) -> None:
    """注册 key 子系统及其子命令和别名。"""
    from scsh.commands.gp import cmd_gp_put_key, cmd_gp_delete_key

    registry.register_subsystem("key", "密钥管理子系统（卡片上的密钥）")

    registry.register_subcommand(
        "key", "put", "更新卡片上的 SCP 密钥", cmd_gp_put_key, KEY_HELP["put"]
    )
    registry.register_subcommand(
        "key", "delete", "删除指定版本密钥", cmd_gp_delete_key, KEY_HELP["delete"]
    )

    # 别名
    registry.register_alias("gp-put-key", "key", "put")
    registry.register_alias("gp-delete-key", "key", "delete")
