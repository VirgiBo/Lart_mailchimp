import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import html


def bar_fascia_stato(_href, df=None):
    # df expected to contain columns 'STATO' and 'FASCIA PREZZO'
    if df is None or df.empty:
        fig = px.bar(title='Nessun dato disponibile')
        return fig
    
    # Drop FASCIA PREZZO rows that are NaN or empty
    df = df[df['FASCIA PREZZO'].notna() & (df['FASCIA PREZZO'].str.strip() != '')]

    # normalize column names just in case
    cols = df.columns.astype(str).tolist()
    if 'STATO' not in cols or 'FASCIA PREZZO' not in cols:
        fig = px.bar(title='Colonne mancanti: STATO o FASCIA PREZZO')
        return fig

    # compute counts per STATO and FASCIA PREZZO
    tmp = df.copy()
    tmp['STATO'] = tmp['STATO'].astype(str)
    tmp['FASCIA PREZZO'] = tmp['FASCIA PREZZO'].astype(str)
    counts = tmp.groupby(['STATO', 'FASCIA PREZZO']).size().reset_index(name='count')

    # compute percent within each STATO (for hover only)
    totals = counts.groupby('STATO')['count'].transform('sum')
    counts['percent'] = counts['count'] / totals * 100

    # order STATO by total count descending
    state_order = counts.groupby('STATO')['count'].sum().sort_values(ascending=False).index.tolist()

    # pivot to get counts per STATO x FASCIA PREZZO
    pivot_count = counts.pivot(index='STATO', columns='FASCIA PREZZO', values='count').fillna(0)

    # ensure consistent state order
    pivot_count = pivot_count.reindex(state_order)

    # compute percent per state (row-wise)
    pivot_pct = pivot_count.div(pivot_count.sum(axis=1).replace({0: 1}), axis=0) * 100

    # build stacked traces (one per FASCIA PREZZO) so counts align correctly
    traces = []
    fascia_order = pivot_count.columns.tolist()
    for fascia in fascia_order:
        y_pct = pivot_pct[fascia].values.tolist()
        y_count = pivot_count[fascia].values.tolist()
        traces.append(go.Bar(
            x=pivot_count.index.tolist(),
            y=y_pct,
            name=fascia,
            text=[str(int(c)) if c > 0 else '' for c in y_count],
            textposition='inside',
            hovertemplate='STATO: %{x}<br>FASCIA PREZZO: ' + str(fascia) + '<br>Count: %{customdata[0]}<br>Percent: %{y:.1f}%<extra></extra>',
            customdata=[[c] for c in y_count]
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(barmode='stack', yaxis=dict(range=[0, 100], title='Percentuale (%)'),
                      legend_title_text='FASCIA PREZZO', title='Distribuzione % FASCIA PREZZO per STATO',
                      template='plotly_white', margin=dict(t=60, b=120))

    return fig