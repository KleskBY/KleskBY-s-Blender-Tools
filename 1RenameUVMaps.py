bl_info = {
    "name": "Rename UV Maps",
    "author": "KleskBY",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "Properties > Object Data > UV Maps, 3D Viewport > Object > Clean Up",
    "description": "Rename the active UV map of many meshes to one common name.",
    "category": "UV",
}

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

TEMP_NAME = "__uv_rename_tmp__"


def collect_meshes(context, scope):
    """Return every mesh datablock in scope exactly once (linked duplicates share one mesh)."""
    if scope == 'ALL':
        return [m for m in bpy.data.meshes if m.users]

    if scope == 'SCENE':
        objs = list(context.scene.objects)
    else:
        objs = list(context.selected_objects)
        if context.active_object is not None:
            objs.append(context.active_object)

    meshes = {o.data.as_pointer(): o.data for o in objs if o.type == 'MESH'}
    return list(meshes.values())


def pick_layer(mesh, target):
    layers = mesh.uv_layers
    if not layers:
        return None
    if target == 'FIRST':
        return layers[0]
    if target == 'RENDER':
        for layer in layers:
            if layer.active_render:
                return layer
    return layers.active or layers[0]


def rename_layer(mesh, layer, name):
    """Give `layer` the name `name`. Returns the {old: new} name mapping that was applied."""
    old = layer.name
    if old == name:
        return {}

    other = mesh.uv_layers.get(name)
    if other is None:
        layer.name = name
        return {old: name}

    # UV map names are unique per mesh. A plain rename would silently turn into
    # "UVMap.001", so swap the two names instead.
    other.name = TEMP_NAME
    layer.name = name
    other.name = old
    return {old: name, name: old}


def remap_uv_nodes(mesh, mapping, done):
    """UV Map shader nodes reference a map by name; retarget them so materials keep working."""
    key_map = tuple(sorted(mapping.items()))
    stack = [m.node_tree for m in mesh.materials
             if m is not None and m.node_tree is not None and m.library is None]
    changed = 0
    while stack:
        tree = stack.pop()
        key = (tree.as_pointer(), key_map)
        if key in done:
            continue
        done.add(key)
        for node in tree.nodes:
            if node.type == 'UVMAP' and node.uv_map in mapping:
                node.uv_map = mapping[node.uv_map]
                changed += 1
            elif node.type == 'GROUP' and node.node_tree is not None and node.node_tree.library is None:
                stack.append(node.node_tree)
    return changed


class OBJECT_OT_rename_uv_maps(bpy.types.Operator):
    """Rename the active UV map of the chosen meshes to one common name"""
    bl_idname = "object.rename_uv_maps"
    bl_label = "Rename UV Maps"
    bl_options = {'REGISTER', 'UNDO'}

    uv_name: StringProperty(
        name="Name",
        description="New name for the UV map",
        default="UVMap",
        maxlen=63,
    )
    scope: EnumProperty(
        name="Meshes",
        description="Which meshes to process",
        items=[
            ('SELECTED', "Selected", "Selected objects and the active object"),
            ('SCENE', "Scene", "Every mesh object in the current scene"),
            ('ALL', "All Data", "Every mesh in the file, including other scenes"),
        ],
        default='SELECTED',
    )
    target: EnumProperty(
        name="UV Map",
        description="Which UV map of each mesh to rename",
        items=[
            ('ACTIVE', "Active", "The UV map selected in the UV Maps list"),
            ('RENDER', "Active Render", "The UV map flagged for rendering (camera icon)"),
            ('FIRST', "First", "The first UV map in the list"),
        ],
        default='ACTIVE',
    )
    fix_nodes: BoolProperty(
        name="Update UV Map Nodes",
        description="Retarget UV Map shader nodes that reference a renamed map, "
                    "so materials do not lose their UVs",
        default=True,
    )
    log: BoolProperty(
        name="Log to Console",
        description="Print every rename to the system console",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "uv_name")
        col.prop(self, "scope")
        col.prop(self, "target")
        col.prop(self, "fix_nodes")
        col.prop(self, "log")

    def execute(self, context):
        name = self.uv_name.strip()
        if not name:
            self.report({'ERROR'}, "UV map name is empty")
            return {'CANCELLED'}

        # Edit-mode meshes hold their UV layers in a BMesh; leave edit mode so
        # renames land on the real mesh data.
        was_edit = context.mode == 'EDIT_MESH'
        if was_edit:
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            meshes = collect_meshes(context, self.scope)
            if not meshes:
                self.report({'WARNING'}, "No mesh objects to process")
                return {'CANCELLED'}
            stats = self.process(meshes, name)
        finally:
            if was_edit:
                bpy.ops.object.mode_set(mode='EDIT')

        labels = (
            ('renamed', "renamed"),
            ('swapped', "swapped with an existing map"),
            ('same', "already named"),
            ('no_uv', "without UV map"),
            ('linked', "linked (skipped)"),
            ('nodes', "UV Map node(s) retargeted"),
        )
        parts = ["%d %s" % (stats[key], text) for key, text in labels if stats[key]]
        self.report({'INFO'}, "UV maps: " + (", ".join(parts) or "nothing to do"))
        return {'FINISHED'}

    def process(self, meshes, name):
        stats = dict.fromkeys(('renamed', 'swapped', 'same', 'no_uv', 'linked', 'nodes'), 0)
        done = set()

        for mesh in meshes:
            if mesh.library is not None:
                stats['linked'] += 1
                continue

            layer = pick_layer(mesh, self.target)
            if layer is None:
                stats['no_uv'] += 1
                if self.log:
                    print("%s: no UV map" % mesh.name)
                continue

            old = layer.name
            mapping = rename_layer(mesh, layer, name)
            if not mapping:
                stats['same'] += 1
                continue

            stats['swapped' if len(mapping) == 2 else 'renamed'] += 1
            if self.fix_nodes:
                stats['nodes'] += remap_uv_nodes(mesh, mapping, done)
            if self.log:
                print("%s: %s -> %s%s" % (mesh.name, old, layer.name,
                                          " (swapped)" if len(mapping) == 2 else ""))
        return stats


def menu_func(self, context):
    self.layout.operator(OBJECT_OT_rename_uv_maps.bl_idname, text="Rename UV Maps...", icon='GROUP_UVS')


def panel_func(self, context):
    self.layout.operator(OBJECT_OT_rename_uv_maps.bl_idname, text="Rename UV Maps...", icon='GROUP_UVS')


def register():
    bpy.utils.register_class(OBJECT_OT_rename_uv_maps)
    bpy.types.VIEW3D_MT_object_cleanup.append(menu_func)
    bpy.types.DATA_PT_uv_texture.append(panel_func)


def unregister():
    bpy.types.DATA_PT_uv_texture.remove(panel_func)
    bpy.types.VIEW3D_MT_object_cleanup.remove(menu_func)
    bpy.utils.unregister_class(OBJECT_OT_rename_uv_maps)


# Allows running the script directly from Blender's Text editor.
if __name__ == "__main__":
    register()
