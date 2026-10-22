"""The judge's sealed image (brief 2 A2 Scope 3, A3 item 2): an OCI image composed from bytes, not built, so that its
digest is a function of the tree alone and anyone holding the baseline re-derives it on any host and any runtime version.

The image is the judge's pinned base image (`judge/config.toml` [candidate] base_image, the one FROM of
`release/Containerfile`) and one layer: every file of `judge/` but bytecode caches, at `/release/judge/`, in path order,
owner 0:0, mode 0644 (directories 0755), mtime 0, ustar. Its config is the base's config blob with what
`release/Containerfile` states appended (`PYTHONDONTWRITEBYTECODE=1`, working directory `/release`, entrypoint
`python -B -m judge`, no command), `created` at the epoch, and one history entry; its manifest lists the base's
layers and that layer, every layer uncompressed, so no compressor's version enters a digest. JSON is written with sorted
keys and no spaces. The base's config blob and layers are read from an uncompressed OCI save of the base and checked
against its image ID and diff IDs before use.

`python -m harness.seal OUT`: compose the image into the OCI layout OUT (absent) under podman and print the manifest
digest, the digest the seal records, and the image ID (the config digest)."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from harness.pin import ROOT

MANIFEST = "application/vnd.oci.image.manifest.v1+json"
CONFIG = "application/vnd.oci.image.config.v1+json"
LAYER = "application/vnd.oci.image.layer.v1.tar"
EPOCH = "1970-01-01T00:00:00Z"
PREFIX = "release/judge"
ENV = "PYTHONDONTWRITEBYTECODE=1"
WORKDIR = "/release"
ENTRYPOINT = ["python", "-B", "-m", "judge"]
HISTORY = "harness.seal: judge/ at /release/judge (release/Containerfile, composed)"


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def judge_files(root: Path) -> list[tuple[str, bytes]]:
    """(path under the image root, bytes) for every file of `root`/judge but bytecode caches, in path order."""
    top = root / "judge"
    return sorted((f"{PREFIX}/{p.relative_to(top).as_posix()}", p.read_bytes()) for p in top.rglob("*")
                  if p.is_file() and "__pycache__" not in p.relative_to(top).parts)


def _info(name: str, kind: bytes, mode: int, size: int = 0) -> tarfile.TarInfo:
    t = tarfile.TarInfo(name)
    t.type, t.mode, t.size, t.mtime, t.uid, t.gid, t.uname, t.gname = kind, mode, size, 0, 0, 0, "", ""
    return t


def layer(files: list[tuple[str, bytes]]) -> bytes:
    """The ustar layer holding `files` and every directory above them, each directory before its entries."""
    dirs = sorted({"/".join(n.split("/")[:i]) for n, _ in files for i in range(1, n.count("/") + 1)})
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for d in dirs:
            tar.addfile(_info(d + "/", tarfile.DIRTYPE, 0o755))
        for n, data in files:
            tar.addfile(_info(n, tarfile.REGTYPE, 0o644, len(data)), io.BytesIO(data))
    return buf.getvalue()


def config(base: bytes, diff_id: str) -> bytes:
    """The base's config blob `base` with release/Containerfile's statements and the layer `diff_id` appended."""
    cfg = json.loads(base)
    inner = cfg.get("config", {})
    inner = {k: v for k, v in inner.items() if k != "Cmd"} | {
        "Env": [*inner.get("Env", []), ENV], "WorkingDir": WORKDIR, "Entrypoint": ENTRYPOINT}
    return canonical(cfg | {
        "config": inner, "created": EPOCH,
        "rootfs": {"type": "layers", "diff_ids": [*cfg["rootfs"]["diff_ids"], diff_id]},
        "history": [*cfg.get("history", []), {"created": EPOCH, "created_by": HISTORY}]})


def manifest(cfg: bytes, layers: list[tuple[str, int]]) -> bytes:
    """The manifest of config blob `cfg` and the uncompressed layers `layers` ((digest, size), base first)."""
    return canonical({"schemaVersion": 2, "mediaType": MANIFEST,
                      "config": {"mediaType": CONFIG, "digest": sha(cfg), "size": len(cfg)},
                      "layers": [{"mediaType": LAYER, "digest": d, "size": n} for d, n in layers]})


def base_blobs(saved: Path, image_id: str) -> tuple[bytes, list[Path]]:
    """The base's config blob and its layer files from the uncompressed OCI save at `saved`, checked: the config's
    digest is `image_id` and each layer's digest is its diff ID, in order."""
    blob = lambda d: saved / "blobs" / "sha256" / d.split(":", 1)[1]  # noqa: E731
    index = json.loads((saved / "index.json").read_text())
    man = json.loads(blob(index["manifests"][0]["digest"]).read_bytes())
    cfg = blob(man["config"]["digest"]).read_bytes()
    if sha(cfg) != image_id:
        raise ValueError(f"the saved base config is {sha(cfg)}, not the base image {image_id}")
    diff_ids = json.loads(cfg)["rootfs"]["diff_ids"]
    paths = [blob(m["digest"]) for m in man["layers"]]
    got = [sha(p.read_bytes()) for p in paths]
    if got != diff_ids:
        raise ValueError(f"the saved base layers {got} are not its diff IDs {diff_ids}")
    return cfg, paths


def compose(root: Path, base_cfg: bytes, base_layers: list[Path], out: Path) -> tuple[str, str]:
    """Write the sealed image of `root`'s judge/ over the base (config blob, layer files) as the OCI layout `out`;
    return (manifest digest, image ID)."""
    ours = layer(judge_files(root))
    cfg = config(base_cfg, sha(ours))
    man = manifest(cfg, [(sha(p.read_bytes()), p.stat().st_size) for p in base_layers] + [(sha(ours), len(ours))])
    blobs = out / "blobs" / "sha256"
    blobs.mkdir(parents=True)
    for p in base_layers:
        (blobs / p.name).write_bytes(p.read_bytes())
    for data in (ours, cfg, man):
        (blobs / sha(data).split(":", 1)[1]).write_bytes(data)
    (out / "oci-layout").write_bytes(canonical({"imageLayoutVersion": "1.0.0"}))
    (out / "index.json").write_bytes(canonical({"schemaVersion": 2, "manifests": [
        {"mediaType": MANIFEST, "digest": sha(man), "size": len(man)}]}))
    return sha(man), sha(cfg)


def seal(binary: str, base: str, root: Path, out: Path) -> tuple[str, str]:
    """Save the base image `base` uncompressed under the runtime `binary` and compose the sealed image into `out`."""
    image_id = subprocess.run([binary, "image", "inspect", "--format", "{{.Id}}", base], check=True,
                              capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="assize-seal-base-") as d:
        saved = Path(d) / "base"
        subprocess.run([binary, "save", "--uncompressed", "--format", "oci-dir", "-o", str(saved), base], check=True,
                       capture_output=True)
        cfg, paths = base_blobs(saved, image_id if image_id.startswith("sha256:") else f"sha256:{image_id}")
        return compose(root, cfg, paths, out)


def main(argv: list[str] | None = None) -> int:
    from judge import runtime

    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m harness.seal OUT", file=sys.stderr)
        return 2
    base = runtime.candidate_config()["base_image"]
    runtime.pull(runtime.Runtime("podman", "podman"), base)
    digest, image = seal("podman", base, ROOT, Path(args[0]))
    print(f"manifest {digest}\nimage {image}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
