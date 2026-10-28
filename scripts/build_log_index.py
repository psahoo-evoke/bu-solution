"""Rebuild the run index in ai-logs/README.md from the log files."""
import pathlib, re
root = pathlib.Path(__file__).resolve().parents[1] / "ai-logs"
rows = []
for f in sorted(root.glob("20*/*.md")):
    text = f.read_text(encoding="utf-8")
    title = text.splitlines()[0].lstrip("# ").strip()
    owner = re.search(r"\| Human owner \| (.+?) \|", text)
    rows.append(f"| {f.parent.name} | [{f.stem}]({f.parent.name}/{f.name}) | {title.split('·', 1)[-1].strip()} | {owner.group(1) if owner else ''} |")
table = "| Date | Run | What | Human owner |\n| --- | --- | --- | --- |\n" + "\n".join(rows)
readme = root / "README.md"
s = readme.read_text(encoding="utf-8")
s = re.sub(r"<!-- INDEX:START -->.*<!-- INDEX:END -->", f"<!-- INDEX:START -->\n{table}\n<!-- INDEX:END -->", s, flags=re.S)
readme.write_text(s, encoding="utf-8")
print(f"{len(rows)} runs indexed")
