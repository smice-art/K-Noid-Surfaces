"""
This is a Blender Add-on to generate a k-Noid minimal surface.
It adds a panel to the 3D View's "N-Panel" (side panel).

To use:
1.  Run this script once from the Text Editor to register the add-on.
2.  Go to the 3D Viewport.
3.  Press 'N' to open the side panel.
4.  Find the "k-Noid" tab.
5.  Adjust the sliders and click "Generate k-Noid".
"""

import bpy
import math

# --- Blender Add-on Information ---
bl_info = {
    "name": "k-Noid Generator",
    "author": "claudio",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > N-Panel > k-Noid Tab",
    "description": "Generates a k-Noid minimal surface",
    "category": "Add Mesh",
}

# === Helper Functions (The Math) ===
# These are the same functions as before, but they will
# now read the parameters from the operator that calls them.

def Catenoidx(u, v, r_val):
    return r_val * math.cosh(v / 2) * math.cos(u)

def Catenoidy(u, v, r_val):
    return r_val * math.cosh(v / 2) * math.sin(u)

def Catenoidz(u, v, R_val):
    return v + R_val + math.pi

def Sphere_x(u, v, R_val):
    return R_val * math.sin(u + math.pi / 2)

def Sphere_y(u, v, R_val, vmin_val, Noid_val):
    return R_val * math.cos(u + math.pi / 2) * math.sin(vmin_val / Noid_val)

def Sphere_z(u, v, R_val, vmin_val, Noid_val):
    base_val = R_val * math.cos(u + math.pi / 2) * math.cos(vmin_val / Noid_val)
    return base_val if u < 0 else -base_val

def threshold(u, v, vmin_val, vmax_val, k_val):
    v_norm = (v - vmin_val) / (vmax_val - vmin_val)
    # Clamp v_norm to avoid math domain errors if v is outside range
    v_norm_clamped = max(0.0, min(1.0, v_norm))
    return math.pow(v_norm_clamped, k_val)

def threshold2(u, v, vmin_val, vmax_val, k_val):
    v_norm = (v - vmin_val) / (vmax_val - vmin_val)
    v_norm_clamped = max(0.0, min(1.0, v_norm))
    return math.pow(1.0 - v_norm_clamped, k_val)

def Catenoid_x(u, v, r_val, R_val, vmin_val, vmax_val, k_val, Noid_val):
    th = threshold(u, v, vmin_val, vmax_val, k_val)
    th2 = threshold2(u, v, vmin_val, vmax_val, k_val)
    return th2 * Catenoidx(u, v, r_val) + th * Sphere_x(u, v, R_val)

def Catenoid_y(u, v, r_val, R_val, vmin_val, vmax_val, k_val, Noid_val):
    th = threshold(u, v, vmin_val, vmax_val, k_val)
    th2 = threshold2(u, v, vmin_val, vmax_val, k_val)
    return th2 * Catenoidy(u, v, r_val) + th * Sphere_y(u, v, R_val, vmin_val, Noid_val)

def Catenoid_z(u, v, r_val, R_val, vmin_val, vmax_val, k_val, Noid_val):
    th = threshold(u, v, vmin_val, vmax_val, k_val)
    th2 = threshold2(u, v, vmin_val, vmax_val, k_val)
    return th2 * Catenoidz(u, v, R_val) + th * Sphere_z(u, v, R_val, vmin_val, Noid_val)

def Roty(y_in, z_in, t, Teta_val, Noid_val):
    s = math.sin(t * Teta_val / Noid_val)
    c = math.cos(t * Teta_val / Noid_val)
    common = (s * y_in + c * z_in)
    return z_in - 2 * common * c

def Rotz(y_in, z_in, t, Teta_val, Noid_val):
    s = math.sin(t * Teta_val / Noid_val)
    c = math.cos(t * Teta_val / Noid_val)
    common = (s * y_in + c * z_in)
    return y_in - 2 * common * s


# === Blender Operator Class (The "Button") ===

