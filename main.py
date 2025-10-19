import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, State
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from dotenv import load_dotenv  # optional, only if you want .env support
import secrets
import time
import os
import re
import io
import requests


# load .env (optional)
load_dotenv()

DRIVE_PATH = os.getenv("DRIVE_PATH")
# Require DRIVE_PATH only (no local fallback)
if not DRIVE_PATH:
    raise RuntimeError("DRIVE_PATH environment variable not set. Set DRIVE_PATH to the folder containing 'data/dati.xlsx' or to the full path of the Excel file.")

# normalize user input (expand ~ and env vars)
DRIVE_PATH = os.path.expanduser(os.path.expandvars(DRIVE_PATH))

# The app will use DRIVE_PATH directly; the actual Excel path is computed inside leggi_dati().
is_url = DRIVE_PATH.lower().startswith(('http://', 'https://'))
if not is_url and not os.path.exists(DRIVE_PATH) and not DRIVE_PATH.lower().endswith(('.xlsx', '.xls', '.xlsm', '.ods')):
    # If user provided a folder path that doesn't exist, fail early with a clear message.
    raise RuntimeError(f"DRIVE_PATH does not exist: {DRIVE_PATH}. Set DRIVE_PATH to an existing folder or an existing Excel file path, or provide a publicly accessible Google Sheets URL.")

# 🔹 Funzione per leggere i dati Excel
def leggi_dati():
    """Read the 2nd and 3rd sheets, tag rows from the 2nd sheet as STATO='Italia', and return a single combined DataFrame.

    Behavior:
    - sheet 1 (second sheet) -> add column STATO with value 'Italia'
    - sheet 2 (third sheet) -> use existing STATO column if present
    - result is concat of both sheets with same columns (missing columns filled with NaN)
    """
    # compute the actual excel source from DRIVE_PATH (it may be a Google Sheets URL, a file, or a folder)
    try:
        df0 = pd.DataFrame()
        df1 = pd.DataFrame()

        if DRIVE_PATH.lower().startswith(('http://', 'https://')):
            # try to convert common Google Sheets share link to the export xlsx URL
            url = DRIVE_PATH
            m = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
            if m:
                sheet_id = m.group(1)
                export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
            else:
                # fallback: use the provided URL directly
                export_url = url

            try:
                resp = requests.get(export_url, timeout=20)
                resp.raise_for_status()
                excel_bytes = io.BytesIO(resp.content)

                # read the 2nd and 3rd sheets (sheet_name=1 and sheet_name=2)
                try:
                    df0 = pd.read_excel(excel_bytes, sheet_name=1)
                    df0.rename(columns=lambda x: x.strip(), inplace=True)
                    # Drop rows with no name
                    df0 = df0[df0['NOME'].notna()]

                except Exception as e0:
                    print("⚠️ unable to read sheet 1 from URL:", e0)

                # reset buffer to read third sheet
                excel_bytes.seek(0)
                try:
                    df1 = pd.read_excel(excel_bytes, sheet_name=2)
                    df1.rename(columns=lambda x: x.strip(), inplace=True)
                except Exception as e1:
                    print("⚠️ unable to read sheet 2 from URL:", e1)
            except Exception as e:
                raise FileNotFoundError(f"Unable to download Excel from URL {export_url}: {e}")
        # ensure df0 has STATO column set to 'Italia'
        if not df0.empty:
            df0 = df0.copy()
            df0['STATO'] = 'Italia'

        # If both empty, return empty DF
        if (df0.empty) and (df1.empty):
            return pd.DataFrame()

        # Align columns: union of both frames' columns
        cols = list(dict.fromkeys(list(df0.columns) + list(df1.columns)))
        df0 = df0.reindex(columns=cols)
        df1 = df1.reindex(columns=cols)

        combined = pd.concat([df0, df1], ignore_index=True, sort=False)

        combined['ARTISTA'] = combined['ARTISTA'].str.strip()
        combined['ARTISTA'] = combined['ARTISTA'].str.replace('Dali', 'Dalì', regex=True)

        # Clean up FASCIA PREZZO values
        combined['FASCIA PREZZO'] = combined['FASCIA PREZZO'].str.replace('1500 < X < 5000 €', '1500 - 5000', regex=True)
        combined['FASCIA PREZZO'] = combined['FASCIA PREZZO'].str.replace('> 5000 €', '> 5000', regex=True)
        combined['FASCIA PREZZO'] = combined['FASCIA PREZZO'].str.replace('< 1500 €', '< 1500', regex=True)

        #round to two digits only if the value is float not if is string NO IVA
        def round_if_float(x):
            try:
                return str(round(float(x*100)))+"%"
            except:
                return x
        combined['IVA'] = combined['IVA'].apply(round_if_float)

        #round year
        def clean_year(x):
            try:
                return str(int(float(x)))
            except:
                return x

        combined['ANNO'] = combined['ANNO'].apply(clean_year)

        return combined
    
    except Exception as e:
        print("❌ Errore nel caricamento/merge dei fogli:", e)
        return pd.DataFrame()

