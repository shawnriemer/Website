## IMPORTS
from flask import Flask, request, jsonify, render_template, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
import sqlite3
import pandas as pd
import numpy as np
import random
import os
import json
from datetime import date, timedelta
import plotly
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


## BODY
app = Flask(__name__)
app.jinja_env.filters['zip'] = zip


## Pages
@app.route('/')
@app.route('/home')
def index():
    # overview table
    with open(os.path.join('C:\\', 'Users', 'Owner', 'Documents', 'Moneyball', 'data', 'query_results.json'), 'r') as openfile:
        query_dict = json.load(openfile)

    # quote and source
    quote, author, link = random_quote()
    
    return render_template('index.html', quote=quote, author=author, link=link, **query_dict)


@app.route('/blog.html')
def blog():
    with open('templates/blog.html') as f:
        html = f.read()
    return html

@app.route('/shift.html')
def shift():
    with open(os.path.join('C:\\', 'Users', 'Owner', 'Documents', 'Moneyball', 'website', 'static', 'saved_figs.json'), 'r') as openfile:
        fig_dict = json.load(openfile)

    return render_template('shift.html', **fig_dict)

@app.route('/roster.html')
def roster():
    with open('templates/roster.html') as f:
        html = f.read()
    return html

@app.route('/abs.html')
def abs():
    with open('templates/abs.html') as f:
        html = f.read()
    return html

@app.route('/about.html')
def about():
    with open('templates/about.html') as f:
        html = f.read()
    return html

@app.route('/bts.html')
def bts():
    with open('templates/bts.html') as f:
        html = f.read()
    return html


@app.route('/scouting.html', methods=["GET","POST"])
def scouting():
    if request.method == "POST":
        player = request.form.get("player")
        metric = request.form.get("metric")
    else:
        player = "Seiya Suzuki"
        metric = "wOBA"

    fig = fill_scouting(player, metric)

    return render_template('scouting.html', fig=fig)


@app.route('/statcast.html')
def statcast():
    # overview table
    with open(os.path.join('C:\\', 'Users', 'Owner', 'Documents', 'Moneyball', 'data', 'query_results.json'), 'r') as openfile:
        query_dict = json.load(openfile)

    return render_template('statcast.html', **query_dict)



## Helper Functions
def random_quote():
    """This function randomly selects a baseball-related quote for use on the home page

    Chooses a quote from the static/quotes.csv file, returns quote, author, and Wikipedia link to author
    """

    tbl = pd.read_csv("static/quotes.csv", delimiter="|")
    row_idx = random.randrange(len(tbl))
    quote = tbl.iloc[row_idx, 0]
    author = tbl.iloc[row_idx, 1]
    link = tbl.iloc[row_idx, 2]
    return (quote, author, link)



