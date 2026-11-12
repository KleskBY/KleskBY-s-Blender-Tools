bl_info = {
    "name": "RemoveEverythingContains",
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


class FixTarkov(bpy.types.Operator):
    """RemoveEverythingContains"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "object.tarkovfixer"        # Unique identifier for buttons and menu items to reference.
    bl_label = "RemoveEverythingContains"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.


    def execute(self, context):        # execute() is called when running the operator.
        lastName = ""
        bpy.ops.object.select_all(action='DESELECT')
        scene = bpy.context.scene
        # namesToDelete = ["lod1", "lod2", "lod3", "shadow", "shdw", "trigger", "parts" ]
        namesToDelete = ["/terrain", "prop_fake_nosun" ]
        textuesToDelete = ["damage", "Default-Material_EFT" ]
        totalObjects = len(scene.objects)
        i = 0
        for obj in scene.objects:
                i = i + 1
                if obj.type == 'MESH':
                    res = [ele for ele in namesToDelete if(ele in obj.name.lower())]
                    if bool(res) == True:
                        print("[", i, "/", totalObjects, "] ", "Deleting ", obj.name , " parent: ", obj.parent)
                        # bpy.ops.object.select_all(action='DESELECT')
                        # delete_hierarchy(obj)
                        obj.select_set(True)
                    else:
                        mesh = obj.data
                        shouldDelete = False
                        for f in mesh.polygons:  # iterate over faces
                            if len(obj.material_slots) > 0:
                                slot = obj.material_slots[f.material_index]
                                mat = slot.material
                                if mat is not None:
                                    res2 = [ele for ele in textuesToDelete if(ele in mat.name.lower())]
                                    if bool(res2) == True:
                                        shouldDelete = True
                                        break
                            else: #maybe wrong
                                shouldDelete = True
                        
                        if  shouldDelete == True:
                            obj.select_set(True)

                        
                else:
                    if obj.parent:
                        print("[", i, "/", totalObjects, "] ", "Deleting ", obj.name , " parent: ", obj.parent)
                        obj.select_set(True)
                    
                    # temp = obj.name.split("_")
                    # if(temp[0] == lastName):
                        # print("Merge ", lastName, " with ", obj.name)
                        # mesh = obj.data
                        # skip = False

                        # for f in mesh.polygons:  # iterate over faces
                            # slot = obj.material_slots[f.material_index]
                            # mat = slot.material
                            # if mat is not None:
                                # print(mat.name)
                                # if(mat.name in texturesToSkip):
                                    # if(temp[0] == "entity0"):
                                        # skip = True
                        
                        # if(skip == False):
                            # obj.select_set(True)
                            # print(bpy.context.selected_objects)
                            # bpy.ops.object.join()
                    # else:
                        # print("Now joining ", temp[0])
                        # bpy.ops.object.select_all(action='DESELECT')
                        # lastName = temp[0]
                        # bpy.context.view_layer.objects.active = obj
                        # obj.select_set(True)
        bpy.ops.object.delete() 


        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

def menu_func(self, context):
    self.layout.operator(FixTarkov.bl_idname)

def register():
    bpy.utils.register_class(FixTarkov)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(FixTarkov)


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()