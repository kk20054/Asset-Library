"""Prepare readiness before build_downloads.py, then publish local repository metadata.
Usage: publish_collection.py prepare|publish --work DIR --repo DIR --release-tag TAG
Publish stages planned GitHub URLs; it does not upload, commit, or certify runtime parity.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
from urllib.parse import quote
import zipfile

from build_downloads import CATEGORIES, PREFIX, classify

REPOSITORY = "kk20054/ThreeJS-Stylized-World-Assets"
RAW = "https://raw.githubusercontent.com/" + REPOSITORY + "/main/"
COLLECTION = "collections/sostylized/"
TARGETS = {"StaticMesh", "Texture2D", "SoundWave"}
SAMPLES = ("SM_Bush1", "SM_Bamboo1", "SM_Pine01", "SM_WaterRiver04")
KNOWN = SAMPLES + ("SM_CliffClassic1", "SM_IndividualCloudPlane")
COMPACT = ("id", "source", "path", "category", "status", "bytes", "sha256",
           "triangles", "bounds", "exported_lods", "self_contained", "required_extensions",
           "warnings", "engine_log_warnings", "material_slots", "engine", "srgb", "compression_settings",
           "flip_green_channel", "channel_mapping", "material_readiness", "download_category", "content_labels",
           "download", "direct_sample_url", "direct_sample")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def safe(root, relative):
    value = PurePosixPath(str(relative).replace("\\", "/"))
    if not value.parts or value.is_absolute() or ".." in value.parts or ":" in str(value):
        raise ValueError("Unsafe relative path: " + str(relative))
    path = (root / value.as_posix()).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Escaping relative path")
    return path


def identity(asset):
    return asset["source"]["class"], asset["source"]["path"]


def completed(work):
    portable = work / "portable"
    catalog = read(portable / "catalog.json")
    inventory = read(work / "native_catalog.json")
    if catalog.get("generator") != "sostylized/package_portable.py":
        raise ValueError("Catalog is not owned by package_portable.py")
    assets = catalog["assets"]
    counts = dict(Counter(a["status"] for a in assets))
    targets = {(a["class"], a["path"]) for a in inventory["assets"] if a["class"] in TARGETS}
    if len(targets) != 1090 or len(assets) != 1090 or counts != {"packaged": 1090}:
        raise ValueError("Requires all 1090 native targets packaged; no pending, failed or exclusions")
    if {identity(a) for a in assets} != targets or len({a["id"] for a in assets}) != len(assets):
        raise ValueError("Catalog identities do not match the complete native inventory")
    if any(catalog.get("summary", {}).get(k, 0) != counts.get(k, 0)
           for k in set(counts) | set(catalog.get("summary", {}))):
        raise ValueError("Catalog summary disagrees with actual statuses")
    paths = set()
    for a in assets:
        path = safe(portable, a["path"])
        if a["path"].casefold() in paths or not path.is_file() or path.stat().st_size != a["bytes"]:
            raise ValueError("Duplicate, missing or wrong-sized payload: " + a["id"])
        paths.add(a["path"].casefold())
        if not re.fullmatch(r"[0-9a-f]{64}", a.get("sha256", "")):
            raise ValueError("Missing payload digest: " + a["id"])
        if a["source"]["class"] == "StaticMesh" and (a.get("exported_lods") != [0] or not a.get("self_contained")):
            raise ValueError("Static mesh must be self-contained LOD0: " + a["id"])
    return portable, catalog, inventory


def readiness(a):
    kind, name = a["source"]["class"], a["source"]["name"]
    result = {"status": "static_bake_not_individually_visual_reviewed",
              "runtime_effects": "not_ported", "notes": [],
              "reference": RAW + COLLECTION + "MATERIAL_READINESS.md"}
    if kind == "Texture2D":
        result.update(status="native_texture_source", channel_mapping=None,
                      notes=["Raw native PNG/EXR preserved; no inferred packed-channel semantics.",
                             "sRGB is an authored source import setting, not independent texture-role verification."])
    elif kind == "SoundWave":
        result.update(status="native_wav_source",
                      notes=["Native WAV; Unreal cues, attenuation and runtime audio behavior are not ported."])
    else:
        package = a["source"]["package"]
        if re.search(r"/(sky|water|effects?|vfx)/", package + "/", re.I):
            result["notes"].append("Target-engine shader/effect work is required for source runtime behavior.")
        if re.search(r"/rocks/", package + "/", re.I):
            result["notes"].append("Review source terrain/RVT blending before using exposed rock surfaces.")
        if name in SAMPLES[:3]:
            result.update(status="representative_static_pbr_preview",
                          preview_scope="Selected native GLB in Blender CPU; not runtime or whole-family acceptance.")
        elif name == "SM_CliffClassic1":
            result.update(status="requires_landscape_material_adaptation")
            result["notes"].append("Black lower base-color is identical to earlier bake; UseVTBlend enabled with landscape RVT references.")
        elif name == "SM_IndividualCloudPlane":
            result.update(status="custom_shader_required")
            result["notes"].append("Invisible bake: alpha=0 throughout; source uses CameraDepthFade, MPC and Blueprint opacity/fade parameters.")
        elif name == "SM_WaterRiver04":
            result.update(status="static_water_mesh_only")
            result["notes"].append("Pale static approximation only; animated water and depth behavior need a custom material.")
    if name == "SM_OakTree1":
        result.update(status="requires_material_repair")
        result["notes"].append("Additional Blender CPU view shows large near-black canopy/card regions; cause not isolated. See previews/oak-contact-sheet.png.")
    elif name == "SM_OakFallen1_SnowCover":
        result["notes"].append("Additional single Blender CPU view shows visible wood and snow geometry without the observed OakTree1 canopy defect; not whole-family acceptance.")
    if kind == "Texture2D" and re.search(r"/(sky|water|effects?|vfx)/", a["source"]["package"] + "/", re.I):
        result["notes"].append("Source runtime appearance requires a target-engine shader/effect; this is a texture source only.")
    if a.get("engine_log_warnings"):
        result["notes"].append("Native exporter warnings are retained in engine_log_warnings; inspect shading fallbacks and overlapping/degenerate bake UVs.")
    return result


def compact(catalog):
    return {"schema_version": 1, "collection": "sostylized", "asset_count": len(catalog["assets"]),
            "summary": catalog["summary"], "full_catalog": "catalog.json",
            "assets": [{k: a[k] for k in COMPACT if k in a} for a in catalog["assets"]]}


def prepare(work):
    portable, catalog, _ = completed(work)
    for a in catalog["assets"]:
        a["material_readiness"] = readiness(a)
        a["download_category"], a["content_labels"] = classify(a)
    # Retain the original generator and all existing metadata for packager resume ownership.
    write(portable / "catalog.json", catalog)
    write(portable / "compact-index.json", compact(catalog))
    return {"stage": "prepared", "assets": len(catalog["assets"]),
            "next": "Build category ZIPs from this prepared catalog before publish."}


def public_metadata(value, key=""):
    if isinstance(value, dict):
        return {k: public_metadata(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [public_metadata(v, key) for v in value]
    if isinstance(value, str):
        local = bool(re.match(r"^[A-Za-z]:[/\\]|^\\\\", value))
        local = local or (value.startswith("/") and not value.startswith(("/Game/", "/Engine/", "/Script/")))
        if local and any(x in key.lower() for x in ("path", "file", "directory", "source")):
            return "redacted-local-path/" + value.replace("\\", "/").rsplit("/", 1)[-1]
        if re.search(r"(?<![A-Za-z0-9])(?:[A-Za-z]:[/\\]|\\\\[A-Za-z])", value):
            raise ValueError("Unexpected embedded local path in published metadata field: " + key)
    return value


def download_mapping(work, catalog, tag):
    downloads = read(work / "downloads" / "downloads.json")
    if downloads.get("portable_catalog_sha256") != digest(work / "portable" / "catalog.json"):
        raise ValueError("ZIPs were not built from this exact prepared catalog")
    if downloads.get("source_archive_sha256") != catalog["source_archive_sha256"]:
        raise ValueError("Download/source archive identity mismatch")
    if downloads.get("reviewed_exclusions") or downloads.get("asset_count") != len(catalog["assets"]):
        raise ValueError("Downloads must contain the full target set without exclusions")
    by_id, mapping = {a["id"]: a for a in catalog["assets"]}, {}
    release = "https://github.com/" + REPOSITORY + "/releases/download/" + quote(tag, safe="") + "/"
    for item in downloads["files"]:
        name = item["zipname"]
        path = safe(work / "downloads", name)
        if PurePosixPath(name).name != name or not path.is_file() or path.stat().st_size != item["bytes"]:
            raise ValueError("Missing/wrong-sized category ZIP: " + name)
        if item["bytes"] >= downloads["maximum_zip_bytes_exclusive"] or item["category"] not in CATEGORIES:
            raise ValueError("Invalid ZIP category/size: " + name)
        ids, paths = item["included_ids"], item["included_paths"]
        if len(ids) != item["count"] or len(ids) != len(paths) or len(set(ids)) != len(ids):
            raise ValueError("Invalid ZIP mapping: " + name)
        prefix = item.get("entry_prefix", downloads["entry_prefix"])
        if prefix != PREFIX + "/":
            raise ValueError("Unexpected ZIP root")
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Duplicate ZIP members: " + name)
            for asset_id, relative in zip(ids, paths):
                a = by_id[asset_id]
                member = prefix + relative
                if asset_id in mapping or relative != a["path"] or classify(a)[0] != item["category"]:
                    raise ValueError("Duplicate/incorrect asset download mapping: " + asset_id)
                if archive.getinfo(member).file_size != a["bytes"]:
                    raise ValueError("ZIP member size mismatch: " + asset_id)
                mapping[asset_id] = {"zipname": name, "zip_member": member,
                                     "download_url": release + quote(name, safe=""),
                                     "url_status": "planned_release_url_not_verified_online"}
        item["download_url"] = release + quote(name, safe="")
        item["url_status"] = "planned_release_url_not_verified_online"
    if set(mapping) != set(by_id):
        raise ValueError("Downloads do not cover every catalog asset exactly once")
    downloads.update(release_tag=tag, url_status="planned_release_urls_not_verified_online")
    return downloads, mapping


def publish_previews(work, destination, catalog):
    manifest = read(work / "previews" / "preview_manifest.json")
    rendered = manifest["samples_rendered"]
    if manifest.get("errors") or {s["name"] for s in rendered} != set(KNOWN) or len(rendered) != 6:
        raise ValueError("Expected the known six successful native sample render receipts")
    by_name = {a["source"]["name"]: a for a in catalog["assets"] if a["source"]["name"] in KNOWN}
    samples = []
    for s in rendered:
        a = by_name[s["name"]]
        native = safe(work / "native", a["path"])
        if digest(native) != s["source_sha256"] or a["native_sha256"] != s["source_sha256"]:
            raise ValueError("Native preview identity mismatch: " + s["name"])
        samples.append({"id": a["id"], "name": s["name"], "native_path": a["path"],
                        "native_sha256": s["source_sha256"], "native_bytes": native.stat().st_size,
                        "portable_sha256": a["sha256"], "material_readiness": a["material_readiness"],
                        "uv_normalization": a.get("uv_normalization")})
    image = work / "previews" / "contact_sheet.png"
    receipt = {"schema_version": 1, "scope": "Six selected native GLBs before portable UV normalization; not whole-collection acceptance.",
               "image_kind": "Converted-asset Blender CPU render; not original Unreal screenshot.",
               "normalization_note": "UV references/tangent declarations may change; binary geometry and images are unchanged.",
               "renderer": {k: manifest[k] for k in ("blender", "engine", "device", "samples", "size")},
               "contact_sheet": {"path": "contact_sheet.png", "bytes": image.stat().st_size, "sha256": digest(image)},
               "full_catalog": "../catalog.json", "samples": samples}
    target = destination / "previews"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(image, target / "contact_sheet.png")
    write(target / "preview-receipt.json", receipt)


def publish(work, repo, tag):
    portable, original, inventory = completed(work)
    for a in original["assets"]:
        if a.get("material_readiness") != readiness(a):
            raise ValueError("Run prepare before building ZIPs: " + a["id"])
    downloads, mapping = download_mapping(work, original, tag)
    catalog = public_metadata(copy.deepcopy(original))
    destination = repo / COLLECTION
    for a in catalog["assets"]:
        a["download"] = mapping[a["id"]]
        a["download_category"], a["content_labels"] = classify(a)
        if a["source"]["name"] in SAMPLES:
            src = safe(portable, a["path"])
            relative = "samples/" + a["source"]["name"] + ".glb"
            if digest(src) != a["sha256"]:
                raise ValueError("Direct sample identity mismatch: " + a["id"])
            target = safe(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            a["direct_sample_url"] = RAW + COLLECTION + quote(relative, safe="/")
            a["direct_sample"] = {"path": relative, "bytes": target.stat().st_size, "sha256": digest(target),
                                  "url_status": "planned_repository_url_not_verified_online"}
    public_inventory = public_metadata(inventory)
    catalog["source_inventory_original_sha256"] = catalog["source_inventory_sha256"]
    catalog["source_inventory"] = "source-catalog.json"
    catalog["source_inventory_sha256"] = hashlib.sha256(encoded(public_inventory)).hexdigest()
    catalog["downloads"] = "downloads.json"
    catalog["release_tag"] = tag
    catalog["path_scope"] = "Asset path is inside the extracted ZIP root, not a direct repository model path. Use download.zip_member or direct_sample_url."
    publish_previews(work, destination, catalog)
    for name, value in (("catalog.json", catalog), ("asset-index.json", compact(catalog)),
                        ("source-catalog.json", public_inventory),
                        ("source-worlds.json", public_metadata(read(portable / "source-worlds.json"))),
                        ("downloads.json", public_metadata(downloads))):
        write(destination / name, value)
    categories = []
    for category in CATEGORIES:
        assets = [a for a in catalog["assets"] if a["download_category"] == category]
        filename = "indexes/" + category + ".json"
        rows, pages = [], []
        for offset in range(0, len(assets), 20):
            page = "indexes/details/" + category + "-" + str(offset // 20 + 1).zfill(2) + ".json"
            subset = assets[offset:offset + 20]
            detail = {"schema_version": 1, "category": category, "catalog": "../../catalog.json",
                      "scope": "Selected full asset records; payload paths are extracted ZIP members.", "assets": subset}
            if len(encoded(detail)) > 200000:
                raise ValueError("Detail page is too large for text clients: " + page)
            write(destination / page, detail)
            pages.append(page.removeprefix("indexes/"))
            for a in subset:
                rows.append({"id": a["id"], "name": a["source"]["name"], "path": a["path"],
                             "bytes": a["bytes"], "triangles": a.get("triangles"),
                             "material_status": a["material_readiness"]["status"],
                             "download_zip": a["download"]["zipname"],
                             "details": page.removeprefix("indexes/")})
        selection = {"schema_version": 1, "category": category, "asset_count": len(assets),
                     "full_catalog": "../catalog.json", "downloads": "../downloads.json",
                     "path_scope": catalog["path_scope"], "detail_pages": pages, "assets": rows}
        if len(encoded(selection)) > 200000:
            raise ValueError("Category selection index is too large: " + category)
        write(destination / filename, selection)
        categories.append({"category": category, "asset_count": len(assets), "index": filename})
    write(destination / "index.json", {"schema_version": 1, "collection": "sostylized", "summary": catalog["summary"],
                                       "asset_count": len(catalog["assets"]), "catalog": "catalog.json", "asset_index": "asset-index.json",
                                       "downloads": "downloads.json", "source_inventory": "source-catalog.json", "source_worlds": "source-worlds.json",
                                       "material_readiness": "MATERIAL_READINESS.md", "preview": "previews/preview-receipt.json",
                                       "release_tag": tag, "categories": categories,
                                       "publication_status": "Local metadata staged; release upload and URL verification are separate."})
    return {"stage": "published_local_metadata", "assets": len(catalog["assets"]), "categories": len(categories), "zip_files": len(downloads["files"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "publish"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--release-tag", required=True)
    args = parser.parse_args()
    if not args.release_tag.strip() or any(c in args.release_tag for c in "\r\n"):
        parser.error("release-tag must be nonempty and single-line")
    try:
        result = prepare(args.work.resolve()) if args.command == "prepare" else publish(args.work.resolve(), args.repo.resolve(), args.release_tag)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
