"""CLI 入口 — 终端中运行多 Agent 辩论"""

import sys

# 修复 Windows 终端编码问题（GBK 无法输出 emoji）
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.table import Table

from src.roles import get_preset, get_preset_names, recommend_roles
from src.orchestrator import DebateOrchestrator

console = Console()

# Agent 颜色映射
AGENT_COLORS = ["cyan", "yellow", "green", "magenta", "blue", "red"]


def _get_color(index: int) -> str:
    return AGENT_COLORS[index % len(AGENT_COLORS)]


@click.group()
def main():
    """🎤 多Agent辩论式团队 — 基于 DeepSeek API 的智能辩论系统"""
    pass


@main.command()
@click.argument("topic", type=str)
@click.option("--preset", "-p", type=click.Choice(get_preset_names()), help="使用预设角色模板")
@click.option("--roles", "-r", type=str, help="自定义角色名（逗号分隔），如: 经济学家,环保主义者")
@click.option("--rounds", "-n", type=int, default=3, help="辩论轮次（默认 3）")
@click.option("--ai-roles", is_flag=True, help="使用 AI 自动推荐角色（忽略 --preset 和 --roles）")
def debate(topic: str, preset: str | None, roles: str | None, rounds: int, ai_roles: bool):
    """开始一场辩论。话题用引号包裹，如: "AI是否应该被严格监管" """

    # --- 1. 确定角色 ---
    agents = None
    role_source = ""

    if ai_roles:
        with console.status("[bold yellow]🤖 AI 正在分析话题，推荐辩论角色...[/bold yellow]"):
            try:
                agents = recommend_roles(topic)
                role_source = "AI 推荐"
            except Exception as e:
                console.print(f"[red]AI 推荐失败: {e}[/red]")
                console.print("[yellow]回退到默认模板: 正反辩论[/yellow]")
                agents = get_preset("正反辩论")
                role_source = "正反辩论（回退）"
    elif preset:
        agents = get_preset(preset)
        role_source = f"预设模板: {preset}"
    elif roles:
        role_names = [r.strip() for r in roles.split(",")]
        agents = []
        for name in role_names:
            from src.agent import DebateAgent
            agents.append(DebateAgent(
                name=name,
                role=f"你是 {name}，从你的专业角度参与辩论。",
                stance=f"从{name}的专业视角出发",
            ))
        role_source = "自定义角色"
    else:
        # 默认使用正反辩论
        agents = get_preset("正反辩论")
        role_source = "正反辩论（默认）"

    # --- 2. 打印辩论信息 ---
    console.print()
    console.print(Panel.fit(
        f"[bold white]辩论话题:[/bold white] {topic}",
        title="🎤 辩论开始",
        border_style="bold blue",
    ))

    agent_table = Table(title=f"👥 辩论角色 ({role_source})", show_header=True)
    agent_table.add_column("角色", style="bold")
    agent_table.add_column("立场", style="italic")
    for a in agents:
        agent_table.add_row(a.name, a.stance or "—")
    console.print(agent_table)
    console.print(f"[dim]辩论轮次: {rounds} | Agent 数量: {len(agents)}[/dim]")
    console.print()

    # --- 3. 运行辩论 ---
    orchestrator = DebateOrchestrator(topic=topic, agents=agents, total_rounds=rounds)

    # 用 accumulator 收集每个 agent 当前轮次的流式文本
    accumulators: dict[str, str] = {}

    for event in orchestrator.run_stream():
        etype = event["type"]

        if etype == "round_start":
            r, t = event["round"], event["total"]
            console.print()
            console.rule(f"[bold blue]第 {r}/{t} 轮[/bold blue]")

        elif etype == "agent_start":
            name = event["agent"]
            accumulators[name] = ""
            console.print(f"\n[bold {_get_color(len(accumulators)-1)}]📣 {name}:[/bold {_get_color(len(accumulators)-1)}]")

        elif etype == "chunk":
            name = event["agent"]
            accumulators[name] += event["text"]
            # 实时逐字打印
            console.print(event["text"], end="", highlight=False)

        elif etype == "agent_end":
            console.print()  # 换行

        elif etype == "round_end":
            console.print()

        elif etype == "done":
            break

    # --- 4. 辩论结束 ---
    console.print()
    console.print(Panel.fit(
        f"[green]辩论结束！共 {rounds} 轮，{len(agents)} 位辩手，{len(orchestrator.record.messages)} 条发言[/green]",
        border_style="green",
    ))


@main.command()
@click.argument("topic", type=str)
def recommend(topic: str):
    """AI 根据话题推荐合适的辩论角色"""
    console.print()
    with console.status(f"[bold yellow]🤖 分析话题: {topic}...[/bold yellow]"):
        try:
            agents = recommend_roles(topic)
        except Exception as e:
            console.print(f"[red]推荐失败: {e}[/red]")
            sys.exit(1)

    console.print(Panel.fit(f"推荐角色 for: [bold]{topic}[/bold]", title="🤖 AI 推荐"))
    table = Table(show_header=True)
    table.add_column("#", style="dim")
    table.add_column("角色", style="bold")
    table.add_column("描述")
    table.add_column("立场", style="italic")
    for i, a in enumerate(agents, 1):
        # 截断 role 显示
        desc = a.role[:80] + "..." if len(a.role) > 80 else a.role
        table.add_row(str(i), a.name, desc, a.stance or "—")
    console.print(table)

    console.print("\n[dim]使用方法: python cli.py debate \"{topic}\" --roles {names}[/dim]".format(
        topic=topic,
        names=",".join(a.name for a in agents),
    ))


@main.command()
def presets():
    """列出所有预设角色模板"""
    console.print()
    for name in get_preset_names():
        agents = get_preset(name)
        console.print(f"[bold cyan]{name}[/bold cyan] ({len(agents)} 个角色):")
        for a in agents:
            console.print(f"  • [bold]{a.name}[/bold] — {a.stance}" if a.stance else f"  • [bold]{a.name}[/bold]")
        console.print()


if __name__ == "__main__":
    main()
