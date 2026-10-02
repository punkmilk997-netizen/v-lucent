"""
Build an improved Noctelle VRM from Sol-derived PNG sprites.

Quality: alpha-cutout shallow card (silhouette mesh + thickness + height-banded
weights). Still NOT true mesh-from-image AI (no TripoSR/torch/CUDA on this PC).
Uses only Blender built-ins + already-installed VRM Add-on for Blender.
"""
import bpy
import bmesh
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(r"C:\Users\punkm\Desktop\desktop-assistant\v-lucent\local-companion")
ADDON_ZIP = ROOT / "tools" / "vrm-build" / "vrm_addon.zip"
SPRITE = ROOT / "public" / "media" / "noctelle" / "noctelle-active.png"
OUT_VRM = ROOT / "public" / "models" / "noctelle.vrm"
OUT_BLEND = ROOT / "tools" / "vrm-build" / "noctelle-sol.blend"

# Grid resolution for silhouette sampling (higher = smoother cutout, heavier mesh)
GRID_W = 72
GRID_H = 110
ALPHA_THRESHOLD = 0.12
CARD_HEIGHT_M = 1.55
THICKNESS_M = 0.045  # shallow 3D card depth


def log(msg: str) -> None:
    print(f"[noctelle-vrm] {msg}", flush=True)


def install_vrm_addon() -> None:
    # Always enable the installed addon; hasattr(export_scene.vrm) can be true
    # as a stub before the real module is loaded.
    for mod in ("VRM_Addon_for_Blender-release", "vrm", "io_scene_vrm"):
        try:
            result = bpy.ops.preferences.addon_enable(module=mod)
            log(f"enabled module={mod} -> {result}")
            if hasattr(bpy.ops, "icyp") and hasattr(bpy.ops.icyp, "make_basic_armature"):
                return
        except Exception as e:
            log(f"enable {mod} failed: {e}")

    zip_path = str(ADDON_ZIP.resolve())
    if ADDON_ZIP.is_file():
        log(f"Installing addon from {zip_path}")
        try:
            result = bpy.ops.extensions.package_install_files(
                filepath=zip_path,
                repo="user_default",
                enable_on_install=True,
                overwrite_pkg_once=True,
            )
            log(f"extensions.package_install_files -> {result}")
        except Exception as e:
            log(f"extensions install failed: {e}")
        try:
            result = bpy.ops.preferences.addon_install(filepath=zip_path, overwrite=True)
            log(f"addon_install -> {result}")
        except Exception as e:
            log(f"addon_install failed: {e}")
        try:
            bpy.ops.preferences.addon_enable(module="VRM_Addon_for_Blender-release")
            log("enabled VRM_Addon_for_Blender-release after zip install")
        except Exception as e:
            log(f"post-install enable failed: {e}")

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


def load_alpha_grid(img):
    """Cache full pixel buffer once (Blender img.pixels is slow per-index)."""
    w, h = img.size
    log(f"Caching pixel buffer {w}x{h}...")
    px = list(img.pixels)
    alpha = [px[i + 3] for i in range(0, len(px), 4)]
    return w, h, alpha


def sample_alpha(w, h, alpha, u: float, v: float) -> float:
    """Sample cached alpha at UV (u,v) in [0,1], Blender pixels bottom-up."""
    x = min(w - 1, max(0, int(round(u * (w - 1)))))
    y = min(h - 1, max(0, int(round(v * (h - 1)))))
    return float(alpha[y * w + x])


def cell_opaque(w, h, alpha, i: int, j: int, gw: int, gh: int) -> bool:
    """True if any of the 4 cell corners (plus center) exceed alpha threshold."""
    best = 0.0
    for du, dv in ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0), (0.5, 0.5)):
        u = (i + du) / gw
        v = (j + dv) / gh
        a = sample_alpha(w, h, alpha, u, v)
        if a > best:
            best = a
            if best >= ALPHA_THRESHOLD:
                return True
    return best >= ALPHA_THRESHOLD


