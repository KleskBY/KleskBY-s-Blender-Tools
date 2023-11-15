

from copy import copy
import os
import math
import bpy
import bmesh
import addon_utils
from bpy_extras.io_utils import ImportHelper

bl_info = {
    "name": "Fill Texture",
    "author": "KleskBY",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "description": "Fill a texture over the object.",
    "category": "Scene",
}

bpy.types.Object.ceiling_texture_scale_offset = bpy.props.FloatVectorProperty(
    name="Top scale",
    default=(1, 1),
    min=0,
    step=10,
    precision=3,
    size=2
)
bpy.types.Object.wall_texture_scale_offset = bpy.props.FloatVectorProperty(
    name="Wall Scale",
    default=(1, 1),
    min=0,
    step=10,
    precision=3,
    size=2
)
bpy.types.Object.floor_texture_scale_offset = bpy.props.FloatVectorProperty(
    name="Bottom Scale",
    default=(1, 1),
    min=0,
    step=10,
    precision=3,
    size=2
)
bpy.types.Object.ceiling_texture_rotation = bpy.props.FloatProperty(
    name="Top rotation",
    default=0,
    min=0,
    step=10,
    precision=3,
)
bpy.types.Object.wall_texture_rotation = bpy.props.FloatProperty(
    name="Wall rotation",
    default=0,
    min=0,
    step=10,
    precision=3,
)
bpy.types.Object.floor_texture_rotation = bpy.props.FloatProperty(
    name="Bottom rotation",
    default=0,
    min=0,
    step=10,
    precision=3,
)

bpy.types.Object.ceiling_texture_offset = bpy.props.FloatVectorProperty(
    name="Top offset",
    default=(0, 0),
    min=0,
    step=10,
    precision=3,
    size=2
)
bpy.types.Object.wall_texture_offset = bpy.props.FloatVectorProperty(
    name="Wall offset",
    default=(0, 0),
    min=0,
    step=10,
    precision=3,
    size=2
)
bpy.types.Object.floor_texture_offset = bpy.props.FloatVectorProperty(
    name="Bottom offset",
    default=(0, 0),
    min=0,
    step=10,
    precision=3,
    size=2
)

