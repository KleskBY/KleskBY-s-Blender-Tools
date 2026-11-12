bl_info = {
    "name": "Auto Texture from Material Name",
    "author": "KleskBY",
    "version": (1, 1),
    "blender": (2, 80, 0),
    "location": "3D Viewport > Object",
    "description": "Attach texture based on material name, remove material duplicates",
    "category": "Material",
}

import bpy
import os
import re
from bpy.types import AddonPreferences, Operator
from bpy.props import BoolProperty, StringProperty


#    Addon Preferences

class AutoTextureAddonPreferences(AddonPreferences):
    bl_idname = __name__

    texture_search_path: StringProperty(
        name="Texture Folder Path",
        description="Folder to search for textures (recursively)",
        subtype='DIR_PATH',
        default="D:\\GameDev\\ObjectN\\data"
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Set the path to your texture directory:")
        layout.prop(self, "texture_search_path")


#    Shared helpers (keep this block identical in TrenchbroomImporter.py)

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


#    Operator

class MATERIAL_OT_attach_textures(Operator):
    bl_idname = "material.attach_textures_from_names"
    bl_label = "Attach Textures from Material Names"
    bl_description = "Attach textures to materials based on name and remove duplicates"
    bl_options = {'REGISTER', 'UNDO'}

    merge_duplicates: BoolProperty(
        name="Merge Duplicate Materials",
        description="Merge Name.001 style copies into the original and delete them",
        default=True,
    )
    attach_textures: BoolProperty(
        name="Attach Textures",
        description="Look up a texture file for every material by its name",
        default=True,
    )
    overwrite: BoolProperty(
        name="Overwrite Textured Materials",
        description="Also rebuild materials that already have an image texture "
                    "(this wipes their node tree)",
        default=False,
    )

    def execute(self, context):
        addon = context.preferences.addons.get(__name__)
        if addon is None:
            self.report({'ERROR'}, "Enable the add-on first (it is not running from the Text Editor)")
            return {'CANCELLED'}
        search_path = bpy.path.abspath(addon.preferences.texture_search_path)

        if self.attach_textures and not os.path.isdir(search_path):
            self.report({'ERROR'}, "Texture folder not found: " + search_path)
            return {'CANCELLED'}

        # Merge first so no texture is loaded for a material that is about to go.
        removed = replace_duplicate_materials() if self.merge_duplicates else 0

        attached = 0
        missing = []
        if self.attach_textures:
            clear_texture_index()  # pick up files added since the last run
            for mat in bpy.data.materials:
                if mat.library is not None or mat.is_grease_pencil or mat.users == 0:
                    continue
                tex_path = find_texture(mat.name, search_path)
                if tex_path is None:
                    missing.append(mat.name)
                elif apply_texture(mat, tex_path, self.overwrite):
                    attached += 1

        if missing:
            print("Auto Texture: no texture for:", ", ".join(sorted(missing)))
        self.report({'INFO'}, "%d texture(s) attached, %d duplicate material(s) removed" % (attached, removed))
        if missing:
            self.report({'WARNING'}, "%d material(s) without texture (see console)" % len(missing))
        return {'FINISHED'}


#    Registration

classes = (
    AutoTextureAddonPreferences,
    MATERIAL_OT_attach_textures,
)


def menu_func(self, context):
    self.layout.operator(MATERIAL_OT_attach_textures.bl_idname)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_object.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
