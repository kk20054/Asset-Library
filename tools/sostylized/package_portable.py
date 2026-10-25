"""Package native SoStylized exports without Unreal, Blender, or network access.
Usage: python package_portable.py --work EXPORT_WORKSPACE --output NEW_PORTABLE_DIR
Reruns update only files named by this tool's previous catalog; native inputs are read-only.
"""
import argparse
import base64
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import sys

GENERATOR = "sostylized/package_portable.py"
TARGETS = {"StaticMesh": {".glb"}, "Texture2D": {".png", ".exr"}, "SoundWave": {".wav"}}
IDENTITY = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]
JSON_CHUNK, BIN_CHUNK = 0x4E4F534A, 0x004E4942


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def inside(root, relative):
    relative = PurePosixPath(str(relative).replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts or ":" in str(relative):
        raise ValueError("Unsafe relative path: " + str(relative))
    path = (root / str(relative)).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("Path escapes its root: " + str(relative))
    return path


def parse_glb(raw):
    if len(raw) < 20 or struct.unpack_from("<4sII", raw) != (b"glTF", 2, len(raw)):
        raise ValueError("Invalid GLB2 header or declared length")
    chunks, cursor = [], 12
    while cursor < len(raw):
        if cursor + 8 > len(raw):
            raise ValueError("Truncated GLB chunk header")
        length, kind = struct.unpack_from("<II", raw, cursor)
        if length % 4 or cursor + 8 + length > len(raw):
            raise ValueError("Invalid GLB chunk boundary/alignment")
        chunks.append((kind, raw[cursor + 8:cursor + 8 + length]))
        cursor += 8 + length
    if not chunks or chunks[0][0] != JSON_CHUNK or sum(k == JSON_CHUNK for k, _ in chunks) != 1:
        raise ValueError("Expected exactly one initial JSON chunk")
    if sum(k == BIN_CHUNK for k, _ in chunks) > 1:
        raise ValueError("Multiple BIN chunks are unsupported")
    doc = json.loads(chunks[0][1])
    for item in doc.get("buffers", []) + doc.get("images", []):
        if "uri" in item and not item["uri"].startswith("data:"):
            raise ValueError("External dependency in self-contained GLB: " + item["uri"])
    return doc, chunks


def texture_infos(value):
    result = []
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, dict) and key.lower().endswith("texture") and "index" in child:
                result.append(child)
            else:
                result.extend(texture_infos(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(texture_infos(child))
    return result


def normalize_uv(raw):
    original, chunks = parse_glb(raw)
    doc, channels, details = copy.deepcopy(original), [], []
    for index, material in enumerate(doc.get("materials", [])):
        infos = texture_infos(material)
        uv = {i.get("extensions", {}).get("KHR_texture_transform", {}).get("texCoord", i.get("texCoord", 0)) for i in infos}
        if any(not isinstance(n, int) or n < 0 for n in uv):
            raise ValueError("Invalid material texCoord")
        channels.append(uv)
        details.append({"material": index, "name": material.get("name"), "source_uvs": sorted(uv)})
    mixed = [i for i, uv in enumerate(channels) if len(uv) > 1]
    if mixed:
        return raw, original, {"status": "preserved_mixed_uv", "materials": details, "mixed_materials": mixed}
    changed, tangent_removals = False, 0
    for mesh in doc.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            material = primitive.get("material")
            if material is None or not channels[material]:
                continue
            uv = next(iter(channels[material]))
            attrs = primitive["attributes"]
            key = "TEXCOORD_" + str(uv)
            if key not in attrs:
                raise ValueError("Material references absent " + key)
            if uv != 0:
                attrs["TEXCOORD_0"] = attrs[key]
                for old in list(attrs):
                    if old.startswith("TEXCOORD_") and old != "TEXCOORD_0":
                        del attrs[old]
                if "TANGENT" in attrs:
                    del attrs["TANGENT"]
                    tangent_removals += 1
                changed = True
    for material in doc.get("materials", []):
        for info in texture_infos(material):
            transform = info.get("extensions", {}).get("KHR_texture_transform", {})
            if info.get("texCoord", 0) != 0 or transform.get("texCoord", 0) != 0:
                info["texCoord"] = 0
                if "texCoord" in transform:
                    transform["texCoord"] = 0
                changed = True
    report = {"status": "normalized_uv0" if changed else "already_uv0", "materials": details,
              "removed_stale_tangents": tangent_removals, "binary_chunks_unchanged": True}
    if not changed:
        return raw, doc, report
    encoded = json.dumps(doc, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    encoded += b" " * (-len(encoded) % 4)
    tail = b"".join(struct.pack("<II", len(data), kind) + data for kind, data in chunks[1:])
    output = struct.pack("<4sIIII", b"glTF", 2, 20 + len(encoded) + len(tail), len(encoded), JSON_CHUNK) + encoded + tail
    if parse_glb(output)[1][1:] != chunks[1:]:
        raise ValueError("Unexpected binary chunk modification")
    return output, doc, report


def accessor_values(doc, chunks, index):
    accessor = doc["accessors"][index]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[accessor["type"]]
    formats = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
    fmt = "<" + formats[accessor["componentType"]] * width
    size = struct.calcsize(fmt)
    bins = [data for kind, data in chunks if kind == BIN_CHUNK]
    def view_data(view_index):
        view = doc["bufferViews"][view_index]
        buffer = doc["buffers"][view["buffer"]]
        if "uri" in buffer:
            data = base64.b64decode(buffer["uri"].split(",", 1)[1], validate=True)
        else:
            if view["buffer"] != 0 or not bins:
                raise ValueError("Missing embedded buffer")
            data = bins[0]
        start = view.get("byteOffset", 0)
        if start + view["byteLength"] > len(data):
            raise ValueError("Buffer view exceeds buffer")
        return data[start:start + view["byteLength"]], view
    values = [(0,) * width for _ in range(accessor["count"])]
    if "bufferView" in accessor:
        data, view = view_data(accessor["bufferView"])
        stride = view.get("byteStride", size)
        for i in range(accessor["count"]):
            values[i] = struct.unpack_from(fmt, data, accessor.get("byteOffset", 0) + i * stride)
    if "sparse" in accessor:
        sparse = accessor["sparse"]
        indices, _ = view_data(sparse["indices"]["bufferView"])
        data, _ = view_data(sparse["values"]["bufferView"])
        index_fmt = "<" + formats[sparse["indices"]["componentType"]]
        for i in range(sparse["count"]):
            destination = struct.unpack_from(index_fmt, indices, sparse["indices"].get("byteOffset", 0) + i * struct.calcsize(index_fmt))[0]
            values[destination] = struct.unpack_from(fmt, data, sparse["values"].get("byteOffset", 0) + i * size)
    if accessor.get("normalized") and accessor["componentType"] != 5126:
        bits = size // width * 8
        signed = accessor["componentType"] in (5120, 5122)
        maximum = (1 << (bits - int(signed))) - 1
        values = [tuple(max(-1., x / maximum) for x in row) for row in values]
    return values


def multiply(a, b):
    return [sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4)) for col in range(4) for row in range(4)]


def local_matrix(node):
    if "matrix" in node:
        return node["matrix"]
    x, y, z, w = node.get("rotation", [0., 0., 0., 1.])
    sx, sy, sz = node.get("scale", [1., 1., 1.])
    tx, ty, tz = node.get("translation", [0., 0., 0.])
    return [(1-2*(y*y+z*z))*sx, 2*(x*y+z*w)*sx, 2*(x*z-y*w)*sx, 0.,
            2*(x*y-z*w)*sy, (1-2*(x*x+z*z))*sy, 2*(y*z+x*w)*sy, 0.,
            2*(x*z+y*w)*sz, 2*(y*z-x*w)*sz, (1-2*(x*x+y*y))*sz, 0., tx, ty, tz, 1.]


def glb_statistics(doc, raw):
    _, chunks = parse_glb(raw)
    mesh_triangles, points, warnings = [], {}, []
    for mesh in doc.get("meshes", []):
        triangles = 0
        for primitive in mesh.get("primitives", []):
            position = primitive["attributes"]["POSITION"]
            points.setdefault(position, None)
            count = doc["accessors"][primitive.get("indices", position)]["count"]
            mode = primitive.get("mode", 4)
            triangles += count // 3 if mode == 4 else max(0, count - 2) if mode in (5, 6) else 0
            if mode not in (4, 5, 6):
                warnings.append("Nontriangle primitive mode " + str(mode))
        mesh_triangles.append(triangles)
    for index in points:
        points[index] = accessor_values(doc, chunks, index)
    lo, hi, scene_triangles = [math.inf] * 3, [-math.inf] * 3, 0
    nodes = doc.get("nodes", [])
    def visit(index, parent, ancestors):
        nonlocal scene_triangles
        if index in ancestors:
            raise ValueError("Cyclic scene hierarchy")
        node = nodes[index]
        world = multiply(parent, local_matrix(node))
        if "mesh" in node:
            scene_triangles += mesh_triangles[node["mesh"]]
            for primitive in doc["meshes"][node["mesh"]]["primitives"]:
                for point in points[primitive["attributes"]["POSITION"]]:
                    for axis in range(3):
                        value = sum(world[k * 4 + axis] * point[k] for k in range(3)) + world[12 + axis]
                        if not math.isfinite(value):
                            raise ValueError("Nonfinite POSITION/world transform")
                        lo[axis], hi[axis] = min(lo[axis], value), max(hi[axis], value)
        for child in node.get("children", []):
            visit(child, world, ancestors | {index})
    scenes = doc.get("scenes", [])
    roots = scenes[doc.get("scene", 0)].get("nodes", []) if scenes else []
    for root in roots:
        visit(root, IDENTITY, set())
    if any("skin" in n or "weights" in n for n in nodes) or any("weights" in m for m in doc.get("meshes", [])):
        warnings.append("Bounds use unskinned base POSITION data; skin/morph deformation is not evaluated")
    return {"triangles": sum(mesh_triangles), "scene_triangles": scene_triangles,
            "mesh_count": len(mesh_triangles), "material_count": len(doc.get("materials", [])),
            "image_count": len(doc.get("images", [])), "bounds": {"min": lo, "max": hi} if all(math.isfinite(x) for x in lo + hi) else None,
            "bounds_scope": "Default scene base POSITION vertices with complete node world matrices; metres",
            "required_extensions": doc.get("extensionsRequired", []), "extensions_used": doc.get("extensionsUsed", []), "warnings": sorted(set(warnings))}


def source_key(source):
    return source.get("path") or source["package"]


def source_id(source, duplicate_names):
    name = source["name"]
    suffix = "_" + source["package"].removeprefix("/Game/SoStylized/").rsplit("/", 1)[0].replace("/", "_") if name in duplicate_names else ""
    return "SOSTYLIZED_" + re.sub(r"[^A-Za-z0-9_]+", "_", name + suffix)


def engine_warnings(work):
    result = {}
    marker = "SO_STYLIZED_EXPORT_PROGRESS "
    for name in ("pilot_stdout.log", "export_initial_stdout.log", "export_stdout.log"):
        path = work / name
        if not path.is_file():
            continue
        pending = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "LogGLTFExporter: Warning:" in line:
                pending.append(line.split("LogGLTFExporter: Warning:", 1)[1].strip())
            if marker in line:
                info = json.loads(line.split(marker, 1)[1])
                result.setdefault(info["current"], []).extend(pending)
                pending = []
    return {key: list(dict.fromkeys(values)) for key, values in result.items() if values}


def package(work, output):
    work, output = work.resolve(), output.resolve()
    native = work / "native"
    if output == work or work.is_relative_to(output) or any(output.is_relative_to(p) or p.is_relative_to(output) for p in [native, work / "project"]):
        raise ValueError("Output must be separate from native/source trees and their parents")
    inventory = read_json(work / "native_catalog.json")
    previous = read_json(output / "catalog.json") if (output / "catalog.json").exists() else {}
    if previous and previous.get("generator") != GENERATOR:
        raise ValueError("Refusing to overwrite a catalog owned by another tool")
    if output.exists() and any(output.iterdir()) and not previous:
        raise ValueError("Output must be new/empty or an earlier output of this tool")
    records = {}
    for line in (work / "export_records.jsonl").read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            record = json.loads(line)
            records[source_key(record["source"])] = record
    sources = {source_key(s): s for s in inventory["assets"] if s["class"] in TARGETS}
    sources.update({k: r["source"] for k, r in records.items() if r["source"]["class"] in TARGETS})
    duplicate_names = {name for name, count in Counter(s["name"] for s in sources.values()).items() if count > 1}
    output.mkdir(parents=True, exist_ok=True)
    log_warnings = engine_warnings(work)
    assets, produced, ids = [], set(), set()
    for key, source in sorted(sources.items()):
        entry = {"id": source_id(source, duplicate_names), "source": source, "category": source["package"].removeprefix("/Game/SoStylized/").rsplit("/", 1)[0], "status": "pending", "warnings": []}
        if entry["id"] in ids:
            raise ValueError("Stable ID collision: " + entry["id"])
        ids.add(entry["id"])
        source_file = inside(work / "project" / "Content", source["package"].removeprefix("/Game/") + ".uasset")
        entry["source_uasset_sha256"] = digest(source_file.read_bytes()) if source_file.is_file() else None
        if source["package"] in log_warnings:
            entry["engine_log_warnings"] = log_warnings[source["package"]]
            entry["engine_log_warning_scope"] = "GLTFExporter warnings before this asset completion in native log"
        record = records.get(key)
        if record:
            entry.update({k: record[k] for k in ("lod_count", "exported_lods", "export_messages", "material_slots", "engine",
                    "srgb", "compression_settings", "flip_green_channel", "channel_mapping", "format_attempts") if k in record})
            entry["native_status"] = record.get("status")
            entry["status"] = "failed"
            try:
                if record.get("status") != "exported":
                    raise ValueError("Native export did not succeed")
                if record.get("export_messages", {}).get("errors"):
                    raise ValueError("Native receipt contains export errors")
                relative = record["relative_path"].replace("\\", "/")
                if relative in produced:
                    raise ValueError("Duplicate output path: " + relative)
                src, dst = inside(native, relative), inside(output, relative)
                if src.suffix.lower() not in TARGETS[source["class"]]:
                    raise ValueError("Unexpected file type for source class")
                raw = src.read_bytes()
                if not raw:
                    raise ValueError("Empty native export")
                if record.get("bytes", len(raw)) != len(raw):
                    raise ValueError("Native receipt byte length mismatch")
                entry["native_sha256"] = digest(raw)
                entry["native_bytes"] = len(raw)
                if src.suffix.lower() == ".glb":
                    if record.get("exported_lods") != [0]:
                        raise ValueError("Static portable policy requires exactly exported_lods=[0]")
                    raw, doc, entry["uv_normalization"] = normalize_uv(raw)
                    entry.update(glb_statistics(doc, raw))
                    entry["self_contained"] = True
                    if entry["uv_normalization"]["status"] == "preserved_mixed_uv":
                        entry["warnings"].append("Mixed material UV sets retained byte-for-byte; no UV0 remapping performed")
                    if not doc.get("materials") or not doc.get("images"):
                        entry["warnings"].append("No material or embedded image; inspect for intentionally untextured source or missing bake")
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(raw)
                entry.update(path=relative, bytes=len(raw), sha256=digest(raw), status="packaged")
                produced.add(relative)
            except (ValueError, KeyError, IndexError, TypeError, OSError, struct.error) as error:
                entry["error"] = str(error)
        assets.append(entry)
    for old in previous.get("assets", []):
        if old.get("status") == "packaged" and old.get("path") not in produced:
            stale = inside(output, old["path"])
            if stale.is_file():
                stale.unlink()
    counts = dict(Counter(asset["status"] for asset in assets))
    catalog = {
        "schema_version": 1, "generator": GENERATOR, "collection": "sostylized",
        "units": "metres", "up_axis": "+Y", "handedness": "right-handed",
        "source_inventory": "native_catalog.json",
        "source_inventory_sha256": digest((work / "native_catalog.json").read_bytes()),
        "source_archive_sha256": "59425c4db32a6f4c164829cb5c6cbe7e8e2714eb6da517eb52f4bdfa9ba32333",
        "source_world_index": "source-worlds.json",
        "source_class_counts": inventory.get("class_counts", dict(Counter(s["class"] for s in inventory["assets"]))),
        "summary": counts,
        "lod_policy": "Native LOD0 only; exported_lods records actual output. No coincident LOD stacking.",
        "rights": "Original third-party ownership and license terms remain applicable; conversion grants no new license.",
        "limits": [
            "Static material bakes do not transfer Unreal wind, weather, water shaders, Blueprint/Niagara or Landscape behavior.",
            "Source Worlds are indexed only; no authored layouts are claimed converted.",
            "Six source animations and one skeletal mesh belong to DemoPawn, outside this static environment conversion.",
            "NS_WindLines_v2_Local.uasset is absent from the native registry and is not a StaticMesh."],
        "assets": assets}
    shutil.copyfile(work / "native_catalog.json", output / "native_catalog.json")
    write_json(output / "source-worlds.json", {"scope": "Source World identity only; layouts not converted", "worlds": [s for s in inventory["assets"] if s["class"] == "World"]})
    write_json(output / "catalog.json", catalog)
    fields = ("id", "path", "category", "bytes", "sha256", "triangles", "bounds", "exported_lods", "required_extensions")
    write_json(output / "compact-index.json", {"schema_version": 1, "collection": "sostylized", "asset_count": counts.get("packaged", 0), "summary": counts, "assets": [{k: a[k] for k in fields if k in a} for a in assets if a["status"] == "packaged"]})
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    counts = package(args.work, args.output)
    print(json.dumps({"output": str(args.output), "summary": counts}))
    return int(bool(counts.get("failed") or counts.get("pending")))


if __name__ == "__main__":
    sys.exit(main())
