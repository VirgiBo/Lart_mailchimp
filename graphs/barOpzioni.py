import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import html


def bar_per_anno(_href, category_name='ARTISTA', asse_x='ANNO', df=None):
    """Stacked bar: X=asse_x (ANNO or STATO), Y=percentage of category within the group.
    Each stacked segment shows the raw count inside the bar and hover shows count and percent.

    asse_x: either 'ANNO' or 'STATO'
    """

    if df is None or df.empty:
        fig = px.bar(title='Nessun dato disponibile')
        return fig
    
    # Drop rows where category or asse_x is missing/empty
    if category_name == 'IVA':
        df = df[df[category_name].notna()]
    else:
        df = df[df[category_name].notna() & (df[category_name].astype(str).str.strip() != '')]

    if asse_x not in df.columns:
        return px.bar(title=f"Colonna mancante: {asse_x}")
    df = df[df[asse_x].notna()]

    # normalize column names
    cols = df.columns.astype(str).tolist()
    if 'ANNO' not in cols or category_name not in cols:
        fig = px.bar(title=f'Colonne mancanti: ANNO o {category_name}')
        return fig

    tmp = df.copy()
    tmp[asse_x] = tmp[asse_x].astype(str)
    tmp[category_name] = tmp[category_name].astype(str)

    # compute counts per group and category
    counts = tmp.groupby([asse_x, category_name]).size().reset_index(name='count')

    # pivot to get counts per group x category
    pivot_count = counts.pivot(index=asse_x, columns=category_name, values='count').fillna(0)

    # order groups: if ANNO try numeric, otherwise lexical
    if asse_x == 'ANNO':
        try:
            group_order = sorted(pivot_count.index, key=lambda x: int(float(x)))
        except Exception:
            group_order = sorted(pivot_count.index)
    elif asse_x == 'STATO':
        # order STATO by total count descending (like bar03)
        group_order = pivot_count.sum(axis=1).sort_values(ascending=False).index.tolist()
    else:
        group_order = sorted(pivot_count.index)
    pivot_count = pivot_count.reindex(group_order)

    # compute percent per ANNO (row-wise)
    pivot_pct = pivot_count.div(pivot_count.sum(axis=1).replace({0: 1}), axis=0) * 100

    # prepare x-axis display labels as: GROUP (total)
    totals_per_group = pivot_count.sum(axis=1).astype(int).to_dict()
    x_raw = pivot_count.index.tolist()
    x_display = []
    for a in x_raw:
        if asse_x == 'ANNO':
            try:
                label_group = str(int(float(a)))
            except Exception:
                label_group = str(a)
        else:
            label_group = str(a)
        total = totals_per_group.get(a, 0)
        x_display.append(f"{label_group} ({int(total)})")

    # build stacked traces (one per category)
    traces = []
    category_order = pivot_count.columns.tolist()
    for category in category_order:
        y_pct = pivot_pct[category].values.tolist()
        y_count = pivot_count[category].values.tolist()
        # customdata: [count, raw_group]
        custom = [[int(c), a] for c, a in zip(y_count, x_raw)]
        # show category label plus count inside the segment, e.g. "Value (12)"
        hover_label = f'{asse_x}: %{{customdata[1]}}<br>{category_name}: {category}<br>Count: %{{customdata[0]}}<br>Percent: %{{y:.1f}}%<extra></extra>'
        traces.append(go.Bar(
            x=x_display,
            y=y_pct,
            name=category,
            text=[f"{category} ({int(c)})" if c > 0 else '' for c in y_count],
            textposition='inside',
            hovertemplate=hover_label,
            customdata=custom
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(barmode='stack', yaxis=dict(range=[0, 100], title='Percentuale (%)'),
                      legend_title_text=category_name, title=f'Distribuzione % {category_name} per {asse_x}',
                      template='plotly_white', margin=dict(t=60, b=120))

    return fig