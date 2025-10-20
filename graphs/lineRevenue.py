
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _parse_data_anno(row, date_col, anno_col):
    """Parse a single row's DATA and ANNO columns to produce a datetime.
    
    Handles:
    - YYYY-MM-DD HH:MM:SS (datetime timestamp) → parse directly
    - dd/mm (day/month, year from ANNO) → combine with year
    - dd/mm/yy or dd/mm/yyyy → parse all three
    """
    try:
        raw = str(row[date_col]).strip().replace('\u200b', '')
    except (KeyError, TypeError):
        return pd.NaT
    
    if not raw or raw.lower() in ('nan', 'none', ''):
        return pd.NaT
    
    # Try direct pandas parsing first (handles YYYY-MM-DD HH:MM:SS)
    try:
        dt = pd.to_datetime(raw, errors='coerce')
        if pd.notna(dt):
            return dt
    except Exception:
        pass
    
    # Manual parsing for dd/mm or dd/mm/yy formats
    parts = [p.strip() for p in raw.replace('-', '/').split('/')]
    parts = [p.split()[0] if p else p for p in parts]  # strip time if attached to any part
    parts = [p for p in parts if p]  # remove empty strings
    
    try:
        if len(parts) == 2:
            # Case 1: day/month, year from ANNO
            day = int(parts[0])
            month = int(parts[1])
            year = None
            try:
                year = int(float(row[anno_col]))
            except (ValueError, TypeError, KeyError):
                pass
            if year is not None:
                return pd.Timestamp(year=year, month=month, day=day)
            else:
                return pd.NaT
        elif len(parts) == 3:
            # Case 2: day/month/year from DATA
            day = int(parts[0])
            month = int(parts[1])
            year_str = parts[2]
            year = int(year_str) if len(year_str) > 2 else 2000 + int(year_str)
            return pd.Timestamp(year=year, month=month, day=day)
        else:
            #print(f"DEBUG: unexpected parts count {len(parts)} for raw={raw} parts={parts}")
            return pd.NaT
    except (ValueError, TypeError) as e:
        #print(f"DEBUG: Exception parsing raw={raw} parts={parts}: {e}")
        return pd.NaT


