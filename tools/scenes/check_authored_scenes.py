"""Independently check authored glTF hierarchy against original Unity evidence.

Run after scene assembly:
  python check_authored_scenes.py --repo <repository>
  python check_authored_scenes.py --scene <layout.json> <scene.gltf>

Only the validation report is written. Source files and assembled scenes are read-only.
"""
import argparse
import datetime
import json
import math
from pathlib import Path

IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def multiply(a, b):
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4))
            for r in range(4) for c in range(4)]


def from_column_major(values):
    if len(values) != 16 or not all(math.isfinite(v) for v in values):
        raise ValueError("Invalid glTF matrix")
    return [values[c * 4 + r] for r in range(4) for c in range(4)]


def inverse4(matrix):
    augmented = [[float(matrix[r*4+c]) for c in range(4)] +
                 [float(r == c) for c in range(4)] for r in range(4)]
    for column in range(4):
        pivot = max(range(column, 4), key=lambda r: abs(augmented[r][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("Singular coordinate conversion matrix")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        factor = augmented[column][column]
        augmented[column] = [v / factor for v in augmented[column]]
        for row in range(4):
            if row != column:
                factor = augmented[row][column]
                augmented[row] = [a - factor*b for a, b in zip(augmented[row], augmented[column])]
    return [augmented[r][c+4] for r in range(4) for c in range(4)]


def coordinate_matrix(layout):
    contract = layout.get("coordinate_contract")
    if not isinstance(contract, dict):
        raise ValueError("layout.coordinate_contract must explicitly declare H")
    row_keys = ("H_row_major", "matrix_row_major", "unity_to_gltf_matrix_row_major",
                "unity_to_gltf_matrix", "handedness_matrix", "H", "matrix", "unity_to_gltf",
                "unity_to_gltf_basis")
    for key in row_keys + ("H_column_major", "matrix_column_major"):
        value = contract.get(key)
        if isinstance(value, list) and len(value) == 4 and all(isinstance(r, list) and len(r) == 4 for r in value):
            value = [n for row in value for n in row]
        if isinstance(value, list) and len(value) == 16 and all(isinstance(v, (int, float)) for v in value):
            value = [float(v) for v in value]
            if not all(math.isfinite(v) for v in value):
                raise ValueError("Nonfinite coordinate conversion matrix")
            column_major = ("column_major" in key or
                            (key == "unity_to_gltf_basis" and
                             "column-major" in contract.get("matrix_layout", "")))
            return from_column_major(value) if column_major else value
    raise ValueError("No numeric H matrix in layout.coordinate_contract; prefer H_row_major")


def converted_expected(item, h):
    return multiply(multiply(h, item["world_matrix_unity_row_major"]), inverse4(h))


def local_matrix(node):
    if "matrix" in node:
        return from_column_major(node["matrix"])
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm == 0:
        raise ValueError("Zero glTF quaternion")
    x, y, z, w = [v / norm for v in (x, y, z, w)]
    sx, sy, sz = node.get("scale", [1, 1, 1])
    px, py, pz = node.get("translation", [0, 0, 0])
    return [
        (1 - 2 * (y*y + z*z))*sx, 2*(x*y - z*w)*sy, 2*(x*z + y*w)*sz, px,
        2*(x*y + z*w)*sx, (1 - 2*(x*x + z*z))*sy, 2*(y*z - x*w)*sz, py,
        2*(x*z - y*w)*sx, 2*(y*z + x*w)*sy, (1 - 2*(x*x + y*y))*sz, pz,
        0, 0, 0, 1,
    ]


def build_worlds(gltf):
    nodes = gltf.get("nodes", [])
    parents = {}
    for index, node in enumerate(nodes):
        for child in node.get("children", []):
            if not isinstance(child, int) or not 0 <= child < len(nodes):
                raise ValueError("Invalid child node index")
            if child in parents:
                raise ValueError("Node has multiple parents: " + str(child))
            parents[child] = index
    active_scene = gltf.get("scene", 0)
    roots = gltf.get("scenes", [])[active_scene].get("nodes", [])
    worlds, visiting = {}, set()

    def visit(index, parent_world):
        if index in visiting:
            raise ValueError("Cycle in glTF hierarchy")
        if index in worlds:
            raise ValueError("Node is reachable by multiple paths")
        visiting.add(index)
        world = multiply(parent_world, local_matrix(nodes[index]))
        if not all(math.isfinite(v) for v in world):
            raise ValueError("Nonfinite world matrix")
        worlds[index] = world
        for child in nodes[index].get("children", []):
            visit(child, world)
        visiting.remove(index)

    for index in roots:
        visit(index, IDENTITY)
    mesh_cache = {}

    def has_mesh(index):
        if index not in mesh_cache:
            mesh_cache[index] = ("mesh" in nodes[index] or
                                 any(has_mesh(c) for c in nodes[index].get("children", [])))
        return mesh_cache[index]

    return nodes, parents, worlds, has_mesh


def pick_evidence(layout, layout_path, evidence):
    serialized = json.dumps(layout)
    exact = [s for s in evidence["scenes"] if s["source_scene"]["guid"] in serialized]
    if len(exact) == 1:
        return exact[0]
    text = (str(layout_path.parent) + " " + str(layout.get("id", "")) + " " +
            str(layout.get("scene_id", ""))).lower()
    matches = [s for s in evidence["scenes"] if s["scene_id"] in text]
    if len(matches) != 1:
        raise ValueError("Cannot identify independent scene evidence for " + str(layout_path))
    return matches[0]


def extras(node):
    return node.get("extras", {}) if isinstance(node.get("extras", {}), dict) else {}


def topmost(candidates, parents):
    ids = set(candidates)
    result = []
    for index in candidates:
        parent = parents.get(index)
        nested = False
        while parent is not None:
            if parent in ids:
                nested = True
                break
            parent = parents.get(parent)
        if not nested:
            result.append(index)
    return result


def matrix_result(expected, actual, tolerance):
    delta = max(abs(a - b) for a, b in zip(expected, actual))
    position_delta = max(abs(expected[i] - actual[i]) for i in (3, 7, 11))
    return {
        "passed": delta <= tolerance,
        "max_matrix_absolute_error": delta,
        "max_position_absolute_error": position_delta,
        "expected_world_gltf_row_major": expected,
        "actual_world_gltf_row_major": actual,
        "expected_basis_xz_dot": sum(expected[i] * expected[i + 2] for i in (0, 4, 8)),
        "actual_basis_xz_dot": sum(actual[i] * actual[i + 2] for i in (0, 4, 8)),
    }


def validate_pair(layout_path, gltf_path, evidence):
    layout, gltf = read_json(layout_path), read_json(gltf_path)
    source = pick_evidence(layout, layout_path, evidence)
    h = coordinate_matrix(layout)
    nodes, parents, worlds, has_mesh = build_worlds(gltf)
    tolerance = evidence["comparison_contract"]["matrix_absolute_tolerance"]
    report = {"scene_id": source["scene_id"], "layout": str(layout_path),
              "gltf": str(gltf_path), "source_scene": source["source_scene"],
              "tolerance": tolerance, "H_row_major_from_layout": h,
              "landmarks": [], "direct_cubes": [], "errors": []}
    approved_h = evidence["coordinate_conversion"]["H_row_major"]
    if max(abs(a-b) for a, b in zip(h, approved_h)) > 1e-9:
        report["errors"].append("Layout H differs from independently approved coordinate contract")
    roots = [i for i in worlds if extras(nodes[i]).get("source_is_prefab_root") is True]
    by_instance = {}
    for i in roots:
        instance = extras(nodes[i]).get("source_instance_id")
        if not isinstance(instance, str):
            report["errors"].append("Prefab root source_instance_id must be a string: " + str(i))
        else:
            by_instance.setdefault(instance, []).append(i)
    for instance, indices in by_instance.items():
        if len(indices) != 1:
            report["errors"].append("Duplicate Prefab root anchor: " + instance)
    for landmark in source["landmarks"]:
        instance = landmark["source_instance_id"]
        candidates = by_instance.get(instance, [])
        item = {"source_instance_id": instance,
                "source_prefab_guid": landmark["source_prefab_guid"],
                "source_scene_line": landmark["source_scene_line"]}
        if len(candidates) != 1:
            item.update(passed=False, error="Expected one explicit Prefab root anchor",
                        candidates=candidates)
        else:
            index = candidates[0]
            item.update(node_index=index, node_name=nodes[index].get("name"))
            item.update(matrix_result(converted_expected(landmark, h),
                                      worlds[index], tolerance))
            guid = extras(nodes[index]).get("source_prefab_guid")
            if guid != landmark["source_prefab_guid"]:
                item.update(passed=False, prefab_guid_error="Source Prefab GUID mismatch")
        report["landmarks"].append(item)
        if not item["passed"]:
            report["errors"].append("Landmark mismatch: " + instance)
    # Compare source transform anchors, never an imported FBX geometry-unit child.
    for cube in source["direct_visible_cubes"]:
        candidates = [i for i in worlds if has_mesh(i) and
                      (extras(nodes[i]).get("source_transform_id") == cube["source_transform_id"] or
                       extras(nodes[i]).get("source_renderer_id") == cube["source_renderer_id"])]
        candidates = topmost(candidates, parents)
        item = {"source_renderer_id": cube["source_renderer_id"],
                "source_transform_id": cube["source_transform_id"]}
        if len(candidates) != 1:
            item.update(passed=False, error="Expected one visible source Cube transform anchor",
                        candidates=candidates)
        else:
            item.update(node_index=candidates[0])
            item.update(matrix_result(converted_expected(cube, h),
                                      worlds[candidates[0]], tolerance))
        report["direct_cubes"].append(item)
        if not item["passed"]:
            report["errors"].append("Direct Cube mismatch: " + cube["source_renderer_id"])
    fx_ids = {v["source_instance_id"] for v in source["excluded_fx_instances"]}
    global_ids = {v["source_instance_id"] for v in source["global_settings_instances"]}
    rendered_ids = {instance for instance, indices in by_instance.items()
                    if any(has_mesh(i) for i in indices)}
    actual_static = rendered_ids - fx_ids - global_ids
    expected = source["source_counts"]
    report["counts"] = {"source": expected,
                        "renderable_static_prefab_roots": len(actual_static),
                        "matched_direct_cubes": sum(c["passed"] for c in report["direct_cubes"]),
                        "source_fx_instances_recorded": len(fx_ids),
                        "source_global_instances_recorded": len(global_ids),
                        "rendered_fx_source_ids": sorted(rendered_ids & fx_ids),
                        "rendered_global_source_ids": sorted(rendered_ids & global_ids),
                        "reachable_gltf_nodes": len(worlds),
                        "gltf_camera_nodes": sum("camera" in nodes[i] for i in worlds)}
    if len(actual_static) != expected["static_prefab_instances"]:
        report["errors"].append("Static Prefab root count differs from independent source count")
    if len(fx_ids) != expected["fx_prefab_instances"] or len(global_ids) != 1:
        report["errors"].append("Independent exclusion inventory is internally inconsistent")
    if rendered_ids & (fx_ids | global_ids):
        report["errors"].append("Omitted FX/global source contains rendered geometry")
    if (expected["static_prefab_instances"] + len(fx_ids) + len(global_ids) !=
            expected["scene_prefab_instances"]):
        report["errors"].append("Independent original Prefab counts do not reconcile")
    report["passed"] = not report["errors"]
    return report


def main():
    work_default = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=work_default)
    parser.add_argument("--repo", type=Path,
                        required=True)
    parser.add_argument("--scene", nargs=2, action="append", metavar=("LAYOUT_JSON", "SCENE_GLTF"))
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evidence_path = args.evidence or args.work / "audit" / "scene_landmarks_independent.json"
    evidence = read_json(evidence_path)
    pairs = [(Path(a), Path(b)) for a, b in args.scene] if args.scene else [
        (p, p.parent / "scene.gltf") for p in sorted((args.repo / "scenes").glob("*/layout.json"))]
    report = {"schema_version": 1,
              "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "evidence": str(evidence_path),
              "coordinate_conversion": "Read each layout.coordinate_contract matrix; expected=H*UnityWorld*inverse(H)",
              "scope": "Independent source-root world matrices/counts, not visual or full glTF validation",
              "scenes": [], "errors": []}
    if not pairs:
        report["errors"].append("No authored scene layout.json/scene.gltf pairs found")
    for layout, gltf in pairs:
        try:
            report["scenes"].append(validate_pair(layout, gltf, evidence))
        except Exception as error:
            report["scenes"].append({"layout": str(layout), "gltf": str(gltf),
                                     "passed": False, "errors": [str(error)]})
    report["passed"] = not report["errors"] and all(s["passed"] for s in report["scenes"])
    destination = args.output or args.work / "audit" / "authored_scene_validation.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "scenes": len(report["scenes"]),
                      "report": str(destination)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
