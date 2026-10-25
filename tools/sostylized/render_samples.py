"""Render read-only GLB samples with Blender Cycles CPU (no source re-export).
Usage: blender --background --threads 4 --python render_samples.py -- \
  --models A.glb B.glb --output D:/asset-work/previews
Single oblique view per GLB plus contact_sheet.png and preview_manifest.json.
Only preview transforms are normalized. Imported PBR/cutout nodes are untouched.
Method reference: ClaudeFlight asset-audit/unreal-export/render_final_cpu.py.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, choices=(8, 16, 32), default=16)
    parser.add_argument("--threads", type=int, choices=(4, 8), default=4)
    parser.add_argument("--size", type=int, default=640)
    parser.add_argument("--columns", type=int, default=3)
    parser.add_argument("--max-models", type=int, default=24)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if not 256 <= args.size <= 1024 or not 1 <= args.columns <= 8:
        parser.error("--size must be 256..1024 and --columns 1..8")
    if not 1 <= len(args.models) <= args.max_models <= 64:
        parser.error("Preview batch exceeds --max-models (allowed range 1..64)")
    args.models = [p.resolve() for p in args.models]
    args.output = args.output.resolve()
    for model in args.models:
        if model.suffix.lower() != ".glb":
            parser.error("Only GLB inputs are supported: " + str(model))
        if model == args.output or args.output in model.parents:
            parser.error("Output must not contain source GLBs")
    return args


def source_info(path):
    raw = path.read_bytes()
    if len(raw) < 20 or struct.unpack_from("<4sII", raw) != (b"glTF", 2, len(raw)):
        raise ValueError("Invalid GLB2 header")
    length, kind = struct.unpack_from("<II", raw, 12)
    if kind != 0x4E4F534A or length + 20 > len(raw):
        raise ValueError("Invalid GLB JSON chunk")
    doc = json.loads(raw[20:20 + length])
    materials = doc.get("materials", [])
    return {
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw), "source_meshes": len(doc.get("meshes", [])),
        "source_materials": [{"name": m.get("name", ""),
                              "alpha_mode": m.get("alphaMode", "OPAQUE"),
                              "double_sided": m.get("doubleSided", False)} for m in materials],
        "source_images": len(doc.get("images", [])),
        "extensions_required": doc.get("extensionsRequired", []),
    }


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
                       bpy.data.cameras, bpy.data.lights):
        for item in list(collection):
            if item.users == 0:
                collection.remove(item)


def mesh_corners(objects):
    return [o.matrix_world @ Vector(corner) for o in objects if o.type == "MESH"
            and not o.hide_render for corner in o.bound_box]


def normalize_preview(imported):
    bpy.context.view_layer.update()
    corners = mesh_corners(imported)
    if not corners:
        raise ValueError("Imported GLB has no renderable mesh")
    lo = Vector(tuple(min(c[i] for c in corners) for i in range(3)))
    hi = Vector(tuple(max(c[i] for c in corners) for i in range(3)))
    extent = hi - lo
    if not all(math.isfinite(v) for v in (*lo, *hi)) or max(extent) < 1e-8:
        raise ValueError("Nonfinite or degenerate imported bounds")
    scale = 3.2 / max(extent)
    offset = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
    transform = Matrix.Scale(scale, 4) @ Matrix.Translation(offset)
    roots = [o for o in imported if o.parent not in imported]
    for root in roots:
        root.matrix_world = transform @ root.matrix_world
    bpy.context.view_layer.update()
    return mesh_corners(imported), {
        "source_blender_bounds": {"min": list(lo), "max": list(hi)},
        "preview_uniform_scale": scale, "source_transform_saved": False,
    }


def light(location, energy, size):
    bpy.ops.object.light_add(type="AREA", location=location)
    lamp = bpy.context.object
    lamp.data.energy, lamp.data.shape, lamp.data.size = energy, "DISK", size
    lamp.rotation_euler = (Vector((0, 0, 1)) - lamp.location).to_track_quat("-Z", "Y").to_euler()


def setup_scene(args, corners, label):
    lo = Vector(tuple(min(c[i] for c in corners) for i in range(3)))
    hi = Vector(tuple(max(c[i] for c in corners) for i in range(3)))
    target = (lo + hi) / 2
    bpy.ops.object.camera_add(location=target + Vector((5.5, -8, 5.0)))
    camera = bpy.context.object
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    bpy.context.view_layer.update()
    inv = camera.matrix_world.inverted()
    projected = [inv @ point for point in corners]
    width = max(p.x for p in projected) - min(p.x for p in projected)
    height = max(p.y for p in projected) - min(p.y for p in projected)
    camera.data.ortho_scale = max(width, height, .1) * 1.28
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.025))
    floor = bpy.context.object
    material = bpy.data.materials.new("Preview neutral floor")
    material.diffuse_color = (.32, .35, .38, 1)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    output = material.node_tree.nodes.new("ShaderNodeOutputMaterial")
    material.node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = (.32, .35, .38, 1)
    bsdf.inputs["Roughness"].default_value = .85
    floor.data.materials.append(material)
    light((-3.5, -4.5, 7), 650, 5)
    light((4, 1, 5), 350, 4)
    scene = bpy.context.scene
    scene.camera = camera
    scene.world.use_nodes = True
    world_nodes = scene.world.node_tree.nodes
    world_nodes.clear()
    background = world_nodes.new("ShaderNodeBackground")
    world_output = world_nodes.new("ShaderNodeOutputWorld")
    scene.world.node_tree.links.new(background.outputs["Background"], world_output.inputs["Surface"])
    background.inputs["Color"].default_value = (.4, .43, .48, 1)
    background.inputs["Strength"].default_value = .65
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = args.threads
    scene.render.resolution_x = scene.render.resolution_y = args.size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast" if "Medium High Contrast" in [i.name for i in scene.view_settings.bl_rna.properties["look"].enum_items] else "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.film_transparent = False
    scene.render.use_stamp = True
    for key in ("date", "time", "render_time", "frame", "frame_range", "memory",
                "hostname", "camera", "lens", "scene", "marker", "filename", "sequencer_strip"):
        attr = "use_stamp_" + key
        if hasattr(scene.render, attr):
            setattr(scene.render, attr, False)
    scene.render.use_stamp_note = True
    scene.render.stamp_note_text = label
    scene.render.stamp_font_size = 13
    scene.render.stamp_foreground = (.96, .96, .96, 1)
    scene.render.stamp_background = (.025, .03, .04, .85)
    return scene


def contact_sheet(paths, output, columns, size):
    columns = min(columns, len(paths))
    rows = math.ceil(len(paths) / columns)
    gap = 8
    width, height = columns * (size + gap) + gap, rows * (size + gap) + gap
    pixels = np.full((height, width, 4), (.07, .08, .09, 1), dtype=np.float32)
    for index, path in enumerate(paths):
        source = bpy.data.images.load(str(path), check_existing=False)
        data = np.empty(size * size * 4, dtype=np.float32)
        source.pixels.foreach_get(data)
        x = gap + index % columns * (size + gap)
        y = height - gap - (index // columns + 1) * size - index // columns * gap
        pixels[y:y + size, x:x + size] = data.reshape(size, size, 4)
        bpy.data.images.remove(source)
    sheet = bpy.data.images.new("CPU sample contact sheet", width, height, alpha=True)
    sheet.colorspace_settings.name = "sRGB"
    sheet.pixels.foreach_set(pixels.ravel())
    sheet.filepath_raw = str(output)
    sheet.file_format = "PNG"
    sheet.save()
    bpy.data.images.remove(sheet)


def main():
    args = arguments()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {"generator": "sostylized/render_samples.py", "blender": bpy.app.version_string,
                "engine": "CYCLES", "device": "CPU", "threads": args.threads,
                "samples": args.samples, "size": args.size,
                "scope": "Selected static GLB meshes/materials only; no source editing or engine behavior validation",
                "material_policy": "Original glTF importer PBR, alpha mode and textures retained without node edits",
                "samples_rendered": [], "errors": []}
    renders = []
    for path in args.models:
        started = time.monotonic()
        entry = {"source": str(path), "name": path.stem}
        try:
            entry.update(source_info(path))
            clean_scene()
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=str(path))
            imported = set(bpy.data.objects) - before
            corners, bounds = normalize_preview(imported)
            entry.update(bounds)
            static_only = any(token in path.as_posix().lower() for token in ("/sky/", "/water/", "cloud"))
            entry["static_material_only"] = static_only
            label = path.stem + (" | static mesh/material only" if static_only else " | static GLB preview")
            scene = setup_scene(args, corners, label)
            suffix = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:8]
            destination = args.output / (path.stem + "_" + suffix + ".png")
            scene.render.filepath = str(destination)
            bpy.ops.render.render(write_still=True)
            entry["source_unchanged"] = hashlib.sha256(path.read_bytes()).hexdigest() == entry["source_sha256"]
            if not entry["source_unchanged"]:
                raise RuntimeError("Source changed during read-only preview")
            entry.update(png=destination.name, seconds=round(time.monotonic() - started, 2))
            renders.append(destination)
            manifest["samples_rendered"].append(entry)
            print("PREVIEW_OK " + json.dumps(entry, ensure_ascii=False), flush=True)
        except Exception as error:
            entry["error"] = type(error).__name__ + ": " + str(error)
            manifest["errors"].append(entry)
            print("PREVIEW_ERROR " + json.dumps(entry, ensure_ascii=False), flush=True)
    if renders:
        sheet = args.output / "contact_sheet.png"
        contact_sheet(renders, sheet, args.columns, args.size)
        manifest["contact_sheet"] = sheet.name
    (args.output / "preview_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if manifest["errors"]:
        raise RuntimeError(str(len(manifest["errors"])) + " GLB preview(s) failed; see preview_manifest.json")


if __name__ == "__main__":
    main()
