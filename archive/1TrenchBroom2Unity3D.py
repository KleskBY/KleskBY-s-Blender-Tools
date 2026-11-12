bl_info = {
    "name": "Trenchbroom2Unity3D",
    "blender": (2, 80, 0),
    "category": "Object",
}

import bpy


class ObjectMoveX(bpy.types.Operator):
    """Trenchbroom2Unity3D"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "object.trenchbroom2unity"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Trenchbroom2Unity3D"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):        # execute() is called when running the operator.

        # The original script
        lastName = ""
        scene = bpy.context.scene
        texturesToSkip = ["clip", "*water1", "sky1", "lampbulb", "crate01", "crate02", "crate03", "box01", "box02", "box03", "box04", "box05", "crate1", "crate2"] # "barrel01", "barrel02", "barrel03", "barrel_top01",
        for obj in scene.objects:
                if obj.type == 'MESH':
                    temp = obj.name.split("_")
                    if(temp[0] == lastName):
                        print("Merge ", lastName, " with ", obj.name)
                        mesh = obj.data
                        skip = False

                        for f in mesh.polygons:  # iterate over faces
                            slot = obj.material_slots[f.material_index]
                            mat = slot.material
                            if mat is not None:
                                #print(mat.name)
                                if(mat.name in texturesToSkip):
                                    if(temp[0] == "entity0"):
                                        skip = True
                        
                        if(skip == False):
                            obj.select_set(True)
                            print(bpy.context.selected_objects)
                            bpy.ops.object.join()
                    else:
                        print("Now joining ", temp[0])
                        bpy.ops.object.select_all(action='DESELECT')
                        lastName = temp[0]
                        bpy.context.view_layer.objects.active = obj
                        obj.select_set(True)

        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

def menu_func(self, context):
    self.layout.operator(ObjectMoveX.bl_idname)

def register():
    bpy.utils.register_class(ObjectMoveX)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(ObjectMoveX)


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()