class FillTextureClass(bpy.types.Operator):
    """FillTexture"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "scene.filltexture"        # Unique identifier for buttons and menu items to reference.
    bl_label = "FillTexture"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def translate(val, t):
        return val + t

    def scale(val, s):
        return val * s

    def rotate2D(uv, degrees):
        radians = math.radians(degrees)
        newUV = copy(uv)
        newUV.x = uv.x*math.cos(radians) - uv.y*math.sin(radians)
        newUV.y = uv.x*math.sin(radians) + uv.y*math.cos(radians)
        return newUV

    def auto_texture(source_obj):
        mesh = source_obj.data
        objectLocation = source_obj.location
        objectScale = source_obj.scale
        
        bm = bmesh.new()
        bm.from_mesh(mesh)

        uv_layer = bm.loops.layers.uv.verify()
        for f in bm.faces:
            nX = f.normal.x
            nY = f.normal.y
            nZ = f.normal.z
            if nX < 0:
                nX = nX * -1
            if nY < 0:
                nY = nY * -1
            if nZ < 0:
                nZ = nZ * -1
            faceNormalLargest = nX
            faceDirection = "x"
            if faceNormalLargest < nY:
                faceNormalLargest = nY
                faceDirection = "y"
            if faceNormalLargest < nZ:
                faceNormalLargest = nZ
                faceDirection = "z"
            if faceDirection == "x":
                if f.normal.x < 0:
                    faceDirection = "-x"
            if faceDirection == "y":
                if f.normal.y < 0:
                    faceDirection = "-y"
            if faceDirection == "z":
                if f.normal.z < 0:
                    faceDirection = "-z"
            for l in f.loops:
                luv = l[uv_layer]
                if faceDirection == "x":
                    luv.uv.x = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                    luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                    luv.uv = FillTextureClass.rotate2D(luv.uv, source_obj.wall_texture_rotation)
                    luv.uv.x = FillTextureClass.translate(FillTextureClass.scale(luv.uv.x, source_obj.wall_texture_scale_offset[0]), 0)
                    luv.uv.y = FillTextureClass.translate(FillTextureClass.scale(luv.uv.y, source_obj.wall_texture_scale_offset[1]), 0)
                    luv.uv.x = luv.uv.x + source_obj.wall_texture_offset[0];
                    luv.uv.y = luv.uv.y + source_obj.wall_texture_offset[1];
                if faceDirection == "-x":
                    luv.uv.x = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                    luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                    luv.uv = FillTextureClass.rotate2D(luv.uv, source_obj.wall_texture_rotation)
                    luv.uv.x = FillTextureClass.translate(FillTextureClass.scale(luv.uv.x, source_obj.wall_texture_scale_offset[0]), 0)
                    luv.uv.y = FillTextureClass.translate(FillTextureClass.scale(luv.uv.y, source_obj.wall_texture_scale_offset[1]), 0)
                    luv.uv.x = luv.uv.x + source_obj.wall_texture_offset[0];
                    luv.uv.y = luv.uv.y + source_obj.wall_texture_offset[1];
                if faceDirection == "y":
                    luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                    luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                    luv.uv = FillTextureClass.rotate2D(luv.uv, source_obj.wall_texture_rotation)
                    luv.uv.x = FillTextureClass.translate(FillTextureClass.scale(luv.uv.x, source_obj.wall_texture_scale_offset[0]), 0)
                    luv.uv.y = FillTextureClass.translate(FillTextureClass.scale(luv.uv.y, source_obj.wall_texture_scale_offset[1]), 0)
                    luv.uv.x = luv.uv.x + source_obj.wall_texture_offset[0];
                    luv.uv.y = luv.uv.y + source_obj.wall_texture_offset[1];
                if faceDirection == "-y":
                    luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                    luv.uv.y = ((l.vert.co.z * objectScale[2]) + objectLocation[2])
                    luv.uv = FillTextureClass.rotate2D(luv.uv, source_obj.wall_texture_rotation)
                    luv.uv.x =  FillTextureClass.translate(FillTextureClass.scale(luv.uv.x, source_obj.wall_texture_scale_offset[0]), 0)
                    luv.uv.y =  FillTextureClass.translate(FillTextureClass.scale(luv.uv.y, source_obj.wall_texture_scale_offset[1]), 0)
                    luv.uv.x = luv.uv.x + source_obj.wall_texture_offset[0];
                    luv.uv.y = luv.uv.y + source_obj.wall_texture_offset[1];
                if faceDirection == "z":
                    luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                    luv.uv.y = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                    luv.uv = FillTextureClass.rotate2D(luv.uv, source_obj.ceiling_texture_rotation)
                    luv.uv.x =  FillTextureClass.translate(FillTextureClass.scale(luv.uv.x, source_obj.ceiling_texture_scale_offset[0]), 0)
                    luv.uv.y =  FillTextureClass.translate(FillTextureClass.scale(luv.uv.y, source_obj.ceiling_texture_scale_offset[1]), 0)
                    luv.uv.x = luv.uv.x + source_obj.ceiling_texture_offset[0];
                    luv.uv.y = luv.uv.y + source_obj.ceiling_texture_offset[1];
                if faceDirection == "-z":
                    luv.uv.x = ((l.vert.co.x * objectScale[0]) + objectLocation[0])
                    luv.uv.y = ((l.vert.co.y * objectScale[1]) + objectLocation[1])
                    luv.uv = FillTextureClass.rotate2D(luv.uv, source_obj.floor_texture_rotation)
                    luv.uv.x =  FillTextureClass.translate(FillTextureClass.scale(luv.uv.x, source_obj.floor_texture_scale_offset[0]), 0)
                    luv.uv.y =  FillTextureClass.translate(FillTextureClass.scale(luv.uv.y, source_obj.floor_texture_scale_offset[1]), 0)
                    luv.uv.x = luv.uv.x + source_obj.floor_texture_offset[0];
                    luv.uv.y = luv.uv.y + source_obj.floor_texture_offset[1];
        bm.to_mesh(mesh)
        bm.free()
        source_obj.data = mesh
        
    def execute(self, context):
        was_edit_mode = False
        if bpy.context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
            was_edit_mode = True
    
        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH':
                FillTextureClass.auto_texture(obj)
            
        if was_edit_mode:
            bpy.ops.object.mode_set(mode='EDIT')
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
        if ob:
            col = layout.column(align=True)
            col = layout.row(align=True)
            col.prop(ob, "ceiling_texture_scale_offset")
            col = layout.row(align=True)
            col.prop(ob, "wall_texture_scale_offset")
            col = layout.row(align=True)
            col.prop(ob, "floor_texture_scale_offset")
            col = layout.row(align=True)
            col.prop(ob, "ceiling_texture_rotation")
            col = layout.row(align=True)
            col.prop(ob, "wall_texture_rotation")
            col = layout.row(align=True)
            col.prop(ob, "floor_texture_rotation")
            col = layout.row(align=True)
            col.prop(ob, "ceiling_texture_offset")
            col = layout.row(align=True)
            col.prop(ob, "wall_texture_offset")
            col = layout.row(align=True)
            col.prop(ob, "floor_texture_offset")
            col = layout.row(align=True)
            col.operator("scene.filltexture", text="APPLY", icon="MOD_BUILD")
        else:
            layout.label(text="Select an object")



def menu_func(self, context):
    self.layout.operator(FillTextureClass.bl_idname)

def register():
    bpy.utils.register_class(FillTextureClass)
    bpy.utils.register_class(TexturePanel)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(FillTextureClass)
    bpy.utils.unregister_class(TexturePanel)

if __name__ == "__main__":
    register()