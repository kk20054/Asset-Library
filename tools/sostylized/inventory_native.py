"""Inventory the mounted source using the same config as export_native.py.
Run inside UnrealEditor-Cmd; this creates metadata, not portable model files.
"""
from collections import Counter
import json
import os
from pathlib import Path
import unreal

config = json.loads(Path(os.environ["SOSTYLIZED_EXPORT_CONFIG"]).read_text(encoding="utf-8"))
work = Path(config["work"])
work.mkdir(parents=True, exist_ok=True)
registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous(["/Game/SoStylized"], True)
rows = [{"name": str(a.asset_name),
         "path": str(a.package_name) + "." + str(a.asset_name),
         "package": str(a.package_name),
         "class": str(a.asset_class_path.asset_name)}
        for a in registry.get_assets_by_path("/Game/SoStylized", True)]
rows.sort(key=lambda a: a["package"])
result = {"engine": unreal.SystemLibrary.get_engine_version(),
          "source_scope": "Full user-supplied SoStylized archive, native asset registry",
          "assets": rows, "class_counts": dict(Counter(a["class"] for a in rows))}
(work / "native_catalog.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
print("SO_STYLIZED_CATALOG_DONE " + str(len(rows)))
