"""
Build an approximate Noctelle VRM from Sol-derived PNG sprites.
Quality: flat billboard / paper-doll style (no true 3D mesh-from-image; no GPU AI).
"""
import bpy
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\punkm\Desktop\desktop-assistant\v-lucent\local-companion")
ADDON_ZIP = ROOT / "tools" / "vrm-build" / "vrm_addon.zip"
SPRITE = ROOT / "public" / "media" / "noctelle" / "noctelle-active.png"
OUT_VRM = ROOT / "public" / "models" / "noctelle.vrm"
OUT_BLEND = ROOT / "tools" / "vrm-build" / "noctelle-sol.blend"

def log(msg: str) -> None:
    print(f"[noctelle-vrm] {msg}", flush=True)

def install_vrm_addon() -> None:
    zip_path = str(ADDON_ZIP.resolve())
    log(f"Installing addon from {zip_path}")
    # Prefer extensions API (Blender 4.2+)
    try:
        result = bpy.ops.extensions.package_install_files(
            filepath=zip_path,
            repo="user_default",
            enable_on_install=True,
            overwrite_pkg_once=True,
        )
        log(f"extensions.package_install_files -> {result}")
        if result == {"FINISHED"}:
            return
    except Exception as e:
        log(f"extensions install failed: {e}")

    try:
        result = bpy.ops.preferences.addon_install(filepath=zip_path, overwrite=True)
        log(f"addon_install -> {result}")
    except Exception as e:
        log(f"addon_install failed: {e}")

    # Enable likely module names
    for mod in (
        "vrm",
        "VRM_Addon_for_Blender-release",
        "io_scene_vrm",
    ):
        try:
            bpy.ops.preferences.addon_enable(module=mod)
            log(f"enabled module={mod}")
            return
        except Exception as e:
            log(f"enable {mod} failed: {e}")

    # Fallback: list enabled and hope export_scene.vrm exists
    if not hasattr(bpy.ops, "export_scene") or not hasattr(bpy.ops.export_scene, "vrm"):
        # Try enabling any installed addon containing VRM
        import addon_utils
        for mod in addon_utils.modules():
            name = getattr(mod, "__name__", "")
            if "vrm" in name.lower() or "VRM" in name:
                try:
                    bpy.ops.preferences.addon_enable(module=name)
                    log(f"enabled discovered module={name}")
                except Exception as e:
                    log(f"enable discovered {name} failed: {e}")

def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block)
    for block in list(bpy.data.images):
        bpy.data.images.remove(block)
    for block in list(bpy.data.armatures):
        bpy.data.armatures.remove(block)

