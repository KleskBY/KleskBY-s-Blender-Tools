import math

import bpy
import bmesh
from bpy.props import BoolProperty, FloatProperty, FloatVectorProperty

bl_info = {
    "name": "Fill Texture",
    "author": "KleskBY",
    "version": (1, 2),
    "blender": (3, 0, 0),
    "description": "Fill a texture over the object.",
    "category": "Scene",
}

# (property prefix, label). "ceiling" is the +Z side, "floor" the -Z side.
SURFACES = (("ceiling", "Top"), ("wall", "Wall"), ("floor", "Bottom"))


def object_props():
    """Per-object settings. Names are unchanged, so values saved in old .blend files still load."""
    props = {}
    for key, label in SURFACES:
        props[key + "_texture_scale_offset"] = FloatVectorProperty(
            name=label + " scale", default=(1, 1), step=10, precision=3, size=2)
        props[key + "_texture_rotation"] = FloatProperty(
            name=label + " rotation", description="Degrees", default=0, step=10, precision=3)
        props[key + "_texture_offset"] = FloatVectorProperty(
            name=label + " offset", default=(0, 0), step=10, precision=3, size=2)
    return props


def surface_params(obj):
    """{surface: (cos, sin, scale_u, scale_v, offset_u, offset_v)}, read once per object."""
    params = {}
    for key, _ in SURFACES:
        rot = math.radians(getattr(obj, key + "_texture_rotation"))
        sx, sy = getattr(obj, key + "_texture_scale_offset")
        ox, oy = getattr(obj, key + "_texture_offset")
        params[key] = (math.cos(rot), math.sin(rot), sx, sy, ox, oy)
    return params


def face_axis(n):
    """Dominant axis of a world-space normal: ('x'|'y'|'z', points_negative)."""
    ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
    if ax >= ay and ax >= az:
        return 'x', n.x < 0
    if ay >= az:
        return 'y', n.y < 0
    return 'z', n.z < 0


def planar_uv(axis, negative, p, fix_mirroring):
    """Project world position p onto the face plane. Returns (u, v, surface)."""
    if axis == 'x':
        u, v, surface, flip = p.y, p.z, "wall", negative
    elif axis == 'y':
        u, v, surface, flip = p.x, p.z, "wall", not negative
    else:
        u, v, surface, flip = p.x, p.y, ("floor" if negative else "ceiling"), negative
    # Seen from the front, the faces that point to -X, +Y and -Z run right to left.
    if fix_mirroring and flip:
        u = -u
    return u, v, surface


def fill_bmesh(bm, matrix_world, params, fix_mirroring, selected_only):
    """Write world-space planar UVs. Returns the number of faces filled."""
    bm.normal_update()
    normal_matrix = matrix_world.to_3x3().inverted_safe().transposed()
    uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.verify()

    world = {}  # vertex -> world position, each computed once
    count = 0
    for face in bm.faces:
        if selected_only and not face.select:
            continue
        normal = normal_matrix @ face.normal
        if normal.length_squared == 0.0:
            continue
        axis, negative = face_axis(normal)
        for loop in face.loops:
            vert = loop.vert
            p = world.get(vert)
            if p is None:
                p = world[vert] = matrix_world @ vert.co
            u, v, surface = planar_uv(axis, negative, p, fix_mirroring)
            c, s, sx, sy, ox, oy = params[surface]
            loop[uv_layer].uv = ((u * c - v * s) * sx + ox, (u * s + v * c) * sy + oy)
        count += 1
    return count


class FillTextureClass(bpy.types.Operator):
    """Project the texture onto the faces by world position, like TrenchBroom"""
    bl_idname = "scene.filltexture"
    bl_label = "FillTexture"
    bl_options = {'REGISTER', 'UNDO'}

    selected_faces_only: BoolProperty(
        name="Selected Faces Only",
        description="In Edit Mode, only fill the selected faces",
        default=True,
    )
    fix_mirroring: BoolProperty(
        name="Fix Mirrored Faces",
        description="Flip U on faces pointing to -X, +Y and -Z so the texture reads correctly from the front",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            return True
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        faces = 0
        skipped = 0

        if context.mode == 'EDIT_MESH':
            for obj in context.objects_in_mode_unique_data:
                if obj.type != 'MESH':
                    continue
                bm = bmesh.from_edit_mesh(obj.data)
                faces += fill_bmesh(bm, obj.matrix_world, surface_params(obj),
                                    self.fix_mirroring, self.selected_faces_only)
                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
            if not faces:
                self.report({'WARNING'}, "No faces selected")
                return {'CANCELLED'}
        else:
            done = set()
            for obj in context.selected_objects:
                if obj.type != 'MESH':
                    continue
                mesh = obj.data
                if mesh.as_pointer() in done:  # linked duplicates: the first object wins
                    skipped += 1
                    continue
                done.add(mesh.as_pointer())
                bm = bmesh.new()
                bm.from_mesh(mesh)
                faces += fill_bmesh(bm, obj.matrix_world, surface_params(obj), self.fix_mirroring, False)
                bm.to_mesh(mesh)
                bm.free()
                mesh.update()

        if skipped:
            self.report({'WARNING'}, "%d object(s) skipped: they share mesh data with another selected object" % skipped)
        self.report({'INFO'}, "Filled %d face(s)" % faces)
        return {'FINISHED'}


class TexturePanel(bpy.types.Panel):
    bl_label = "Texture"
    bl_idname = "TexturePanel_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = 'UI'
    bl_category = 'Texture'

    def draw(self, context):
        ob = context.active_object
        layout = self.layout
        if ob is None or ob.type != 'MESH':
            layout.label(text="Select a mesh object")
            return
        for key, label in SURFACES:
            box = layout.box()
            box.label(text=label)
            col = box.column(align=True)
            col.prop(ob, key + "_texture_scale_offset", text="Scale")
            col.prop(ob, key + "_texture_rotation", text="Rotation")
            col.prop(ob, key + "_texture_offset", text="Offset")
        layout.operator("scene.filltexture", text="APPLY", icon="MOD_BUILD")


def menu_func(self, context):
    self.layout.operator(FillTextureClass.bl_idname)


classes = (FillTextureClass, TexturePanel)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    for name, prop in object_props().items():
        setattr(bpy.types.Object, name, prop)
    bpy.types.VIEW3D_MT_object.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    for name in object_props():
        if hasattr(bpy.types.Object, name):
            delattr(bpy.types.Object, name)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
