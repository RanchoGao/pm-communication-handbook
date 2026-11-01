"""Install pinned portable build tools inside this workspace, without admin rights."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {"mdbook": "0.5.4", "pandoc": "3.13"}


def fetch(url, target):
    request = urllib.request.Request(url, headers={"User-Agent": "pm-communication-handbook"})
    with urllib.request.urlopen(request, timeout=120) as response:
        target.write_bytes(response.read())


def install(name):
    version = VERSIONS[name]
    base = ROOT / ".tools" / name
    base.mkdir(parents=True, exist_ok=True)
    exe = name + (".exe" if os.name == "nt" else "")
    destination = base / exe
    if destination.exists():
        return
    if platform.machine().lower() not in ("amd64", "x86_64") and not (os.name == "nt" and struct.calcsize("P") == 8 and not platform.machine()):
        raise SystemExit("自动安装仅支持 x64；其他架构请自行安装固定版本到 PATH。")
    if name == "mdbook":
        triplet = "x86_64-pc-windows-msvc" if os.name == "nt" else "x86_64-unknown-linux-gnu"
        asset = f"mdbook-v{version}-{triplet}" + (".zip" if os.name == "nt" else ".tar.gz")
        url = f"https://github.com/rust-lang/mdBook/releases/download/v{version}/{asset}"
    else:
        asset = f"pandoc-{version}-windows-x86_64.zip" if os.name == "nt" else f"pandoc-{version}-linux-amd64.tar.gz"
        url = f"https://github.com/jgm/pandoc/releases/download/{version}/{asset}"
    archive = base / asset
    print(f"Downloading {name} {version}", flush=True)
    fetch(url, archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (base / "download.json").write_text(json.dumps({"version": version, "url": url, "sha256": digest}, indent=2), encoding="utf-8")
    if asset.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            matches = [m for m in z.namelist() if m.split("/")[-1] == exe]
            destination.write_bytes(z.read(matches[0]))
    else:
        with tarfile.open(archive) as t:
            member = next(m for m in t.getmembers() if m.name.split("/")[-1] == exe and m.isfile())
            destination.write_bytes(t.extractfile(member).read())
    destination.chmod(0o755)
    print(f"Installed {destination}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tools", nargs="*")
    for tool in (parser.parse_args().tools or list(VERSIONS)):
        if tool not in VERSIONS:
            parser.error(f"Unknown tool: {tool}")
        install(tool)
