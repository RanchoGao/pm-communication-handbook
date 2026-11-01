"""Validate every deliverable with the official EPUBCheck distribution."""
from pathlib import Path
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '5.3.0'
if __name__ == '__main__':
    base = ROOT/'.tools'/'epubcheck'
    jar = base/f'epubcheck-{VERSION}'/'epubcheck.jar'
    if not jar.exists():
        base.mkdir(parents=True, exist_ok=True)
        archive = base/'epubcheck.zip'
        urllib.request.urlretrieve(f'https://github.com/w3c/epubcheck/releases/download/v{VERSION}/epubcheck-{VERSION}.zip', archive)
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                target = (base/item.filename).resolve()
                assert target.is_relative_to(base.resolve()), 'Unsafe ZIP path'
            z.extractall(base)
    epubs = list((ROOT/'dist').glob('*.epub'))
    assert epubs, 'No EPUB deliverable found'
    for epub in epubs:
        subprocess.run(['java', '-jar', str(jar), str(epub)], check=True)
