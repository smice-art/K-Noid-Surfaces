"""
blender_k_noid_ui_analytic.py

K-Noid Generator with Analytic (hypergeometric) method + Numeric fallback
- Uses Jorge–Meeks closed-form expressions (Gauss hypergeometric) when mpmath is available.
- If mpmath is missing, falls back to numeric line integration.
- Includes a UI in the N-panel (tab: K-Noid) with method selector, "Install mpmath" helper, precision control,
  and a Mirror option to create the lower sheet if desired.

Notes:
- To make analytic mode work you must install `mpmath` into the Blender Python environment used by Blender.
  The panel provides a one-click installer that calls pip using Blender's Python (may require permission).
- Analytic mode is usually faster and more accurate than numeric integration, but still needs branch/precision care.

Author: Generated with ChatGPT
"""

bl_info = {
    "name": "K-Noid Generator (Analytic + Numeric)",
    "author": "ChatGPT",
    "version": (1, 2),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > K-Noid",
    "description": "Jorge–Meeks k-noid generator: analytic hypergeometric method when mpmath is available, numeric fallback otherwise",
    "category": "Add Mesh",
}

import bpy
import bmesh
import cmath
import sys
import subprocess
from math import pi

# Try import mpmath; keep a flag
HAS_MPMATH = False
_mp = None
try:
    import mpmath as mp
    from mpmath import hyp2f1
    HAS_MPMATH = True
    _mp = mp
except Exception:
    HAS_MPMATH = False
    _mp = None

# -------------------------
# Weierstrass analytic closed form using hypergeometric functions
# -------------------------
def jorge_meeks_closedform(z, k, mp_dps=30, pole_eps=1e-8):
    """Return (x,y,z) using closed-form hypergeometric expressions (mpmath required).
    Returns None if point is too near a pole or evaluation fails.
    """
    if not HAS_MPMATH:
        return None
    mp = _mp
    try:
        mp.mp.dps = int(max(15, mp_dps))
    except Exception:
        pass

    # avoid poles: z^k == 1
    for j in range(k):
        root = cmath.exp(2j * pi * j / k)
        if abs(z - root) < pole_eps:
            return None

    # handle z==0 limit
    if z == 0:
        return (0.0, 0.0, float((1.0 / k).real))

    # compute w = z^k (principal branch)
    try:
        w = z ** k
    except Exception:
        # if power failed due to branch issues
        return None

    # prepare mpmath complex
    try:
        mp_w = mp.mpc(w.real, w.imag)
    except Exception:
        return None

    a1, b1, c1 = 1, -1.0 / k, (k - 1.0) / k
    a2, b2, c2 = 1, 1.0 / k, 1.0 + 1.0 / k

    try:
        H1 = hyp2f1(a1, b1, c1, mp_w)
        H2 = hyp2f1(a2, b2, c2, mp_w)
    except Exception:
        return None

    # assemble complex expressions
    try:
        zc = z
        term1 = (k - 1.0) * (z ** k - 1.0) * complex(H1.real, H1.imag)
        term2 = (k - 1.0) * (z ** 2) * (z ** k - 1.0) * complex(H2.real, H2.imag)
        bracketX = term1 - term2 - k * (z ** k) + k + z ** 2 - 1.0
        bracketY = term1 + term2 - k * (z ** k) + k - z ** 2 - 1.0
        denom = k * z * (z ** k - 1.0)
        if abs(denom) == 0:
            return None
        compX = (-1.0 / denom) * bracketX
        compY = (1.0j / denom) * bracketY
        compZ = 1.0 / (k - k * (z ** k))
        X = 0.5 * compX.real
        Y = 0.5 * compY.real
        Z = compZ.real
        return (float(X), float(Y), float(Z))
    except Exception:
        return None


# -------------------------
# Numeric integration fallback (trapezoid along line from 0->z)
# -------------------------
def phi_components(z, k):
    g = (0+0j) if z == 0 else cmath.exp((k - 1) * cmath.log(z))
    f = 1.0 / ((z ** k - 1.0) ** 2)
    phi1 = 0.5 * (1.0 - g * g) * f
    phi2 = 0.5j * (1.0 + g * g) * f
    phi3 = g * f
    return phi1, phi2, phi3


def integrate_to_z_numeric(z, k, steps):
    if abs(z) == 0:
        return 0.0, 0.0, 0.0
    dz = z / steps
    acc1 = acc2 = acc3 = 0+0j
    prev1 = prev2 = prev3 = None
    for i in range(steps + 1):
        t = i / steps
        zi = t * z
        try:
            p1, p2, p3 = phi_components(zi, k)
        except ZeroDivisionError:
            return None
        if i == 0:
            prev1, prev2, prev3 = p1, p2, p3
            continue
        avg1 = 0.5 * (prev1 + p1)
        avg2 = 0.5 * (prev2 + p2)
        avg3 = 0.5 * (prev3 + p3)
        acc1 += avg1 * dz
        acc2 += avg2 * dz
        acc3 += avg3 * dz
        prev1, prev2, prev3 = p1, p2, p3
    return (acc1.real, acc2.real, acc3.real)


