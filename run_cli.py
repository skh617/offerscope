"""Offerscope CLI 调度入口

用法:
    python run_cli.py              # 执行所有任务
    python run_cli.py --dry-run    # 预览模式（使用已有数据）
"""
from offerscope.cli import main

if __name__ == "__main__":
    main()
