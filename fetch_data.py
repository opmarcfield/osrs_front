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
SELECT * FROM weekly_experience_summary

"""
SQL_QUERY_PVM = """
SELECT * FROM weekly_pvm_summary
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