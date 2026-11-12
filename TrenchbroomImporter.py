bl_info = {
    "name": "TrenchBroom Importer",
    "author": "KleskBY",
    "version": (1, 4),
    "blender": (3, 6, 3),
    "location": "View3D > Sidebar > TrenchBroom Importer",
    "description": "Import OBJ from TrenchBroom, clean and auto-attach textures",
    "category": "Import-Export",
}

import bpy
import bmesh
import os
import re
import math

BAD_MATERIALS = [
    "caulk", "clip", "null", "full_clip", "missileclip", "trigger",
    "AAATRIGGER", "HINT", "skip", "TRANSLUCENT", "sky", "CONTENTWATER",
    "CONTENTSKY", "origin", "botclip", "invisible", "nodraw", "nodrop",
    "weapclip", "slick"
]

TEXTURES_TO_SKIP = [
    "clip", "*water1", "sky1", "lampbulb", "crate01", "crate02", "crate03",
    "box01", "box02", "box03", "box04", "box05", "crate1", "crate2"
]

_BAD_SET = {m.lower() for m in BAD_MATERIALS}
_SKIP_SET = {m.lower() for m in TEXTURES_TO_SKIP}


#    Shared helpers (keep this block identical in auto_texture_attach.py)

TEXTURE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".dds"}
PREFERRED_EXTS = (".png", ".tga", ".dds", ".jpg", ".jpeg")

# Blender's duplicate suffix: ".001", ".002", ... ".1000"
_DUP_SUFFIX = re.compile(r"\.\d{3,}$")

# { normalized_root: {"by_rel": {rel_lower: abs_path}, "by_name": {name_lower: [abs_paths]}, "root": root} }
_TEXTURE_INDEX_CACHE = {}


def strip_dup_suffix(name):
    return _DUP_SUFFIX.sub("", name)


def _norm_key(p):
    return os.path.normpath(p).replace("\\", "/").lower()


def clear_texture_index():
    """Forget the scanned texture folder. Call at the start of every run so new files are found."""
    _TEXTURE_INDEX_CACHE.clear()


def _build_texture_index(root):
    root = os.path.abspath(root)
    root_key = _norm_key(root)

    cached = _TEXTURE_INDEX_CACHE.get(root_key)
    if cached:
        return cached

    by_rel = {}
    by_name = {}
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() not in TEXTURE_EXTS:
                continue
            abs_path = os.path.join(dirpath, fn)
            by_rel.setdefault(_norm_key(os.path.relpath(abs_path, root)), abs_path)
            by_name.setdefault(fn.lower(), []).append(abs_path)

    idx = {"by_rel": by_rel, "by_name": by_name, "root": root}
    _TEXTURE_INDEX_CACHE[root_key] = idx
    return idx


def find_texture(material_name, search_path):
    """
    Case-insensitive lookup. material_name may be a plain name ("brick01") or a
    path relative to the folder without extension ("textures/brick/brick01").
    """
    if not search_path or not os.path.isdir(search_path):
        return None

    idx = _build_texture_index(search_path)
    root = idx["root"]

    key = strip_dup_suffix(material_name).strip()
    key_norm = os.path.normpath(key).replace("\\", "/")

    # 1) exact relative path
    for ext in PREFERRED_EXTS:
        hit = idx["by_rel"].get(_norm_key(key_norm + ext))
        if hit and os.path.isfile(hit):
            return hit

    # 2) file name only, closest to the root first
    filename_only = os.path.basename(key_norm)
    for ext in PREFERRED_EXTS:
        hits = idx["by_name"].get((filename_only + ext).lower())
        if hits:
            hits = sorted(hits, key=lambda p: len(os.path.relpath(p, root)))
            for p in hits:
                if os.path.isfile(p):
                    return p
    return None


def material_has_image(mat):
    tree = mat.node_tree if mat.use_nodes else None
    return tree is not None and any(n.type == 'TEX_IMAGE' and n.image for n in tree.nodes)


