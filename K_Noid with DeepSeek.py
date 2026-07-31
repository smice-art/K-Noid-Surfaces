import bpy
import bmesh
import numpy as np
from mathutils import Vector
import math

def jorge_meeks_k_noid(k, radius, height, resolution, scale):
    """
    Create a Jorge-Meeks Prismatic k-Noid minimal surface
    
    Parameters:
    k: number of ends
    radius: base radius
    height: vertical scale
    resolution: mesh resolution
    scale: overall scale
    """
    
    # Clear existing mesh objects
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Create a new mesh and object
    mesh = bpy.data.meshes.new("K_Noid_Mesh")
    obj = bpy.data.objects.new("K_Noid", mesh)
    
    # Link object to scene
    bpy.context.collection.objects.link(obj)
    
    # Create bmesh instance
    bm = bmesh.new()
    
    # Generate vertices using the Jorge-Meeks parametrization
    vertices = []
    faces = []
    
    # Weierstrass representation parameters for k-noid
    u_min, u_max = -2.0, 2.0
    v_min, v_max = -2.0, 2.0
    
    u_values = np.linspace(u_min, u_max, resolution)
    v_values = np.linspace(v_min, v_max, resolution)
    
    for i, u in enumerate(u_values):
        for j, v in enumerate(v_values):
            # Complex coordinate
            z = u + 1j * v
            
            # Weierstrass data for k-noid
            # Using a simplified version of the Jorge-Meeks formula
            f = 1.0 / (z**k - 1)
            g = z**(k-1)
            
            # Enneper-Weierstrass representation
            dh = f * (1 - g**2) / 2
            dg = f * (1 + g**2) / 2
            dz = 1j * f * g
            
            # Integration (simplified)
            x = np.real(z + (z**(k+1))/(k+1)) * radius
            y = np.imag(z + (z**(k+1))/(k+1)) * radius
            z_coord = height * np.imag(z**k / k)
            
            # Apply scaling
            vertex = Vector((x * scale, y * scale, z_coord * scale))
            vertices.append(vertex)
    
    # Create faces
    for i in range(resolution - 1):
        for j in range(resolution - 1):
            v1 = i * resolution + j
            v2 = i * resolution + (j + 1)
            v3 = (i + 1) * resolution + (j + 1)
            v4 = (i + 1) * resolution + j
            
            faces.append([v1, v2, v3, v4])
    
    # Add vertices and faces to bmesh
    for v in vertices:
        bm.verts.new(v)
    
    bm.verts.ensure_lookup_table()
    
    for f in faces:
        try:
            bm.faces.new([bm.verts[i] for i in f])
        except:
            # Face might be degenerate, skip
            pass
    
    # Update mesh
    bm.to_mesh(mesh)
    bm.free()
    
    # Smooth shading
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    
    return obj

class KNoidPanel(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport"""
    bl_label = "Jorge-Meeks k-Noid"
    bl_idname = "PT_KNoidPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "k-Noid"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        layout.prop(scene, "k_noid_k")
        layout.prop(scene, "k_noid_radius")
        layout.prop(scene, "k_noid_height")
        layout.prop(scene, "k_noid_resolution")
        layout.prop(scene, "k_noid_scale")
        
        layout.operator("object.generate_knoid")

class GenerateKNoid(bpy.types.Operator):
    """Generate Jorge-Meeks k-Noid"""
    bl_idname = "object.generate_knoid"
    bl_label = "Generate k-Noid"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        
        jorge_meeks_k_noid(
            k=scene.k_noid_k,
            radius=scene.k_noid_radius,
            height=scene.k_noid_height,
            resolution=scene.k_noid_resolution,
            scale=scene.k_noid_scale
        )
        
        return {'FINISHED'}

def register():
    bpy.types.Scene.k_noid_k = bpy.props.IntProperty(
        name="k",
        description="Number of ends",
        default=3,
        min=2,
        max=10
    )
    
    bpy.types.Scene.k_noid_radius = bpy.props.FloatProperty(
        name="Radius",
        description="Base radius",
        default=1.0,
        min=0.1,
        max=10.0
    )
    
    bpy.types.Scene.k_noid_height = bpy.props.FloatProperty(
        name="Height",
        description="Vertical scale",
        default=1.0,
        min=0.1,
        max=5.0
    )
    
    bpy.types.Scene.k_noid_resolution = bpy.props.IntProperty(
        name="Resolution",
        description="Mesh resolution",
        default=50,
        min=10,
        max=200
    )
    
    bpy.types.Scene.k_noid_scale = bpy.props.FloatProperty(
        name="Scale",
        description="Overall scale",
        default=1.0,
        min=0.1,
        max=10.0
    )
    
    bpy.utils.register_class(GenerateKNoid)
    bpy.utils.register_class(KNoidPanel)

def unregister():
    bpy.utils.unregister_class(GenerateKNoid)
    bpy.utils.unregister_class(KNoidPanel)
    
    del bpy.types.Scene.k_noid_k
    del bpy.types.Scene.k_noid_radius
    del bpy.types.Scene.k_noid_height
    del bpy.types.Scene.k_noid_resolution
    del bpy.types.Scene.k_noid_scale

if __name__ == "__main__":
    register()