# -------------------------
# Mesh generation (shared logic)
# -------------------------
OBJ_NAME = 'k_noid_live'


def generate_grid(props, method='ANALYTIC'):
    k = int(props.k)
    u_res = max(8, int(props.u_res))
    r_res = max(2, int(props.r_res))
    r_max = float(props.r_max)
    integr_steps = max(8, int(props.integr_steps))
    pole_eps = float(props.pole_eps)
    scale = float(props.scale)
    mp_dps = int(max(15, props.mp_dps))

    verts = []
    faces = []
    valid_index = []

    for ir in range(r_res + 1):
        r = (r_max * ir / r_res)
        row = []
        for iu in range(u_res):
            theta = 2.0 * pi * iu / u_res
            zc = r * cmath.exp(1j * theta)
            # skip poles
            skip = False
            for j in range(k):
                root = cmath.exp(2j * pi * j / k)
                if r > 0 and abs(zc - root) < pole_eps:
                    skip = True
                    break
            if skip:
                row.append(-1)
                continue

            if method == 'ANALYTIC' and HAS_MPMATH:
                xyz = jorge_meeks_closedform(zc, k, mp_dps=mp_dps, pole_eps=pole_eps)
            else:
                xyz = integrate_to_z_numeric(zc, k, integr_steps)
            if xyz is None:
                row.append(-1)
                continue
            x, y, z_val = xyz
            verts.append((scale * x, scale * y, scale * z_val))
            row.append(len(verts) - 1)
        valid_index.append(row)

    for ir in range(r_res):
        for iu in range(u_res):
            v0 = valid_index[ir][iu]
            v1 = valid_index[ir][(iu + 1) % u_res]
            v2 = valid_index[ir + 1][(iu + 1) % u_res]
            v3 = valid_index[ir + 1][iu]
            if v0 >= 0 and v1 >= 0 and v2 >= 0 and v3 >= 0:
                faces.append((v0, v1, v2, v3))

    return verts, faces


def replace_mesh_geometry(obj, verts, faces):
    mesh = obj.data
    try:
        if hasattr(mesh, 'clear_geometry'):
            mesh.clear_geometry()
        else:
            new_mesh = bpy.data.meshes.new(obj.name + '_mesh_temp')
            new_mesh.from_pydata(verts, [], faces)
            new_mesh.update()
            obj.data = new_mesh
            return obj
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        bm = bmesh.new()
        bm.from_mesh(mesh)
        for f in bm.faces:
            f.smooth = True
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
    except Exception as e:
        print('replace_mesh_geometry failed, will recreate object:', e)
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass
        mesh2 = bpy.data.meshes.new(obj.name + '_mesh')
        mesh2.from_pydata(verts, [], faces)
        mesh2.update()
        obj2 = bpy.data.objects.new(obj.name, mesh2)
        bpy.context.collection.objects.link(obj2)
        return obj2
    return obj


# -------------------------
# Mirror utility (optional)
# -------------------------
def ensure_mirrored_join(obj):
    ctx = bpy.context
    col = ctx.collection
    obj_m = obj.copy()
    obj_m.data = obj.data.copy()
    obj_m.name = obj.name + '_mirror'
    col.objects.link(obj_m)
    obj_m.scale.z *= -1.0
    ctx.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    obj_m.select_set(True)
    ctx.view_layer.objects.active = obj_m
    try:
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    except Exception:
        pass
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    obj_m.select_set(True)
    ctx.view_layer.objects.active = obj
    try:
        bpy.ops.object.join()
    except Exception:
        # fallback: copy mesh data and append
        pass
    try:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=1e-6)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:
        me = obj.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
    return obj


# -------------------------
# Blender Property Group & UI
# -------------------------
class KNoidProperties(bpy.types.PropertyGroup):
    def _update_cb(self, context):
        if not self.auto_update:
            return
        try:
            props = context.scene.k_noid_props
            obj = bpy.data.objects.get(OBJ_NAME)
            if obj is None:
                bpy.ops.knoid.create_update('INVOKE_DEFAULT')
                return
            verts, faces = generate_grid(props, method=self.method)
            res = replace_mesh_geometry(obj, verts, faces)
            if isinstance(res, bpy.types.Object):
                obj = res
            if self.auto_mirror:
                ensure_mirrored_join(obj)
        except Exception as e:
            print('Auto-update error (k-noid):', e)

    k: bpy.props.IntProperty(name='k', default=5, min=2, max=24, update=_update_cb)
    u_res: bpy.props.IntProperty(name='U Res', default=240, min=8, max=1024, update=_update_cb)
    r_res: bpy.props.IntProperty(name='R Res', default=80, min=2, max=512, update=_update_cb)
    r_max: bpy.props.FloatProperty(name='R Max', default=1.0, min=0.01, max=5.0, update=_update_cb)
    integr_steps: bpy.props.IntProperty(name='Integr Steps', default=64, min=4, max=512, update=_update_cb)
    pole_eps: bpy.props.FloatProperty(name='Pole Eps', default=0.06, min=1e-4, max=1.0, update=_update_cb)
    scale: bpy.props.FloatProperty(name='Scale', default=1.0, min=0.001, max=10.0, update=_update_cb)
    mp_dps: bpy.props.IntProperty(name='MP Precision', default=30, min=15, max=200, update=_update_cb)
    auto_update: bpy.props.BoolProperty(name='Auto Update', default=False)
    auto_mirror: bpy.props.BoolProperty(name='Mirror Across XY', default=False)
    method: bpy.props.EnumProperty(name='Method', items=[('ANALYTIC', 'Analytic (hypergeometric)', ''), ('NUMERIC', 'Numeric integral', '')], default='ANALYTIC', update=_update_cb)


