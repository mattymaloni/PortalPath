import math
import os
import sys
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, no_update

# Allow running directly as `python viz/map.py` from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coords import SCHOOL_COORDS

# ── Data ──────────────────────────────────────────────────────────────────────
df = pd.read_csv('data/processed/edges.csv')
df = df[df['transfer_count'] >= 3]

all_schools = set(df['origin'].tolist() + df['destination'].tolist())
missing = all_schools - set(SCHOOL_COORDS.keys())
if missing:
    for s in missing:
        SCHOOL_COORDS[s] = (25.0, -80.0)
    print(f"WARNING: Missing coords for: {sorted(missing)}")

incoming_delta = df.groupby('destination')['avg_success_delta'].mean().to_dict()

min_count = df['transfer_count'].min()
max_count = df['transfer_count'].max()
def line_width(count):
    return 2 + ((count - min_count) / max(max_count - min_count, 1)) * 9

color_hex = {'green': '#2ecc71', 'amber': '#f39c12', 'red': '#e74c3c'}

def edge_color(delta):
    if delta > 0.1: return 'green'
    if delta > 0:   return 'amber'
    return 'red'

# ── Build figure ───────────────────────────────────────────────────────────────
def build_figure(highlight_school=None):
    fig = go.Figure()

    if highlight_school:
        conn_mask = (df['origin'] == highlight_school) | (df['destination'] == highlight_school)
        edge_groups = [(df[conn_mask], 0.9)]
    else:
        edge_groups = []

    edge_set = set(zip(df['origin'], df['destination']))
    bidir_pairs = {(a, b) for (a, b) in edge_set if (b, a) in edge_set}

    def perpendicular_offset(olat, olon, dlat, dlon, amount=0.3):
        dx = dlon - olon
        dy = dlat - olat
        dist = math.sqrt(dx*dx + dy*dy) or 1
        return dy/dist * amount, -dx/dist * amount

    for edge_df, opacity in edge_groups:
        for _, row in edge_df.iterrows():
            olat, olon = SCHOOL_COORDS[row['origin']]
            dlat, dlon = SCHOOL_COORDS[row['destination']]
            w = line_width(row['transfer_count'])
            col = color_hex[edge_color(row['avg_success_delta'])]
            tip_text = (f"<b>{row['origin']} → {row['destination']}</b><br>"
                        f"Avg delta: {row['avg_success_delta']:+.3f}<br>"
                        f"Transfers: {int(row['transfer_count'])}")

            plat, plon = 0, 0
            pair = (row['origin'], row['destination'])
            if pair in bidir_pairs:
                sign = 1 if row['origin'] < row['destination'] else -1
                plat, plon = perpendicular_offset(olat, olon, dlat, dlon)
                plat, plon = plat * sign, plon * sign

            olat_o, olon_o = olat + plat, olon + plon
            dlat_o, dlon_o = dlat + plat, dlon + plon

            fig.add_trace(go.Scattergeo(
                lat=[olat_o, dlat_o], lon=[olon_o, dlon_o],
                mode='lines',
                line=dict(width=w, color=col),
                opacity=opacity,
                hoverinfo='text',
                hovertext=tip_text,
                showlegend=False,
            ))
            fig.add_trace(go.Scattergeo(
                lat=[dlat_o], lon=[dlon_o],
                mode='markers',
                marker=dict(symbol='circle', size=max(w + 2, 6), color=col,
                            line=dict(width=1, color='rgba(0,0,0,0.5)')),
                opacity=opacity,
                hoverinfo='skip',
                showlegend=False,
            ))

    # ── School nodes ──────────────────────────────────────────────────────────
    dest_counts = df.groupby('destination')['transfer_count'].sum().to_dict()
    schools = sorted(all_schools)
    node_lats  = [SCHOOL_COORDS[s][0] for s in schools]
    node_lons  = [SCHOOL_COORDS[s][1] for s in schools]
    node_sizes = [10 + dest_counts.get(s, 0) * 0.35 for s in schools]

    if highlight_school:
        connected_schools = set(
            df[df['origin'] == highlight_school]['destination'].tolist() +
            df[df['destination'] == highlight_school]['origin'].tolist() +
            [highlight_school]
        )
        node_opacity = [1.0 if s in connected_schools else 0.12 for s in schools]
    else:
        node_opacity = [0.9] * len(schools)

    hover_texts = []
    for s in schools:
        out_r = len(df[df['origin'] == s])
        in_r  = len(df[df['destination'] == s])
        avg_d = incoming_delta.get(s)
        delta_str = f"{avg_d:+.3f}" if avg_d is not None else "N/A"
        hover_texts.append(
            f"<b>{s}</b><br>"
            f"Avg incoming delta: {delta_str}<br>"
            f"Outgoing routes: {out_r} | Incoming: {in_r}"
        )

    fig.add_trace(go.Scattergeo(
        lat=node_lats, lon=node_lons,
        mode='markers+text',
        marker=dict(
            size=node_sizes,
            color='#3498db',
            opacity=node_opacity,
            line=dict(width=1, color='rgba(255,255,255,0.4)'),
        ),
        text=schools,
        textposition='top center',
        textfont=dict(size=8, color='rgba(255,255,255,0.7)'),
        customdata=schools,
        hovertext=hover_texts,
        hoverinfo='text',
        showlegend=False,
    ))

    fig.update_layout(
        geo=dict(
            scope='usa',
            projection_type='albers usa',
            showland=True,    landcolor='#1e2a3a',
            showocean=True,   oceancolor='#0d1117',
            showlakes=True,   lakecolor='#0d1117',
            showcoastlines=True, coastlinecolor='#2c3e50',
            showsubunits=True,   subunitcolor='#2c3e50',
            bgcolor='#0d1117',
        ),
        paper_bgcolor='#0d1117',
        plot_bgcolor='#0d1117',
        margin=dict(l=0, r=0, t=0, b=0),
        hoverlabel=dict(bgcolor='#1a1a2e', font_color='white'),
    )
    return fig

