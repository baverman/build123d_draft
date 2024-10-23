import sys
import re
import textwrap

from build123d_draft.render import ImageExporter

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

    def execute(source, fname):
        exec(source, ctx, ctx)
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
