#!/usr/bin/env python3
"""统计收集的 GitHub issues 和 PRs 数量"""

import json
import os
from pathlib import Path


def count_items(json_file: Path) -> int:
    """读取 JSON 文件并返回数组长度"""
    if not json_file.exists():
        return 0
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return len(data) if isinstance(data, list) else 0
    except (json.JSONDecodeError, IOError) as e:
        print(f"  警告: 无法读取 {json_file}: {e}")
        return 0


def main():
    # 获取 raw 目录路径
    raw_dir = Path(__file__).parent
    
    total_issues = 0
    total_prs = 0
    project_stats = []
    
    # 遍历所有项目目录
    for project_dir in sorted(raw_dir.iterdir()):
        if not project_dir.is_dir():
            continue
            
        issues_file = project_dir / "issues.json"
        prs_file = project_dir / "prs.json"
        
        issues_count = count_items(issues_file)
        prs_count = count_items(prs_file)
        
        project_stats.append({
            "project": project_dir.name,
            "issues": issues_count,
            "prs": prs_count,
        })
        
        total_issues += issues_count
        total_prs += prs_count
    
    # 打印统计结果
    print("=" * 60)
    print("GitHub Issues 和 PRs 统计")
    print("=" * 60)
    print()
    
    if not project_stats:
        print("未找到任何项目数据")
        return
    
    # 表头
    print(f"{'项目名称':<30} {'Issues':>10} {'PRs':>10}")
    print("-" * 60)
    
    # 每个项目的统计
    for stat in project_stats:
        print(f"{stat['project']:<30} {stat['issues']:>10} {stat['prs']:>10}")
    
    # 总计
    print("-" * 60)
    print(f"{'总计':<30} {total_issues:>10} {total_prs:>10}")
    print()
    print(f"共收集 {len(project_stats)} 个项目的数据")
    print(f"总计 {total_issues + total_prs} 个条目 (Issues: {total_issues}, PRs: {total_prs})")


if __name__ == "__main__":
    main()
