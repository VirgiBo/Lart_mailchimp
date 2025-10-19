import pandas as pd
from dash import dash_table, html


def top10_long(df):
    """Return a long/tidy DataFrame with columns ARTISTA, ANNO, rank, OPERA, count (top 3 per group).
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count'])

    if not set(['ARTISTA', 'ANNO', 'OPERA']).issubset(df.columns):
        return pd.DataFrame(columns=['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count'])

    df2 = df[['ARTISTA', 'ANNO', 'OPERA']].dropna()
    df2['ARTISTA'] = df2['ARTISTA'].astype(str).str.strip()
    df2['ANNO'] = df2['ANNO'].astype(str).str.strip()
    df2['OPERA'] = df2['OPERA'].astype(str).str.strip()

    counts = df2.groupby(['ARTISTA', 'ANNO', 'OPERA']).size().reset_index(name='count')
    counts = counts.sort_values(['ARTISTA', 'ANNO', 'count', 'OPERA'], ascending=[True, True, False, True])
    counts['rank'] = counts.groupby(['ARTISTA', 'ANNO'])['count'].rank(method='first', ascending=False).astype(int)

    top10 = counts[counts['rank'] <= 10].sort_values(['ARTISTA', 'ANNO', 'rank'])
    return top10[['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count']]


def top10_wide(df):
    long = top10_long(df)
    if long.empty:
        return pd.DataFrame()

    out_rows = []
    for (artist, anno), g in long.groupby(['ARTISTA', 'ANNO']):
        row = {'ARTISTA': artist, 'ANNO': anno}
        for _, r in g.sort_values('rank').iterrows():
            k = r['rank']
            row[f'OPERA{k}'] = r['OPERA']
            row[f'COUNT{k}'] = int(r['count'])
        out_rows.append(row)
    return pd.DataFrame(out_rows).sort_values(['ARTISTA', 'ANNO'])


def dash_table_from_df(df, page_size=20):
    if df is None or df.empty:
        return html.Div("Nessun dato disponibile")
    columns = [{"name": c, "id": c} for c in df.columns]
    table = dash_table.DataTable(
        data=df.to_dict('records'),
        columns=columns,
        page_size=page_size,
        sort_action='native',
        filter_action='native',
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'whiteSpace': 'normal', 'height': 'auto'},
    )
    return table