def build() -> None:
    if not SPRITE.is_file():
        raise SystemExit(f"Missing sprite: {SPRITE}")
    if not ADDON_ZIP.is_file():
        raise SystemExit(f"Missing addon zip: {ADDON_ZIP}")

    install_vrm_addon()
    clear_scene()

    # Basic VRM humanoid armature from the addon
    if not hasattr(bpy.ops, "icyp") or not hasattr(bpy.ops.icyp, "make_basic_armature"):
        raise SystemExit("VRM addon not loaded (icyp.make_basic_armature missing)")

    bpy.ops.icyp.make_basic_armature()
    armature = bpy.context.active_object
    if armature is None or armature.type != "ARMATURE":
        raise SystemExit("Failed to create armature")

    armature.data.vrm_addon_extension.spec_version = "1.0"
    meta = armature.data.vrm_addon_extension.vrm1.meta
    meta.vrm_name = "Noctelle"
    meta.version = "0.1.0-sol-billboard"
    if hasattr(meta, "authors") and len(meta.authors) == 0:
        meta.authors.add().value = "Punk Milk / Sol handoff (approx billboard)"
    meta.copyright_information = "Sol-derived Noctelle sprite billboard VRM (approximate)"
    meta.avatar_permission = "onlyAuthor"
    meta.commercial_usage = "personalNonProfit"
    meta.credit_notation = "required"
    meta.allow_redistribution = False
    meta.modification = "allowModification"
    humanoid = armature.data.vrm_addon_extension.vrm1.humanoid

    # Load Sol sprite
    img = bpy.data.images.load(str(SPRITE.resolve()))
    img.name = "noctelle-active"
    img.alpha_mode = "STRAIGHT"
    meta.thumbnail_image = img

    # Aspect-correct vertical plane (sprite is 720x1100)
    aspect = 720 / 1100
    height = 1.55  # meters-ish full body card
    width = height * aspect

    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, height * 0.5))
    plane = bpy.context.active_object
    plane.name = "NoctelleSprite"
    plane.scale = (width, 1.0, height)
    # Plane is XY by default; rotate to stand upright facing +Y (typical VRM front)
    plane.rotation_euler = (1.57079632679, 0.0, 0.0)  # 90 deg X
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    # Parent to hips bone so it moves with humanoid root
    hips_name = humanoid.human_bones.hips.node.bone_name or "hips"
    plane.parent = armature
    plane.parent_type = "BONE"
    plane.parent_bone = hips_name

    # Material with alpha blend + Sol texture
    mat = bpy.data.materials.new("NoctelleSolBillboard")
    mat.use_nodes = True
    mat.vrm_addon_extension.mtoon1.enabled = True
    gltf = mat.vrm_addon.extension.mtoon1 if False else mat.vrm_addon_extension.mtoon1
    gltf.pbr_metallic_roughness.base_color_texture.index.source = img
    gltf.pbr_metallic_roughness.base_color_factor = (1, 1, 1, 1)
    gltf.alpha_mode = "BLEND"
    gltf.double_sided = True
    plane.data.materials.append(mat)

    # Tiny marker meshes on limbs so humanoid validation is happier (optional stubs)
    stubs = [
        ("head", 0.08),
        ("spine", 0.05),
        ("left_upper_arm", 0.04),
        ("right_upper_arm", 0.04),
        ("left_hand", 0.03),
        ("right_hand", 0.03),
        ("left_upper_leg", 0.04),
        ("right_upper_leg", 0.04),
        ("left_lower_leg", 0.04),
        ("right_lower_leg", 0.04),
    ]
    hb = humanoid.human_bones
    bone_attr = {
        "head": hb.head,
        "spine": hb.spine,
        "left_upper_arm": hb.left_upper_arm,
        "right_upper_arm": hb.right_upper_arm,
        "left_hand": hb.left_hand,
        "right_hand": hb.right_hand,
        "left_upper_leg": hb.left_upper_leg,
        "right_upper_leg": hb.right_upper_leg,
        "left_lower_leg": hb.left_lower_leg,
        "right_lower_leg": hb.right_lower_leg,
    }
    for key, radius in stubs:
        bone_name = bone_attr[key].node.bone_name
        if not bone_name:
            continue
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=(0, 0, 0))
        stub = bpy.context.active_object
        stub.name = f"stub_{key}"
        stub.parent = armature
        stub.parent_type = "BONE"
        stub.parent_bone = bone_name
        # Nearly invisible dark material so billboard dominates
        sm = bpy.data.materials.new(f"stubmat_{key}")
        sm.use_nodes = True
        sm.vrm_addon_extension.mtoon1.enabled = True
        g = sm.vrm_addon_extension.mtoon1
        g.pbr_metallic_roughness.base_color_factor = (0.05, 0.05, 0.08, 0.15)
        g.alpha_mode = "BLEND"
        stub.data.materials.append(sm)

    OUT_VRM.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND.resolve()))

    log(f"Exporting {OUT_VRM}")
    result = bpy.ops.export_scene.vrm(filepath=str(OUT_VRM.resolve()))
    if result != {"FINISHED"}:
        raise SystemExit(f"VRM export failed: {result}")
    log(f"Wrote {OUT_VRM} size={OUT_VRM.stat().st_size}")

if __name__ == "__main__":
    try:
        build()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