# ── Dash app ───────────────────────────────────────────────────────────────────
app = Dash(__name__)

def default_panel():
    return [
        html.P('Click any school to reveal its transfer routes.',
               style={'color': '#aaa', 'font-size': '13px'}),
        html.P('Click the same school or Clear Selection to reset.',
               style={'color': '#666', 'font-size': '12px'}),
        html.Hr(style={'border-color': '#2c3e50', 'margin': '16px 0 12px 0'}),
        html.P('Arc colors:', style={'color': '#aaa', 'font-size': '12px', 'margin-bottom': '6px'}),
        html.Div([html.Span('●', style={'color': '#2ecc71'}), ' Delta > 0.1 (improved)'],
                 style={'color': '#ccc', 'font-size': '12px', 'margin-bottom': '3px'}),
        html.Div([html.Span('●', style={'color': '#f39c12'}), ' Delta 0–0.1 (slight gain)'],
                 style={'color': '#ccc', 'font-size': '12px', 'margin-bottom': '3px'}),
        html.Div([html.Span('●', style={'color': '#e74c3c'}), ' Delta < 0 (declined)'],
                 style={'color': '#ccc', 'font-size': '12px', 'margin-bottom': '12px'}),
        html.P('Arc thickness = transfer volume', style={'color': '#666', 'font-size': '11px'}),
        html.P('Node size = incoming transfer volume', style={'color': '#666', 'font-size': '11px'}),
    ]

app.layout = html.Div([
    dcc.Store(id='selected-school', data=None),
    html.Div([
        dcc.Graph(
            id='map',
            figure=build_figure(),
            style={'height': '100vh'},
            config={'scrollZoom': True},
        )
    ], style={'width': '75%', 'display': 'inline-block', 'vertical-align': 'top'}),

    html.Div([
        html.H2('PortalPath', style={'color': '#3498db', 'margin': '0 0 2px 0', 'font-size': '22px'}),
        html.P('Transfer Network Map', style={'color': '#555', 'margin': '0 0 14px 0', 'font-size': '11px'}),
        html.Button('Clear Selection', id='clear-btn',
                    style={
                        'background': '#1e2a3a', 'color': '#aaa', 'border': '1px solid #2c3e50',
                        'padding': '6px 12px', 'border-radius': '4px', 'cursor': 'pointer',
                        'font-size': '12px', 'margin-bottom': '16px', 'display': 'none',
                    },
                    n_clicks=0),
        html.Div(id='panel-content', children=default_panel()),
    ], style={
        'width': '23%', 'display': 'inline-block', 'vertical-align': 'top',
        'background': '#0d1117', 'color': 'white',
        'padding': '24px 16px', 'height': '100vh',
        'overflow-y': 'auto', 'box-sizing': 'border-box',
        'border-left': '1px solid #2c3e50',
    }),
], style={'display': 'flex', 'background': '#0d1117', 'margin': 0, 'padding': 0})


