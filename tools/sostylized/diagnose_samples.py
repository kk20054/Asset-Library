"""Read-only GLB material diagnosis and one old-LOD0 Cycles CPU comparison.
Run inside Blender: --background --python-exit-code 1 --threads 4 --python
  diagnose_samples.py -- --old OLD.glb --new NEW.glb --cloud CLOUD.glb --output PREVIEWS
Only embedded PNG copies, one CPU PNG and diagnosis.json are written to output.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import struct
import sys
from types import SimpleNamespace

import bpy
import numpy as np


def read_glb(path):
    raw = path.read_bytes()
    if struct.unpack_from("<4sII", raw) != (b"glTF", 2, len(raw)):
        raise ValueError("Invalid GLB header")
    chunks, offset = {}, 12
    while offset < len(raw):
        length, kind = struct.unpack_from("<II", raw, offset)
        chunks[kind] = raw[offset + 8:offset + 8 + length]
        offset += 8 + length
    return raw, json.loads(chunks[0x4E4F534A]), chunks[0x004E4942]


def accessor(doc, binary, index):
    a = doc["accessors"][index]
    if "sparse" in a:
        raise ValueError("Sparse accessor unsupported by diagnostic")
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
    dtype = np.dtype({5120:"i1", 5121:"u1", 5122:"<i2", 5123:"<u2", 5125:"<u4", 5126:"<f4"}[a["componentType"]])
    v = doc["bufferViews"][a["bufferView"]]
    offset = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = v.get("byteStride", width * dtype.itemsize)
    result = np.ndarray((a["count"], width), dtype, buffer=binary,
                        offset=offset, strides=(stride, dtype.itemsize)).astype(np.float64)
    if a.get("normalized") and dtype.kind != "f":
        maximum = np.iinfo(dtype).max
        result = np.maximum(result / maximum, -1)
    return result


def texture_refs(material):
    pbr = material.get("pbrMetallicRoughness", {})
    refs = {"baseColor": pbr.get("baseColorTexture"),
            "metallicRoughness": pbr.get("metallicRoughnessTexture"),
            "normal": material.get("normalTexture"), "emissive": material.get("emissiveTexture")}
    return {k: v for k, v in refs.items() if v}


def image_data(doc, binary, texture, output, filename):
    texture_doc = doc["textures"][texture["index"]]
    image = doc["images"][texture_doc["source"]]
    view = doc["bufferViews"][image["bufferView"]]
    raw = binary[view.get("byteOffset", 0):view.get("byteOffset", 0) + view["byteLength"]]
    if image.get("mimeType") != "image/png":
        raise ValueError("Expected embedded PNG")
    path = output / filename
    path.write_bytes(raw)
    loaded = bpy.data.images.load(str(path), check_existing=False)
    loaded.colorspace_settings.name = "Non-Color"
    width, height = loaded.size
    if width * height > 4096 * 4096:
        raise ValueError("Diagnostic image bound exceeded")
    pixels = np.empty(width * height * 4, np.float32)
    loaded.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, 4)[::-1].copy()
    bpy.data.images.remove(loaded)
    black = np.max(pixels[:, :, :3], axis=2) <= 1 / 255
    stats = {"png": filename, "sha256": hashlib.sha256(raw).hexdigest(),
             "size": [width, height], "min_rgba": pixels.min(axis=(0, 1)).tolist(),
             "max_rgba": pixels.max(axis=(0, 1)).tolist(),
             "mean_rgba": pixels.mean(axis=(0, 1)).tolist(),
             "black_rgb_fraction": float(black.mean()),
             "zero_alpha_fraction": float((pixels[:, :, 3] <= 1 / 255).mean()),
             "nonzero_alpha_fraction": float((pixels[:, :, 3] > 1 / 255).mean()),
             "pixel_scope": "Embedded PNG decoded as Non-Color; top-left origin"}
    return pixels, stats, texture_doc


def sample_base(doc, binary, primitive, info, pixels, texdoc):
    transform = info.get("extensions", {}).get("KHR_texture_transform", {})
    uvset = transform.get("texCoord", info.get("texCoord", 0))
    key = "TEXCOORD_" + str(uvset)
    attrs = primitive["attributes"]
    uv = accessor(doc, binary, attrs[key])
    xy = uv * np.array(transform.get("scale", [1, 1]))
    angle = transform.get("rotation", 0)
    rotation = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    xy = xy @ rotation.T + np.array(transform.get("offset", [0, 0]))
    sampler = doc.get("samplers", [])[texdoc["sampler"]] if "sampler" in texdoc else {}
    wrapped = xy.copy()
    for axis, name in enumerate(("wrapS", "wrapT")):
        mode = sampler.get(name, 10497)
        wrapped[:, axis] = np.clip(xy[:, axis], 0, 1) if mode == 33071 else 1 - np.abs((xy[:, axis] % 2) - 1) if mode == 33648 else xy[:, axis] % 1
    height, width = pixels.shape[:2]
    sampled = pixels[(wrapped[:, 1] * (height - 1)).astype(int),
                     (wrapped[:, 0] * (width - 1)).astype(int)]
    positions = accessor(doc, binary, attrs["POSITION"])
    y = positions[:, 1]
    split = (y.min() + y.max()) / 2
    bands = {}
    for label, mask in (("lower_half_y", y < split), ("upper_half_y", y >= split)):
        selected = sampled[mask]
        bands[label] = {"vertex_count": int(mask.sum()),
                        "black_rgb_fraction": float((selected[:, :3].max(axis=1) <= 1 / 255).mean()),
                        "mean_rgba": selected.mean(axis=0).tolist()}
    return {"uv_key": key, "raw_uv_min": uv.min(axis=0).tolist(),
            "raw_uv_max": uv.max(axis=0).tolist(), "transform": transform,
            "transformed_uv_min": xy.min(axis=0).tolist(), "transformed_uv_max": xy.max(axis=0).tolist(),
            "outside_unit_fraction": float(((xy < -1e-6) | (xy > 1 + 1e-6)).any(axis=1).mean()),
            "uv_tolerance": 1e-6,
            "height_split_gltf_y": float(split), "bands": bands,
            "sampling_scope": "Nearest texel at source vertices, not area-weighted surface coverage"}


def inspect(path, ident, output):
    raw, doc, binary = read_glb(path)
    chosen = 0
    primitives = doc["meshes"][chosen]["primitives"]
    result = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
              "mesh_count": len(doc["meshes"]), "inspected_mesh_index": chosen,
              "inspected_mesh_name": doc["meshes"][chosen].get("name"), "primitives": []}
    for index, primitive in enumerate(primitives):
        attrs = primitive["attributes"]
        material = doc["materials"][primitive["material"]]
        item = {"attributes": list(attrs), "material": material, "textures": {}}
        normals = accessor(doc, binary, attrs["NORMAL"])
        lengths = np.linalg.norm(normals, axis=1)
        item["normals"] = {"finite": bool(np.isfinite(normals).all()),
                           "length_min": float(lengths.min()), "length_max": float(lengths.max())}
        item["vertex_color_present"] = "COLOR_0" in attrs
        if "COLOR_0" in attrs:
            color = accessor(doc, binary, attrs["COLOR_0"])
            item["vertex_color_range"] = [color.min(axis=0).tolist(), color.max(axis=0).tolist()]
        for name, info in texture_refs(material).items():
            pixels, stats, texture = image_data(doc, binary, info, output, "diagnosis_" + ident + "_" + str(index) + "_" + name + ".png")
            item["textures"][name] = stats
            if name == "baseColor":
                item["basecolor_uv_sampling"] = sample_base(doc, binary, primitive, info, pixels, texture)
        result["primitives"].append(item)
    return result


def text_evidence(root):
    result = {}
    for filename in ("M_Rock.t3d", "MI_RockClassic.t3d"):
        path = root / "geography" / filename
        raw = path.read_bytes()
        text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
        result[str(path)] = [{"line": i + 1, "text": line.strip()} for i, line in enumerate(text.splitlines())
                             if re.search(r"bottom edge|MF_VTBlend|UseVTBlend|VT Blend -|RVT_Landscape", line)]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("old", "new", "cloud", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    args.output.mkdir(parents=True, exist_ok=True)
    paths = {name: getattr(args, name).resolve() for name in ("old", "new", "cloud")}
    for path in paths.values():
        if args.output.resolve() in path.parents:
            raise ValueError("Output must not contain the source GLBs")
    diagnosis = {"scope": "Three existing GLBs and source evidence only; not whole-package acceptance",
                 "models": {name: inspect(path, name, args.output) for name, path in paths.items()}}
    oldbase = diagnosis["models"]["old"]["primitives"][0]["textures"]["baseColor"]
    newbase = diagnosis["models"]["new"]["primitives"][0]["textures"]["baseColor"]
    diagnosis["comparison"] = {"old_lod0_basecolor_png_byte_identical_to_new": oldbase["sha256"] == newbase["sha256"]}
    reference_root = Path(r"D:/凡人修仙_工具验证/ClaudeFlight_20261025/asset-audit/unreal-export")
    diagnosis["source_graph_evidence"] = text_evidence(reference_root)
    source_root = paths["new"].parents[5] / "project" / "Content" / "SoStylized"
    cloud_sources = [source_root / "Environment/Sky/Materials/M_IndividualCloud.uasset",
                     source_root / "Environment/Sky/BP_IndividualCloud.uasset"]
    diagnosis["cloud_source_binary_strings"] = {}
    for path in cloud_sources:
        if path.is_file():
            strings = re.findall(rb"[ -~]{5,}", path.read_bytes())
            chosen = sorted(set(s.decode("ascii") for s in strings if re.search(rb"CameraDepthFade|MaterialExpressionDepthFade|SetScalarParameterValue|CreateDynamicMaterialInstance|Opacity|Camera Fade|Intersect Fade|MPC_GlobalEnvironment|fade when|Fade when|Fade as", s)))
            diagnosis["cloud_source_binary_strings"][str(path)] = chosen
    module_path = Path(__file__).with_name("render_samples.py")
    spec = importlib.util.spec_from_file_location("render_samples", module_path)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    renderer.clean_scene()
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(paths["old"]))
    imported = set(bpy.data.objects) - before
    hidden = []
    for obj in imported:
        parent = obj
        while parent:
            if "_LOD1" in parent.name or "_LOD2" in parent.name:
                obj.hide_render = True
                hidden.append(obj.name)
                break
            parent = parent.parent
    corners, bounds = renderer.normalize_preview(imported)
    scene = renderer.setup_scene(SimpleNamespace(samples=16, threads=4, size=640), corners,
                                 "OLD SM_CliffClassic1 | LOD0 only | CPU")
    destination = args.output / "diagnosis_old_cliff_lod0.png"
    scene.render.filepath = str(destination)
    bpy.ops.render.render(write_still=True)
    diagnosis["old_comparison_render"] = {"png": destination.name, "hidden_lod_objects": hidden,
                                           "device": "CPU", "threads": 4, "samples": 16, "bounds": bounds}
    diagnosis["sources_unchanged"] = {name: hashlib.sha256(path.read_bytes()).hexdigest() == diagnosis["models"][name]["sha256"] for name, path in paths.items()}
    (args.output / "diagnosis.json").write_text(json.dumps(diagnosis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DIAGNOSIS_COMPLETE " + str(args.output / "diagnosis.json"), flush=True)


if __name__ == "__main__":
    main()