def apply_texture(material, texture_path, overwrite=False):
    """
    Build Image Texture -> Principled BSDF -> Material Output.
    A material that already has an image is left alone unless overwrite is set.
    Returns True when the material was changed.
    """
    if not overwrite and material_has_image(material):
        return False

    if not material.use_nodes:
        material.use_nodes = True

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    tex_node = nodes.new(type='ShaderNodeTexImage')
    bsdf_node = nodes.new(type='ShaderNodeBsdfPrincipled')
    output_node = nodes.new(type='ShaderNodeOutputMaterial')

    tex_node.location = (-400, 0)
    bsdf_node.location = (0, 0)
    output_node.location = (400, 0)

    tex_node.image = bpy.data.images.load(texture_path, check_existing=True)

    links.new(tex_node.outputs['Color'], bsdf_node.inputs['Base Color'])
    links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
    return True


def replace_duplicate_materials():
    """
    Merge "Name.001" style copies into "Name" and delete the copies.
    The survivor is the material that already has an image (the original if several
    do, or if none does), so a texture is never thrown away. It ends up named "Name".
    Returns the number of materials removed.
    """
    groups = {}
    for mat in bpy.data.materials:
        if mat.library is not None:
            continue
        m = _DUP_SUFFIX.search(mat.name)
        if m:
            groups.setdefault(mat.name[:m.start()], []).append(mat)

    removed = 0
    for base, dupes in groups.items():
        members = sorted(dupes, key=lambda mat: mat.name)
        original = bpy.data.materials.get(base)
        if original is not None:
            members.insert(0, original)

        survivor = next((mat for mat in members if material_has_image(mat)), members[0])
        for mat in members:
            if mat is survivor:
                continue
            mat.user_remap(survivor)
            mat.use_fake_user = False
            if mat.users == 0:
                bpy.data.materials.remove(mat)
                removed += 1
        if survivor.name != base:
            survivor.name = base
    return removed


#    Importer

