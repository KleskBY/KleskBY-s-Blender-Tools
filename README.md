# KleskBY's Blender Tools
 Blender Tools from KleskBY. Tested on Blender 3.6.
<br>
<h3>TrenchbroomImporter.py</h3>
Imports an OBJ from TrenchBroom: scales and applies transforms, removes caulk/clip/trigger faces, merges brushes per entity, fixes shading, merges duplicate materials and attaches textures by material name. Sidebar tab "TrenchBroom".<br>
<hr>
<h3>auto_texture_attach.py</h3>
Attaches textures to materials by material name (case-insensitive search in a folder set in the add-on preferences) and merges duplicated materials (MaterialName.001, .002). Object &gt; Attach Textures from Material Names.<br>
<hr>
<h3>1BakeLightmapsToTexture.py</h3>
Magic button that bakes textures and/or lightmaps of each selected mesh to a single image on a clean copy (the original is not modified). Sidebar tab "Baker".<br>
<hr>
<h3>1TextureFill.py</h3>
Assign and tile textures over objects by world position. Works like Trenchbroom or other BSP tree software. Sidebar tab "Texture"; in Edit Mode it fills the selected faces.<br>
<hr>
<h3>1RenameUVMaps.py</h3>
Renames the active UV map of many meshes to one common name (default "UVMap"). Selected objects, the whole scene or all data. Keeps materials working by retargeting UV Map nodes. Properties &gt; Object Data &gt; UV Maps and Object &gt; Clean Up.<br>
<hr>
<h3>BatchExport.py</h3>
Exports every selected mesh as its own triangulated FBX into a folder. File &gt; Export &gt; Each Selected Object as FBX (Triangulated).<br>
<hr>
<h3>archive/</h3>
Old scripts replaced by the add-ons above (RemoveDuplicateMaterials, TrenchBroom2Unity3D, RemoveEverythingContains, RemoveEverytingButNot). Kept for reference, see <a href="archive/README.md">archive/README.md</a>.<br>