# 🔹 Crea l'app Dash
app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "Analisi Dati in Tempo Reale"

# ensure Flask session secret is set (avoids: "Session is not available. Have you set a secret key?")
app.server.secret_key = os.getenv('SECRET_KEY') or secrets.token_hex(16)


# read env vars safely
dash_user = os.getenv("DASH_USER")
dash_pass = os.getenv("DASH_PASS")

if not (dash_user and dash_pass):
    print("⚠️ DASH_USER/DASH_PASS not set. App will run without basic auth.")
    VALID = {}
else:
    VALID = {dash_user: dash_pass}
    try:
        from dash_auth import BasicAuth
        BasicAuth(app, VALID)
        print("🔒 BasicAuth enabled")
    except Exception as e:
        print("⚠️ dash-auth not installed or failed to initialize:", e)
        print("→ install: pip install dash-auth")
        VALID = {}


# 🔹 Layout iniziale
app.layout = html.Div([
    html.H1("📊 Analisi Dati ", style={'textAlign': 'center'}),
    # separation line with spacing
    html.Hr(style={
    'height': '2px',
    'backgroundColor': '#cfcfcf',
    'border': 'none',
    'width': '90%',
    'margin': '20px auto'
    }),

    # pie chart with built-in Plotly legend
    html.Div([
        dcc.Graph(id='pie-stato', style={'width': '100%'}),
    ], style={'width': '90%', 'margin': 'auto'}),

    # separation line with spacing
    html.Hr(style={
    'height': '2px',
    'backgroundColor': '#cfcfcf',
    'border': 'none',
    'width': '90%',
    'margin': '20px auto'
    }),

    # selectable category bar chart (ARTISTA / IVA / FASCIA PREZZO)
    html.Div([
        html.Label('Scegli asse X:'),
        dcc.Dropdown(id='bar-asse-x-select', options=[
            {'label': 'ANNO', 'value': 'ANNO'},
            {'label': 'STATO', 'value': 'STATO'},
        ], value='ANNO', clearable=False, style={'width': '200px', 'display': 'inline-block', 'marginRight': '12px'}),

        html.Label('Scegli categoria:'),
        dcc.Dropdown(id='bar-category-select', options=[
            {'label': 'ARTISTA', 'value': 'ARTISTA'},
            {'label': 'IVA', 'value': 'IVA'},
            {'label': 'FASCIA PREZZO', 'value': 'FASCIA PREZZO'},
        ], value='ARTISTA', clearable=False, style={'width': '300px', 'display': 'inline-block'}),

        dcc.Graph(id='bar-artista', style={'width': '100%'})
    ], style={'width': '90%', 'margin': 'auto'}),

    # separation line with spacing
    html.Hr(style={
    'height': '2px',
    'backgroundColor': '#cfcfcf',
    'border': 'none',
    'width': '90%',
    'margin': '20px auto'
    }),


    # Top-10 operas table controls
    html.H2("Top 10 opere per ARTISTA × ANNO", style={'textAlign': 'center'}),
    html.Div([
        dcc.Dropdown(id='top10-artist-filter', placeholder='Filtro ARTISTA (opzionale)', multi=False, style={'width': '45%', 'display': 'inline-block', 'marginRight': '10px'}),
        dcc.Dropdown(id='top10-year-filter', placeholder='Filtro ANNO (opzionale)', multi=False, style={'width': '30%', 'display': 'inline-block'}),
    ], style={'width': '90%', 'margin': 'auto', 'marginTop': 10}),
    html.Div(id='top10-table-container', style={'width': '90%', 'margin': 'auto', 'marginTop': 10}),

    html.Div(id='ultimo-aggiornamento', style={'textAlign': 'center', 'marginTop': 20}),
    # trigger updates on page load / refresh
    dcc.Location(id='url', refresh=False),
])

df = leggi_dati()

from graphs.tortaStati import pie_stato
@app.callback(Output('pie-stato', 'figure'), Input('url', 'href'))
def update_pie_chart(_href, df=df):
    return pie_stato(_href, df=df)

