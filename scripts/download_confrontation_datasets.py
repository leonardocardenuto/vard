"""Baixa SCFD, AIRTLab e os videos RGB domesticos/normais do VID, com verificacao."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePosixPath

HEADERS = {"User-Agent": "VARD-Research/1.0"}


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as response:
        return json.load(response)


def digest(path, algorithm="md5", git_blob=False):
    result = hashlib.new(algorithm)
    if git_blob:
        result.update(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def download(url, path, size, checksum, algorithm="md5", git_blob=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size == size and digest(path, algorithm, git_blob) == checksum:
        return
    temporary = path.with_name(path.name + ".part")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120) as response, temporary.open("wb") as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
            if temporary.stat().st_size != size or digest(temporary, algorithm, git_blob) != checksum:
                raise ValueError(f"Checksum/tamanho invalido: {path.name}")
            temporary.replace(path)
            return
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def github_dataset(root, name, repository):
    tree = get_json(f"https://api.github.com/repos/{repository}/git/trees/master?recursive=1")
    if tree.get("truncated"):
        raise ValueError("Manifesto GitHub truncado")
    entries = [item for item in tree["tree"] if item["type"] == "blob" and
               (item["path"].lower().endswith((".mp4", ".csv", ".txt", ".md")) or item["path"] == "LICENSE")]
    destination = root / name
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "download_manifest.json").write_text(json.dumps(tree, indent=2), encoding="utf-8")

    def fetch(item):
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Caminho inseguro no manifesto")
        url = f"https://raw.githubusercontent.com/{repository}/{tree['sha']}/{item['path']}"
        download(url, destination / str(relative), item["size"], item["sha"], "sha1", True)

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fetch, item) for item in entries]
        for index, future in enumerate(as_completed(futures), 1):
            future.result()
            if index % 50 == 0 or index == len(entries):
                print(f"{name}: {index}/{len(entries)} arquivos verificados", flush=True)


def vid_dataset(root):
    url = "https://dataverse.harvard.edu/api/datasets/export?exporter=dataverse_json&persistentId=doi%3A10.7910%2FDVN%2FN4LNZD"
    metadata = get_json(url)
    destination = root / "vid"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "download_manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    files = [entry for entry in metadata["datasetVersion"]["files"]
             if entry["dataFile"]["filename"].startswith(("v_d_b_", "nv_b_"))]
    for entry in files:
        if entry.get("restricted"):
            raise ValueError("Arquivo VID restrito: acesso autorizado necessario")
        data = entry["dataFile"]
        path = destination / "archives" / data["filename"]
        print(f"VID: baixando/verificando {path.name} ({data['filesize'] / 1e6:.0f} MB)", flush=True)
        download(f"https://dataverse.harvard.edu/api/access/datafile/{data['id']}", path,
                 data["filesize"], data["checksum"]["value"], data["checksum"]["type"].lower())
        extracted = destination / path.stem
        marker = extracted / ".extracted"
        if marker.exists():
            continue
        names = subprocess.check_output(["tar", "-tf", str(path)], text=True, encoding="utf-8", errors="replace")
        for filename in names.splitlines():
            relative = PurePosixPath(filename.replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts or ":" in filename:
                raise ValueError(f"Caminho inseguro no arquivo: {filename}")
        extracted.mkdir(parents=True, exist_ok=True)
        subprocess.run(["tar", "-xf", str(path.resolve()), "-C", str(extracted.resolve())], check=True)
        marker.write_text(data["checksum"]["value"], encoding="utf-8")
        print(f"VID: extraido {path.name}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("var/datasets/confrontation"))
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(github_dataset, args.root, "scfd", "seymanurakti/fight-detection-surv-dataset"),
                pool.submit(github_dataset, args.root, "airtlab", "airtlab/A-Dataset-for-Automatic-Violence-Detection-in-Videos"),
                pool.submit(vid_dataset, args.root)]
        for job in as_completed(jobs):
            job.result()
    print("Downloads e checksums concluidos para as tres bases.", flush=True)


if __name__ == "__main__":
    main()
