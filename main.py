#!/usr/bin/env python3
"""
MathModel Dev Agent - 主入口
基于 Multi-Agent 的数学建模与自动开发系统

使用方法:
    python main.py <题目文件路径> [--project-name 项目名称]
    python main.py examples/sample_optimization.txt --project-name 优化问题
    python main.py examples/sample_prediction.txt -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

BANNER = r"""
  __  __           _     _                    _____    _
 |  \/  | ___   __| | __| | ___  _ __ ___   |  ___|__| |__   ___  _ __   __ _  ___ _ __
 | |\/| |/ _ \ / _` |/ _` |/ _ \| '_ ` _ \  | |_ / _ \ '_ \ / _ \| '_ \ / _` |/ _ \ '__|
 | |  | | (_) | (_| | (_| | (_) | | | | | | |  _|  __/ |_) | (_) | | | | (_| |  __/ |
 |_|  |_|\___/ \__,_|\__,_|\___/|_| |_| |_| |_|  \___|_.__/ \___/|_| |_|\__, |\___|_|
                                                                          |___/
"""


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="MathModel Dev Agent - 数学建模自动开发系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py examples/sample_optimization.txt
  python main.py examples/sample_prediction.txt --project-name 人口预测
  python main.py problem.pdf --verbose
        """,
    )
    parser.add_argument(
        "problem_file",
        help="题目文件路径 (支持 .txt, .md, .pdf)",
    )
    parser.add_argument(
        "--project-name", "-n",
        default="mathmodel",
        help="项目名称 (默认: mathmodel)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细输出",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式",
    )

    args = parser.parse_args()

    problem_path = Path(args.problem_file)
    if not problem_path.exists():
        print(f"错误: 文件不存在 - {problem_path}")
        sys.exit(1)

    from mathmodel.config import AppConfig
    from mathmodel.orchestrator import Orchestrator

    config = AppConfig()
    config.verbose = args.verbose
    config.debug = args.debug

    orchestrator = Orchestrator(config)

    print(BANNER)
    print(f"  题目文件: {problem_path}")
    print(f"  项目名称: {args.project_name}")
    print("=" * 64)

    try:
        result = orchestrator.execute(
            problem_file=problem_path,
            project_name=args.project_name,
        )

        # 输出 Pipeline 摘要
        print("\n")
        print("=" * 64)
        print("  Pipeline 执行摘要")
        print("=" * 64)

        summary = result.get("summary", {})
        timing = result.get("timing", {})

        status_str = "[OK] 成功" if result["success"] else "[FAIL] 失败"
        print(f"\n  状态:   {status_str}")
        print(f"  项目:   {result['project_dir']}")

        # Agent 执行详情
        print(f"\n  {'Agent':<20} {'状态':<8} {'耗时':<10}")
        print(f"  {'-' * 40}")

        from mathmodel.orchestrator import AGENT_LABELS
        for name in orchestrator.pipeline:
            label = AGENT_LABELS.get(name, name)
            elapsed = timing.get(name, "-")
            elapsed_str = f"{elapsed}s" if isinstance(elapsed, (int, float)) else elapsed

            if name in result.get("results", {}):
                ok = result["results"][name].success
                status = "[OK]" if ok else "[FAIL]"
            else:
                status = "  --  "
                elapsed_str = "  --"

            print(f"  {label:<18} {status:<8} {elapsed_str:<10}")

        total = timing.get("total", "-")
        total_str = f"{total}s" if isinstance(total, (int, float)) else total
        print(f"  {'-' * 40}")
        print(f"  {'总计':<18} {'':8} {total_str:<10}")

        # 输出文件列表
        output_files = summary.get("output_files", {})
        if output_files:
            print(f"\n  输出文件:")
            for key, path in output_files.items():
                if path:
                    if isinstance(path, list):
                        for p in path:
                            print(f"    - {p}")
                    else:
                        print(f"    - {path}")

        # 模型指标
        results = result.get("results", {})
        if "experiment" in results and results["experiment"].success:
            metrics = results["experiment"].output.get("metrics", {})
            if metrics:
                print(f"\n  模型指标:")
                for key, val in metrics.items():
                    print(f"    {key}: {val}")

        print("\n" + "=" * 64)

        if result["success"]:
            print("  全部完成! 可查看以下文件:")
            print(f"    论文: {result['project_dir']}/paper/paper.md")
            print(f"    代码: {result['project_dir']}/code/solution.py")
            print(f"    报告: {result['project_dir']}/experiment_report.md")
            print(f"    README: {result['project_dir']}/README.md")
        else:
            print("  部分步骤失败，请检查上述输出。")

        print("=" * 64)
        sys.exit(0 if result["success"] else 1)

    except Exception as e:
        print(f"\n执行异常: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
