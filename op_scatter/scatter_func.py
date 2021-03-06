# ##### BEGIN GPL LICENSE BLOCK #####
#
#  JewelCraft jewelry design toolkit for Blender.
#  Copyright (C) 2015-2020  Mikhail Rachinskiy
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####


from mathutils import Matrix, Vector

from ..lib import mesh, asset


class Scatter:

    def execute(self, context):
        import operator

        space_data = context.space_data
        use_local_view = bool(space_data.local_view)
        collection = context.collection
        start = self.start
        end = self.end

        # Init
        # ---------------------------

        if self.is_scatter:
            num = self.number - 1

            curve = context.object
            curve.select_set(False)

            ob = context.selected_objects[0]
            context.view_layer.objects.active = ob

        else:
            obs = []
            app = obs.append

            for ob in context.selected_objects:
                for con in ob.constraints:
                    if con.type == "FOLLOW_PATH":
                        app((ob, con, con.offset))
                        break

            obs.sort(key=operator.itemgetter(2), reverse=True)
            num = len(obs) - 1
            ob = context.object

            for con in ob.constraints:
                if con.type == "FOLLOW_PATH":
                    break
            else:
                ob, con, _ = obs[0]

            curve = con.target

        curve.data.use_radius = False
        asset.apply_scale(curve)

        # Offset
        # ---------------------------

        ofst = 0.0

        if num:

            if self.use_absolute_offset:
                ob_size = ob.dimensions[1]
                base_unit = 100.0 / self.curve_length

                ofst = base_unit * (ob_size + self.spacing)

            else:
                closed_scattering = True if round(end - start, 1) == 100.0 else False

                if self.cyclic and closed_scattering:
                    ofst = (end - start) / (num + 1)
                else:
                    if not self.cyclic:
                        start = start if start >= 0.0 else 0.0
                        end = end if end <= 100.0 else 100.0

                    ofst = (end - start) / num

        # Scatter/Redistribute
        # ---------------------------

        if self.is_scatter:

            mat_sca = Matrix.Diagonal(ob.scale).to_4x4()
            ob.matrix_world = mat_sca

            if self.rot_x:
                mat_rot = Matrix.Rotation(self.rot_x, 4, "X")
                ob.matrix_world @= mat_rot

            if self.rot_z:
                mat_rot = Matrix.Rotation(self.rot_z, 4, "Z")
                ob.matrix_world @= mat_rot

            if self.loc_z:
                mat_loc = Matrix.Translation((0.0, 0.0, self.loc_z))
                ob.matrix_world @= mat_loc

            ofst_fac = start + ofst

            for _ in range(num):
                ob_copy = ob.copy()
                collection.objects.link(ob_copy)

                if use_local_view:
                    ob_copy.local_view_set(space_data, True)

                con = ob_copy.constraints.new("FOLLOW_PATH")
                con.target = curve
                con.offset = -ofst_fac
                con.use_curve_follow = True
                con.forward_axis = "FORWARD_X"

                ofst_fac += ofst

                if ob.children:
                    for child in ob.children:
                        child_copy = child.copy()
                        collection.objects.link(child_copy)
                        child_copy.parent = ob_copy
                        child_copy.matrix_parent_inverse = child.matrix_parent_inverse

            con = ob.constraints.new("FOLLOW_PATH")
            con.target = curve
            con.offset = -start
            con.use_curve_follow = True
            con.forward_axis = "FORWARD_X"

        else:

            ofst_fac = start

            for ob, con, _ in obs:

                if self.rot_x:
                    ob_mat_rot = ob.matrix_basis.to_quaternion().to_matrix().to_4x4()
                    mat_rot = Matrix.Rotation(self.rot_x, 4, "X")
                    ob.matrix_basis @= ob_mat_rot.inverted() @ mat_rot @ ob_mat_rot

                if self.rot_z:
                    mat_rot = Matrix.Rotation(self.rot_z, 4, "Z")
                    ob.matrix_basis @= mat_rot

                if self.rot_x or self.loc_z:
                    dist = ob.matrix_basis.translation.length
                    mat_rot = ob.matrix_basis.to_quaternion().to_matrix()
                    ob.matrix_basis.translation = mat_rot @ Vector((0.0, 0.0, dist + self.loc_z))

                con.offset = -ofst_fac
                ofst_fac += ofst

        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager

        if self.is_scatter:

            if len(context.selected_objects) < 2:
                self.report({"ERROR"}, "At least two objects must be selected")
                return {"CANCELLED"}

            curve = context.object

            if curve.type != "CURVE":
                self.report({"ERROR"}, "Active object must be a curve")
                return {"CANCELLED"}

            self.cyclic = curve.data.splines[0].use_cyclic_u
            self.curve_length = mesh.curve_length(curve)

            wm.invoke_props_popup(self, event)
            return self.execute(context)

        values = []
        curve = None

        for ob in context.selected_objects:
            for con in ob.constraints:
                if con.type == "FOLLOW_PATH":
                    values.append(-con.offset)
                    curve = con.target
                    break

        if not curve:
            self.report({"ERROR"}, "Selected objects do not have Follow Path constraint")
            return {"CANCELLED"}

        self.start = min(values)
        self.end = max(values)

        self.cyclic = curve.data.splines[0].use_cyclic_u
        self.curve_length = mesh.curve_length(curve)

        return wm.invoke_props_popup(self, event)
