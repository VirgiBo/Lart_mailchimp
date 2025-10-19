import pandas as pd
import plotly.express as px
from dash import html


def pie_stato(_href, df=None):

    counts = {}
    if not df.empty and 'STATO' in df.columns:
        vc = df['STATO'].fillna('N/A').astype(str).value_counts()
        counts = vc.to_dict()

    if not counts:
        fig = px.pie(names=['N/A'], values=[1], title='Opere vendute per Stato')
        legend_children = [html.Div('No data available')]
        return fig, legend_children

    # sort descending
    items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    labels = [k for k, v in items]
    values = [v for k, v in items]

    fig = px.pie(names=labels, values=values, title='Opere vendute per Stato', template='plotly_white')
    # compute percentages for legend labels
    total = sum(values) if values else 1
    legend_labels = [f"{lab} ({val})" for lab, val in items]

    # Keep inside slice text as the STATE name and value, but set legend labels to include percent
    # We set `labels` (used by legend) to legend_labels and use `text` for the slice text.
    fig.data[0].labels = legend_labels
    fig.data[0].text = labels
    fig.update_traces(textinfo='text+value', 
                        textposition='inside', 
                        insidetextfont=dict(size=14, color="white", family="Arial Black"),
                        marker=dict(line=dict(width=0)),
                        hovertemplate='%{text}<br>Value: %{value}<br>Percent: %{percent:.1%}<extra></extra>')
    fig.update_layout(showlegend=True, legend=dict(orientation='v', y=0.5, x=1.02), margin=dict(t=100, l=10, r=140, b=50), height=640)

    return fig