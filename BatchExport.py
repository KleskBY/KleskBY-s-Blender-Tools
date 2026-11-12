bl_info = {
    "name": "Export Selected Objects as Separate FBX (Triangulated)",
    "author": "KleskBY",
    "version": (1, 2),
    "blender": (3, 0, 0),
    "location": "File > Export > Each Selected Object as FBX (Triangulated)",
    "description": "Export each selected object as its own FBX with triangulated faces and applied transforms.",
    "category": "Import-Export",
}

import bpy
import os
import re
from bpy.types import Operator
from bpy.props import BoolProperty, StringProperty

_BAD_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name):
    """Object names may contain characters a file name cannot ("/terrain", "*water1")."""
    return _BAD_FILENAME_CHARS.sub("_", name).strip(" .") or "object"


def export_paths(objs, folder):
    """One unique .fbx path per object (names that clash after cleaning get a number)."""
    used = set()
    paths = []
    for obj in objs:
        base = safe_filename(obj.name)
        name, n = base, 1
        while name.lower() in used:  # Windows file names are case-insensitive
            name = "%s_%d" % (base, n)
            n += 1
        used.add(name.lower())
        paths.append(os.path.join(folder, name + ".fbx"))
    return paths


class EXPORT_OT_each_object_as_fbx(Operator):
    """Export every selected mesh object to its own FBX file in a folder"""
    bl_idname = "export_scene.each_object_fbx"
    bl_label = "Export Each Selected Object as FBX"
    bl_options = {'REGISTER', 'UNDO'}

    directory: StringProperty(subtype='DIR_PATH')
    filter_folder: BoolProperty(default=True, options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        folder = bpy.path.abspath(self.directory)
        if not os.path.isdir(folder):
            self.report({'ERROR'}, "Selected path is not a folder: " + folder)
            return {'CANCELLED'}

        if context.object is not None and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if not meshes:
            self.report({'WARNING'}, "No mesh objects selected")
            return {'CANCELLED'}

        original_active = context.view_layer.objects.active
        original_selection = list(context.selected_objects)
        exported = 0
        failed = []

        try:
            for obj, path in zip(meshes, export_paths(meshes, folder)):
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                context.view_layer.objects.active = obj
                try:
                    bpy.ops.export_scene.fbx(
                        filepath=path,
                        use_selection=True,
                        apply_unit_scale=True,
                        apply_scale_options='FBX_SCALE_ALL',
                        object_types={'MESH'},
                        mesh_smooth_type='OFF',
                        bake_space_transform=True,
                        add_leaf_bones=False,
                        use_mesh_modifiers=True,
                        use_triangles=True,
                    )
                    exported += 1
                except RuntimeError as e:
                    failed.append(obj.name)
                    print("Batch FBX export failed for %s: %s" % (obj.name, e))
        finally:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in original_selection:
                obj.select_set(True)
            context.view_layer.objects.active = original_active

        if failed:
            self.report({'WARNING'}, "%d object(s) failed: %s" % (len(failed), ", ".join(failed[:5])))
        self.report({'INFO'}, "Exported %d object(s) to: %s" % (exported, folder))
        return {'FINISHED'} if exported else {'CANCELLED'}


def menu_func_export(self, context):
    self.layout.operator(EXPORT_OT_each_object_as_fbx.bl_idname, text="Each Selected Object as FBX (Triangulated)")


def register():
    bpy.utils.register_class(EXPORT_OT_each_object_as_fbx)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(EXPORT_OT_each_object_as_fbx)


if __name__ == "__main__":
    register()
