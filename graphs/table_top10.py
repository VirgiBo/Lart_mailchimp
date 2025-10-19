import pandas as pd
from dash import dash_table, html


def top10_long(df, artist=None, anno=None, top_n=10):
    """Return a long/tidy DataFrame with columns ARTISTA, ANNO, rank, OPERA, count.

    Filtering behavior:
    - If artist is provided and not 'Tutti', filter by that artist.
    - If anno is provided and not 'Tutti', filter by that year.
    - If artist == 'Tutti' or artist is None -> include all artists.
    - If anno == 'Tutti' or anno is None -> include all years.

    Output cases:
    - artist specified & anno specified: top-N per (ARTISTA, ANNO) as before.
    - artist == 'Tutti' & anno specified: top-N operas in that year (ARTISTA set to 'Tutti').
    - artist specified & anno == 'Tutti': top-N operas for that artist across all years (ANNO set to 'Tutti').
    - artist == 'Tutti' & anno == 'Tutti': all-time top-N operas across dataset (ARTISTA and ANNO set to 'Tutti').
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count'])

    required = {'ARTISTA', 'ANNO', 'OPERA'}
    if not required.issubset(set(df.columns)):
        return pd.DataFrame(columns=['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count'])

    df2 = df[['ARTISTA', 'ANNO', 'OPERA']].dropna().copy()
    df2['ARTISTA'] = df2['ARTISTA'].astype(str).str.strip()
    df2['ANNO'] = df2['ANNO'].astype(str).str.strip()
    df2['OPERA'] = df2['OPERA'].astype(str).str.strip()

    def is_all(x):
        if x is None:
            return True
        s = str(x).strip()
        return s == '' or s.lower() in ('tutti', 'all', 'tutto', 'tutte')

    artist_all = is_all(artist)
    anno_all = is_all(anno)

    # Case 1: both specific -> group by ARTISTA, ANNO, OPERA and rank per (ARTISTA,ANNO)
    if not artist_all and not anno_all:
        dff = df2[(df2['ARTISTA'] == str(artist)) & (df2['ANNO'] == str(anno))]
        if dff.empty:
            return pd.DataFrame(columns=['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count'])
        counts = dff.groupby(['ARTISTA', 'ANNO', 'OPERA']).size().reset_index(name='count')
        counts = counts.sort_values(['ARTISTA', 'ANNO', 'count', 'OPERA'], ascending=[True, True, False, True])
        counts['rank'] = counts.groupby(['ARTISTA', 'ANNO'])['count'].rank(method='first', ascending=False).astype(int)
        top = counts[counts['rank'] <= top_n].sort_values(['ARTISTA', 'ANNO', 'rank'])
        return top[['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count']]

    # Case 2: all artists, specific year -> top-N per year across all artists
    if artist_all and not anno_all:
        dff = df2[df2['ANNO'] == str(anno)]
        if dff.empty:
            return pd.DataFrame(columns=['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count'])
        counts = dff.groupby(['ANNO', 'OPERA']).size().reset_index(name='count')
        counts = counts.sort_values(['ANNO', 'count', 'OPERA'], ascending=[True, False, True])
        counts['rank'] = counts.groupby(['ANNO'])['count'].rank(method='first', ascending=False).astype(int)
        counts['ARTISTA'] = 'Tutti'
        top = counts[counts['rank'] <= top_n].sort_values(['ANNO', 'rank'])
        return top[['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count']]

    # Case 3: specific artist, all years -> top-N for artist across all years
    if not artist_all and anno_all:
        dff = df2[df2['ARTISTA'] == str(artist)]
        if dff.empty:
            return pd.DataFrame(columns=['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count'])
        counts = dff.groupby(['ARTISTA', 'OPERA']).size().reset_index(name='count')
        counts = counts.sort_values(['ARTISTA', 'count', 'OPERA'], ascending=[True, False, True])
        counts['rank'] = counts.groupby(['ARTISTA'])['count'].rank(method='first', ascending=False).astype(int)
        counts['ANNO'] = 'Tutti'
        top = counts[counts['rank'] <= top_n].sort_values(['ARTISTA', 'rank'])
        return top[['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count']]

    # Case 4: all artists and all years -> all-time top-N operas
    # Group by OPERA (and optionally ARTISTA if you want breaking by artist)
    dff = df2.copy()
    if dff.empty:
        return pd.DataFrame(columns=['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count'])
    counts = dff.groupby(['OPERA']).size().reset_index(name='count')
    counts = counts.sort_values(['count', 'OPERA'], ascending=[False, True])
    counts['rank'] = counts['count'].rank(method='first', ascending=False).astype(int)
    counts['ARTISTA'] = 'Tutti'
    counts['ANNO'] = 'Tutti'
    top = counts[counts['rank'] <= top_n].sort_values(['rank'])
    return top[['ARTISTA', 'ANNO', 'rank', 'OPERA', 'count']]


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
