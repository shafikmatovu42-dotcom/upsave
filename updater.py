import requests
import os
import sys
import zipfile
from pathlib import Path
from version import __repo__, __version__


def fetch_latest_release_info():
    api = __repo__.replace('https://github.com/', 'https://api.github.com/repos/')
    url = f"{api}/releases/latest"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def download_asset(asset_url, dest):
    headers = {'Accept': 'application/octet-stream'}
    with requests.get(asset_url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def apply_update(zip_path, target_dir):
    # Extract zip to target_dir (use atomic swap if necessary)
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(target_dir)


def check_for_update():
    try:
        info = fetch_latest_release_info()
        tag = info.get('tag_name')
        if not tag:
            return None
        if tag == __version__:
            return None
        # Pick first asset that's a zip or exe
        assets = info.get('assets', [])
        for a in assets:
            name = a.get('name', '').lower()
            if name.endswith('.zip') or name.endswith('.exe'):
                return {'tag': tag, 'asset': a}
        return None
    except Exception:
        return None


if __name__ == "__main__":
    update = check_for_update()
    if not update:
        print("No update available")
        sys.exit(0)
    asset = update['asset']
    dest = Path(os.getcwd()) / asset['name']
    print(f"Downloading {asset['name']}")
    download_asset(asset['browser_download_url'], dest)
    print("Downloaded. Please run installer or unzip to update.")
