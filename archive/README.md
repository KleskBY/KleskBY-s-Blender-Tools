# Archive

Old scripts, no longer maintained. Known bugs were not fixed because newer add-ons replace them.

| Script | Replaced by |
|---|---|
| `1RemoveDuplicateMaterials.py` | `replace_duplicate_materials()` in `auto_texture_attach.py` and `TrenchbroomImporter.py` (also deletes the copies, handles any name) |
| `1TrenchBroom2Unity3D.py` | "Merge Brushes by Entity" in `TrenchbroomImporter.py` |
| `1RemoveEverythingContains.py` | "Delete empty faces" (bad materials) in `TrenchbroomImporter.py`. Delete-by-object-name (`/terrain`, ...) has no replacement |
| `1RemoveEverytingButNot.py` | Same as above. Keep-only-by-name has no replacement |

Known problems, if you ever revive them: deleting a parent empty makes its children jump, materials are matched case-sensitively against lower-case text, objects without material slots are deleted, and `scene.objects` is modified while iterating.