def fill_scouting(player, metric):
    """This function fills the Scouting page

    Connects to data.db and loads data for Seiya Suzuki as default
    Creates figures for wOBA/BA/OPS by pitch location, pitch type, defensive alignment, platoon, ...
    """

    conn = sqlite3.connect('../data/data.db')
    c = conn.cursor()

    if player=="":
        player = "Seiya Suzuki"
    player = player.lower()
    metric_dict = {'wOBA':'woba_value', 'BA':'babip_value'}
    try:
        metric_code = metric_dict[metric]
    except:
        metric = "wOBA"
        metric_code = "woba_value"

    # Find Player's Total Average for Metric
    metric_avg = pd.read_sql(f"""SELECT AVG({metric_code}) FROM data22
        WHERE LOWER(batter_name)='{player}' AND {metric_code}<>'NaN'""", conn).iloc[0,0]

    # Get Team's Color Scheme
    team = pd.read_sql(f"SELECT batter_team FROM data22 WHERE LOWER(batter_name)='{player}'", conn).iloc[0,0]
    team_colors = pd.read_csv('static/team_colors.csv')
    cols = team_colors[team_colors.team==f'{team}'].values.tolist()[0][1:]*10

    # query player's data
    df_player = pd.read_sql(f"""SELECT * FROM data22 WHERE LOWER(batter_name)='{player}'""", conn)

    # define pitch types
    def def_pitch_type(row):
        if row['pitch_type'] in ['FC', 'FF', 'FT', 'SI']:
            return 'Fastball'
        elif row['pitch_type'] in ['CU', 'SL', 'KC', 'KN']:
            return 'Breaking'
        elif row['pitch_type'] in ['CH', 'FS', 'FO', 'SC']:
            return 'Offspeed'
        else:
            return 'Other'

    def group_extra_innings(row):
        if row['inning'] > 9:
            return 'Extras'
        else:
            return str(row['inning'])

    df_player['pitch'] = df_player.apply(def_pitch_type, axis=1)
    df_player['inning'] = df_player.apply(group_extra_innings, axis=1)

    # create DataFrames
    df_shift = df_player[['if_fielding_alignment', 'woba_value', 'events']].groupby('if_fielding_alignment').agg(woba_value=('woba_value', np.mean), PAs=('events', np.count_nonzero)).reset_index().rename(columns={'if_fielding_alignment':'Shift', 'woba_value':'Metric'})

    df_pitch_type = df_player[['pitch', 'woba_value', 'events']].groupby('pitch').agg(woba_value=('woba_value', np.mean), PAs=('events', np.count_nonzero)).reset_index().rename(columns={'pitch':'Pitch', 'woba_value':'Metric'})

    df_inning = df_player[['inning', 'woba_value', 'events']].groupby('inning').agg(woba_value=('woba_value', np.mean), PAs=('events', np.count_nonzero)).reset_index().rename(columns={'inning':'Inning', 'woba_value':'Metric'})

    df_platoon = df_player[['p_throws', 'woba_value', 'events']].groupby('p_throws').agg(woba_value=('woba_value', np.mean), PAs=('events', np.count_nonzero)).reset_index().rename(columns={'p_throws':'Platoon', 'woba_value':'Metric'})

    # create plots
    fig = make_subplots(rows=2, cols=2,
                        shared_yaxes=True,
                        column_widths=[0.25, 0.75],
                        horizontal_spacing=0.02)

    ## Row 1
    # Shift
    fig.add_bar(x=df_shift['Shift'], y=df_shift['Metric'],
                text=round(df_shift['Metric'],3).astype(str) + '<br><br>' + df_shift['PAs'].astype(str) +'<br>PAs',
                insidetextanchor="start",
                marker_color=cols,
                row=1, col=1)
    fig.update_xaxes(title_text="Shift", row=1, col=1)
    fig.update_yaxes(title_text=f"{metric}",
                    tickformat='.3f',
                    range=[0, 0.6],
                    row=1, col=1)

    # Pitch
    fig.add_bar(x=df_pitch_type['Pitch'], y=df_pitch_type['Metric'],
                text=round(df_pitch_type['Metric'],3).astype(str) + '<br><br>' + df_pitch_type['PAs'].astype(str) +'<br>PAs',
                insidetextanchor="start",
                marker_color=cols[len(df_shift.Shift)%2:],    # finds number of bars used in first plot, makes sure colors alternate
                row=1, col=2)
    fig.update_xaxes(title_text="Pitch Type", row=1, col=2)

    # Ref Lines
    fig.add_hline(y=metric_avg,
                 line_color='white',
                 line_dash='dash',
                 row=1, col=1)

    fig.add_hline(y=metric_avg,
                 line_color='white',
                 line_dash='dash',
                 annotation_text=f'<b>Player average ({round(metric_avg,3)})</b>',
                 annotation_font_color='#989898',
                 row=1, col=2)

    ## Row 2
    # Platoon
    fig.add_bar(x=df_platoon['Platoon'], y=df_platoon['Metric'],
                text=round(df_platoon['Metric'],3).astype(str) + '<br><br>' + df_platoon['PAs'].astype(str) +'<br>PAs',
                insidetextanchor="start",
                marker_color=cols,    # finds number of bars used in first plot, makes sure colors alternate
                row=2, col=1)
    fig.update_xaxes(title_text="Platoon", row=2, col=1)
    fig.update_yaxes(title_text=f"{metric}",
                    tickformat='.3f',
                    range=[0, 0.6],
                    row=2, col=1)

    # Inning
    fig.add_bar(x=df_inning['Inning'], y=df_inning['Metric'],
                text=round(df_inning['Metric'],3).astype(str) + '<br><br>' + df_inning['PAs'].astype(str) +'<br>PAs',
                insidetextanchor="start",
                marker_color=cols[len(df_platoon.Platoon)%2:],
                row=2, col=2)
    fig.update_xaxes(title_text="Inning", dtick=1, row=2, col=2)

    # Ref Lines
    fig.add_hline(y=metric_avg,
                 line_color='white',
                 line_dash='dash',
                 row=2, col=1)

    fig.add_hline(y=metric_avg,
                 line_color='white',
                 line_dash='dash',
                 annotation_text=f'<b>Player average ({round(metric_avg,3)})</b>',
                 annotation_font_color='#989898',
                 row=2, col=2)

    # Layout
    fig.update_layout(
        title=f'{player.title()} {metric} Splits',
        showlegend=False,
        plot_bgcolor='#fff',
        paper_bgcolor='white',
        height=800)


    fig = fig.to_html(full_html=False, config={'displayModeBar':False, 'responsive':True})

    conn.close()

    return fig



if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True) # don't change this line!
