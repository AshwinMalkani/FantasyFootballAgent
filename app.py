from flask import Flask, jsonify
from flask_cors import CORS
import requests
from players import PlayerDatabase
import os

app = Flask(__name__)
CORS(app, origins=["http://localhost:5000", "http://127.0.0.1:5000", "http://localhost:8000"])

# Initialize player database
player_db = PlayerDatabase()

# Make sure player data is loaded
print("Loading player database...")
if not player_db.load_from_file():
    print("No cache found, downloading fresh player data...")
    player_db.fetch_and_store_players()
else:
    print(f"Loaded {len(player_db.players_by_id)} players from cache")


@app.route('/')
def index():
    """Serve the main HTML page"""
    try:
        with open('index.html', 'r') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return "index.html not found", 404

@app.route('/api/roster/<username>')
def get_roster(username):
    """Get just the roster data for now"""
    try:
        print(f"Loading roster for: {username}")
        
        # Step 1: Get user ID
        response = requests.get(f'https://api.sleeper.app/v1/user/{username}')
        if response.status_code != 200:
            return jsonify({'error': f'User {username} not found'}), 404
        
        user_data = response.json()
        user_id = user_data.get('user_id')
        
        # Step 2: Get user's leagues
        response = requests.get(f'https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/2024')
        if response.status_code != 200:
            return jsonify({'error': 'No leagues found'}), 404
        
        leagues = response.json()
        if not leagues:
            return jsonify({'error': 'No leagues found for 2024'}), 404
        
        league_id = leagues[0].get('league_id')
        
        # Step 3: Get league rosters
        response = requests.get(f'https://api.sleeper.app/v1/league/{league_id}/rosters')
        if response.status_code != 200:
            return jsonify({'error': 'Failed to get rosters'}), 500
        
        rosters = response.json()
        
        # Step 4: Find user's roster
        user_roster = None
        for roster in rosters:
            if roster.get('owner_id') == user_id:
                user_roster = roster
                break
        
        if not user_roster:
            return jsonify({'error': 'User roster not found'}), 404
        
        # Step 5: Convert player IDs to player objects with names
        enhanced_players = []
        for player_id in user_roster.get('players', []):
            # Use the methods we know exist in your PlayerDatabase
            player_name = player_db.get_player_name(player_id)
            player_info = player_db.get_player_info(player_id)
            
            enhanced_players.append({
                'id': player_id,
                'name': player_name,
                'position': player_info.get('position', 'UNK') if player_info else 'UNK',
                'team': player_info.get('team', 'FA') if player_info else 'FA',
                'injury_status': player_info.get('injury_status', '') if player_info else ''
            })
        
        print(enhanced_players)
        
        # Step 6: Group by position
        roster_by_position = {}
        for player in enhanced_players:
            pos = player['position']
            if pos not in roster_by_position:
                roster_by_position[pos] = []
            roster_by_position[pos].append(player)
        
        return jsonify({
            'success': True,
            'players': enhanced_players,
            'roster_by_position': roster_by_position
        })
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"Players loaded: {len(player_db.players_by_id)}")
    print(f"Server starting on port {port}")
    app.run(debug=False, host='0.0.0.0', port=port)