@app.callback(
    Output('map', 'figure'),
    Output('panel-content', 'children'),
    Output('selected-school', 'data'),
    Output('clear-btn', 'style'),
    Input('map', 'clickData'),
    Input('clear-btn', 'n_clicks'),
    State('selected-school', 'data'),
    prevent_initial_call=True,
)
def on_interaction(clickData, _clear_clicks, current_school):
    from dash import ctx
    btn_hidden  = {'background': '#1e2a3a', 'color': '#aaa', 'border': '1px solid #2c3e50',
                   'padding': '6px 12px', 'border-radius': '4px', 'cursor': 'pointer',
                   'font-size': '12px', 'margin-bottom': '16px', 'display': 'none'}
    btn_visible = {**btn_hidden, 'display': 'block'}

    if ctx.triggered_id == 'clear-btn':
        return build_figure(), default_panel(), None, btn_hidden

    if not clickData:
        return no_update, no_update, no_update, no_update

    point = clickData['points'][0]
    if 'customdata' not in point:
        return no_update, no_update, no_update, no_update

    school = point['customdata']

    if school == current_school:
        return build_figure(), default_panel(), None, btn_hidden

    outgoing = df[df['origin'] == school].sort_values('avg_success_delta', ascending=False)
    incoming = df[df['destination'] == school].sort_values('avg_success_delta', ascending=False)

    def dc(d):
        if d > 0.1: return '#2ecc71'
        if d > 0:   return '#f39c12'
        return '#e74c3c'

    def route_rows(rows, col):
        items = []
        for _, r in rows.head(5).iterrows():
            other = r['destination'] if col == 'destination' else r['origin']
            d = r['avg_success_delta']
            arrow = '→' if col == 'destination' else '←'
            items.append(html.Div([
                html.Span(f"{arrow} {other}", style={'flex': '1', 'font-size': '12px'}),
                html.Span(f"{d:+.3f}", style={'color': dc(d), 'font-size': '12px', 'font-weight': 'bold'}),
            ], style={'display': 'flex', 'justify-content': 'space-between',
                      'padding': '5px 0', 'border-bottom': '1px solid #1e2a3a'}))
        return items

    avg_out = outgoing['avg_success_delta'].mean() if len(outgoing) else 0
    avg_in  = incoming['avg_success_delta'].mean() if len(incoming) else 0

    panel = [
        html.H3(school, style={'color': '#3498db', 'margin': '0 0 12px 0', 'font-size': '18px'}),
        html.Hr(style={'border-color': '#2c3e50', 'margin': '0 0 12px 0'}),
        html.Div([
            html.Div([
                html.Div(str(len(outgoing)), style={'font-size': '24px', 'color': '#3498db', 'font-weight': 'bold'}),
                html.Div('outgoing', style={'font-size': '10px', 'color': '#666'}),
            ], style={'text-align': 'center', 'flex': '1'}),
            html.Div([
                html.Div(str(len(incoming)), style={'font-size': '24px', 'color': '#9b59b6', 'font-weight': 'bold'}),
                html.Div('incoming', style={'font-size': '10px', 'color': '#666'}),
            ], style={'text-align': 'center', 'flex': '1'}),
        ], style={'display': 'flex', 'margin-bottom': '16px'}),

        html.Div('Top Outgoing Destinations', style={'color': '#aaa', 'font-size': '11px',
                 'text-transform': 'uppercase', 'letter-spacing': '1px', 'margin-bottom': '6px'}),
        html.Div(route_rows(outgoing, 'destination') or
                 [html.P('No data', style={'color': '#666', 'font-size': '12px'})]),
        html.Div(f"Avg delta: {avg_out:+.3f}", style={'color': dc(avg_out),
                 'font-size': '12px', 'margin': '6px 0 14px 0'}),

        html.Div('Top Incoming Sources', style={'color': '#aaa', 'font-size': '11px',
                 'text-transform': 'uppercase', 'letter-spacing': '1px', 'margin-bottom': '6px'}),
        html.Div(route_rows(incoming, 'origin') or
                 [html.P('No data', style={'color': '#666', 'font-size': '12px'})]),
        html.Div(f"Avg delta: {avg_in:+.3f}", style={'color': dc(avg_in),
                 'font-size': '12px', 'margin': '6px 0 0 0'}),
    ]

    return build_figure(highlight_school=school), panel, school, btn_visible


if __name__ == '__main__':
    print("Starting PortalPath map at http://localhost:8050")
    app.run(debug=False, port=8050)
