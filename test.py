# repl-client
from typing import Any

import OCP
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.Geom2d import Geom2d_TrimmedCurve
from OCP.Precision import Precision

from build123d import *
from build123d_draft.tools import tangent_center
from build123d_draft.testing import *
from build123d_draft.render import ImageExporter
from build123d_draft import *



@set_current
def find_circle():
    l = build_line(Plane.XZ).append(
        op_line(start=At((14, 19 + 32), angle=-10), end=100))
    ec = Edge.make_circle(19, l.plane.shift_origin(l.to_vector((81 - 29, 57))))
    sadd(ec=ec)
    v, t = tangent_center(l.plane, l[-1].edge(), ec, 19)
    l.append(op_arc(start=At(v, t), end=(81-29, 57)))
    return l

    # e = build_line().append(
    #     op_start(tangent=-Axis.X),
    #     op_ellipse_arc(5, 10, 90)
    # )
    # sadd(e)
    # c = build_line().append(
    #     op_start(tangent=-Axis.X),
    #     op_arc(10, 90)
    # )
    # sadd(c)


if __name__ == '__main__':
    # main_yacv(reset=False)
    main_ocp_vscode()
    # ie = ImageExporter(bg=(1, 1, 1), transparent=False)
    # for o in slist.objects:
    #     ie.show(o)
    # ie.setup_view(rotz=-20)
    # ie.export().save('/tmp/boo.png')
