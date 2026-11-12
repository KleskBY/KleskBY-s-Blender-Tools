bl_info = {
    "name": "RemoveEverytingBut",
    "blender": (2, 80, 0),
    "category": "Object",
}

import bpy
def delete_hierarchy(obj):
    names = set([obj.name])

    # recursion
    def get_child_names(obj):
        for child in obj.children:
            names.add(child.name)
            if child.children:
                get_child_names(child)

    get_child_names(obj)

    print(names)
    objects = bpy.data.objects
    for n in names:
        objects[n].select_set(True)
        
    bpy.ops.object.delete()


class RemoveEverytingBut(bpy.types.Operator):
    """RemoveEverytingBut"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "object.removeeverytingbut"        # Unique identifier for buttons and menu items to reference.
    bl_label = "RemoveEverytingBut"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.


    def execute(self, context):        # execute() is called when running the operator.

        # The original script
        lastName = ""
        bpy.ops.object.select_all(action='DESELECT')
        scene = bpy.context.scene
        namesToKeep = ["level" ]
        totalObjects = len(scene.objects)
        i = 0
        for obj in scene.objects:
                i = i + 1
                if obj.type == 'MESH':
                    res = [ele for ele in namesToKeep if(ele in obj.name.lower())]
                    if bool(res) == False:
                        print("[", i, "/", totalObjects, "] ", "Deleting ", obj.name , " parent: ", obj.parent)
                        obj.select_set(True)
                else:
                    if obj.parent:
                        print("[", i, "/", totalObjects, "] ", "Deleting ", obj.name , " parent: ", obj.parent)
                        obj.select_set(True)
        bpy.ops.object.delete() 


        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

def menu_func(self, context):
    self.layout.operator(RemoveEverytingBut.bl_idname)

def register():
    bpy.utils.register_class(RemoveEverytingBut)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(RemoveEverytingBut)


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()