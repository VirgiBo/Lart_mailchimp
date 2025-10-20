import plotly.express as px

def pie_stato(_href, df=None):

    counts = {}
    if not df.empty and 'STATO' in df.columns:
        vc = df['STATO'].fillna('N/A').astype(str).value_counts()
        counts = vc.to_dict()

    if not counts:
        # return a minimal pie with a single 'N/A' slice so the layout still renders
        fig = px.pie(names=['N/A'], values=[1], title='Opere vendute per Stato', template='plotly_white')
        fig.update_traces(textinfo='text+value', textposition='inside')
        fig.update_layout(showlegend=False, margin=dict(t=80, l=10, r=10, b=50), height=480)
        return fig

    # sort descending
    items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    labels = [k for k, v in items]
    values = [v for k, v in items]

    fig = px.pie(names=labels, values=values, title='Opere vendute per Stato', template='plotly_white')

    # compute legend labels (name with absolute count)
    legend_labels = [f"{lab} ({val})" for lab, val in items]

    # Safely update the first trace if present
    if fig.data:
        trace = fig.data[0]
        # Keep inside slice text as the STATE name, but show counts in the legend
        trace.text = labels
        # plotly pie uses 'labels' attribute for the legend; set it if available
        try:
            trace.labels = legend_labels
        except Exception:
            pass
        trace.textinfo = 'text+value'
        trace.textposition = 'inside'
        try:
            trace.insidetextfont = dict(size=14, color="white", family="Arial Black")
        except Exception:
            pass
        try:
            trace.marker = dict(line=dict(width=0))
        except Exception:
            pass
        trace.hovertemplate = '%{text}<br>Value: %{value}<br>Percent: %{percent:.1%}<extra></extra>'

    fig.update_layout(showlegend=True, legend=dict(orientation='v', y=0.5, x=1.02), margin=dict(t=100, l=10, r=140, b=50), height=640)

    return fig