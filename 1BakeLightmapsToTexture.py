bl_info = {
    "name": "Texture Baker",
    "author": "KleskBY, Farhan Shaikh",
    "version": (1, 1),
    "blender": (3, 0, 0),
    "description": "Baker lightmaps and textures to a single image.",
    "category": "Scene",
}

import os
import traceback

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty


class BakerSettings(bpy.types.PropertyGroup):
    resolution: IntProperty(
        name="Texture resolution", default=2048, min=256, max=16384, step=256)
    margin: IntProperty(
        name="Margin (px)",
        description="Bake margin in pixels. UV islands are packed twice this far apart",
        default=4, min=0, max=64)
    use_direct: BoolProperty(name="Direct", default=True)
    use_indirect: BoolProperty(name="Indirect", default=False)
    use_color: BoolProperty(name="Color", default=True)
    ray_distance: FloatProperty(
        name="Max Ray Distance",
        description="Scene units; depends on the scale of your scene",
        default=0.1, min=0.0, precision=4)
    cage_extrusion: FloatProperty(
        name="Cage Extrusion",
        description="Scene units; depends on the scale of your scene",
        default=0.01, min=0.0, precision=4)
    device: EnumProperty(
        name="Device",
        items=[
            ('AUTO', "Auto", "GPU if one is enabled in the Cycles preferences, otherwise CPU"),
            ('CPU', "CPU", ""),
            ('GPU', "GPU", "Uses the devices enabled in the Cycles preferences"),
        ],
        default='AUTO')
    hide_original: BoolProperty(
        name="Hide Original", description="Hide the source object after baking", default=True)
    output_dir: StringProperty(
        name="Save To",
        description="Save the baked image as PNG in this folder. Empty packs it into the .blend",
        subtype='DIR_PATH', default="")


#    Helpers

