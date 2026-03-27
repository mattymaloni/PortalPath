"""
dashboard.py — PortalPath interactive chart browser

Usage:
    python viz/dashboard.py
    Open http://localhost:8051
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import request, send_from_directory
from dash import Dash, dcc, html, Input, Output, callback_context
from bokeh.embed import file_html
from bokeh.resources import CDN

from viz.bokeh_charts import (
    bokeh_scatter, bokeh_ranking, bokeh_pagerank_ranking, get_conferences,
)

_LOGO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logos')
_YEARS    = [None, 2021, 2022, 2023, 2024, 2025, 2026]
_LABELS   = ['All-Time', '2021', '2022', '2023', '2024', '2025', '2026']

app = Dash(__name__)

# ── Static assets ──────────────────────────────────────────────────────────────
@app.server.route('/logos/<path:filename>')
def serve_logo(filename):
    return send_from_directory(_LOGO_DIR, filename)


# ── Chart endpoints ────────────────────────────────────────────────────────────
def _parse_args():
    year_str = request.args.get('year', 'all')
    conf     = request.args.get('conf', 'All')
    year     = None if year_str == 'all' else int(year_str)
    return year, conf


@app.server.route('/chart/scatter')
def chart_scatter():
    year, conf = _parse_args()
    try:
        plot = bokeh_scatter(year=year, conference=conf)
    except FileNotFoundError:
        return _empty_html()
    return file_html(plot, CDN)


@app.server.route('/chart/ranking')
def chart_ranking():
    year, conf = _parse_args()
    try:
        plot = bokeh_ranking(year=year, conference=conf)
    except FileNotFoundError:
        return _empty_html()
    return file_html(plot, CDN)


@app.server.route('/chart/pagerank')
def chart_pagerank():
    year, conf = _parse_args()
    try:
        plot = bokeh_pagerank_ranking(year=year, conference=conf)
    except FileNotFoundError:
        return _empty_html()
    return file_html(plot, CDN)


def _empty_html():
    return ('<html><body style="background:white;font-family:sans-serif;'
            'padding:32px;color:#999">No data available.</body></html>')


# ── Layout ─────────────────────────────────────────────────────────────────────
_IFRAME_BORDER = {'border': 'none', 'background': 'white'}

app.layout = html.Div([
    html.H2('PortalPath — Chart Browser',
            style={'fontFamily': 'sans-serif', 'color': '#222',
                   'margin': '24px 0 4px 32px'}),

    html.Div([
        html.Label('Year', style={'fontFamily': 'sans-serif', 'fontWeight': 'bold',
                                  'fontSize': '13px', 'marginRight': '10px'}),
        dcc.Dropdown(
            id='year-select',
            options=[{'label': l, 'value': i} for i, l in enumerate(_LABELS)],
            value=0,
            clearable=False,
            style={'width': '160px', 'fontFamily': 'sans-serif'},
        ),
        html.Label('Conference', style={'fontFamily': 'sans-serif', 'fontWeight': 'bold',
                                        'fontSize': '13px',
                                        'marginLeft': '28px', 'marginRight': '10px'}),
        dcc.Dropdown(
            id='conf-select',
            options=[{'label': c, 'value': c} for c in get_conferences()],
            value='All',
            clearable=False,
            style={'width': '200px', 'fontFamily': 'sans-serif'},
        ),
        *[html.Button(
            label,
            id=f'btn-{label.lower().replace(" ", "")}',
            n_clicks=0,
            style={
                'marginLeft': '10px',
                'padding': '4px 14px',
                'fontFamily': 'sans-serif',
                'fontSize': '12px',
                'border': '1px solid #d1d5db',
                'borderRadius': '4px',
                'background': 'white',
                'cursor': 'pointer',
                'color': '#222',
            },
        ) for label in ['All', 'SEC', 'Big Ten']],
    ], style={'display': 'flex', 'alignItems': 'center', 'margin': '0 0 20px 32px'}),

    # Scatter — fills screen width
    html.Div(
        html.Iframe(id='scatter-frame',
                    style={**_IFRAME_BORDER, 'width': '100%', 'height': 'calc(100vh - 130px)'}),
        id='scatter-div',
        style={'padding': '0 8px'},
    ),

    # Rankings — side by side, fixed height matching Bokeh figure
    html.Div([
        html.Iframe(id='ranking-frame',
                    style={**_IFRAME_BORDER, 'width': '49%', 'height': '880px',
                           'display': 'inline-block', 'verticalAlign': 'top'}),
        html.Iframe(id='pagerank-frame',
                    style={**_IFRAME_BORDER, 'width': '49%', 'height': '880px',
                           'display': 'inline-block', 'verticalAlign': 'top'}),
    ], id='rankings-div', style={'padding': '0 8px', 'marginTop': '12px'}),

], style={'background': 'white', 'minHeight': '100vh'})


# ── Callbacks ─────────────────────────────────────────────────────────────────
@app.callback(
    Output('conf-select', 'value'),
    Input('btn-all',    'n_clicks'),
    Input('btn-sec',    'n_clicks'),
    Input('btn-bigten', 'n_clicks'),
    prevent_initial_call=True,
)
def quick_conf(*_):
    triggered = callback_context.triggered[0]['prop_id']
    if 'sec'    in triggered: return 'SEC'
    if 'bigten' in triggered: return 'Big Ten'
    return 'All'


@app.callback(
    Output('scatter-frame',  'src'),
    Output('ranking-frame',  'src'),
    Output('pagerank-frame', 'src'),
    Output('scatter-div',    'style'),
    Output('ranking-frame',  'style'),
    Input('year-select', 'value'),
    Input('conf-select', 'value'),
)
def update_charts(year_idx, conference):
    year      = _YEARS[year_idx]
    is_2026   = (year == 2026)
    year_param = 'all' if year is None else str(year)
    conf_param = conference or 'All'
    base       = f'?year={year_param}&conf={conf_param}'

    scatter_src  = f'/chart/scatter{base}'
    ranking_src  = f'/chart/ranking{base}'
    pagerank_src = f'/chart/pagerank{base}'

    if is_2026:
        scatter_style = {'display': 'none'}
        ranking_style = {'display': 'none'}
    else:
        scatter_style = {'padding': '0 16px'}
        ranking_style = {**_IFRAME_BORDER, 'width': '49%', 'height': '880px',
                         'display': 'inline-block', 'verticalAlign': 'top'}

    return scatter_src, ranking_src, pagerank_src, scatter_style, ranking_style


if __name__ == '__main__':
    print('Starting PortalPath chart browser at http://localhost:8051')
    app.run(debug=False, port=8051)
