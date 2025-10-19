import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import html


def bar_per_anno(_href, category_name='ARTISTA', df=None):
    """Stacked bar: X=ANNO, Y=percentage of category within the year.
    Each stacked segment shows the raw count inside the bar and hover shows count and percent.
    """

    if df is None or df.empty:
        fig = px.bar(title='Nessun dato disponibile')
        return fig
    
    #Drop category and anno NaN or empty
    if category_name=='IVA':
        df = df[df[category_name].notna()]
    else:
        df = df[df[category_name].notna() & (df[category_name].str.strip() != '')]

    df = df[df['ANNO'].notna()]

    # normalize column names
    cols = df.columns.astype(str).tolist()
    if 'ANNO' not in cols or category_name not in cols:
        fig = px.bar(title=f'Colonne mancanti: ANNO o {category_name}')
        return fig

    tmp = df.copy()
    tmp['ANNO'] = tmp['ANNO'].astype(str)
    tmp[category_name] = tmp[category_name].astype(str)

    # compute counts per ANNO and category
    counts = tmp.groupby(['ANNO', category_name]).size().reset_index(name='count')

    # pivot to get counts per ANNO x category
    pivot_count = counts.pivot(index='ANNO', columns=category_name, values='count').fillna(0)

    # order ANNO ascending (try numeric if possible)
    try:
        anno_order = sorted(pivot_count.index, key=lambda x: int(float(x)))
    except Exception:
        anno_order = sorted(pivot_count.index)
    pivot_count = pivot_count.reindex(anno_order)

    # compute percent per ANNO (row-wise)
    pivot_pct = pivot_count.div(pivot_count.sum(axis=1).replace({0: 1}), axis=0) * 100

    # prepare x-axis display labels as: YEAR (total)
    totals_per_anno = pivot_count.sum(axis=1).astype(int).to_dict()
    x_raw = pivot_count.index.tolist()
    x_display = []
    for a in x_raw:
        try:
            year_int = int(float(a))
            label_year = str(year_int)
        except Exception:
            label_year = str(a)
        total = totals_per_anno.get(a, 0)
        x_display.append(f"{label_year} ({int(total)})")

    # build stacked traces (one per category)
    traces = []
    category_order = pivot_count.columns.tolist()
    for category in category_order:
        y_pct = pivot_pct[category].values.tolist()
        y_count = pivot_count[category].values.tolist()
        # customdata: [count, raw_year]
        custom = [[int(c), a] for c, a in zip(y_count, x_raw)]
        # show artist label plus count inside the segment, e.g. "P. Rossi (12)"
        traces.append(go.Bar(
            x=x_display,
            y=y_pct,
            name=category,
            text=[f"{category} ({int(c)})" if c > 0 else '' for c in y_count],
            textposition='inside',
            hovertemplate=f'ANNO: %{{customdata[1]}}<br>{category_name}: {category}<br>Count: %{{customdata[0]}}<br>Percent: %{{y:.1f}}%<extra></extra>',
            customdata=custom
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(barmode='stack', yaxis=dict(range=[0, 100], title='Percentuale (%)'),
                      legend_title_text=category_name, title=f'Distribuzione % {category_name} per ANNO',
                      template='plotly_white', margin=dict(t=60, b=120))

    return fig