"""Build bounded category ZIPs from a completed portable SoStylized catalog.
CLI: --portable DIR --output DIR [--allow-listed-exclusions]
An exception must be catalog.reviewed_exclusions[{id, reviewed:true,
scope:"native_dynamic_shader_not_ported", reason:"specific explanation"}].
Pending assets are never publishable. Existing output files are never replaced.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile

PREFIX = "SoStylized_Godot_Blender"
ZIP_LIMIT = 1_800_000_000  # Strictly less than 1.8 GB, decimal bytes.
CATEGORIES = ("Trees", "Rocks", "Foliage", "WaterSky", "Other", "Textures", "Audio")
NOTES = """SoStylized portable assets for Godot and Blender

Import extracted GLBs using Godot's scene importer or Blender File > Import >
glTF 2.0. GLB geometry and portable static material textures are self-contained.
Units are already metres, +Y up in glTF; do not apply another 0.01 conversion.
Keep source pivots, node hierarchy and local transforms. Use an outer parent for
application placement. Read each asset's exported_lods: render one supplied LOD
at a time. This collection currently packages native LOD0 only.

Preserve opacity masks, cutoff and double-sided foliage. Static material bakes
do not transfer Unreal wind, weather, water shaders, Blueprint/Niagara,
Landscape behavior or world simulation. Source map identities do not establish
converted authored layouts. Collision/helper meshes remain explicitly labeled;
their inclusion does not install gameplay collision or navigation.

