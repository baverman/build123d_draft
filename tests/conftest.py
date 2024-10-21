import os
import pytest
import dataclasses

import PIL

from build123d_draft import export_image
from build123d import Plane

@dataclasses.dataclass()
class view:
    rotz: float = 0
    vroty: float = 0
    clip: Plane | None = None


@pytest.fixture(autouse=True)
def render(request):
    yield
    if os.environ.get('RENDER_MODELS', '0') != '0':
        fname = 'assets/' + os.path.basename(request.node.path).rpartition('.')[0] + '_' + request.node.name + '.png'
        os.makedirs(os.path.dirname(fname), exist_ok=True)

        m = request.node.get_closest_marker('views')
        size = (m.kwargs if m else {}).get('size', (720, 480))
        views = m.args if m else [None]

        images = []
        for v in views:
            if v is None:
                v = view()
            elif isinstance(v, tuple):
                v = view(*v)
            loc = v.rotz, v.vroty
            img = export_image(request.module.slist.objects[-1], bg=(1, 0, 1),
                               transparent=True, loc=loc, size=size, clip=v.clip)
            images.append(img)

        if len(images) == 1:
            images[0].save(fname)
        else:
            total_width = sum(it.size[0] for it in images)
            out = PIL.Image.new('RGBA', (total_width, images[0].size[1]))
            x = 0
            for it in images:
                out.paste(im=it, box=(x, 0))
                x += it.size[0]

            out.save(fname)
