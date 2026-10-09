"""Blender rig report for the MotionCapture-Prototype pipeline.

HOW TO RUN
    Open your hand-rig .blend in Blender -> Scripting workspace ->
    Open -> this file -> Run Script (Alt+P).
    (Also works headless:  blender rig.blend -b -P blender_rig_report.py)

WHY
    MotionCapture-Prototype.py targets one hard-coded rig shape:
        object  'MoCap_Rig'
        bones   'Hand', 'Thumb_1', 'Index_1', 'Middle_1', 'Ring_1', 'Pinky_1'
    and applies the ESP32 angles to each bone's local X axis, with
    rotation_mode forced to 'XYZ'.
    This script prints what YOUR rig actually provides (plus the scene frame
    rate, which is what the serial update timer should be derived from) so the
    names / axes / FPS can be matched without guessing.

    It changes nothing in the scene. It only reads data and writes a .txt report.
"""

import os

import bpy

EXPECTED_OBJECT = "MoCap_Rig"
EXPECTED_BONES = ["Hand", "Thumb_1", "Index_1", "Middle_1", "Ring_1", "Pinky_1"]

lines = []


def out(text=""):
    lines.append(str(text))


def report_scene():
    scn = bpy.context.scene
    eff = scn.render.fps / scn.render.fps_base if scn.render.fps_base else 0.0
    out("SCENE")
    out("  name ................ %s" % scn.name)
    out("  render.fps .......... %s (fps_base=%s -> effective %.3f fps)"
        % (scn.render.fps, scn.render.fps_base, eff))
    out("  -> serial timer that matches this scene: %.4f s"
        % (1.0 / eff if eff else 0.0))
    out("  frame_start/end ..... %s / %s" % (scn.frame_start, scn.frame_end))
    out("  frame_current ....... %s" % scn.frame_current)
    out("  unit scale .......... %s (system: %s)"
        % (scn.unit_settings.scale_length, scn.unit_settings.system))
    out("  note ................ the sender emits ~12 frames/s, so a 30 fps "
        "scene cannot be filled 1:1 from UART data")
    out()


def report_objects():
    out("OBJECTS (%d)" % len(bpy.data.objects))
    for ob in bpy.data.objects:
        tags = []
        if ob.type == "ARMATURE":
            tags.append("armature=%s" % ob.data.name)
            tags.append("bones=%d" % len(ob.data.bones))
        if ob.parent:
            tags.append("parent=%s" % ob.parent.name)
        out("  %-28s type=%-9s %s" % (ob.name, ob.type, "  ".join(tags)))
    out()



def report_armature(ob):
    out("ARMATURE '%s'  (this is the name the receiver must look up)" % ob.name)
    out("  %-24s %-22s %-12s %-26s %s"
        % ("bone", "parent", "rot_mode", "head->tail (armature)", "local X axis"))
    for pb in ob.pose.bones:
        bone = pb.bone
        v = bone.tail_local - bone.head_local
        x = bone.matrix_local.to_3x3().col[0]
        out("  %-24s %-22s %-12s (%7.3f,%7.3f,%7.3f)  (%5.2f,%5.2f,%5.2f)"
            % (pb.name, (bone.parent.name if bone.parent else "-"),
               pb.rotation_mode, v.x, v.y, v.z, x.x, x.y, x.z))
    out()

    present = [b for b in EXPECTED_BONES if b in ob.pose.bones]
    missing = [b for b in EXPECTED_BONES if b not in ob.pose.bones]
    out("  receiver compatibility for '%s':" % ob.name)
    out("    found  : %s" % (", ".join(present) if present else "(none)"))
    out("    MISSING: %s" % (", ".join(missing) if missing else "(none)"))
    if missing:
        out("    -> rename those bones, or change the names in "
            "MotionCapture-Prototype.py lines 44/46")
    for pb in ob.pose.bones:
        if pb.constraints:
            out("    note: '%s' has constraints: %s"
                % (pb.name, ", ".join(c.type for c in pb.constraints)))
        if pb.rotation_mode not in ("XYZ", "QUATERNION"):
            out("    WARNING: '%s' rotation_mode=%s; the receiver switches it to "
                "XYZ, so values stored for that other mode are ignored"
                % (pb.name, pb.rotation_mode))
    out()

    ad = ob.animation_data
    if ad and ad.action:
        out("  existing action '%s': its channels are overwritten in the "
            "viewport while streaming" % ad.action.name)
        for fcu in list(ad.action.fcurves)[:12]:
            out("    %s[%s]" % (fcu.data_path, fcu.array_index))
    else:
        out("  existing action: (none)")
    out()


def report_extras():
    out("OTHER THINGS THE RECEIVER DEPENDS ON")
    names = [o.name for o in bpy.data.objects]
    ok = EXPECTED_OBJECT in names
    out("  object '%s' present: %s" % (EXPECTED_OBJECT, ok))
    if not ok:
        out("    -> the receiver silently does NOTHING without this exact "
            "object name (bpy.data.objects.get returns None)")
    out("  bpy version ......... %s" % bpy.app.version_string)
    try:
        import serial
        out("  pyserial ............ import OK (%s)" % serial.__version__)
    except Exception as exc:
        out("  pyserial ............ MISSING: %s" % exc)
        out("    -> Blender does not bundle pyserial; install it into Blender's "
            "own Python")
    out("  sys.executable ...... %s" % os.sys.executable)
    out()


report_scene()
report_objects()
for ob in bpy.data.objects:
    if ob.type == "ARMATURE":
        report_armature(ob)
report_extras()

text = "\n".join(lines)
print("\n" + "=" * 78)
print("MOTIONCAPTURE RIG REPORT")
print("=" * 78)
print(text)

blend_dir = bpy.path.abspath("//") if bpy.data.filepath else ""
target_dir = blend_dir if os.path.isdir(blend_dir) else bpy.app.tempdir
path = os.path.join(target_dir, "mocap_rig_report.txt")
try:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print("\nreport written to: %s" % path)
except OSError as exc:
    print("\ncould not write report file: %s" % exc)
