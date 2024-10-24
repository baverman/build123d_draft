import io
import functools
import math

import OCP
import numpy as np
from PIL import Image

from build123d import Face, Color

dpr = math.pi/180


def ocp_color(r, g=None, b=None):
    if isinstance(r, OCP.Quantity.Quantity_Color):
        return r
    elif isinstance(r, Color):
        return r.wrapped
    elif isinstance(r, tuple):
        r, g, b = r
    return OCP.Quantity.Quantity_Color(r, g, b, OCP.Quantity.Quantity_TypeOfColor.Quantity_TOC_RGB)


PROJECTIONS = {
    'Z': OCP.V3d.V3d_Zpos,
    '-Z': OCP.V3d.V3d_Zneg,
    'Y': OCP.V3d.V3d_Ypos,
    '-Y': OCP.V3d.V3d_Yneg,
}


@functools.lru_cache(1)
def render_context(size, bg):
    disp = OCP.Aspect.Aspect_DisplayConnection()
    gl = OCP.OpenGl.OpenGl_GraphicDriver(disp, True)
    gl.ChangeOptions().swapInterval = 0
    viewer = OCP.V3d.V3d_Viewer(gl)
    ctx = OCP.AIS.AIS_InteractiveContext(viewer)
    viewer.SetDefaultLights()
    viewer.SetLightOn()

    window = OCP.Xw.Xw_Window(disp, "some", 64, 64, *size)
    window.SetVirtual(True)
    view = OCP.V3d.V3d_View(viewer)
    view.SetWindow(window)
    # view.SetShadingModel(OCP.Graphic3d.Graphic3d_TypeOfShadingModel_Pbr)

    if bg:
        view.SetBackgroundColor(ocp_color(bg))

    return view, ctx


class ImageExporter:
    default_color = ocp_color(0.9, 0.8, 0.23)

    def __init__(self, size=(720, 480), bg=None, transparent=True, render_scale=2.0):
        self.size = size
        self.rsize = int(size[0]*render_scale), int(size[1]*render_scale)
        self.render_scale = render_scale
        self.bg = bg
        self.transparent = transparent
        self.view, self.ctx = render_context(self.rsize, bg)

        self.clear()
        self.configure()

    def clear(self, reset_view=True):
        self.ctx.RemoveAll(False)
        if reset_view:
            self.view.Reset(False)

    def configure(self):
        drawer = self.ctx.DefaultDrawer()
        mname = OCP.Graphic3d.Graphic3d_NameOfMaterial_Steel
        m = OCP.Graphic3d.Graphic3d_MaterialAspect(mname)
        drawer.ShadingAspect().SetMaterial(m);
        drawer.SetFaceBoundaryDraw(True)
        drawer.ShadingAspect().SetColor(ocp_color(self.default_color))

    def show(self, shape, clip=None, hatch=True, hscale=0.05, alpha=None,
             edges=None, line_width=None, clip_outline=True, color=None):
        shape_color = color or getattr(shape, 'color', None)

        prs = OCP.AIS.AIS_Shape(shape.wrapped)
        if alpha is not None:
            prs.SetTransparency(alpha)

        if line_width is not None:
            prs.SetWidth(line_width)

        if shape_color:
            prs.SetColor(ocp_color(shape_color))

        if edges is not None:
            prs.Attributes().SetFaceBoundaryDraw(edges)

        if clip:
            if clip_outline:
                outline = shape & Face.make_plane(clip)

                for w in outline.wires():
                    prs_outline = OCP.AIS.AIS_Shape(w.wrapped)
                    prs_outline.SetColor(ocp_color(0.9, 0.1, 0.1))
                    prs_outline.SetWidth(3)
                    self.ctx.Display(prs_outline, OCP.AIS.AIS_Shaded, -1, False)

            cp = OCP.Graphic3d.Graphic3d_ClipPlane(clip.wrapped)
            if hatch:
                tx = OCP.Graphic3d.Graphic3d_Texture2D(OCP.TCollection.TCollection_AsciiString('resources/hatch_2.png'))
                tx.GetParams().SetScale(OCP.gp.gp_Vec2f(hscale, hscale))
                tx.EnableModulate()
                tx.EnableRepeat()
                cp.SetCappingTexture(tx)

            cp.SetCapping(True)
            cp.SetCappingColor(ocp_color(shape_color or self.default_color))
            cp.SetUseObjectMaterial(True)
            prs.AddClipPlane(cp)

        self.ctx.Display(prs, OCP.AIS.AIS_Shaded, -1, False)

    def setup_view(self, start=None, rotz=None, roty=None, zoom=None, fit=0.01, proj=None):
        if not start:
            start = (0, 0, 0)

        self.view.SetAxis(*start, 0, 0, -1)
        self.view.SetAt(*start)
        self.view.SetProj(PROJECTIONS.get(proj, proj or OCP.V3d.V3d_TypeOfOrientation_Zup_AxoRight))

        if rotz is not None:
            self.view.Rotate(rotz*dpr)

        if roty is not None:
            self.view.Rotate(0, roty*dpr, 0)

        if zoom is not None:
            self.view.SetZoom(zoom)
        else:
            self.view.FitAll(fit, False)

    def export(self):
        image = OCP.Image.Image_AlienPixMap()
        self.view.ToPixMap(image, *self.rsize)
        buf = io.BytesIO()
        image.Save(buf, OCP.TCollection.TCollection_AsciiString('.png'))

        out = Image.open(buf)

        if self.transparent:
            out = out.convert('RGBA')
            d = np.array(out)
            key_color = tuple(int(it*255) for it in self.bg) + (255,)
            d[(d == key_color).all(axis=-1)] = [0, 0, 0, 0]
            out = Image.fromarray(d, mode='RGBA')

        if self.size != self.rsize:
            return out.resize(self.size)
        return out
