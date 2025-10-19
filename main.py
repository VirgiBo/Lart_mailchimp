import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, State
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import time
# ...existing code...
import os
from dotenv import load_dotenv  # optional, only if you want .env support
# ...existing code...

# load .env (optional)
load_dotenv()

# 🔹 CONFIGURA QUI IL PERCORSO DEL TUO FILE EXCEL
EXCEL_PATH = r"data/dati.xlsx"  # 🔄 Cambia questo percorso

# 🔹 Funzione per leggere i dati Excel
def leggi_dati():
    try:
        df = pd.read_excel(EXCEL_PATH)
        return df
    except Exception as e:
        print("❌ Errore nel caricamento del file:", e)
        return pd.DataFrame()

# 🔹 Crea l'app Dash
app = Dash(__name__)
app.title = "Analisi Dati in Tempo Reale"


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
    html.H1("📊 Analisi Dati in Tempo Reale", style={'textAlign': 'center'}),

    html.Div([
        html.Label("Seleziona Asse X:"),
        dcc.Dropdown(id='colonna-x', clearable=False),

        html.Label("Seleziona Asse Y:"),
        dcc.Dropdown(id='colonna-y', clearable=False),

        html.Label("Seleziona Colore (opzionale):"),
        dcc.Dropdown(id='colonna-colore', clearable=True, placeholder="Nessuno"),
    ], style={'width': '60%', 'margin': 'auto'}),

    dcc.Graph(id='grafico'),

    html.Div(id='ultimo-aggiornamento', style={'textAlign': 'center', 'marginTop': 20}),

    dcc.Interval(
        id='aggiorna',
        interval=5000,  # ogni 5 secondi
        n_intervals=0
    )
])

# 🔹 Callback per aggiornare le opzioni delle dropdown
@app.callback(
    [Output('colonna-x', 'options'),
     Output('colonna-y', 'options'),
     Output('colonna-colore', 'options'),
     Output('colonna-x', 'value'),
     Output('colonna-y', 'value')],
    Input('aggiorna', 'n_intervals'),
    State('colonna-x', 'value'),
    State('colonna-y', 'value')
)
def aggiorna_opzioni(_intervals, current_x, current_y):
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
     Input('colonna-colore', 'value'),
     Input('aggiorna', 'n_intervals')]
)
def aggiorna_grafico(col_x, col_y, col_colore, _):
    df = leggi_dati()
    if df.empty or not col_x or not col_y:
        return px.scatter(title="In attesa di dati..."), "⏳ Nessun dato disponibile"

    fig = px.scatter(df, x=col_x, y=col_y, color=col_colore,
                     title=f"{col_x} vs {col_y}",
                     template="plotly_white")

    fig.update_traces(marker=dict(size=10, opacity=0.8))
    return fig, f"Ultimo aggiornamento: {time.strftime('%H:%M:%S')}"

# 🔹 Watchdog per rilevare modifiche del file Excel
class Watcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path == EXCEL_PATH:
            print("🔄 File Excel modificato — aggiornamento in corso...")

def avvia_watcher():
    path = os.path.dirname(EXCEL_PATH)
    observer = Observer()
    observer.schedule(Watcher(), path, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

# 🔹 Avvio app
if __name__ == "__main__":
    threading.Thread(target=avvia_watcher, daemon=True).start()
    print("🚀 Avvio server Dash su http://0.0.0.0:10000 ...")
    app.run (host="0.0.0.0", port=10000, debug=True)
