"""
bokeh_charts.py — Interactive Bokeh visualizations for PortalPath
"""
import os
import pandas as pd
from bokeh.plotting import figure
from bokeh.models import (
    ColumnDataSource, HoverTool, Span, Label, LabelSet,
    Range1d, FixedTicker,
)

_BASE     = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE, '..', 'data', 'processed')

COLORS = {
    'Elite':       '#2563eb',
    'Hidden Gem':  '#16a34a',
    'Talent Sink': '#d97706',
    'Avoid':       '#dc2626',
}


def get_conferences():
    sp = pd.read_csv(os.path.join(_BASE, '..', 'data', 'raw', 'sp_ratings.csv'))
    confs = sorted(sp['conference'].dropna().unique().tolist())
    priority = ['All', 'SEC', 'Big Ten']
    return priority + [c for c in confs if c not in priority]


def _conf_map():
    sp = pd.read_csv(os.path.join(_BASE, '..', 'data', 'raw', 'sp_ratings.csv'))
    return (sp.sort_values('year')
              .drop_duplicates('team', keep='last')
              .set_index('team')['conference']
              .to_dict())


def _load(year=None, conference=None):
    if year is None:
        path = os.path.join(_DATA_DIR, 'portal_index_alltime.csv')
        label = 'All-Time'
    else:
        path = os.path.join(_DATA_DIR, f'portal_index_{year}.csv')
        label = str(year)

    df_all = pd.read_csv(path)
    cm = _conf_map()
    df_all['conference'] = df_all['school'].map(cm).fillna('Other')

    df_display = (df_all[df_all['conference'] == conference].copy()
                  if conference and conference != 'All'
                  else df_all.copy())

    # df_all used for global scale/medians, df_display for what's plotted
    return df_display, df_all, label


def _assign_quads(df, mx, my):
    def q(row):
        hi_pr  = row['pagerank'] >= mx
        hi_dev = row['dev_score_norm'] >= my
        if hi_pr  and hi_dev:     return 'Elite'
        if not hi_pr and hi_dev:  return 'Hidden Gem'
        if hi_pr  and not hi_dev: return 'Talent Sink'
        return 'Avoid'
    df = df.copy()
    df['quad'] = df.apply(q, axis=1)
    return df


def _quad_medians(df):
    return df['pagerank'].median(), df['dev_score_norm'].median()


def _base_fig(**kwargs):
    p = figure(
        background_fill_color='white',
        border_fill_color='white',
        outline_line_color=None,
        toolbar_location='above',
        **kwargs,
    )
    p.title.text_font_size  = '13pt'
    p.title.text_font_style = 'bold'
    p.title.text_color      = '#222222'
    p.xaxis.axis_label_text_font_size = '10pt'
    p.yaxis.axis_label_text_font_size = '10pt'
    p.grid.grid_line_color  = '#e5e5e5'
    p.grid.grid_line_width  = 0.7
    p.axis.major_label_text_color  = '#444444'
    p.axis.axis_label_text_color   = '#222222'
    return p


def bokeh_scatter(year=None, conference=None):
    df, df_all, label = _load(year, conference)
    if df.empty:
        return _base_fig(width=900, height=580, title=f'Portal Index — {label}')

    # Medians from global data so quadrant lines don't shift
    mx, my = _quad_medians(df_all)
    df     = _assign_quads(df, mx, my)

    df['color']    = df['quad'].map(COLORS)
    df['logo_url'] = '/logos/' + df['school'] + '.png'
    df['pi_fmt']   = df['portal_index'].round(3).astype(str)
    df['pr_fmt']   = df['pagerank'].round(3).astype(str)
    df['dev_fmt']  = df['dev_score_norm'].round(3).astype(str)

    # Axis ranges from global data so axes don't shift
    df_sorted = df_all.sort_values('portal_index', ascending=False)
    top1 = df_sorted.iloc[0]
    top2 = df_sorted.iloc[1] if len(df_sorted) > 1 else top1
    gap  = top1['portal_index'] - top2['portal_index']
    outlier = gap > 0.20

    if outlier:
        others = df_all[df_all['school'] != top1['school']]
        x_max = min(others['pagerank'].max() * 1.18, 1.0)
        y_max = min(others['dev_score_norm'].max() * 1.18, 1.0)
    else:
        x_max = df_all['pagerank'].max() * 1.10
        y_max = df_all['dev_score_norm'].max() * 1.10

    x_range = Range1d(df_all['pagerank'].min() - 0.02, x_max)
    y_range = Range1d(df_all['dev_score_norm'].min() - 0.02, y_max)

    p = _base_fig(
        height=600, sizing_mode='stretch_both',
        title=f'Portal Index — {label}',
        x_range=x_range, y_range=y_range,
        tools='pan,wheel_zoom,box_zoom,reset',
    )

    main_df = df[df['school'] != top1['school']] if outlier else df
    source  = ColumnDataSource(main_df)

    p.scatter('pagerank', 'dev_score_norm', source=source,
              color='color', size=4, alpha=0.3)

    p.image_url(url='logo_url', x='pagerank', y='dev_score_norm',
                w=36, h=36, source=source,
                anchor='center', w_units='screen', h_units='screen')

    hover = HoverTool(tooltips=[
        ('School',           '@school'),
        ('Quadrant',         '@quad'),
        ('Portal Index',     '@pi_fmt'),
        ('Pipeline Quality', '@pr_fmt'),
        ('Dev Score',        '@dev_fmt'),
    ])
    p.add_tools(hover)

    # Outlier pinned in corner
    if outlier:
        pin_x = x_range.end * 0.93
        pin_y = y_range.end * 0.93
        out_src = ColumnDataSource(dict(
            x=[pin_x], y=[pin_y],
            logo_url=[f'/logos/{top1["school"]}.png'],
            school=[top1['school']],
            quad=[top1['quad']],
            pi_fmt=[f'{top1["portal_index"]:.3f}'],
            pr_fmt=[f'{top1["pagerank"]:.3f}'],
            dev_fmt=[f'{top1["dev_score_norm"]:.3f}'],
        ))
        out_r = p.image_url(url='logo_url', x='x', y='y', w=36, h=36,
                            source=out_src, anchor='center',
                            w_units='screen', h_units='screen')
        p.add_tools(HoverTool(renderers=[out_r], tooltips=[
            ('School',       '@school'),
            ('Portal Index', '@pi_fmt  ▶ off-chart'),
            ('Pipeline',     '@pr_fmt'),
            ('Dev Score',    '@dev_fmt'),
        ]))
        p.add_layout(Label(
            x=pin_x, y=pin_y,
            text=f'{top1["school"]} ▶ off-chart',
            text_font_size='8pt', text_color=COLORS.get(top1['quad'], '#888'),
            x_offset=0, y_offset=-28, text_align='center',
        ))

    # Quadrant dividers
    p.add_layout(Span(location=mx, dimension='height',
                      line_color='#bbbbbb', line_dash='dashed', line_width=0.9))
    p.add_layout(Span(location=my, dimension='width',
                      line_color='#bbbbbb', line_dash='dashed', line_width=0.9))

    # Corner labels
    xmin, xmax2 = x_range.start, x_range.end
    ymin, ymax2 = y_range.start, y_range.end
    pw, ph = xmax2 - xmin, ymax2 - ymin
    for x, y, text, align, baseline in [
        (xmax2 - pw*0.02, ymax2 - ph*0.02, 'Elite',        'right', 'top'),
        (xmin  + pw*0.02, ymax2 - ph*0.02, 'Hidden Gem',   'left',  'top'),
        (xmax2 - pw*0.02, ymin  + ph*0.02, 'Talent Sink',  'right', 'bottom'),
        (xmin  + pw*0.02, ymin  + ph*0.02, 'Avoid',        'left',  'bottom'),
    ]:
        p.add_layout(Label(
            x=x, y=y, text=text,
            text_font_size='12pt', text_font_style='bold', text_color='black',
            text_align=align, text_baseline=baseline,
        ))

    p.xaxis.axis_label = 'Transfer Pipeline Quality (PageRank Score)'
    p.yaxis.axis_label = 'Development Score  (player outcome quality)'
    return p


