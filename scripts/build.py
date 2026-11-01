"""Single source build: checks, mdBook website, EPUB and A5 PDF."""
import argparse
from datetime import date
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / 'book'
BUILD = ROOT / 'build'
DIST = ROOT / 'dist'
LINK = re.compile(r'(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)')
ANCHOR = re.compile(r'<a id="([^"]+)"></a>')


def run(*args):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True)


def binary(name):
    local = ROOT / '.tools' / name / (name + ('.exe' if os.name == 'nt' else ''))
    found = str(local) if local.exists() else shutil.which(name)
    if not found:
        raise RuntimeError(f'Missing {name}; run python scripts/setup_tools.py')
    return found


def chapters():
    summary = (BOOK / 'SUMMARY.md').read_text(encoding='utf-8')
    return [(label, BOOK / filename) for label, filename in LINK.findall(summary)]


def body(text):
    return text.split('<!-- book-navigation -->')[0].rstrip() + '\n'


def check():
    entries = chapters()
    summary = (BOOK/'SUMMARY.md').read_text(encoding='utf-8')
    assert (ROOT/'SUMMARY.md').read_text(encoding='utf-8') == re.sub(r'\]\(([^)]+)\)', r'](book/\1)', summary), 'Root SUMMARY.md must mirror book/SUMMARY.md'
    assert len(entries) == 15, f'Expected frontmatter + 14 chapters; got {len(entries)}'
    assert len({p for _, p in entries}) == len(entries), 'Duplicate chapter entries'
    anchors = {}
    for _, path in entries:
        assert path.is_file(), f'Missing chapter: {path}'
        text = path.read_text(encoding='utf-8')
        ids = ANCHOR.findall(text)
        assert len(ids) == len(set(ids)), f'Duplicate anchor: {path}'
        anchors[path.resolve()] = set(ids)
    checked = 0
    for path in list(ROOT.glob('*.md')) + [BOOK/'SUMMARY.md'] + [p for _,p in entries]:
        text = path.read_text(encoding='utf-8')
        # Code examples are not navigation targets.
        text = re.sub(r'```[^\n]*\n.*?```', '', text, flags=re.S)
        for _, target in LINK.findall(text):
            uri = urlsplit(target)
            if uri.scheme or target.startswith('//'):
                continue
            dest = (path.parent / unquote(uri.path)).resolve() if uri.path else path.resolve()
            assert dest.is_relative_to(ROOT), f'Link escapes project: {target}'
            assert dest.exists(), f'Broken link in {path.name}: {target}'
            if uri.fragment:
                assert unquote(uri.fragment) in anchors.get(dest, set()), f'Broken anchor in {path.name}: {target}'
            checked += 1
    print(f'PASS: {len(entries)-1} chapters, {checked} local links')


def prepare_assets():
    BUILD.mkdir(exist_ok=True)
    (BUILD/'images').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'node_modules/mermaid/dist/mermaid.min.js', ROOT/'theme/mermaid.min.js')
    definitions = []
    for _, path in chapters():
        definitions += re.findall(r'```mermaid\s*\n(.*?)```', body(path.read_text(encoding='utf-8')), re.S)
    for i, definition in enumerate(definitions):
        source = BUILD/'images'/f'diagram-{i}.mmd'
        image = source.with_suffix('.png')
        digest = hashlib.sha256(definition.encode()).hexdigest()
        stamp = source.with_suffix('.sha256')
        if not image.exists() or not stamp.exists() or stamp.read_text() != digest:
            source.write_text(definition, encoding='utf-8')
            run('node', 'scripts/browser.mjs', 'diagram', source, image)
            stamp.write_text(digest)
    cover = BUILD/'images'/'cover.png'
    if not cover.exists():
        run('node', 'scripts/browser.mjs', 'cover', '-', cover)
    return cover


def website():
    # mdBook has no Mermaid preprocessor dependency; ship the pinned local JS.
    shutil.copyfile(ROOT/'node_modules/mermaid/dist/mermaid.min.js', ROOT/'theme/mermaid.min.js')
    run(binary('mdbook'), 'build')
    assert (ROOT/'site/index.html').exists()
    # mdBook treats README as index and doesn't emit its reserved SUMMARY page.
    # Keep the same footer links working in GitHub and in the generated website.
    for page in (ROOT/'site').glob('*.html'):
        content = page.read_text(encoding='utf-8').replace('href="README.html"', 'href="index.html"')
        page.write_text(content, encoding='utf-8')
    directory = '<main><h1>章节目录</h1><ol>'
    for label, file in chapters():
        target = 'index.html' if file.name == 'README.md' else file.with_suffix('.html').name
        directory += f'<li><a href="{html.escape(target)}">{html.escape(label)}</a></li>'
    directory += '</ol></main>'
    template = (ROOT/'site/index.html').read_text(encoding='utf-8')
    (ROOT/'site/SUMMARY.html').write_text(re.sub(r'<main>.*?</main>', lambda _: directory, template, count=1, flags=re.S), encoding='utf-8')
    downloads = sorted(DIST.glob('*.epub')) + sorted(DIST.glob('*.pdf'))
    if downloads:
        destination = ROOT/'site'/'downloads'
        destination.mkdir(exist_ok=True)
        for file in downloads + list(DIST.glob('SHA256SUMS.txt')):
            shutil.copyfile(file, destination/file.name)
        links = ' · '.join(f'<a download href="downloads/{html.escape(file.name)}">下载 {file.suffix[1:].upper()}</a>' for file in downloads)
        panel = '<aside class="download-panel"><strong>离线阅读</strong><p>'+links+'</p></aside>'
        page = ROOT/'site/index.html'
        content = page.read_text(encoding='utf-8')
        content = content.replace('<main>', '<main>'+panel, 1)
        page.write_text(content, encoding='utf-8')
    print('PASS: mdBook website generated')