class MESH_OT_generate_knoid(bpy.types.Operator):
    """Generates the k-Noid mesh based on panel properties"""
    bl_idname = "mesh.generate_knoid"
    bl_label = "Generate k-Noid"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Get properties from the Scene (set by the panel sliders)
        scene = context.scene
        props = scene.knoid_props
        
        R = props.R
        r = props.r
        k = props.k
        Noid = props.Noid
        U_STEPS = props.u_steps
        V_STEPS = props.v_steps
        
        # Hard-coded parameters (can also be made into props)
        umin = -math.pi
        umax = math.pi
        vmin = -math.pi
        vmax = math.pi
        Teta = math.pi
        
        # --- Delete old mesh if it exists ---
        obj_name = "k_Noid_Generated"
        if obj_name in bpy.data.objects:
            old_obj = bpy.data.objects[obj_name]
            bpy.data.objects.remove(old_obj, do_unlink=True)
        
        if obj_name in bpy.data.meshes:
            old_mesh = bpy.data.meshes[obj_name]
            bpy.data.meshes.remove(old_mesh, do_unlink=True)

        # --- Mesh Generation Logic ---
        verts = []
        faces = []
        vert_offset = 0

        for t in range(int(Noid)):  # Loop for Noid components
            for i in range(V_STEPS + 1):
                v = vmin + (vmax - vmin) * i / V_STEPS
                for j in range(U_STEPS + 1):
                    u = umin + (umax - umin) * j / U_STEPS
                    
                    cat_x = Catenoid_x(u, v, r, R, vmin, vmax, k, Noid)
                    cat_y = Catenoid_y(u, v, r, R, vmin, vmax, k, Noid)
                    cat_z = Catenoid_z(u, v, r, R, vmin, vmax, k, Noid)
                    
                    fx = -cat_x
                    fy = Roty(cat_y, cat_z, t, Teta, Noid)
                    fz = Rotz(cat_y, cat_z, t, Teta, Noid)
                    
                    verts.append((fx, fy, fz))

            for i in range(V_STEPS):
                for j in range(U_STEPS):
                    v1 = vert_offset + i * (U_STEPS + 1) + j
                    v2 = vert_offset + i * (U_STEPS + 1) + (j + 1)
                    v3 = vert_offset + (i + 1) * (U_STEPS + 1) + (j + 1)
                    v4 = vert_offset + (i + 1) * (U_STEPS + 1) + j
                    faces.append((v1, v2, v3, v4))
            
            vert_offset = len(verts)

        # --- Create Mesh and Object in Blender ---
        mesh_data = bpy.data.meshes.new(obj_name)
        mesh_data.from_pydata(verts, [], faces)
        
        obj = bpy.data.objects.new(obj_name, mesh_data)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.001)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.shade_smooth()
        
        self.report({'INFO'}, f"Generated k-Noid with {len(verts)} verts")
        return {'FINISHED'}


# === Blender Property Group (The Sliders) ===

class KnoidProperties(bpy.types.PropertyGroup):
    R: bpy.props.FloatProperty(
        name="R",
        description="Main Radius (Sphere part)",
        default=8.0,
        min=0.1
    )
    r: bpy.props.FloatProperty(
        name="r",
        description="Minor Radius (Catenoid part)",
        default=1.0,
        min=0.1
    )
    k: bpy.props.FloatProperty(
        name="k",
        description="Blending exponent",
        default=2.0,
        min=0.1,
        max=20.0
    )
    Noid: bpy.props.IntProperty(
        name="Noid",
        description="Number of 'noids' (affects rotation)",
        default=4,
        min=1
    )
    u_steps: bpy.props.IntProperty(
        name="U Steps",
        description="Resolution along U",
        default=128,
        min=10,
        max=512
    )
    v_steps: bpy.props.IntProperty(
        name="V Steps",
        description="Resolution along V",
        default=128,
        min=10,
        max=512
    )


# === Blender Panel Class (The UI) ===

class VIEW3D_PT_knoid_panel(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport N-Panel"""
    bl_label = "k-Noid Generator"
    bl_idname = "VIEW3D_PT_knoid_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'k-Noid'  # This creates the new tab

    def draw(self, context):
        layout = self.layout
        props = context.scene.knoid_props

        layout.label(text="Parameters:")
        layout.prop(props, "R")
        layout.prop(props, "r")
        layout.prop(props, "k")
        layout.prop(props, "Noid")
        
        layout.separator()
        
        layout.label(text="Resolution:")
        layout.prop(props, "u_steps")
        layout.prop(props, "v_steps")
        
        layout.separator()
        
        layout.operator(MESH_OT_generate_knoid.bl_idname)


# === Registration ===

classes = (
    KnoidProperties,
    MESH_OT_generate_knoid,
    VIEW3D_PT_knoid_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # Attach the properties to the scene
    bpy.types.Scene.knoid_props = bpy.props.PointerProperty(type=KnoidProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    # Remove the properties from the scene
    del bpy.types.Scene.knoid_props

if __name__ == "__main__":
    # unregister() # Uncomment this line to test un-registering
    register()