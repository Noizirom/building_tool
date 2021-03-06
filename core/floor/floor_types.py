import bmesh
import itertools as it
import functools as ft
from bmesh.types import BMVert, BMEdge

from ...utils import (
    FaceMap,
    filter_geom,
    add_faces_to_map,
    boundary_edges_from_face_selection,
)


def create_floors(bm, edges, prop):
    """Create extrusions of floor geometry from a floorplan
    """
    start_height = 0.0
    faces_to_delete = []
    if edges is None:
        edges = boundary_edges_from_face_selection(bm)
        faces_to_delete = [f for f in bm.faces if f.select]
        start_height = faces_to_delete[-1].calc_center_median().z

    extrude_slabs_and_floors(bm, edges, prop)
    slabs, walls = get_slab_and_wall_faces(bm, prop, start_height)

    # XXX CAREFUL NOTE XXX
    #   (this solves alot of issues across the whole addon)
    #   This first inset is a very decisive and it's distance is not arbitrary either
    #   0.00011 is just a tad above the default distance for blender's remove_doubles,
    #
    #   This insets acts as a boundary region between slabs and floors and hence it's
    #   a buffer to separate geometry created on walls from geometry created on slabs
    #   especially usefull due to how 'inset_face_with_scale_offset' and
    #   'move_slab_splitface_to_wall' work.
    result_a = bmesh.ops.inset_region(bm, faces=slabs, depth=-0.00011)
    #
    # XXX END NOTE XXX

    result_b = bmesh.ops.inset_region(bm, faces=slabs, depth=-prop.slab_outset)
    slabs.extend(result_a["faces"] + result_b["faces"])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if faces_to_delete:
        bmesh.ops.delete(bm, geom=faces_to_delete, context="FACES")

    add_faces_to_map(bm, slabs, FaceMap.SLABS)
    add_faces_to_map(bm, walls, FaceMap.WALLS)


def extrude_slabs_and_floors(bm, edges, prop):
    """extrude edges alternating between slab and floor heights
    """
    offsets = it.cycle([prop.slab_thickness, prop.floor_height])
    for offset in it.islice(offsets, 0, prop.floor_count * 2):
        if offset == 0:
            continue

        extrusion = bmesh.ops.extrude_edge_only(bm, edges=edges)
        bmesh.ops.translate(
            bm, vec=(0, 0, offset), verts=filter_geom(extrusion["geom"], BMVert)
        )
        edges = filter_geom(extrusion["geom"], BMEdge)
    bmesh.ops.contextual_create(bm, geom=edges)


def get_slab_and_wall_faces(bm, prop, start_height):
    """get faces that form slabs and walls
    """
    slabs, walls = [], []
    slab_heights, wall_heights = [], []

    def H(idx):
        return start_height + (idx * prop.floor_height) + (idx * prop.slab_thickness)

    for idx in range(prop.floor_count):
        slab_heights.append(H(idx) + prop.slab_thickness / 2)
        wall_heights.append(H(idx) + prop.floor_height / 2 + prop.slab_thickness)

    round_4dp = ft.partial(round, ndigits=4)
    for face in bm.faces:
        face_location_z = round_4dp(face.calc_center_median().z)
        if face_location_z in map(round_4dp, slab_heights):
            slabs.append(face)
        elif face_location_z in map(round_4dp, wall_heights):
            walls.append(face)
    return slabs, walls
