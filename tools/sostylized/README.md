# SoStylized conversion tools

These tools produce portable assets from the user-supplied Unreal source. They do not license or download the source package. Use a separate conversion project and retain the original archive unchanged. No game files or saves are required.

1. Mount the extracted SoStylized source under Content/SoStylized in an isolated Unreal project. Enable PythonScriptPlugin, EditorScriptingUtilities and GLTFExporter. Run inventory_native.py using the same SOSTYLIZED_EXPORT_CONFIG described below to inventory the native Asset Registry into native_catalog.json (engine, assets with name/path/package/class, class_counts).
2. Run export_native.py through UnrealEditor-Cmd with SOSTYLIZED_EXPORT_CONFIG pointing to a JSON configuration containing work and bake_pixels (1024 for this delivery). Selected package paths may be supplied for a bounded pilot. The script records work/export_progress.json and resumable export_records.jsonl. Completed native files are reused only when the recorded size matches.
3. Run package_portable.py --work WORK --output WORK/portable. It copies exact native PNG/EXR/WAV data, packages embedded GLBs, and normalizes single-channel texture UV references to UV0 without changing binary geometry/images. Mixed UV material references are retained and reported. All target assets must finish; pending/failed entries are explicit.
4. Run publish_collection.py prepare --work WORK --repo REPO --release-tag TAG to attach material readiness notes.
5. Run build_downloads.py --portable WORK/portable --output WORK/downloads. It checks catalog consistency and packages category ZIPs strictly below 1.8 GB, splitting on whole asset boundaries when necessary. It refuses different existing output identities.
6. Run publish_collection.py publish --work WORK --repo REPO --release-tag TAG to assemble readable repository indexes, four examples, preview provenance, and download URLs. This prepares files; it does not upload, authenticate or change Git. Publish the actual ZIPs separately and verify returned sizes/digests.

Native material baking uses Unreal 5.8.4 GLTFExporter with mesh data, LOD0 only, export_source_model=false, export_vertex_colors=false, PNG baked inputs and 0.01 centimetre-to-metre conversion. bake_pixels controls newly baked inputs; directly reused author textures may be larger. Unreal runtime graphs, RVT/Landscape, water/cloud/wind/Blueprint/Niagara behavior are not reproduced. Read ../../collections/sostylized/MATERIAL_READINESS.md.

render_samples.py imports selected GLBs in Blender 5.2.2 using CPU Cycles for bounded static previews. diagnose_samples.py records specific source-material/image/geometry evidence; its report is diagnostic data, not an automated acceptance of all materials. Python stdlib suffices for portable packaging, while preview diagnosis may require Pillow and Blender APIs.

Texture export now leaves AssetExportTask.exporter unset and lets native FindExporter select a source-compatible PNG or EXR exporter. CompressionSettings alone does not identify the source pixel format; forcing EXR for a non-HDR source can assert even when the compression setting says HDR. Fresh tasks isolate a rejected extension attempt from the successful result. Successful earlier files are reused rather than exported again.

The delivered catalogs preserve source object paths, native material slots, source and output hashes, authored Texture2D sRGB/compression/green-flip settings, actual exported_lods and warnings. Texture channel_mapping remains null unless verified; do not infer ORM channels from names.
