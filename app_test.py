import streamlit as st
import pandas as pd
import sqlite3
from PIL import Image

# Database connection
def get_db_connection():
    conn = sqlite3.connect('lp_tracker.db')
    return conn

# Initialize tables
def initialize_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            player_name TEXT PRIMARY KEY,
            rank TEXT,
            division TEXT,
            current_lp INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT,
            result TEXT,
            lp_change INTEGER,
            total_lp INTEGER,
            rank TEXT,
            division TEXT,
            FOREIGN KEY (player_name) REFERENCES players (player_name)
        )
    ''')
    conn.commit()
    conn.close()

# Initialize database
initialize_db()

# Function to update rank and division based on LP
def update_rank_and_division(rank, division, lp_change):
    ranks = ['Iron', 'Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Master', 'Grandmaster', 'Challenger']
    divisions = ['IV', 'III', 'II', 'I']
    
    division_index = divisions.index(division)
    new_lp = lp_change
    
    while new_lp >= 100:
        new_lp -= 100
        if division_index > 0:
            division_index -= 1
        else:
            current_rank_index = ranks.index(rank)
            if current_rank_index < len(ranks) - 1:
                rank = ranks[current_rank_index + 1]
                division_index = 3
            else:
                new_lp = 100

    division = divisions[division_index]
    return rank, division, new_lp

# Function to register a new player
def register_player(player_name, rank, division, current_lp):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('INSERT INTO players (player_name, rank, division, current_lp) VALUES (?, ?, ?, ?)', 
                       (player_name, rank, division, current_lp))
        conn.commit()
        st.success(f"Player '{player_name}' registered with Rank {rank}, Division {division}, and LP {current_lp}.")
    except sqlite3.IntegrityError:
        st.error("Player already registered.")
    
    conn.close()

# Function to log match results
def log_match(player_name, result, lp_change):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT rank, division, current_lp FROM players WHERE player_name = ?', (player_name,))
    player_data = cursor.fetchone()
    if player_data is None:
        st.error("Player not found.")
        return
    
    rank, division, current_lp = player_data
    lp_change = int(lp_change) if lp_change is not None else 0
    
    new_lp = current_lp + lp_change if result == 'Win' else current_lp - lp_change
    new_rank, new_division, adjusted_lp = update_rank_and_division(rank, division, new_lp)

    cursor.execute('UPDATE players SET current_lp = ?, rank = ?, division = ? WHERE player_name = ?', 
                   (adjusted_lp, new_rank, new_division, player_name))
    cursor.execute('INSERT INTO logs (player_name, result, lp_change, total_lp, rank, division) VALUES (?, ?, ?, ?, ?, ?)', 
                   (player_name, result, lp_change, adjusted_lp, new_rank, new_division))
    conn.commit()
    conn.close()

# Function to generate leaderboard based on total LP gained
def generate_leaderboard():
    conn = get_db_connection()
    
    # Updated SQL query to count total games played by each player
    query = '''
    SELECT 
        p.player_name, 
        p.rank, 
        p.division, 
        p.current_lp,
        COALESCE(SUM(CASE WHEN l.result = 'Win' THEN l.lp_change 
                          WHEN l.result = 'Lose' THEN -l.lp_change 
                          ELSE 0 END), 0) AS total_lp_change,
        COUNT(l.id) AS total_games_played
    FROM players p
    LEFT JOIN logs l ON p.player_name = l.player_name
    GROUP BY p.player_name, p.rank, p.division, p.current_lp
    ORDER BY total_lp_change DESC
    '''
    
    # Execute the query and fetch the results into a DataFrame
    leaderboard = pd.read_sql_query(query, conn)
    conn.close()

    # Debugging: Check column names and sample data

    if leaderboard.empty:
        return leaderboard
    
    # Formatting LP Gained/Lost
    leaderboard['LP Gained/Lost'] = leaderboard['total_lp_change'].apply(lambda x: f"+{x}" if x > 0 else f"{x}")
    
    # Rank players based on LP change
    leaderboard['Rank'] = leaderboard['total_lp_change'].rank(method='first', ascending=False).astype(int)
    
    # Selecting and sorting columns
    leaderboard = leaderboard[['player_name', 'LP Gained/Lost', 'total_games_played', 'current_lp', 'rank', 'division', 'Rank']].sort_values(by='Rank')
    return leaderboard

# Function to display podium for top 3 players
def display_podium(leaderboard):
    podium_colors = ['#FFD700', '#C0C0C0', '#CD7F32']  # Gold, Silver, Bronze

    # Extract top 3 players
    top_3 = leaderboard.head(3)

    # Display the podium
    col1, col2, col3 = st.columns([1, 2, 1])
    
    if len(top_3) >= 3:
        with col1:
            st.markdown(f"<h2 style='text-align: center; color: {podium_colors[1]};'>2nd Place</h2>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='text-align: center;'>{top_3.iloc[1]['player_name']}</h3>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='text-align: center;'>{top_3.iloc[1]['rank']} {top_3.iloc[1]['division']}</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'>LP Gained/Lost: {top_3.iloc[1]['LP Gained/Lost']}</p>", unsafe_allow_html=True)

        with col2:
            st.markdown(f"<h2 style='text-align: center; color: {podium_colors[0]};'>1st Place</h2>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='text-align: center;'>{top_3.iloc[0]['player_name']}</h3>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='text-align: center;'>{top_3.iloc[0]['rank']} {top_3.iloc[0]['division']}</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'>LP Gained/Lost: {top_3.iloc[0]['LP Gained/Lost']}</p>", unsafe_allow_html=True)

        with col3:
            st.markdown(f"<h2 style='text-align: center; color: {podium_colors[2]};'>3rd Place</h2>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='text-align: center;'>{top_3.iloc[2]['player_name']}</h3>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='text-align: center;'>{top_3.iloc[2]['rank']} {top_3.iloc[2]['division']}</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'>LP Gained/Lost: {top_3.iloc[2]['LP Gained/Lost']}</p>", unsafe_allow_html=True)

    elif len(top_3) == 2:
        with col1:
            st.markdown(f"<h2 style='text-align: center; color: {podium_colors[1]};'>2nd Place</h2>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='text-align: center;'>{top_3.iloc[1]['player_name']}</h3>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='text-align: center;'>{top_3.iloc[1]['rank']} {top_3.iloc[1]['division']}</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'>LP Gained/Lost: {top_3.iloc[1]['LP Gained/Lost']}</p>", unsafe_allow_html=True)

        with col2:
            st.markdown(f"<h2 style='text-align: center; color: {podium_colors[0]};'>1st Place</h2>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='text-align: center;'>{top_3.iloc[0]['player_name']}</h3>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='text-align: center;'>{top_3.iloc[0]['rank']} {top_3.iloc[0]['division']}</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'>LP Gained/Lost: {top_3.iloc[0]['LP Gained/Lost']}</p>", unsafe_allow_html=True)

    elif len(top_3) == 1:
        with col2:
            st.markdown(f"<h2 style='text-align: center; color: {podium_colors[0]};'>1st Place</h2>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='text-align: center;'>{top_3.iloc[0]['player_name']}</h3>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='text-align: center;'>{top_3.iloc[0]['rank']} {top_3.iloc[0]['division']}</h4>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'>LP Gained/Lost: {top_3.iloc[0]['LP Gained/Lost']}</p>", unsafe_allow_html=True)

# Streamlit UI
# Add a custom background
st.markdown(
    """
    <style>
    .stApp {
        background: url("https://imgs.getimg.ai/generated/img-r5EhP1DFsmEYbRqNrksDC.jpeg");
        background-size: cover;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Center the image and adjust its size
col1, col2, col3 = st.columns([1, 2, 1])  # Adjust column width ratios as needed

with col1:
    st.write("")  # Empty column for spacing
with col2:
    st.image("lol_logo.png", use_column_width=False, width=400)  # Adjust width to make it bigger
with col3:
    st.write("")  # Empty column for spacing

# Sidebar for navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Register Player", "Log Match Result", "Player Statistics", "Leaderboard"])

# Center the content
st.markdown("<style> .center-text { text-align: center; } </style>", unsafe_allow_html=True)

if page == "Register Player":
    st.header('Register Player')
    player_name = st.text_input('Enter Player Name')
    rank = st.selectbox('Select Rank', ['Iron', 'Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Master', 'Grandmaster', 'Challenger'])
    division = st.selectbox('Select Division', ['IV', 'III', 'II', 'I'] if rank != 'Challenger' else ['I'])
    current_lp = st.number_input('Enter Current LP', min_value=0)

    if st.button('Register Player'):
        register_player(player_name, rank, division, current_lp)

elif page == "Log Match Result":
    st.header('Log Match Result')
    player_name_log = st.selectbox('Select Player', options=[row[0] for row in get_db_connection().execute('SELECT player_name FROM players').fetchall()])
    result = st.radio('Match Result', ['Win', 'Lose'])
    lp_change = st.number_input('LP Change', min_value=0)

    if st.button('Log Match Result'):
        log_match(player_name_log, result, lp_change)

elif page == "Player Statistics":
    st.header('Player Statistics')
    conn = get_db_connection()
    player_logs = pd.read_sql_query('SELECT * FROM logs ORDER BY id DESC', conn)
    conn.close()

    if not player_logs.empty:
        st.write(player_logs)
        total_lp_change = player_logs['lp_change'].sum()
        st.write(f"Total LP Gained/Lost: {'+' + str(total_lp_change) if total_lp_change > 0 else str(total_lp_change)}")
    else:
        st.write("No match results logged yet.")

elif page == "Leaderboard":
    st.header('Leaderboard')
    leaderboard = generate_leaderboard()
    
    if not leaderboard.empty:
        display_podium(leaderboard)  # Display the podium
        st.write(leaderboard)  # Display the leaderboard table
    else:
        st.write("No data available for leaderboard.")
