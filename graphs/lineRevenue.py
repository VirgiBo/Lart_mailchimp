
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def line_revenue(_href, df=None, sum_range='day', time_window="all_time"):
    """Plot singular sells per day.

    Parsing rules for `DATA`:
    - If DATA contains day/month/year (e.g. '31/8/25' or '31/08/2025'), parse directly.
      Two-digit years are interpreted as 2000+year (e.g. '25' -> 2025).
    - If DATA contains only day/month (e.g. '31/08') then year is taken from `ANNO` column.

    The function returns a Figure with one trace per `place_col` (lighter) and an Overall trace (bold).
    It also annotates how many rows had unreadable dates and shows a short sample of their ARTISTA/OPERA.
    # time_window can be 'all_time', 'last_year', 'last_3_months', 'last_month'

    """
    date_col='DATA'
    anno_col='ANNO'
    place_col='LUOGO DI VENDITA'

    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(title='Nessun dato disponibile')
        return fig

    df = df.copy()

    # helper to parse each DATA value
    parsed_dates = []
    unreadable = []

    # detect anno column case-insensitively
    anno_col_found = None
    for c in df.columns:
        if str(c).strip().upper() == str(anno_col).strip().upper():
            anno_col_found = c
            break
    if anno_col_found is None:
        # try any column named like 'ANNO'
        for c in df.columns:
            if str(c).strip().upper() == 'ANNO':
                anno_col_found = c
                break

    for idx, row in df.iterrows():
        raw = ''
        if date_col in df.columns:
            raw = str(row.get(date_col, '')).strip()
        raw = raw.replace('\u200b', '').strip()  # remove zero-width if present
        if not raw or raw.lower() in ('nan', 'none'):
            parsed_dates.append(pd.NaT)
            unreadable.append((idx, row))
            continue

        # try direct pandas parsing first (handles many formats, with dayfirst)
        try:
            direct = pd.to_datetime(raw, dayfirst=True, errors='coerce')
            if pd.notna(direct):
                parsed_dates.append(direct)
                continue
        except Exception:
            pass

        parts = [p.strip() for p in raw.replace('-', '/').split('/') if p.strip()!='']
        year_val = None
        day = None
        month = None
        try:
            if len(parts) == 3:
                # dd/mm/yy or dd/mm/yyyy
                day = int(parts[0])
                month = int(parts[1])
                y = parts[2]
                if len(y) <= 2:
                    year_val = 2000 + int(y)
                else:
                    year_val = int(y)
            elif len(parts) == 2:
                day = int(parts[0])
                month = int(parts[1])
                # take year from ANNO column if available
                if anno_col_found is not None:
                    try:
                        year_val = int(float(row.get(anno_col_found)))
                    except Exception:
                        year_val = None
                else:
                    year_val = None
            else:
                year_val = None

            if year_val is not None and day is not None and month is not None:
                parsed_dates.append(pd.Timestamp(year=year_val, month=month, day=day))
            else:
                parsed_dates.append(pd.NaT)
                unreadable.append((idx, row))
        except Exception:
            parsed_dates.append(pd.NaT)
            unreadable.append((idx, row))

    df['_date'] = pd.to_datetime(pd.Series(parsed_dates), errors='coerce')
    # filter by time_window if requested
    if time_window != "all_time":
        now = pd.Timestamp.now()
        if time_window == "last_year":
            cutoff = now - pd.DateOffset(years=1)
        elif time_window == "last_3_months":
            cutoff = now - pd.DateOffset(months=3)
        elif time_window == "last_month":
            cutoff = now - pd.DateOffset(months=1)
        else:
            cutoff = None

        if cutoff is not None:
            df = df[df['_date'] >= cutoff].copy()

    # Before parsing we already parsed dates; collect unreadable info
    unread_count = int(df['_date'].isna().sum())
    unread_sample = []
    if unread_count > 0:
        bad = df[df['_date'].isna()].head(20)
        # Prepare simple printable sample lines
        for _, r in bad.iterrows():
            artista = r.get('ARTISTA', '')
            opera = r.get('OPERA', '')
            raw_date = r.get(date_col, '') if date_col in df.columns else ''
            unread_sample.append(f"{raw_date} | {artista} | {opera}")

    # drop rows without readable date
    dgood = df[df['_date'].notna()].copy()
    if dgood.empty:
        fig = go.Figure()
        title = 'Nessun dato valido (date parsing fallito)'
        if unread_count:
            title += f' — {unread_count} righe non leggibili'
        fig.update_layout(title=title)
        return fig

    # aggregate daily counts
    # drop rows that do not have a numeric PREZZO before plotting (we were asked to drop them earlier)
    # Ensure price column exists
    price_col = 'PREZZO'
    if price_col not in dgood.columns:
        print(f"Warning: price column '{price_col}' not found. No data to plot.")
        fig = go.Figure()
        fig.update_layout(title="Nessun dato disponibile (colonna PREZZO mancante)")
        return fig

    dgood['_price'] = pd.to_numeric(dgood[price_col], errors='coerce')
    # drop rows without numeric price
    before_drop = len(dgood)
    dgood = dgood[dgood['_price'].notna()].copy()
    dropped_price = before_drop - len(dgood)

    if dgood.empty:
        print(f"No valid rows after dropping non-numeric PREZZO. Dropped {dropped_price} rows.")
        fig = go.Figure()
        fig.update_layout(title='Nessun dato valido (nessun PREZZO numerico)')
        return fig

    # aggregate sum of PREZZO per requested range (day/week/month)
    sr = str(sum_range).strip().lower() if sum_range else 'day'
    if sr == 'day':
        freq = 'D'
        x_title = 'Giorno'
        tickfmt = '%Y-%m-%d'
    elif sr == 'week':
        # week starting Monday
        freq = 'W-MON'
        x_title = 'Settimana (inizio)'
        tickfmt = '%Y-%m-%d'
    elif sr == 'month':
        freq = 'M'
        x_title = 'Mese'
        tickfmt = '%Y-%m'
    else:
        freq = 'D'
        x_title = 'Giorno'
        tickfmt = '%Y-%m-%d'

    base = dgood.set_index('_date')
    # overall sum per period
    overall = base['_price'].resample(freq, label='left', closed='left').sum().reset_index(name='total').sort_values('_date')

    # by place: groupby place then resample, then unstack so rows are periods
    place_df = None
    if place_col in dgood.columns:
        grp = base.groupby(place_col)['_price'].resample(freq, label='left', closed='left').sum()
        # grp is Series with MultiIndex (place, date); unstack to have date index and columns=places
        try:
            place_df = grp.unstack(level=0).fillna(0)
        except Exception:
            # fallback using pivot_table on period
            tmp = base.reset_index()
            tmp['_period'] = tmp['_date'].dt.to_period('M').dt.to_timestamp() if freq == 'M' else tmp['_date'].dt.to_period('W').dt.start_time if freq.startswith('W') else tmp['_date'].dt.floor('D')
            place_df = tmp.pivot_table(index='_period', columns=place_col, values='_price', aggfunc='sum', fill_value=0)

    fig = go.Figure()

    # add place traces as lines
    if place_df is not None and not place_df.empty:
        for col in place_df.columns:
            fig.add_trace(go.Scatter(x=place_df.index, y=place_df[col], mode='lines+markers', name=str(col), line=dict(width=1), opacity=0.7))

    # overall bold line
    # overall['_date'] may be named differently depending on reset_index
    date_col_name = overall.columns[0]
    fig.add_trace(go.Scatter(x=overall[date_col_name], y=overall['total'], mode='lines+markers', name='Overall', line=dict(width=3, color='black')))

    # print unreadable and drop info to terminal (not on graph)
    print(f"Total rows: {len(df)}; Rows with readable dates: {len(dgood)}; Rows with unreadable dates: {unread_count}")
    if unread_count:
        print("Sample unreadable date rows (date | ARTISTA | OPERA):")
        for s in unread_sample[:20]:
            print(" - ", s)
    if dropped_price:
        print(f"Dropped {dropped_price} rows because PREZZO was not numeric.")

    sum_range_conv = {'day': 'giorno', 'week': 'settimana', 'month': 'mese'}
    fig.update_layout(title=f'Vendite {sum_range_conv.get(sr, "giorno")} (somma PREZZO)', xaxis_title=sum_range_conv.get(sr, "giorno"), yaxis_title='PREZZO (somma)', template='plotly_white', legend=dict(orientation='h'))
    fig.update_xaxes(tickformat='%Y-%m-%d')
    return fig