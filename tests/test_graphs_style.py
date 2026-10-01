import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.colors import to_hex

from s1napse import theme
from s1napse.widgets import graphs


def test_style_ax_hides_top_right_and_uses_light_grid():
    fig = Figure(); ax = fig.add_subplot()
    graphs._style_ax(ax, fig, ylabel='km/h')
    assert not ax.spines['top'].get_visible()
    assert not ax.spines['right'].get_visible()
    assert to_hex(ax.spines['left'].get_edgecolor()).upper() == theme.BORDER_SUBTLE.upper()
    assert to_hex(fig.get_facecolor()).upper() == theme.SURFACE.upper()
    xgrid = [l.get_visible() for l in ax.get_xgridlines()]
    assert not any(xgrid)


def test_line_width_constant():
    assert graphs.LINE_W == 1.8
