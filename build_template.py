import sys
import re
import textwrap
import time
from functools import partial

from build123d_draft.render import ImageExporter
from build123d_draft.utils import debug
from build123d import Sphere


def view_setup(view, proj='Z'):
    view.show(Sphere(0.001), color=(1, 0.1, 0.1))
    view.setup_view(fit=0.1, proj=proj)
    origin_r = view.view.Convert(15)
    view.show(Sphere(origin_r), color=(1, 0.1, 0.1))


ctx_tpl = {
    'RED': (1, 0.1, 0.1),
    'GREEN': (0.1, 1, 0.1),
    'BLUE': (0.1, 0.1, 1),
    'LW': 15,
    'view_setup': view_setup,
    'debug': debug,
}

def process(tpl):
    ie = ImageExporter(size=(360, 240), render_scale=4, bg=(1, 0.95, 0.9), transparent=False)

    ctx = {}
    i_src = textwrap.dedent('''\n
        from build123d import *
        from build123d_draft import *
        import OCP
    ''')
    exec(i_src, ctx, ctx)

    ctx['view'] = ie
    ctx.update(ctx_tpl)

    def execute(source, fname):
        source_fname = '/tmp/tmp_script.py'
        with open(source_fname, 'w') as f:
            f.write(source)
        code = compile(source, source_fname, 'exec')
        exec(code, ctx, ctx)
        ie.export().save(fname)

    def replace(m):
        fig = m.group(1)
        source = m.group(2)
        cleaned = '\n'.join(it for it in source.splitlines() if not it.lstrip().startswith('view')).strip()
        execute(source, f'resources/{fig}.png')
        return f'```python\n{cleaned}\n```\n\n![{fig}](./resources/{fig}.png)'

    return re.sub(r'(?ms)```python (\w+)$(.+?)```', replace, tpl)


def main():
    tpl_fname = sys.argv[1]
    out = process(open(tpl_fname).read())
    print(out, end='')


if __name__ == '__main__':
    main()