def line_revenue(_href, df=None, sum_range='day', time_window="all_time"):
    """Plot singular sells per day.

    Parsing rules for `DATA`:
    - If DATA contains day/month (e.g. '31/08'), year is taken from `ANNO` column.
    - If DATA contains day/month/year (e.g. '31/8/25' or '31/08/2025'), parse all three.
      Two-digit years are interpreted as 2000+year (e.g. '25' -> 2025).

    The function returns a Figure with one trace per `place_col` (lighter) and an Overall trace (bold).
    # time_window can be 'all_time', 'last_year', 'last_3_months', 'last_month'
    """
    date_col='DATA'
    anno_col='ANNO'
    place_col='LUOGO DI VENDITA'

    #remove empty date lines
    df = df[df['DATA'].notna()]

    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(title='Nessun dato disponibile')
        return fig

    df = df.copy()

    # Find ANNO column (case-insensitive lookup not needed here; assumes exact column names)
    # Parse dates using apply with the helper function
    df['_date'] = df.apply(lambda row: _parse_data_anno(row, date_col, anno_col), axis=1)
    # filter by time_window if requested
    if time_window != "all_time":
        # Use last day of previous month (end of day) to include full current month's first day
        # This avoids cutting off the first day of the current month
        now = pd.Timestamp.now().replace(day=1) - pd.Timedelta(hours=25)
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

    # Collect unreadable date info
    unread_count = int(df['_date'].isna().sum())
    unread_sample = []
    if unread_count > 0:
        bad = df[df['_date'].isna()].head(20)
        # Prepare simple printable sample lines
        for _, r in bad.iterrows():
            artista = r.get('ARTISTA', '')
            opera = r.get('OPERA', '')
            raw_date = r.get(date_col, '')
            unread_sample.append(f"{raw_date} | {artista} | {opera}")

    print(f"[lineRevenue] Total rows: {len(df)}; Rows with readable dates: {len(df) - unread_count}; Unreadable: {unread_count}")

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

    print(f"[lineRevenue] After PREZZO filter: {len(dgood)} rows (dropped {dropped_price} non-numeric)")

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
        freq = 'MS'
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

    # add place traces as lines (using datetime index)
    if place_df is not None and not place_df.empty:
        # ensure index is datetime
        try:
            place_index = pd.to_datetime(place_df.index)
        except Exception:
            place_index = place_df.index
        for col in place_df.columns:
            fig.add_trace(go.Scatter(x=place_index, y=place_df[col], mode='lines+markers', name=str(col), line=dict(width=1), opacity=0.7))

    # overall bold line
    # overall date column name
    date_col_name = overall.columns[0]
    overall_x = pd.to_datetime(overall[date_col_name])
    fig.add_trace(go.Scatter(x=overall_x, y=overall['total'], mode='lines+markers', name='Overall', line=dict(width=3, color='black')))

    # prepare friendly tick labels: month names for month, ordinal weeks for week
    tickvals = list(overall_x)
    ticktext = None
    if sr == 'month':
        # show month name (e.g., 'August') — include year when multiple years present
        # use .dt.year on a Series
        years = overall_x.dt.year.unique() if hasattr(overall_x, 'dt') else pd.DatetimeIndex(overall_x).year.unique()
        if len(years) > 1:
            ticktext = [d.strftime('%B %Y') for d in overall_x]
        else:
            ticktext = [d.strftime('%B') for d in overall_x]
    elif sr == 'week':
        # ordinal week number like '1° Week'
        ticktext = []
        for d in overall_x:
            try:
                wk = int(d.isocalendar().week)
            except Exception:
                # fallback to weekofyear
                wk = int(d.week)
            ticktext.append(f"{wk}° Week")
    else:
        # day — use ISO date
        ticktext = [d.strftime('%Y-%m-%d') for d in overall_x]

    # limit number of ticks to avoid overcrowding (keep last tick)
    max_ticks = 70
    n_ticks = len(tickvals)
    if n_ticks > max_ticks:
        import math
        step = math.ceil(n_ticks / max_ticks)
        sel = list(range(0, n_ticks, step))
        if sel[-1] != n_ticks - 1:
            sel.append(n_ticks - 1)
        tickvals = [tickvals[i] for i in sel]
        ticktext = [ticktext[i] for i in sel]

    # print unreadable and drop info to terminal (not on graph)
    print(f"Total rows: {len(df)}; Rows with readable dates: {len(dgood)}; Rows with unreadable dates: {unread_count}")
    if unread_count:
        print("Sample unreadable date rows (date | ARTISTA | OPERA):")
        for s in unread_sample[:20]:
            print(" - ", s)
    if dropped_price:
        print(f"Dropped {dropped_price} rows because PREZZO was not numeric.")

    sum_range_conv = {'day': 'giorno', 'week': 'settimana', 'month': 'mese'}
    fig.update_layout(title=f'Vendite {sum_range_conv.get(sr, "giorno")} (somma PREZZO)', xaxis_title=sum_range_conv.get(sr, "giorno"), yaxis_title='PREZZO (somma)', template='plotly_white',
                      legend=dict(orientation='v', x=1.05, y=0.92, xanchor='right', yanchor='top', bgcolor='rgba(255,255,255,0.6)', bordercolor='rgba(0,0,0,0.1)', borderwidth=1, font=dict(size=10)))
    # set tickvals/ticktext for friendly labels but keep datetime x values for hover
    try:
        fig.update_xaxes(tickvals=tickvals, ticktext=ticktext)
    except Exception:
        fig.update_xaxes(tickformat=tickfmt)
    return fig