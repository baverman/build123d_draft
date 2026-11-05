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

ConstrainedArcs

@set_current
def find_circle():
    l = build_line(Plane.XZ)
    ec = Edge.make_circle(10, l.plane)
    ax = -AX(-8).to_axis(l.plane)
    a, b = ec.intersect(ax).vertices()
    a.color = (1, 0, 0)
    b.color = (0, 1, 0)
    p1 = param_on_point(ec, a)
    p2 = param_on_point(ec, b)
    t1 = trim_wire(ec, p1, p2)
    t1.color = (0.8, 0, 0)
    t2 = trim_wire(ec, p2, p1)
    t2.color = (0, 0.8, 0)
    sadd(ec=ec, t1=t1, t2=t2, a=a, b=b)
    normal = l.to_vector((0, 0, 1))
    print(t1 % 0, t2 % 0)
    print(normal.dot(ax.direction.cross(t1 % 0)), normal.dot(ax.direction.cross(t2 % 0)))

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
