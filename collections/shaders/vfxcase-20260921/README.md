# Particle ShaderGraph source pack — 2026-09-21

The owner supplied Shader_2026.09.21.rar from the purchased VFX collection. Its archive integrity check passed; six Unity URP Unlit ShaderGraphs and six .meta files were extracted unchanged. The graphs are AirDistor_1.0, Base_1.0/1.1/1.2 and Fresnel_1.0/1.1. See [inventory.json](inventory.json) for every source path, GUID and hash.

[Retrieve the original archive and complete sources from the existing private game repository](https://github.com/kk20054/fanren-godot-world/tree/main/reference_assets/shaders/vfxcase-20260921). Claude needs an authorized GitHub connection for that repository. The RAR uses Git LFS; the extracted graphs and metadata remain directly readable source text.

**Version isolation:** Base_1.1 shares a Unity GUID with RedFly's Base_1.1 but contains different bytes. Each pack is stored in its own directory so no source graph is overwritten. Use package/path/hash, not GUID alone, when choosing source versions. The inventory records this conflict and the differently named graphs that have identical content.

These are Unity ShaderGraph node sources, not converted Godot materials. They can guide effect-material reconstruction after inspecting their actual node connections. No shader execution, visual equivalence, or Godot runtime validation is claimed. Full source remains private under the existing purchased-VFX arrangement; this public catalog does not grant a new license.
