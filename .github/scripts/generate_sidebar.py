#!/usr/bin/env python3
"""生成 docsify 侧边栏 _sidebar.md。
   - 支持自动扫描目录，按最近修改时间倒序排列
   - 支持排除/包含文件、文件夹，并保留层级
   - 支持完全自定义侧边栏（custom_sidebar）
"""

import argparse
import json
import os
import fnmatch
from datetime import datetime


def get_entry_mtime(root: str, name: str) -> float:
    """获取文件或目录的「最新修改时间」，用于排序。
       文件：自身的 mtime
       目录：递归查找目录下所有文件的最大 mtime（空目录返回 0）
    """
    full = os.path.join(root, name)
    if os.path.isfile(full):
        return os.path.getmtime(full)

    max_mtime = 0.0
    for dirpath, _, filenames in os.walk(full):
        for f in filenames:
            fpath = os.path.join(dirpath, f)
            try:
                mtime = os.path.getmtime(fpath)
                if mtime > max_mtime:
                    max_mtime = mtime
            except OSError:
                continue
    return max_mtime


def should_include(name: str, is_dir: bool, config: dict) -> bool:
    """根据配置决定是否包含某个文件或目录（不区分大小写）。"""
    name_lower = name.lower()  # 转换为小写用于比较

    # 强制包含优先
    if is_dir and 'include_dirs' in config:
        include_dirs_lower = [d.lower() for d in config['include_dirs']]
        if name_lower in include_dirs_lower:
            return True
    if not is_dir and 'include_files' in config:
        for pattern in config['include_files']:
            if fnmatch.fnmatch(name_lower, pattern.lower()):
                return True

    # 排除规则
    if is_dir and 'exclude_dirs' in config:
        exclude_dirs_lower = [d.lower() for d in config['exclude_dirs']]
        if name_lower in exclude_dirs_lower:
            return False
    if not is_dir and 'exclude_files' in config:
        for pattern in config['exclude_files']:
            if fnmatch.fnmatch(name_lower, pattern.lower()):
                return False

    # 默认排除隐藏文件和 _sidebar.md 自身（小写比较）
    if name_lower.startswith('.') or name_lower == '_sidebar.md':
        return False
    return True

def generate_auto_sidebar(root: str, config: dict, title: str) -> str:
    """自动扫描目录，按修改时间降序生成层级侧边栏。
       支持：跳过空文件夹、目录链接到 README.md 等。
    """
    lines = []
    if title:
        lines.append(f"# {title}\n")

    try:
        all_items = os.listdir(root)
    except FileNotFoundError:
        return f"# 错误：目录 '{root}' 不存在\n"

    # 读取配置
    skip_empty = config.get('skip_empty_dirs', True)
    link_readme = config.get('link_dirs_to_readme', False)

    # 分别收集符合条件的目录和文件
    dirs = []
    files = []
    for name in all_items:
        full = os.path.join(root, name)
        is_dir = os.path.isdir(full)
        if not should_include(name, is_dir, config):
            continue
        if is_dir:
            dirs.append(name)
        else:
            files.append(name)

    # 按最新修改时间降序排序
    dirs.sort(key=lambda d: get_entry_mtime(root, d), reverse=True)
    files.sort(key=lambda f: get_entry_mtime(root, f), reverse=True)

    # 处理文件夹
    for d in dirs:
        subdir = os.path.join(root, d)
        # 收集该目录下所有符合规则的 .md 文件（不包含 README.md，因为可能需要特殊处理）
        sub_md_files = []
        try:
            for sub in os.listdir(subdir):
                sub_full = os.path.join(subdir, sub)
                if os.path.isfile(sub_full) and sub.endswith('.md'):
                    if should_include(sub, False, config):
                        sub_md_files.append(sub)
        except PermissionError:
            # 无权限时当作空目录处理
            continue

        # 如果要求跳过空目录，且该目录下没有任何 .md 文件，则跳过
        if skip_empty and not sub_md_files:
            continue

        # 生成目录条目
        has_readme = 'README.md' in sub_md_files  # 注意此时 README.md 也在 sub_md_files 中
        if link_readme and has_readme:
            # 链接到 README.md
            entry = f"- [{d}]({d}/README.md)"
            # 从列表中移除 README.md，避免重复显示
            sub_md_files.remove('README.md')
        else:
            entry = f"- **{d}**"

        lines.append(entry)

        # 排序子文件（按修改时间降序）
        sub_md_files.sort(key=lambda f: get_entry_mtime(subdir, f), reverse=True)

        # 输出子文件（缩进两个空格表示层级）
        for sub in sub_md_files:
            lines.append(f"  - [{sub[:-3]}]({d}/{sub})")

    # 处理根目录下的 Markdown 文件
    for f in files:
        if f.endswith('.md'):
            name = f[:-3]
            lines.append(f"- [{name}]({f})")
    return '\n'.join(lines) + '\n'



def generate_custom_sidebar(custom_structure: list, title: str) -> str:
    """使用用户提供的自定义结构生成侧边栏。"""
    lines = []
    if title:
        lines.append(f"# {title}\n")
    for item in custom_structure:
        if isinstance(item, str):
            lines.append(item)
        elif isinstance(item, dict):
            t = item.get('title', '')
            p = item.get('path', '')
            lines.append(f"- [{t}]({p})")
        else:
            lines.append(str(item))
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description='生成 docsify 侧边栏')
    parser.add_argument('--root', default='.', help='扫描根目录')
    parser.add_argument('--output', default='_sidebar.md', help='输出文件')
    parser.add_argument('--title', default='', help='侧边栏标题')
    parser.add_argument('--config-json', default='{}', help='配置 JSON 字符串')
    args = parser.parse_args()

    try:
        config = json.loads(args.config_json)
    except json.JSONDecodeError as e:
        print(f"❌ 配置 JSON 解析失败: {e}")
        config = {}

    if 'custom_sidebar' in config:
        content = generate_custom_sidebar(config['custom_sidebar'], args.title)
    else:
        content = generate_auto_sidebar(args.root, config, args.title)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 侧边栏已生成：{args.output}")


if __name__ == '__main__':
    main()
