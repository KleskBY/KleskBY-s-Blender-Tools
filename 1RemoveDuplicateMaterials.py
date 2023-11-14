bl_info = {
    "name": "RemoveDuplicateMaterials",
    "blender": (2, 80, 0),
    "category": "Object",
}

import bpy
import re

class ObjectMoveX(bpy.types.Operator):
    """RemoveDuplicateMaterials"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "object.removeduplicatematerials"        # Unique identifier for buttons and menu items to reference.
    bl_label = "RemoveDuplicateMaterials"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):        # execute() is called when running the operator.

        scene = bpy.context.scene
        for obj in scene.objects:
                if obj.type == 'MESH':
                        mesh = obj.data
                        for f in mesh.polygons:  # iterate over faces
                            if len(obj.material_slots) > 0:
                                slot = obj.material_slots[f.material_index]
                                mat = slot.material
                                if mat is not None:
                                    if re.search(r"\.\d+$", mat.name) is not None:
                                        newMat_string = slot.material.name[:-4]
                                        newMat = bpy.data.materials.get(newMat_string)
                                        if newMat:
                                            slot.material = newMat
                                            print("chaning ", mat.name, " to ", newMat_string)
                                        else:
                                            slot.material.name = newMat_string
                                            print("renaming ", mat.name, " to ", newMat_string)
                                    
                                    

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