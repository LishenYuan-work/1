"""桌面快捷方式启动器 — 交互式选择辩论参数"""

from src.roles import get_preset_names

print()
print("=" * 40)
print("  Multi-Agent Debate System")
print("=" * 40)
print()

topic = input("Topic: ").strip()
if not topic:
    print("No topic entered, exiting.")
    exit()

print()
print("Templates:")
presets = get_preset_names()
for i, name in enumerate(presets, 1):
    print(f"  {i}. {name}")
print(f"  {len(presets)+1}. AI Recommend")

choice = input(f"\nChoose (1-{len(presets)+1}, default 1): ").strip()
if not choice:
    choice = "1"

rounds = input("Rounds (default 3): ").strip()
if not rounds:
    rounds = "3"

# Build command
cmd_parts = ["python", "cli.py", "debate", f'"{topic}"']

choice_num = int(choice)
if choice_num == len(presets) + 1:
    cmd_parts.append("--ai-roles")
else:
    preset_name = presets[choice_num - 1]
    cmd_parts.append(f"--preset")
    cmd_parts.append(f'"{preset_name}"')

cmd_parts.append(f"--rounds")
cmd_parts.append(rounds)

cmd = " ".join(cmd_parts)

print()
print("=" * 40)
print("Starting debate...")
print("=" * 40)
print()

import os
os.system(cmd)
