"""One-time lossless chapter migration; preserves the current manuscript locally."""
import hashlib
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
CHAPTER = re.compile(r"^## (?:\d+\. |附录 [A-D]：)")
LINK = re.compile(r"(?<!!)\[([^\]\n]+)\]\(#([^\)]+)\)")


def slug(title):
    title = re.sub(r"[*`]", "", title).lower()
    return "".join(c for c in title if c in "-_ " or unicodedata.category(c)[0] not in "PS").replace(" ", "-")


def migrate(source):
    raw = source.read_text(encoding="utf-8-sig")
    lines = raw.splitlines(keepends=True)
    starts = []
    fenced = False
    for i, line in enumerate(lines):
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and CHAPTER.match(line):
            starts.append(i)
    assert len(starts) == 14, f"Expected 14 chapters, found {len(starts)}"
    starts.append(len(lines))
    names = ["00_阅读指南", "01_开口前的判断", "02_搞清楚", "03_说明白", "04_推着动", "05_修关系", "06_给反馈", "07_麻烦现场", "08_跟谁说", "09_怎么练", "附录A_模型速查卡", "附录B_AI提示词库", "附录C_参考资料", "附录D_整理与维护"]
    paths = [name + "_V1_2026-11-01.md" for name in names]
    docs = ["".join(lines[:starts[0]])] + ["".join(lines[a:b]) for a,b in zip(starts,starts[1:])]
    files = ["README.md"] + paths
    targets = {}
    counts = {}
    records = []
    for filename, doc in zip(files, docs):
        fenced = False
        headings = []
        for line in doc.splitlines():
            if line.startswith("```"):
                fenced = not fenced
            match = re.match(r"^(#{1,6}) (.+)$", line)
            if match and not fenced:
                key = slug(match[2])
                n = counts.get(key, 0)
                counts[key] = n + 1
                key += f"-{n}" if n else ""
                anchor = "h-" + hashlib.sha1(key.encode()).hexdigest()[:12]
                targets[key] = (filename, anchor)
                headings.append((line, anchor))
        records.append(headings)
    unresolved = []
    rendered = []
    for filename, doc, headings in zip(files, docs, records):
        def rewrite(match):
            label, key = match.groups()
            if key not in targets:
                unresolved.append(key)
                return match[0]
            target, anchor = targets[key]
            return f"[{label}]({'' if target == filename else target}#{anchor})"
        output = []
        fenced = False
        hi = 0
        for line in doc.splitlines(keepends=True):
            if line.startswith("```"):
                fenced = not fenced
            if not fenced and re.match(r"^#{1,6} ", line):
                _, anchor = headings[hi]
                hi += 1
                output.append(f'<a id="{anchor}"></a>\n\n')
                if filename != "README.md":
                    line = line[1:]
            output.append(line if fenced else LINK.sub(rewrite, line))
        rendered.append("".join(output))
    assert not unresolved, f"Unresolved source links: {unresolved}"
    # Verify every source line survives except heading depth and link destinations.
    for original, result in zip(docs, rendered):
        result = re.sub(r'<a id="h-[a-f0-9]+"></a>\n\n', '', result)
        normalize = lambda s: re.sub(r"\]\([^\n)]+\)", "](TARGET)", re.sub(r"(?m)^#+ ", "# ", s)).strip()
        assert normalize(original) == normalize(result), "Body changed during migration"
    for index, (filename, output) in enumerate(zip(files, rendered)):
        nav = []
        if index > 0:
            nav.append(f"[上一章]({files[index-1]})")
        nav.append("[目录](SUMMARY.md)")
        if index + 1 < len(files):
            nav.append(f"[下一章]({files[index+1]})")
        output += '\n<!-- book-navigation -->\n\n---\n\n' + " · ".join(nav) + '\n'
        (ROOT / 'book' / filename).write_text(output, encoding='utf-8')
    items = [f"- [书籍首页](README.md)"]
    for filename, doc in zip(paths, docs[1:]):
        title = doc.splitlines()[0][3:]
        items.append(f"- [{title}]({filename})")
    summary = "# 阅读目录\n\n" + "\n".join(items) + "\n"
    (ROOT/'book'/'SUMMARY.md').write_text(summary, encoding='utf-8')
    (ROOT/'SUMMARY.md').write_text(re.sub(r"\]\(([^)]+)\)", r"](book/\1)", summary), encoding='utf-8')
    archive = ROOT / '.local-history' / 'before-chapters'
    archive.mkdir(parents=True, exist_ok=True)
    assert not (archive/source.name).exists(), "Backup exists; stop to avoid overwrite"
    source.rename(archive/source.name)
    print(f"Migrated 14 chapters; {len(targets)} headings; body comparison passed")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    migrate(parser.parse_args().source)