# -------------------------
# Operators + Panel
# -------------------------
class KNOID_OT_install_mpmath(bpy.types.Operator):
    bl_idname = 'knoid.install_mpmath'
    bl_label = 'Install mpmath'
    bl_description = 'Attempt to install mpmath into Blender Python via pip (may require network/permissions)'

    def execute(self, context):
        try:
            python_exe = sys.executable
            self.report({'INFO'}, f'Running: {python_exe} -m pip install mpmath')
            subprocess.check_call([python_exe, '-m', 'pip', 'install', 'mpmath'])
            self.report({'INFO'}, 'mpmath install attempt finished — re-run the script or restart Blender')
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f'mpmath install failed: {e}')
            print('mpmath install failed:', e)
            return {'CANCELLED'}


class KNOID_OT_create_update(bpy.types.Operator):
    bl_idname = 'knoid.create_update'
    bl_label = 'Create/Update K-Noid'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.k_noid_props
        method = props.method
        if method == 'ANALYTIC' and not HAS_MPMATH:
            self.report({'WARNING'}, 'Analytic method requires mpmath. Use "Install mpmath" or switch to Numeric mode.')
        verts, faces = generate_grid(props, method=method)
        name = OBJ_NAME
        obj = bpy.data.objects.get(name)
        if obj is None:
            mesh = bpy.data.meshes.new(name + '_mesh')
            mesh.from_pydata(verts, [], faces)
            mesh.update()
            obj = bpy.data.objects.new(name, mesh)
            context.collection.objects.link(obj)
        else:
            replaced = replace_mesh_geometry(obj, verts, faces)
            if isinstance(replaced, bpy.types.Object):
                obj = replaced
        found = False
        for m in obj.modifiers:
            if m.name == 'KNoid_Subdiv' and m.type == 'SUBSURF':
                found = True
                break
        if not found:
            sub = obj.modifiers.new(name='KNoid_Subdiv', type='SUBSURF')
            sub.levels = 2
            sub.render_levels = 2
        if props.auto_mirror:
            try:
                ensure_mirrored_join(obj)
            except Exception as e:
                print('Mirror/join failed:', e)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        try:
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        except Exception:
            pass
        return {'FINISHED'}


class KNOID_OT_remove(bpy.types.Operator):
    bl_idname = 'knoid.remove'
    bl_label = 'Remove K-Noid'

    def execute(self, context):
        obj = bpy.data.objects.get(OBJ_NAME)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)
        mirror_name = OBJ_NAME + '_mirror'
        mobj = bpy.data.objects.get(mirror_name)
        if mobj:
            bpy.data.objects.remove(mobj, do_unlink=True)
        return {'FINISHED'}


class KNOID_PT_panel(bpy.types.Panel):
    bl_label = 'K-Noid Generator'
    bl_idname = 'KNOID_PT_panel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'K-Noid'

    def draw(self, context):
        layout = self.layout
        props = context.scene.k_noid_props

        row = layout.row()
        row.operator('knoid.create_update', icon='MESH_UVSPHERE')
        row.operator('knoid.remove', icon='X')
        layout.prop(props, 'auto_update')
        layout.prop(props, 'auto_mirror')
        layout.separator()
        layout.prop(props, 'method')
        if props.method == 'ANALYTIC':
            if HAS_MPMATH:
                layout.label(text=f'mpmath available (mp.dps={_mp.mp.dps})', icon='CHECKMARK')
            else:
                col = layout.column()
                col.label(text='mpmath NOT available', icon='ERROR')
                col.operator('knoid.install_mpmath', icon='IMPORT')
                col.label(text='After installing, restart Blender and re-run the script')
        layout.separator()
        layout.prop(props, 'k')
        layout.prop(props, 'u_res')
        layout.prop(props, 'r_res')
        layout.prop(props, 'r_max')
        layout.prop(props, 'integr_steps')
        layout.prop(props, 'pole_eps')
        layout.prop(props, 'scale')
        layout.prop(props, 'mp_dps')


# -------------------------
# Registration
# -------------------------
classes = (
    KNoidProperties,
    KNOID_OT_install_mpmath,
    KNOID_OT_create_update,
    KNOID_OT_remove,
    KNOID_PT_panel,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.k_noid_props = bpy.props.PointerProperty(type=KNoidProperties)


def unregister():
    if hasattr(bpy.types.Scene, 'k_noid_props'):
        del bpy.types.Scene.k_noid_props
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == '__main__':
    register()
