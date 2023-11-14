import bpy

bl_info = {
    "name": "Texture Baker",
    "author": "KleskBY, Farhan Shaikh",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "description": "Baker lightmaps and textures to a single image.",
    "category": "Scene",
}

bpy.types.Object.bake_resolution = bpy.props.IntProperty(
    name="Texture resolution",
    default=2048,
    min=256,
    max=16384,
    step=256,
)

class MyData:
    MainObj = None
    MainObjName = None
    DupeObj = None
    
def CleanModel(context):
    
    #set main object and its name
    MyData.MainObj = bpy.context.active_object
    MyData.MainObjName = bpy.context.active_object.name

    #Merge all vertices
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles()
    bpy.ops.object.editmode_toggle()
    
    #Fix Shading
    bpy.context.object.data.use_auto_smooth = False
    bpy.ops.object.shade_flat()
    
    #duplicate the main obj, set and name dupe 
    bpy.ops.object.duplicate()
    MyData.DupeObj = bpy.context.active_object
    MyData.DupeObj.name = MyData.MainObjName + "cln"
    
    #Hide main obj
    MyData.MainObj.hide_set(True)                           
                           
def EditMaterials(context):
    
    #remove then add a new material
    MyData.DupeObj.data.materials.clear()

    ImageMaterial = bpy.data.materials.new(name = MyData.DupeObj.name)
    MyData.DupeObj.data.materials.append(ImageMaterial)

    #edit the material
    ImageMaterial.use_nodes = True

    nodes = ImageMaterial.node_tree.nodes

    PrincipledBSDF = nodes.get('Principled BSDF')
    ImageTextureNode = nodes.new(type = 'ShaderNodeTexImage')
    ImageTextureNode.location = (-280, 80)

    Links = ImageMaterial.node_tree.links
    NewLink = Links.new(ImageTextureNode.outputs[0], PrincipledBSDF.inputs[0])

    GeneratedTex = bpy.data.images.new(MyData.DupeObj.name, context.active_object.bake_resolution, context.active_object.bake_resolution, alpha = False)
    bpy.data.images[MyData.DupeObj.name].generated_color = (0.1, 0.1, 0.1, 1)
    ImageTextureNode.image = GeneratedTex

    #Set that image in the uv editor, if uv editor is available
    for area in bpy.context.screen.areas :
        if area.type == 'IMAGE_EDITOR' :
            area.spaces.active.image = GeneratedTex
            
    
            
    
def SmartUVProject(context):
    bpy.ops.object.editmode_toggle()    
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=0.523599, island_margin=0.0003, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.editmode_toggle()
    
            
    

def Bake(context):
    MyData.MainObj.hide_set(False) 

    #Select objects in order
    MyData.MainObj.select_set(True)
    MyData.DupeObj.select_set(True)
    bpy.context.view_layer.objects.active = MyData.DupeObj

    #set bake settings
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.device = 'GPU'

    #set device type to cuda cus optix doesnt support baking
    bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "CUDA" # or "OPENCL"

    # get_devices() to let Blender detects GPU device
    bpy.context.preferences.addons["cycles"].preferences.get_devices()
    print(bpy.context.preferences.addons["cycles"].preferences.compute_device_type)
    for d in bpy.context.preferences.addons["cycles"].preferences.devices:
        d["use"] = 1 # Using all devices, include GPU and CPU
        print(d["name"], d["use"])


    bpy.context.scene.cycles.bake_type = 'DIFFUSE'
    # bpy.context.scene.render.bake.use_pass_direct = False
    bpy.context.scene.render.bake.use_pass_indirect = False
    bpy.context.scene.render.bake.use_clear = False
    bpy.context.scene.render.bake.use_selected_to_active = True
    bpy.context.scene.render.bake.cage_extrusion = 0.01
    bpy.context.scene.render.bake.max_ray_distance = 0.1

    bpy.ops.object.bake(type='DIFFUSE')

    MyData.MainObj.hide_set(True) 

    bpy.context.scene.render.engine = 'BLENDER_EEVEE'



class BakerClass(bpy.types.Operator):
    """BakeTexture"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "scene.baketexture"        # Unique identifier for buttons and menu items to reference.
    bl_label = "BakeTexture"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.


    def execute(self, context):
        was_edit_mode = False
        if bpy.context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
            was_edit_mode = True
    
        for obj in bpy.context.selected_objects:
            CleanModel(context)
            EditMaterials(context)
            self.report({'INFO'}, "Geometry optimised and Material Set")
            SmartUVProject(context)
            self.report({'INFO'}, "UVs projected, Bake started")
            Bake(context)
            self.report({'INFO'}, "Model cleaned!")
            
        if was_edit_mode:
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'} 


class BakerPanel(bpy.types.Panel):
    bl_label = "Baker"
    bl_space_type = "VIEW_3D"
    bl_region_type = 'UI'
    bl_category = 'Baker'

    def draw(self, context):
        ob = context.active_object
        if ob:
            layout = self.layout
            col = layout.row(align=True)
            col.prop(context.scene.render.bake, "use_pass_direct", text="Bake lights (non direct)")
            col = layout.row(align=True)
            col.prop(ob, "bake_resolution")
            col = layout.row(align=True)
            col.operator("scene.baketexture", text="BAKE")


def menu_func(self, context):
    self.layout.operator(BakerClass.bl_idname)

def register():
    bpy.utils.register_class(BakerClass)
    bpy.utils.register_class(BakerPanel)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(BakerClass)
    bpy.utils.unregister_class(BakerPanel)

if __name__ == "__main__":
    register()