def base_material_name(name):
    """Lower case, without ".001" suffix and without a leading textures/ or common/."""
    name = strip_dup_suffix(name).lower().replace("\\", "/")
    for prefix in ("textures/", "common/"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name


def is_bad_material(mat_name):
    return base_material_name(mat_name) in _BAD_SET


def uses_skip_material(obj):
    return any(m is not None and base_material_name(m.name) in _SKIP_SET
               for m in obj.data.materials)


def materials_of(objs):
    mats = {}
    for obj in objs:
        if obj.type == 'MESH':
            for mat in obj.data.materials:
                if mat is not None:
                    mats[mat.as_pointer()] = mat
    return list(mats.values())


def remove_bad_faces(mesh, bad_materials):
    """
    Delete faces that use a bad material and drop those material slots.
    The bad materials are added to bad_materials ({pointer: material}). Returns the face count.
    """
    bad = {i for i, mat in enumerate(mesh.materials) if mat is not None and is_bad_material(mat.name)}
    if not bad:
        return 0
    for i in bad:
        mat = mesh.materials[i]
        bad_materials[mat.as_pointer()] = mat

    bm = bmesh.new()
    bm.from_mesh(mesh)
    faces = [f for f in bm.faces if f.material_index in bad]
    bmesh.ops.delete(bm, geom=faces, context='FACES')
    bm.to_mesh(mesh)
    bm.free()

    for i in sorted(bad, reverse=True):
        mesh.materials.pop(index=i)
    return len(faces)


def merge_by_entity(meshes):
    """Join all brushes of an entity ("entity3_brush7" -> "entity3"). Returns objects absorbed."""
    groups = {}
    for obj in sorted(meshes, key=lambda o: o.name):
        groups.setdefault(obj.name.split("_")[0], []).append(obj)

    merged = 0
    for entity, members in groups.items():
        if entity == "entity0":
            members = [o for o in members if not uses_skip_material(o)]
        if len(members) < 2:
            continue
        absorbed = [o.data for o in members[1:]]
        bpy.ops.object.select_all(action='DESELECT')
        for obj in members:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = members[0]
        bpy.ops.object.join()
        for mesh in absorbed:  # join leaves the old meshes behind, still holding their materials
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        merged += len(members) - 1
    return merged


def apply_shading(objs, clear, autosmooth):
    for obj in objs:
        if obj.type != 'MESH':
            continue
        mesh = obj.data

        if clear:
            if mesh.has_custom_normals:
                bpy.context.view_layer.objects.active = obj
                bpy.ops.mesh.customdata_custom_splitnormals_clear()
            mesh.edges.foreach_set("use_edge_sharp", [False] * len(mesh.edges))

        if clear or autosmooth:
            mesh.polygons.foreach_set("use_smooth", [bool(autosmooth)] * len(mesh.polygons))

        if autosmooth:
            mesh.use_auto_smooth = True
            mesh.auto_smooth_angle = math.radians(45)

        mesh.update()


def import_trenchbroom_obj(filepath, settings):
    stats = {"objects": 0, "bad_faces": 0, "emptied": 0, "merged": 0,
             "duplicates": 0, "textured": 0, "missing": []}

    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.obj(filepath=filepath)
    imported = list(bpy.context.selected_objects)
    if not imported:
        return stats

    # Scale everything first, then apply once (one operator call, not one per object).
    for obj in imported:
        obj.scale = (settings.scale,) * 3
    if settings.apply_transform:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in imported:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = imported[0]
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    parent_name = os.path.splitext(os.path.basename(filepath))[0]
    parent_empty = bpy.data.objects.new(parent_name, None)
    bpy.context.collection.objects.link(parent_empty)
    for obj in imported:
        obj.parent = parent_empty

    if settings.delete_bad_faces:
        survivors = []
        bad_materials = {}
        for obj in imported:
            if obj.type != 'MESH':
                survivors.append(obj)
                continue
            stats["bad_faces"] += remove_bad_faces(obj.data, bad_materials)
            if len(obj.data.polygons) == 0:
                mesh = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
                stats["emptied"] += 1
            else:
                survivors.append(obj)
        imported = survivors
        for mat in bad_materials.values():  # caulk, clip, ... nothing uses them any more
            if mat.users == 0:
                bpy.data.materials.remove(mat)

    if settings.ensure_prefix:
        for mat in materials_of(imported):
            if mat.library is None and not mat.name.lower().startswith("textures/"):
                mat.name = "textures/" + mat.name

    if settings.merge_by_entity:
        stats["merged"] = merge_by_entity([o for o in imported if o.type == 'MESH'])
        imported = list(parent_empty.children_recursive)  # joined objects are gone

    stats["objects"] = len(imported)

    # Merge duplicates before loading textures so no image is loaded for a copy.
    if settings.remove_duplicates:
        stats["duplicates"] = replace_duplicate_materials()

    if settings.clear_normals or settings.use_autosmooth:
        apply_shading(imported, settings.clear_normals, settings.use_autosmooth)

    if settings.auto_texture:
        clear_texture_index()
        for mat in materials_of(imported):
            path = find_texture(mat.name, settings.texture_folder)
            if path is None:
                stats["missing"].append(mat.name)
            elif apply_texture(mat, path):
                stats["textured"] += 1

    return stats


#    UI

class TrenchbroomSettings:
    def __init__(self, context):
        scene = context.scene
        self.texture_folder = bpy.path.abspath(scene.trenchbroom_texture_folder)
        self.scale = scene.trenchbroom_scale
        self.apply_transform = scene.trenchbroom_apply_transform
        self.delete_bad_faces = scene.trenchbroom_delete_faces
        self.ensure_prefix = scene.trenchbroom_prefix_textures
        self.merge_by_entity = scene.trenchbroom_merge_entities
        self.clear_normals = scene.trenchbroom_clear_normals
        self.use_autosmooth = scene.trenchbroom_use_autosmooth
        self.auto_texture = scene.trenchbroom_auto_texture
        self.remove_duplicates = scene.trenchbroom_remove_duplicates


class IMPORT_OT_trenchbroom(bpy.types.Operator):
    bl_idname = "import_scene.trenchbroom"
    bl_label = "Import TrenchBroom OBJ"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.obj", options={'HIDDEN'})

    def execute(self, context):
        if not os.path.isfile(self.filepath):
            self.report({'ERROR'}, "File not found: " + self.filepath)
            return {'CANCELLED'}

        if context.object is not None and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        settings = TrenchbroomSettings(context)
        if settings.auto_texture and not os.path.isdir(settings.texture_folder):
            self.report({'WARNING'}, "Texture folder not found, textures will not be attached")

        stats = import_trenchbroom_obj(self.filepath, settings)

        if stats["missing"]:
            print("TrenchBroom Importer: no texture for:", ", ".join(sorted(stats["missing"])))

        parts = ["%d objects" % stats["objects"]]
        for key, label in (("bad_faces", "bad faces removed"), ("emptied", "empty objects removed"),
                           ("merged", "brushes merged"), ("duplicates", "duplicate materials removed"),
                           ("textured", "textures attached")):
            if stats[key]:
                parts.append("%d %s" % (stats[key], label))
        self.report({'INFO'}, "TrenchBroom OBJ imported: " + ", ".join(parts))
        if stats["missing"]:
            self.report({'WARNING'}, "%d material(s) without texture (see console)" % len(stats["missing"]))
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class VIEW3D_PT_trenchbroom(bpy.types.Panel):
    bl_label = "TrenchBroom Importer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "TrenchBroom"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(context.scene, "trenchbroom_texture_folder")
        col.prop(context.scene, "trenchbroom_scale")
        col.prop(context.scene, "trenchbroom_apply_transform")
        col.prop(context.scene, "trenchbroom_delete_faces")
        col.prop(context.scene, "trenchbroom_prefix_textures")
        col.prop(context.scene, "trenchbroom_merge_entities")
        col.prop(context.scene, "trenchbroom_clear_normals")
        col.prop(context.scene, "trenchbroom_use_autosmooth")
        col.prop(context.scene, "trenchbroom_auto_texture")
        col.prop(context.scene, "trenchbroom_remove_duplicates")
        layout.operator("import_scene.trenchbroom", text="Import TrenchBroom OBJ")


classes = [IMPORT_OT_trenchbroom, VIEW3D_PT_trenchbroom]

SCENE_PROPS = {
    "trenchbroom_texture_folder": lambda: bpy.props.StringProperty(
        name="Texture Folder", subtype="DIR_PATH", default=r"D:\Heptyl\Assets"),
    "trenchbroom_scale": lambda: bpy.props.FloatProperty(
        name="Scale", description="Uniform scale applied to the imported objects",
        default=0.025, min=0.000001, precision=4),
    "trenchbroom_apply_transform": lambda: bpy.props.BoolProperty(
        name="Apply Transforms", default=True),
    "trenchbroom_delete_faces": lambda: bpy.props.BoolProperty(
        name="Delete empty faces", default=True),
    "trenchbroom_prefix_textures": lambda: bpy.props.BoolProperty(
        name="Ensure 'textures/' Prefix", default=True),
    "trenchbroom_merge_entities": lambda: bpy.props.BoolProperty(
        name="Merge Brushes by Entity", default=True),
    "trenchbroom_clear_normals": lambda: bpy.props.BoolProperty(
        name="Clear Normals & Flat Shade", default=True),
    "trenchbroom_use_autosmooth": lambda: bpy.props.BoolProperty(
        name="Use Autosmooth", default=True),
    "trenchbroom_auto_texture": lambda: bpy.props.BoolProperty(
        name="Auto-Assign Textures", default=True),
    "trenchbroom_remove_duplicates": lambda: bpy.props.BoolProperty(
        name="Remove Duplicate Materials", default=True),
}


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    for name, make in SCENE_PROPS.items():
        setattr(bpy.types.Scene, name, make())


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    for name in SCENE_PROPS:
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)


if __name__ == "__main__":
    register()
