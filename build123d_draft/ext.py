from build123d.build_enums import Align, Mode
from build123d.geometry import RotationLike
from build123d.objects_sketch import Circle as Circle_orig
from build123d.objects_part import Cylinder as Cylinder_orig
from build123d.topology import tuplify

from .tools import SAlign3D, SAlign2D


class Cylinder(Cylinder_orig):
    def __init__(
        self,
        radius: float,
        height: float | None = None,
        arc_size: float = 360,
        rotation: RotationLike = (0, 0, 0),
        align: SAlign3D = (
            Align.CENTER,
            Align.CENTER,
            Align.CENTER,
        ),
        mode: Mode = Mode.ADD,
        d: float | None = None,
        r: float | None = None,
    ) -> None:
        if d is not None:
            h = radius
            radius = d / 2
        elif r is not None:
            h = radius
            radius = r
        else:
            assert height
            h = height
        super().__init__(radius, h, arc_size=arc_size, rotation=rotation, align=align, mode=mode)

    def new(
        self,
        radius: float | None = None,
        height: float | None = None,
        d: float | None = None,
        r: float | None = None,
    ) -> Cylinder:
        if d is not None:
            if radius is not None:
                height = radius
            radius = d / 2
        elif r is not None:
            if radius is not None:
                height = radius
            radius = r
        if height is None:
            height = self.cylinder_height
        assert radius
        return self.location * Cylinder(radius, height, align=self.align)


class Circle(Circle_orig):
    align: tuple[Align, Align]

    def __init__(
        self,
        radius: float | None = None,
        align: SAlign2D = (Align.CENTER, Align.CENTER),
        mode: Mode = Mode.ADD,
        d: float | None = None,
    ):
        if d is not None:
            radius = d / 2
        assert radius
        super().__init__(radius, align=align, mode=mode)

    def cylinder(
        self,
        height: float,
        d: float | None = None,
        r: float | None = None,
        align: SAlign3D = Align.MIN,
    ) -> Cylinder:
        radius = self.radius
        if d is not None:
            radius = d / 2
        elif r is not None:
            radius = r
        za = tuplify(align, 3)[2]  # type: ignore[index]
        align = self.align[0], self.align[1], za
        return self.location * Cylinder(radius, height, align=align)