def export_source():
    output = []
    diagram_index = 0
    for _, path in chapters():
        text = body(path.read_text(encoding='utf-8'))
        # Explicit portable IDs replace HTML source anchors in intermediate Markdown.
        def heading(match):
            anchor, level, title = match.groups()
            # Keep numbered sections and scenarios in the TOC, omit repeated
            # action labels such as "先问自己" while retaining their link IDs.
            unlisted = ' .unlisted' if len(level) >= 3 and not re.match(r'(?:\d+\.|[A-D]\.\d)', title) else ''
            return f'{level} {title} {{#{anchor}{unlisted}}}'
        text = re.sub(r'<a id="([^"]+)"></a>\s*\n(#{1,6}) ([^\n]+)', heading, text)
        def link(match):
            label, target = match.groups()
            uri = urlsplit(target)
            if not uri.scheme and uri.fragment:
                return f'[{label}](#{uri.fragment})'
            return match[0]
        # Never rewrite examples inside code fences.
        parts = re.split(r'(```.*?```)', text, flags=re.S)
        for i in range(0,len(parts),2):
            parts[i] = LINK.sub(link, parts[i])
        text = ''.join(parts)
        def diagram(match):
            nonlocal diagram_index
            image = f'![沟通框架图](images/diagram-{diagram_index}.png)'
            diagram_index += 1
            return image
        text = re.sub(r'```mermaid\s*\n.*?```', diagram, text, flags=re.S)
        # EPUB starts with its own cover/title page; don't duplicate the manuscript title.
        if path.name == 'README.md':
            text = re.sub(r'^# 产品经理沟通手册 \{#[^}]+\}\n', '', text)
        output.append(text.strip())
    merged = '\n\n'.join(output) + '\n'
    dest = BUILD/'ebook.md'
    dest.write_text(merged, encoding='utf-8')
    return dest


def validate_epub(path):
    with zipfile.ZipFile(path) as z:
        assert z.namelist()[0] == 'mimetype'
        assert z.read('mimetype') == b'application/epub+zip'
        assert z.getinfo('mimetype').compress_type == zipfile.ZIP_STORED
        xhtmls = {name: ET.fromstring(z.read(name)) for name in z.namelist() if name.endswith('.xhtml')}
        idmap = {name: {el.attrib['id'] for el in doc.iter() if 'id' in el.attrib} for name,doc in xhtmls.items()}
        import posixpath
        for name, doc in xhtmls.items():
            for el in doc.iter():
                target = el.attrib.get('href') or el.attrib.get('src')
                if not target:
                    continue
                uri = urlsplit(target)
                if uri.scheme:
                    continue
                dest = posixpath.normpath(posixpath.join(posixpath.dirname(name),unquote(uri.path))) if uri.path else name
                assert dest in z.namelist(), f'EPUB missing resource {dest}'
                if uri.fragment and dest in idmap:
                    assert unquote(uri.fragment) in idmap[dest], f'EPUB broken anchor: {target}'
    print('PASS: EPUB XML, resources and internal links')


def ebooks(version, publication_date):
    cover = prepare_assets()
    merged = export_source()
    DIST.mkdir(exist_ok=True)
    stem = f'产品经理沟通手册_{version}_{publication_date}'
    epub = DIST/(stem+'.epub')
    pdf = DIST/(stem+'.pdf')
    common = [binary('pandoc'), merged, '--from=markdown+raw_html+header_attributes', '--standalone', '--toc', '--toc-depth=3', '--resource-path='+str(BUILD), '-M', 'title=产品经理沟通手册', '-M', 'author=EurekaGao', '-M', 'lang=zh-CN', '-M', 'date='+publication_date]
    run(*common, '--to=epub3', '--epub-cover-image='+str(cover), '--split-level=1', '--css=assets/ebook.css', '-o', epub)
    validate_epub(epub)
    front = BUILD/'front.html'
    front.write_text('<section class="cover"><p>PRODUCT COMMUNICATION</p><h1>产品经理<br>沟通手册</h1><p class="subtitle">先判断处境，再选择行动</p><p class="author">EurekaGao</p><p>'+html.escape(version+' · '+publication_date)+'</p></section>', encoding='utf-8')
    printable = BUILD/'print.html'
    # Metadata title is omitted from the HTML body: cover supplies the title.
    run(*common, '--to=html5', '--embed-resources', '--css=assets/print.css', '--include-before-body='+str(front), '--template=assets/print.html', '-o', printable)
    run('node', 'scripts/browser.mjs', 'pdf', printable, pdf)
    files = [epub, pdf]
    (DIST/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files), encoding='utf-8')
    print('PASS: EPUB + PDF built in dist/')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['check','site','ebooks','all'])
    parser.add_argument('--version', default='V1')
    parser.add_argument('--date', default=date.today().isoformat())
    args = parser.parse_args()
    if not re.fullmatch(r'V\d+(?:\.\d+)*', args.version):
        parser.error('--version must look like V1 or V1.0.0')
    try:
        date.fromisoformat(args.date)
        check()
        if args.command in ('ebooks','all'):
            ebooks(args.version, args.date)
        if args.command in ('site','all'):
            website()
    except (AssertionError, RuntimeError, FileNotFoundError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