def clean_mesh(mesh):
    """Merge doubles and flat shade (on a copy, never on the user's mesh)."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    bm.to_mesh(mesh)
    bm.free()
    mesh.polygons.foreach_set("use_smooth", [False] * len(mesh.polygons))
    if hasattr(mesh, "use_auto_smooth"):  # removed in Blender 4.1
        mesh.use_auto_smooth = False
    mesh.update()


def clone_clean(obj, name, collection):
    mesh = obj.data.copy()
    mesh.name = name
    clean_mesh(mesh)
    clone = obj.copy()
    clone.data = mesh
    clone.name = name
    clone.hide_viewport = False
    clone.hide_render = False
    collection.objects.link(clone)
    clone.hide_set(False)
    return clone


def remove_object(obj):
    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def select_only(context, objs, active):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objs:
        obj.select_set(True)
    context.view_layer.objects.active = active


def make_bake_material(name, image):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None) or nodes.new('ShaderNodeBsdfPrincipled')
    tex = nodes.new('ShaderNodeTexImage')
    tex.location = (-280, 80)
    tex.image = image
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    nodes.active = tex  # bake writes into the active image node
    tex.select = True
    return mat


def show_in_image_editors(context, image):
    if context.screen is None:  # background mode, no UI
        return
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            area.spaces.active.image = image


def store_image(image, folder):
    if folder:
        folder = bpy.path.abspath(folder)
        os.makedirs(folder, exist_ok=True)
        image.filepath_raw = os.path.join(folder, bpy.path.clean_name(image.name) + ".png")
        image.file_format = 'PNG'
        image.save()
    else:
        image.pack()


def gpu_available(context):
    """True if the Cycles preferences have a GPU device switched on."""
    addon = context.preferences.addons.get("cycles")
    if addon is None:
        return False
    prefs = addon.preferences
    if prefs.compute_device_type == 'NONE':
        return False
    prefs.get_devices()
    return any(d.use and d.type != 'CPU' for d in prefs.devices)


def save_scene_state(scene):
    r, b, c = scene.render, scene.render.bake, scene.cycles
    return {
        "engine": r.engine, "device": c.device, "bake_type": c.bake_type,
        "direct": b.use_pass_direct, "indirect": b.use_pass_indirect, "color": b.use_pass_color,
        "clear": b.use_clear, "selected_to_active": b.use_selected_to_active,
        "cage_extrusion": b.cage_extrusion, "ray_distance": b.max_ray_distance, "margin": b.margin,
    }


def restore_scene_state(scene, st):
    r, b, c = scene.render, scene.render.bake, scene.cycles
    r.engine = st["engine"]
    c.device, c.bake_type = st["device"], st["bake_type"]
    b.use_pass_direct, b.use_pass_indirect, b.use_pass_color = st["direct"], st["indirect"], st["color"]
    b.use_clear, b.use_selected_to_active = st["clear"], st["selected_to_active"]
    b.cage_extrusion, b.max_ray_distance, b.margin = st["cage_extrusion"], st["ray_distance"], st["margin"]


def configure_bake(scene, cfg, use_gpu):
    r, b, c = scene.render, scene.render.bake, scene.cycles
    r.engine = 'CYCLES'
    c.device = 'GPU' if use_gpu else 'CPU'
    c.bake_type = 'DIFFUSE'
    b.use_pass_direct = cfg.use_direct
    b.use_pass_indirect = cfg.use_indirect
    b.use_pass_color = cfg.use_color
    b.use_clear = False
    b.use_selected_to_active = True
    b.cage_extrusion = cfg.cage_extrusion
    b.max_ray_distance = cfg.ray_distance
    b.margin = cfg.margin


def bake_object(context, obj, cfg):
    """
    Bake obj's look onto a fresh single-image copy ("<name>cln").
    obj itself is not modified. Returns the new object.
    """
    collection = obj.users_collection[0] if obj.users_collection else context.scene.collection
    was_hide_render = obj.hide_render
    src = dst = image = mat = None
    done = False
    try:
        # src: cleaned copy of the original, the bake source. dst: the bake target.
        src = clone_clean(obj, obj.name + "_bakesrc", collection)
        dst = clone_clean(obj, obj.name + "cln", collection)

        image = bpy.data.images.new(dst.name, cfg.resolution, cfg.resolution, alpha=False)
        image.generated_color = (0.1, 0.1, 0.1, 1)
        mat = make_bake_material(dst.name, image)
        dst.data.materials.clear()
        dst.data.materials.append(mat)
        if not dst.data.uv_layers:
            dst.data.uv_layers.new(name="UVMap")

        select_only(context, [dst], dst)
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(angle_limit=0.523599, island_margin=2 * cfg.margin / cfg.resolution,
                                     correct_aspect=True, scale_to_bounds=False)
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')

        # The original would otherwise render on top of src and shade it.
        obj.hide_render = True
        select_only(context, [src, dst], dst)
        bpy.ops.object.bake(type='DIFFUSE')

        store_image(image, cfg.output_dir)
        show_in_image_editors(context, image)
        if cfg.hide_original:
            obj.hide_set(True)
        done = True
        return dst
    finally:
        obj.hide_render = was_hide_render
        if src is not None:
            remove_object(src)
        if not done:
            if dst is not None:
                remove_object(dst)
            if mat is not None:
                bpy.data.materials.remove(mat)
            if image is not None:
                bpy.data.images.remove(image)


#    Operator and UI

class BakerClass(bpy.types.Operator):
    """Bake the selected meshes to one image each"""
    bl_idname = "scene.baketexture"
    bl_label = "BakeTexture"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode in {'OBJECT', 'EDIT_MESH'}
                and any(o.type == 'MESH' for o in context.selected_objects))

    def execute(self, context):
        scene = context.scene
        cfg = scene.kleskby_baker

        if context.object is not None and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        targets = [o for o in context.selected_objects if o.type == 'MESH' and len(o.data.polygons)]
        if not targets:
            self.report({'ERROR'}, "Select at least one mesh with faces")
            return {'CANCELLED'}
        if not hasattr(scene, "cycles"):
            self.report({'ERROR'}, "The Cycles add-on is disabled")
            return {'CANCELLED'}

        use_gpu = cfg.device == 'GPU' or (cfg.device == 'AUTO' and gpu_available(context))
        state = save_scene_state(scene)
        baked = []
        failed = []
        try:
            configure_bake(scene, cfg, use_gpu)
            for obj in targets:
                try:
                    baked.append(bake_object(context, obj, cfg))
                    self.report({'INFO'}, "Baked " + obj.name)
                except Exception as e:
                    failed.append(obj.name)
                    traceback.print_exc()
                    self.report({'WARNING'}, "%s: %s" % (obj.name, e))
        finally:
            restore_scene_state(scene, state)

        if baked:
            select_only(context, baked, baked[-1])
        if failed:
            self.report({'ERROR'}, "%d object(s) failed: %s" % (len(failed), ", ".join(failed)))
        if not baked:
            return {'CANCELLED'}
        self.report({'INFO'}, "Baked %d object(s) on %s" % (len(baked), "GPU" if use_gpu else "CPU"))
        return {'FINISHED'}


class BakerPanel(bpy.types.Panel):
    bl_label = "Baker"
    bl_space_type = "VIEW_3D"
    bl_region_type = 'UI'
    bl_category = 'Baker'

    def draw(self, context):
        cfg = context.scene.kleskby_baker
        layout = self.layout

        col = layout.column(align=True)
        col.prop(cfg, "resolution")
        col.prop(cfg, "margin")

        layout.label(text="Bake")
        row = layout.row(align=True)
        row.prop(cfg, "use_direct", toggle=True)
        row.prop(cfg, "use_indirect", toggle=True)
        row.prop(cfg, "use_color", toggle=True)

        col = layout.column(align=True)
        col.prop(cfg, "ray_distance")
        col.prop(cfg, "cage_extrusion")

        col = layout.column()
        col.prop(cfg, "device")
        col.prop(cfg, "hide_original")
        col.prop(cfg, "output_dir")

        layout.operator("scene.baketexture", text="BAKE")


def menu_func(self, context):
    self.layout.operator(BakerClass.bl_idname)


classes = (BakerSettings, BakerClass, BakerPanel)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.kleskby_baker = bpy.props.PointerProperty(type=BakerSettings)
    bpy.types.VIEW3D_MT_object.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    del bpy.types.Scene.kleskby_baker
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