Read the category catalog in this ZIP and the full English catalog, source-world
index and GODOT_BLENDER_USAGE.md in kk20054/ThreeJS-Stylized-World-Assets.
Original third-party ownership and source license terms remain applicable.
Conversion and packaging grant no new license or change third-party rights.
"""


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def hash_file(path):
    with path.open("rb") as stream:
        return hash_stream(stream)


def hash_stream(stream):
    digest = hashlib.sha256()
    for data in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(data)
    return digest.hexdigest()


def relative_file(root, name):
    relative = PurePosixPath(str(name).replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts or ":" in str(relative):
        raise ValueError("Unsafe portable path: " + str(relative))
    if not relative.parts or relative.parts[0] not in ("Models", "Textures", "Audio"):
        raise ValueError("Only Models/Textures/Audio payloads may enter ZIPs")
    resolved = (root / str(relative)).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("Missing or escaping portable file: " + str(relative))
    return relative.as_posix(), resolved


def classify(asset):
    source_class = asset["source"]["class"]
    path = "/" + asset["source"]["package"].strip("/") + "/"
    labels = []
    for label, pattern in (("Collision", r"collision"), ("Effects", r"/(effects?|vfx)/"),
                           ("Demo", r"/demo/"), ("Misc", r"/misc/")):
        if re.search(pattern, path, re.I):
            labels.append(label)
    if source_class == "Texture2D":
        return "Textures", labels
    if source_class == "SoundWave":
        return "Audio", labels
    if source_class != "StaticMesh":
        raise ValueError("Unexpected portable class: " + source_class)
    if labels:
        return "Other", labels
    for category, pattern in (("Trees", r"/trees/"), ("Rocks", r"/rocks/"),
                              ("Foliage", r"/(foliage|plants)/"), ("WaterSky", r"/(water|sky)/")):
        if re.search(pattern, path, re.I):
            return category, labels
    return "Other", ["Other"]


def collect(portable, catalog, allow_exclusions):
    approved = {}
    for item in catalog.get("reviewed_exclusions", []):
        if (item.get("reviewed") is not True or item.get("scope") != "native_dynamic_shader_not_ported"
                or not isinstance(item.get("reason"), str) or not item["reason"].strip()):
            raise ValueError("Invalid reviewed exclusion declaration")
        if item["id"] in approved:
            raise ValueError("Duplicate reviewed exclusion: " + item["id"])
        approved[item["id"]] = item
    actual = Counter(item["status"] for item in catalog["assets"])
    for status in ("pending", "failed"):
        if status in catalog.get("summary", {}) and catalog["summary"][status] != actual[status]:
            raise ValueError("Catalog summary disagrees with asset status: " + status)
    grouped = {category: [] for category in CATEGORIES}
    exclusions, seen_ids, seen_paths = [], set(), set()
    for item in catalog["assets"]:
        identity, status = item["id"], item["status"]
        if identity in seen_ids:
            raise ValueError("Duplicate catalog ID: " + identity)
        seen_ids.add(identity)
        if status != "packaged":
            if (status not in ("failed", "excluded") or not allow_exclusions or identity not in approved):
                raise ValueError("Catalog is not publishable: " + identity + " status=" + status)
            exclusions.append(approved[identity])
            continue
        category, labels = classify(item)
        relative, source = relative_file(portable, item["path"])
        expected = {"StaticMesh": ("Models", {".glb"}), "Texture2D": ("Textures", {".png", ".exr"}), "SoundWave": ("Audio", {".wav"})}[item["source"]["class"]]
        if PurePosixPath(relative).parts[0] != expected[0] or source.suffix.lower() not in expected[1]:
            raise ValueError("Class/path/file-type mismatch: " + identity)
        if relative.casefold() in seen_paths:
            raise ValueError("Duplicate or case-colliding portable path: " + relative)
        seen_paths.add(relative.casefold())
        if not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")):
            raise ValueError("Missing valid portable SHA256: " + identity)
        if not isinstance(item.get("bytes"), int) or item["bytes"] <= 0 or source.stat().st_size != item["bytes"]:
            raise ValueError("Portable file size mismatch: " + identity)
        if source.suffix.lower() == ".glb" and (item.get("self_contained") is not True or item.get("exported_lods") != [0]):
            raise ValueError("GLB must be declared self-contained native LOD0: " + identity)
        entry = dict(item, download_category=category, content_labels=labels)
        grouped[category].append((entry, source))
    unused = set(approved) - {item["id"] for item in exclusions}
    if allow_exclusions and unused:
        raise ValueError("Reviewed exclusions do not match excluded assets: " + ", ".join(sorted(unused)))
    if not any(grouped.values()):
        raise ValueError("No packaged portable assets")
    return grouped, exclusions


def metadata(category, part, entries, source_digest):
    catalog = {"schema_version": 1, "category": category, "part": part,
               "source_archive_sha256": source_digest, "asset_count": len(entries),
               "scope": "This ZIP's portable assets only; full catalog and source Worlds are in the repository.",
               "assets": [entry for entry, _ in entries]}
    files = {"IMPORT_NOTES.txt": NOTES.encode("utf-8"), "catalog.json": encoded(catalog)}
    identity = {"schema_version": 1, "category": category, "part": part,
                "source_archive_sha256": source_digest,
                "metadata_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
                "assets": [{"id": entry["id"], "path": entry["path"], "sha256": entry["sha256"], "bytes": entry["bytes"]} for entry, _ in entries]}
    files["package-identity.json"] = encoded(identity)
    return files, identity


def estimated_zip_size(category, part, entries, source_digest):
    files, _ = metadata(category, part, entries, source_digest)
    sizes = [(entry["path"], entry["bytes"]) for entry, _ in entries]
    sizes.extend((name, len(data)) for name, data in files.items())
    # zlib compressBound for default deflate, plus generous ZIP64/header overhead.
    return 1024 + sum(size + (size >> 12) + (size >> 14) + (size >> 25) + 13
                      + 2 * len((PREFIX + "/" + name).encode("utf-8")) + 256 for name, size in sizes)


def split_parts(category, entries, source_digest):
    parts, current = [], []
    for entry in sorted(entries, key=lambda pair: pair[0]["path"]):
        trial = current + [entry]
        if estimated_zip_size(category, len(parts) + 1, trial, source_digest) >= ZIP_LIMIT:
            if not current:
                raise ValueError("Single file plus metadata exceeds ZIP limit: " + entry[0]["path"])
            parts.append(current)
            current = [entry]
            if estimated_zip_size(category, len(parts) + 1, current, source_digest) >= ZIP_LIMIT:
                raise ValueError("Single file plus metadata exceeds ZIP limit: " + entry[0]["path"])
        else:
            current = trial
    if current:
        parts.append(current)
    return parts


def zip_info(relative):
    info = zipfile.ZipInfo(PREFIX + "/" + relative, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def verify_zip(path, entries, files):
    expected = {PREFIX + "/" + entry["path"] for entry, _ in entries}
    expected.update(PREFIX + "/" + name for name in files)
    if path.stat().st_size >= ZIP_LIMIT:
        raise ValueError("Existing ZIP reaches/exceeds size limit: " + path.name)
    with zipfile.ZipFile(path) as archive:
        if len(archive.namelist()) != len(expected) or set(archive.namelist()) != expected:
            raise ValueError("Existing ZIP has different entries: " + path.name)
        for name, data in files.items():
            if archive.read(PREFIX + "/" + name) != data:
                raise ValueError("Existing ZIP identity/metadata differs; choose a fresh output: " + path.name)
        for entry, _ in entries:
            name = PREFIX + "/" + entry["path"]
            if archive.getinfo(name).file_size != entry["bytes"]:
                raise ValueError("Existing ZIP asset size differs: " + name)
            with archive.open(name) as stream:
                if hash_stream(stream) != entry["sha256"]:
                    raise ValueError("Existing ZIP asset digest differs: " + name)


def create_zip(path, entries, files):
    if path.exists():
        verify_zip(path, entries, files)
        return "resumed"
    handle, temporary_name = tempfile.mkstemp(prefix=".sostylized-", suffix=".partial", dir=path.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for name, data in sorted(files.items()):
                archive.writestr(zip_info(name), data, compresslevel=6)
            for entry, source in entries:
                digest = hashlib.sha256()
                with source.open("rb") as incoming, archive.open(zip_info(entry["path"]), "w", force_zip64=True) as outgoing:
                    for block in iter(lambda: incoming.read(1024 * 1024), b""):
                        digest.update(block)
                        outgoing.write(block)
                if digest.hexdigest() != entry["sha256"]:
                    raise ValueError("Portable payload digest mismatch: " + entry["path"])
        if temporary.stat().st_size >= ZIP_LIMIT:
            raise ValueError("ZIP reaches/exceeds size limit; no output published: " + path.name)
        os.link(temporary, path)  # Exclusive creation: never replaces an existing destination.
        return "created"
    finally:
        temporary.unlink(missing_ok=True)


def publish_json_without_overwrite(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("Different downloads.json exists; choose a fresh output directory")
        return
    with path.open("xb") as stream:
        stream.write(data)


def build(portable, output, allow_exclusions=False):
    portable, output = portable.resolve(), output.resolve()
    if output == portable or portable.is_relative_to(output) or output.is_relative_to(portable):
        raise ValueError("Download output must be outside the portable input tree")
    catalog_bytes = (portable / "catalog.json").read_bytes()
    catalog = json.loads(catalog_bytes.decode("utf-8-sig"))
    source_digest = catalog.get("source_archive_sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", source_digest):
        raise ValueError("Catalog must identify the original source archive SHA256")
    catalog_digest = hashlib.sha256(catalog_bytes).hexdigest()
    if (output / "downloads.json").exists():
        previous = json.loads((output / "downloads.json").read_text(encoding="utf-8"))
        if previous.get("portable_catalog_sha256") != catalog_digest or previous.get("source_archive_sha256") != source_digest:
            raise ValueError("Different downloads identity exists; choose a fresh output directory")
    grouped, exclusions = collect(portable, catalog, allow_exclusions)
    plans = [(category, part, entries) for category in CATEGORIES
             for part, entries in enumerate(split_parts(category, grouped[category], source_digest), 1)]
    output.mkdir(parents=True, exist_ok=True)
    downloads = {"schema_version": 1, "source_archive_sha256": source_digest,
                 "portable_catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
                 "entry_prefix": PREFIX + "/", "maximum_zip_bytes_exclusive": ZIP_LIMIT,
                 "reviewed_exclusions": exclusions, "categories": [], "files": []}
    for category, part, entries in plans:
        files, identity = metadata(category, part, entries, source_digest)
        name = PREFIX + "_" + category + "_part" + str(part).zfill(2) + ".zip"
        destination = output / name
        action = create_zip(destination, entries, files)
        downloads["files"].append({"zipname": name, "bytes": destination.stat().st_size,
            "sha256": hash_file(destination), "category": category, "part": part,
            "count": len(entries), "entry_prefix": PREFIX + "/",
            "source_archive_sha256": source_digest,
            "identity_sha256": hashlib.sha256(encoded(identity)).hexdigest(),
            "included_ids": [entry["id"] for entry, _ in entries],
            "included_paths": [entry["path"] for entry, _ in entries]})
        print(json.dumps({"zipname": name, "action": action, "count": len(entries)}), flush=True)
    for category in CATEGORIES:
        subset = [item for item in downloads["files"] if item["category"] == category]
        downloads["categories"].append({"category": category, "asset_count": len(grouped[category]),
                                       "parts": len(subset), "zipnames": [item["zipname"] for item in subset]})
    downloads["asset_count"] = sum(item["count"] for item in downloads["files"])
    downloads["total_zip_bytes"] = sum(item["bytes"] for item in downloads["files"])
    publish_json_without_overwrite(output / "downloads.json", encoded(downloads))
    return downloads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-listed-exclusions", action="store_true")
    args = parser.parse_args()
    try:
        result = build(args.portable, args.output, args.allow_listed_exclusions)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps({"assets": result["asset_count"], "zip_files": len(result["files"]), "bytes": result["total_zip_bytes"]}))


if __name__ == "__main__":
    main()
