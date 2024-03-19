import json
import psycopg2
import os
from datetime import datetime, date


# Database connection params
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')

# SQL queries to fetch xp & pvm data, limited to last weeks data
SQL_QUERY_EXPERIENCE = """
WITH PreviousExperience AS (
    SELECT
        player_name,
        week_start,
        LAG(start_experience) OVER (PARTITION BY player_name ORDER BY week_start) AS previous_start_experience,
        LAG(week_start) OVER (PARTITION BY player_name ORDER BY week_start) AS previous_week_start
    FROM
        weekly_experience_summary
)
SELECT
    ws.player_name,
    CASE 
        WHEN ws.experience_gain = 0 AND pe.previous_start_experience IS NOT NULL AND EXTRACT(DOW FROM ws.week_start) = 1
        THEN pe.previous_week_start
        ELSE ws.week_start 
    END AS week_start,
    ws.start_experience,
    ws.end_experience,
    CASE
        WHEN ws.experience_gain = 0 AND pe.previous_start_experience IS NOT NULL AND EXTRACT(DOW FROM ws.week_start) = 1
        THEN ws.start_experience - pe.previous_start_experience
        ELSE ws.experience_gain
    END AS experience_gain
FROM
    weekly_experience_summary ws
JOIN
    PreviousExperience pe ON ws.player_name = pe.player_name AND ws.week_start = pe.week_start
WHERE
    ws.week_start = (SELECT MAX(week_start) FROM weekly_experience_summary);
"""
SQL_QUERY_PVM = """
WITH PreviousWeekData AS (
    SELECT
        player_name,
        week_start_date,
        raids_start,
        raids_end,
        bosses_start,
        bosses_end,
        LAG(week_start_date) OVER (PARTITION BY player_name ORDER BY week_start_date) AS prev_week_start_date, -- Fetches the previous week's start date
        LAG(raids_start) OVER (PARTITION BY player_name ORDER BY week_start_date) AS prev_raids_start,
        LAG(bosses_start) OVER (PARTITION BY player_name ORDER BY week_start_date) AS prev_bosses_start
    FROM
        weekly_pvm_summary 
)
SELECT
    pwd.player_name,
    CASE 
        WHEN EXTRACT(DOW FROM pwd.week_start_date) = 1 THEN pwd.prev_week_start_date -- Display previous week's date on Mondays
        ELSE pwd.week_start_date -- Otherwise, display current week's date
    END AS week_start_date,
    pwd.raids_start,
    pwd.raids_end,
    CASE
        WHEN EXTRACT(DOW FROM pwd.week_start_date) = 1 THEN pwd.raids_start - COALESCE(pwd.prev_raids_start, pwd.raids_start) -- Calculation for Mondays
        ELSE pwd.raids_end - pwd.raids_start -- Default calculation for other days
    END AS raids_increase,
    pwd.bosses_start,
    pwd.bosses_end,
    CASE
        WHEN EXTRACT(DOW FROM pwd.week_start_date) = 1 THEN pwd.bosses_start - COALESCE(pwd.prev_bosses_start, pwd.bosses_start) -- Calculation for Mondays
        ELSE pwd.bosses_end - pwd.bosses_start -- Default calculation for other days
    END AS bosses_increase
FROM
    PreviousWeekData pwd
WHERE
    pwd.week_start_date = (SELECT MAX(week_start_date) FROM weekly_pvm_summary); -- Ensures only the latest week's data is considered

"""

# Custom JSON encoder for datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            # Handles both datetime and date objects
            return obj.isoformat()
        elif isinstance(obj, date):
            # Specifically for date objects (this is redundant if datetime is already handled, but added for clarity)
            return obj.isoformat()
        return super().default(obj)

try:
    # Connect to your database
    conn = psycopg2.connect(database=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)
    cur = conn.cursor()

    # Function to fetch data and convert to list of dicts
    def fetch_data_and_convert_to_dict(cur, query):
        cur.execute(query)
        column_names = [desc[0] for desc in cur.description]
        data = [dict(zip(column_names, row)) for row in cur.fetchall()]
        return data

    # SQL_QUERY_EXPERIENCE and SQL_QUERY_PVM are your SQL commands as previously defined
    # Fetch and process the experience data
    processed_experience_data = fetch_data_and_convert_to_dict(cur, SQL_QUERY_EXPERIENCE)
    # Fetch and process the PVM data
    processed_pvm_data = fetch_data_and_convert_to_dict(cur, SQL_QUERY_PVM)

    # Find the top XP gain
    top_xp_gain = max(processed_experience_data, key=lambda x: x['experience_gain'])
    # Find the top raids gain
    top_raids_gain = max(processed_pvm_data, key=lambda x: x['raids_increase'])
    # Find the top bosses gain
    top_bosses_gain = max(processed_pvm_data, key=lambda x: x['bosses_increase'])

    # Save the data to JSON files
    with open('data/weekly_experience_gain.json', 'w') as f:
        json.dump(processed_experience_data, f, indent=4, cls=DateTimeEncoder)

    with open('data/weekly_pvm_gain.json', 'w') as f:
        json.dump(processed_pvm_data, f, indent=4, cls=DateTimeEncoder)

    with open('data/top_performers.json', 'w') as f:
        json.dump({
            'top_xp_gain': top_xp_gain,
            'top_raids_gain': top_raids_gain,
            'top_bosses_gain': top_bosses_gain
        }, f, indent=4, cls=DateTimeEncoder)

    cur.close()
    conn.close()
except Exception as e:
    print(f"Database connection failed due to {e}")