def _ranking_fig(df, label, value_col, title, x_label, top_n=25):
    """Shared horizontal bar chart for portal index and pagerank rankings."""
    df = df.sort_values(value_col, ascending=False).head(top_n).reset_index(drop=True)
    n = len(df)
    df['logo_url'] = '/logos/' + df['school'] + '.png'
    df['y']        = list(range(n - 1, -1, -1))
    df['logo_x']   = -0.07
    df['val_fmt']  = df[value_col].round(3).astype(str)
    df['label_x']  = df[value_col] + df[value_col].max() * 0.012

    source = ColumnDataSource(df)

    p = _base_fig(
        height=820, sizing_mode='scale_width',
        title=title,
        x_range=Range1d(-0.13, df[value_col].max() * 1.18),
        y_range=Range1d(-0.5, n - 0.5),
        tools='hover',
    )

    p.hbar(y='y', right=value_col, height=0.65,
           color='color' if 'color' in df.columns else '#2563eb',
           line_color='white', line_width=0.4, source=source)

    p.image_url(url='logo_url', x='logo_x', y='y',
                w=24, h=24, source=source,
                anchor='center', w_units='screen', h_units='screen')

    # Value labels at end of bar
    p.add_layout(LabelSet(
        x='label_x', y='y', text='val_fmt', source=source,
        text_font_size='8pt', text_color='#444444',
        text_baseline='middle',
    ))

    hover = p.select(HoverTool)
    hover.tooltips = [('School', '@school'), (x_label, '@val_fmt')]
    if 'quad' in df.columns:
        hover.tooltips.append(('Quadrant', '@quad'))

    p.yaxis.ticker = FixedTicker(ticks=list(range(n)))
    p.yaxis.major_label_overrides = {int(r['y']): r['school'] for _, r in df.iterrows()}
    p.yaxis.major_label_text_font_size = '9pt'
    p.yaxis.major_tick_out = 28
    p.xaxis.axis_label = x_label
    p.xaxis.axis_label_text_font_size = '9pt'
    return p


def bokeh_ranking(year=None, conference=None, top_n=25):
    df, df_all, label = _load(year, conference)
    if df.empty or df['portal_index'].isna().all():
        return _base_fig(width=480, height=600, title=f'Portal Index — {label}')

    mx, my      = _quad_medians(df_all)
    df          = _assign_quads(df, mx, my)
    df['color'] = df['quad'].map(COLORS)
    return _ranking_fig(
        df, label,
        value_col='portal_index',
        title=f'Top 25 — Portal Index {label}',
        x_label='Portal Index',
        top_n=top_n,
    )


def bokeh_pagerank_ranking(year=None, conference=None, top_n=25):
    df, _, label = _load(year, conference)
    if df.empty:
        return _base_fig(width=480, height=600, title=f'Pipeline Quality — {label}')

    df = df.copy()
    df['color'] = '#2563eb'
    return _ranking_fig(
        df, label,
        value_col='pagerank',
        title=f'Top 25 — Transfer Pipeline Quality {label}',
        x_label='Transfer Pipeline Quality',
        top_n=top_n,
    )