def build_cutout_card(img) -> bpy.types.Object:
    """Alpha silhouette grid extruded into a shallow double-sided card."""
    aspect = img.size[0] / img.size[1]
    height = CARD_HEIGHT_M
    width = height * aspect
    half_t = THICKNESS_M * 0.5
    gw, gh = GRID_W, GRID_H

    log(f"Building cutout card {gw}x{gh} from {img.size[0]}x{img.size[1]} alpha")

    iw, ih, alpha = load_alpha_grid(img)

    mesh = bpy.data.meshes.new("NoctelleCutoutMesh")
    obj = bpy.data.objects.new("NoctelleSprite", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    # Front and back vertex grids: (i,j) -> (front_vert, back_vert)
    front = [[None] * (gh + 1) for _ in range(gw + 1)]
    back = [[None] * (gh + 1) for _ in range(gw + 1)]
    uv_layer = bm.loops.layers.uv.new("UVMap")

    def vert_at(i, j, y):
        x = (i / gw - 0.5) * width
        z = (j / gh) * height
        return bm.verts.new((x, y, z))

    # Precompute opaque mask once
    opaque = [[cell_opaque(iw, ih, alpha, i, j, gw, gh) for j in range(gh)] for i in range(gw)]

    # Only create verts that touch at least one opaque cell
    needed = [[False] * (gh + 1) for _ in range(gw + 1)]
    opaque_cells = 0
    for i in range(gw):
        for j in range(gh):
            if opaque[i][j]:
                opaque_cells += 1
                for ii in (i, i + 1):
                    for jj in (j, j + 1):
                        needed[ii][jj] = True

    log(f"Opaque cells: {opaque_cells}/{gw * gh}")
    if opaque_cells == 0:
        raise SystemExit("No opaque alpha cells found in sprite")

    for i in range(gw + 1):
        for j in range(gh + 1):
            if needed[i][j]:
                front[i][j] = vert_at(i, j, half_t)
                back[i][j] = vert_at(i, j, -half_t)

    bm.verts.ensure_lookup_table()

    def add_face(verts, uvs):
        try:
            face = bm.faces.new(verts)
        except ValueError:
            return
        for loop, uv in zip(face.loops, uvs):
            loop[uv_layer].uv = uv

    # Front faces (CCW facing +Y) and back faces (facing -Y)
    for i in range(gw):
        for j in range(gh):
            if not opaque[i][j]:
                continue
            v00, v10 = front[i][j], front[i + 1][j]
            v01, v11 = front[i][j + 1], front[i + 1][j + 1]
            b00, b10 = back[i][j], back[i + 1][j]
            b01, b11 = back[i][j + 1], back[i + 1][j + 1]
            if None in (v00, v10, v01, v11, b00, b10, b01, b11):
                continue
            u0, u1 = i / gw, (i + 1) / gw
            v0, v1 = j / gh, (j + 1) / gh
            # Front (+Y): winding for outward normal
            add_face(
                (v00, v10, v11, v01),
                (Vector((u0, v0)), Vector((u1, v0)), Vector((u1, v1)), Vector((u0, v1))),
            )
            # Back (-Y)
            add_face(
                (b10, b00, b01, b11),
                (Vector((u1, v0)), Vector((u0, v0)), Vector((u0, v1)), Vector((u1, v1))),
            )

    # Side walls along silhouette edges (shared opaque/transparent boundary)
    def is_opaque(i, j):
        if i < 0 or j < 0 or i >= gw or j >= gh:
            return False
        return opaque[i][j]

    for i in range(gw):
        for j in range(gh):
            if not is_opaque(i, j):
                continue
            u0, u1 = i / gw, (i + 1) / gw
            v0, v1 = j / gh, (j + 1) / gh
            # Left edge
            if not is_opaque(i - 1, j):
                add_face(
                    (back[i][j], front[i][j], front[i][j + 1], back[i][j + 1]),
                    (Vector((u0, v0)), Vector((u0, v0)), Vector((u0, v1)), Vector((u0, v1))),
                )
            # Right edge
            if not is_opaque(i + 1, j):
                add_face(
                    (front[i + 1][j], back[i + 1][j], back[i + 1][j + 1], front[i + 1][j + 1]),
                    (Vector((u1, v0)), Vector((u1, v0)), Vector((u1, v1)), Vector((u1, v1))),
                )
            # Bottom edge
            if not is_opaque(i, j - 1):
                add_face(
                    (back[i][j], back[i + 1][j], front[i + 1][j], front[i][j]),
                    (Vector((u0, v0)), Vector((u1, v0)), Vector((u1, v0)), Vector((u0, v0))),
                )
            # Top edge
            if not is_opaque(i, j + 1):
                add_face(
                    (front[i][j + 1], front[i + 1][j + 1], back[i + 1][j + 1], back[i][j + 1]),
                    (Vector((u0, v1)), Vector((u1, v1)), Vector((u1, v1)), Vector((u0, v1))),
                )

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    log(f"Mesh verts={len(mesh.vertices)} faces={len(mesh.polygons)}")
    return obj


def assign_height_weights(obj: bpy.types.Object, armature: bpy.types.Object, humanoid) -> None:
    """Band vertex groups by local Z for look-at / slight torso bend."""
    hb = humanoid.human_bones
    bone_map = {
        "hips": hb.hips.node.bone_name,
        "spine": hb.spine.node.bone_name,
        "chest": getattr(getattr(hb, "chest", None), "node", None),
        "neck": getattr(getattr(hb, "neck", None), "node", None),
        "head": hb.head.node.bone_name,
        "left_upper_leg": hb.left_upper_leg.node.bone_name,
        "right_upper_leg": hb.right_upper_leg.node.bone_name,
        "left_lower_leg": hb.left_lower_leg.node.bone_name,
        "right_lower_leg": hb.right_lower_leg.node.bone_name,
    }
    # Resolve chest/neck optionally
    chest_name = None
    neck_name = None
    try:
        chest_name = hb.chest.node.bone_name
    except Exception:
        pass
    try:
        neck_name = hb.neck.node.bone_name
    except Exception:
        pass
    bone_map["chest"] = chest_name
    bone_map["neck"] = neck_name

    # Create vertex groups for bones that exist
    groups = {}
    for key, bname in bone_map.items():
        if not bname:
            continue
        groups[key] = obj.vertex_groups.new(name=bname)

    zs = [v.co.z for v in obj.data.vertices]
    zmin, zmax = min(zs), max(zs)
    span = max(1e-6, zmax - zmin)

    def t(z):
        return (z - zmin) / span

    for vi, v in enumerate(obj.data.vertices):
        tt = t(v.co.z)
        x = v.co.x
        # Legs below ~0.28
        if tt < 0.28:
            leg_l = groups.get("left_upper_leg") or groups.get("left_lower_leg")
            leg_r = groups.get("right_upper_leg") or groups.get("right_lower_leg")
            low_l = groups.get("left_lower_leg")
            low_r = groups.get("right_lower_leg")
            if tt < 0.12:
                if x < 0 and low_l:
                    low_l.add([vi], 1.0, "REPLACE")
                elif x >= 0 and low_r:
                    low_r.add([vi], 1.0, "REPLACE")
                elif groups.get("hips"):
                    groups["hips"].add([vi], 1.0, "REPLACE")
            else:
                if x < 0 and leg_l:
                    leg_l.add([vi], 1.0, "REPLACE")
                elif x >= 0 and leg_r:
                    leg_r.add([vi], 1.0, "REPLACE")
                elif groups.get("hips"):
                    groups["hips"].add([vi], 1.0, "REPLACE")
        elif tt < 0.48:
            if groups.get("hips"):
                groups["hips"].add([vi], 1.0, "REPLACE")
        elif tt < 0.68:
            g = groups.get("spine") or groups.get("hips")
            if g:
                g.add([vi], 1.0, "REPLACE")
        elif tt < 0.80:
            g = groups.get("chest") or groups.get("spine") or groups.get("hips")
            if g:
                g.add([vi], 1.0, "REPLACE")
        elif tt < 0.88:
            g = groups.get("neck") or groups.get("head") or groups.get("spine")
            if g:
                g.add([vi], 1.0, "REPLACE")
        else:
            g = groups.get("head") or groups.get("neck") or groups.get("spine")
            if g:
                g.add([vi], 1.0, "REPLACE")

    # Armature deform
    mod = obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = armature
    mod.use_vertex_groups = True
    obj.parent = armature
    obj.parent_type = "OBJECT"
    log(f"Assigned height-banded weights across {len(obj.data.vertices)} verts")


def build() -> None:
    if not SPRITE.is_file():
        raise SystemExit(f"Missing sprite: {SPRITE}")

    install_vrm_addon()
    if not hasattr(bpy.ops, "export_scene") or not hasattr(bpy.ops.export_scene, "vrm"):
        raise SystemExit("VRM addon not loaded (export_scene.vrm missing)")
    if not hasattr(bpy.ops, "icyp") or not hasattr(bpy.ops.icyp, "make_basic_armature"):
        raise SystemExit("VRM addon not loaded (icyp.make_basic_armature missing)")

    clear_scene()

    bpy.ops.icyp.make_basic_armature()
    armature = bpy.context.active_object
    if armature is None or armature.type != "ARMATURE":
        raise SystemExit("Failed to create armature")

    armature.data.vrm_addon_extension.spec_version = "1.0"
    meta = armature.data.vrm_addon_extension.vrm1.meta
    meta.vrm_name = "Noctelle"
    meta.version = "0.2.0-sol-cutout-card"
    if hasattr(meta, "authors") and len(meta.authors) == 0:
        meta.authors.add().value = "Punk Milk / Sol handoff (alpha cutout card)"
    meta.copyright_information = "Sol-derived Noctelle alpha-cutout card VRM (improved billboard)"
    meta.avatar_permission = "onlyAuthor"
    meta.commercial_usage = "personalNonProfit"
    meta.credit_notation = "required"
    meta.allow_redistribution = False
    meta.modification = "allowModification"
    humanoid = armature.data.vrm_addon_extension.vrm1.humanoid

    img = bpy.data.images.load(str(SPRITE.resolve()))
    img.name = "noctelle-active"
    img.alpha_mode = "STRAIGHT"
    img.pack()
    meta.thumbnail_image = img

    plane = build_cutout_card(img)
    assign_height_weights(plane, armature, humanoid)

    mat = bpy.data.materials.new("NoctelleSolCutout")
    mat.use_nodes = True
    mat.vrm_addon_extension.mtoon1.enabled = True
    gltf = mat.vrm_addon_extension.mtoon1
    gltf.pbr_metallic_roughness.base_color_texture.index.source = img
    gltf.pbr_metallic_roughness.base_color_factor = (1, 1, 1, 1)
    gltf.alpha_mode = "MASK"
    gltf.alpha_cutoff = 0.35
    gltf.double_sided = True
    plane.data.materials.append(mat)

    # Tiny stubs so humanoid limbs still have some mesh presence for validation
    stubs = [
        ("left_upper_arm", 0.025),
        ("right_upper_arm", 0.025),
        ("left_hand", 0.02),
        ("right_hand", 0.02),
    ]
    hb = humanoid.human_bones
    bone_attr = {
        "left_upper_arm": hb.left_upper_arm,
        "right_upper_arm": hb.right_upper_arm,
        "left_hand": hb.left_hand,
        "right_hand": hb.right_hand,
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
        sm = bpy.data.materials.new(f"stubmat_{key}")
        sm.use_nodes = True
        sm.vrm_addon_extension.mtoon1.enabled = True
        g = sm.vrm_addon_extension.mtoon1
        g.pbr_metallic_roughness.base_color_factor = (0.05, 0.05, 0.08, 0.08)
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