from graphs.barOpzioni import bar_per_anno
# new chart: selectable category per year (ARTISTA / IVA / FASCIA PREZZO)
@app.callback(Output('bar-artista', 'figure'), [Input('url', 'href'), Input('bar-category-select', 'value'), Input('bar-asse-x-select', 'value')])
def update_bar_chart_category(_href, selected_category, selected_asse_x, df=df):
    # default fallback
    if not selected_category:
        selected_category = 'ARTISTA'
    if not selected_asse_x:
        selected_asse_x = 'ANNO'
    return bar_per_anno(_href, df=df, category_name=selected_category, asse_x=selected_asse_x)


from graphs.table_top10 import top10_long, dash_table_from_df


@app.callback(
    [Output('top10-artist-filter', 'options'), Output('top10-year-filter', 'options'),
     Output('top10-artist-filter', 'value'), Output('top10-year-filter', 'value')],
    Input('url', 'href')
)
def fill_top10_filters(_href):
    """Populate artist/year options and set default selections.

    Default artist: 'Dalì' if present, otherwise first artist or None.
    Default year: '2025' if present, otherwise first year or None.
    """
    df = leggi_dati()
    if df.empty:
        return [], [], None, None

    artists = sorted(df['ARTISTA'].dropna().astype(str).unique())
    years = sorted(df['ANNO'].dropna().astype(str).unique())

    artist_options = [{'label': a, 'value': a} for a in artists]
    year_options = [{'label': y, 'value': y} for y in years]

    # preferred defaults
    preferred_artist = 'Dalì'
    preferred_year = '2025'

    default_artist = preferred_artist if preferred_artist in artists else (artists[0] if artists else None)
    default_year = preferred_year if preferred_year in years else (years[0] if years else None)

    return artist_options, year_options, default_artist, default_year


@app.callback(Output('top10-table-container', 'children'),
              [Input('url', 'href'), Input('top10-artist-filter', 'value'), Input('top10-year-filter', 'value')])
def update_top10_table(_href, artist, anno):
    df = leggi_dati()
    if df.empty:
        return html.Div("Nessun dato disponibile")
    if artist:
        df = df[df['ARTISTA'].astype(str) == str(artist)]
    if anno:
        df = df[df['ANNO'].astype(str) == str(anno)]
    top10 = top10_long(df)
    return dash_table_from_df(top10)

# 🔹 Callback per aggiornare le opzioni delle dropdown
@app.callback(
    [Output('colonna-x', 'options'),
     Output('colonna-y', 'options'),
     Output('colonna-colore', 'options'),
     Output('colonna-x', 'value'),
     Output('colonna-y', 'value')],
    Input('url', 'href'),
    State('colonna-x', 'value'),
    State('colonna-y', 'value')
)
def aggiorna_opzioni(_href, current_x, current_y):
    df = leggi_dati()
    if df.empty:
        return [], [], [], None, None

    cols = list(df.columns)
    opzioni = [{'label': c, 'value': c} for c in cols]

    # determine defaults
    default_x = cols[0] if len(cols) > 0 else None
    default_y = cols[1] if len(cols) > 1 else (cols[0] if len(cols) > 0 else None)

    # preserve current selection if still available, otherwise fall back to defaults
    col_x = current_x if (current_x in cols) else default_x
    col_y = current_y if (current_y in cols) else default_y

    return opzioni, opzioni, opzioni, col_x, col_y

# 🔹 Callback per generare il grafico
@app.callback(
    [Output('grafico', 'figure'),
     Output('ultimo-aggiornamento', 'children')],
    [Input('colonna-x', 'value'),
     Input('colonna-y', 'value'),
     Input('colonna-colore', 'value')]
)
def aggiorna_grafico(col_x, col_y, col_colore):
    df = leggi_dati()
    if df.empty or not col_x or not col_y:
        return px.scatter(title="In attesa di dati..."), "⏳ Nessun dato disponibile"

    fig = px.scatter(df, x=col_x, y=col_y, color=col_colore,
                     title=f"{col_x} vs {col_y}",
                     template="plotly_white")

    fig.update_traces(marker=dict(size=10, opacity=0.8))
    return fig, f"Ultimo aggiornamento: {time.strftime('%H:%M:%S')}"

# 🔹 Avvio app
if __name__ == "__main__":
    print("🚀 Avvio server Dash su http://0.0.0.0:10000 ...")
    app.run (host="0.0.0.0", port=10000)
