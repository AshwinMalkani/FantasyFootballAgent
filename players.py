import json
import requests
from datetime import datetime

class PlayerDatabase:
    def __init__(self):
        self.players_by_id = {}
        self.players_by_name = {}
        self.last_updated = None
        
    def fetch_and_store_players(self):
        """Fetch from API and store efficiently"""
        print("Downloading player database... (this might take a moment)")
        response = requests.get("https://api.sleeper.app/v1/players/nfl")
        raw_data = response.json()
        
        # Store by ID (main lookup)
        self.players_by_id = raw_data
        
        # Create name-based lookup for search
        self.players_by_name = {}
        for player_id, player_data in raw_data.items():
            if player_data.get('full_name'):
                name = player_data['full_name'].lower()
                self.players_by_name[name] = player_id
        
        self.last_updated = datetime.now()
        print(f"Loaded {len(self.players_by_id)} players")
        
        # Save to file so you don't re-download every time
        self.save_to_file()
    
    def save_to_file(self, filename="nfl_players.json"):
        """Save to local file"""
        data = {
            'players_by_id': self.players_by_id,
            'players_by_name': self.players_by_name,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }
        with open(filename, 'w') as f:
            json.dump(data, f)
    
    def load_from_file(self, filename="nfl_players.json"):
        """Load from local file"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            self.players_by_id = data['players_by_id']
            self.players_by_name = data['players_by_name']
            if data['last_updated']:
                self.last_updated = datetime.fromisoformat(data['last_updated'])
            return True
        except FileNotFoundError:
            return False
    
    def get_player_name(self, player_id):
        """Get player name by ID"""
        player = self.players_by_id.get(str(player_id))
        if player:
            return player.get('full_name', f"Player {player_id}")
        return f"Unknown Player ({player_id})"
    
    def get_player_info(self, player_id):
        """Get full player info"""
        return self.players_by_id.get(str(player_id), {})
    
    def search_player(self, name):
        """Find player by name"""
        player_id = self.players_by_name.get(name.lower())
        if player_id:
            return self.players_by_id.get(player_id)
        return None
    
    def get_roster_names(self, player_ids):
        """Convert list of player IDs to names"""
        return [self.get_player_name(pid) for pid in player_ids]
    

    def get_player_display(self, player_id):
        """Get formatted player display with position and injury status"""
        player = self.players_by_id.get(str(player_id))
        if not player:
            return f"Unknown Player ({player_id})"
        
        # Basic info
        name = player.get('full_name', f"Player {player_id}")
        position = player.get('position', 'UNK')
        team = player.get('team', 'FA')
        
        # Injury status
        injury_status = player.get('injury_status', '')
        injury_start = player.get('injury_start_date', '')
        
        # Format injury info
        injury_display = ""
        if injury_status:
            if injury_status.lower() in ['out', 'ir', 'doubtful']:
                injury_display = f" 🔴{injury_status}"
            elif injury_status.lower() in ['questionable', 'q']:
                injury_display = f" 🟡Q"
            elif injury_status.lower() in ['probable', 'p']:
                injury_display = f" 🟢P"
            else:
                injury_display = f" ⚪{injury_status}"
        
        return f"{name} ({position}, {team}){injury_display}"
    
    def get_roster_display(self, player_ids):
        """Convert list of player IDs to detailed display"""
        return [self.get_player_display(pid) for pid in player_ids]
    
    def get_player_detailed_info(self, player_id):
        """Get comprehensive player information"""
        player = self.players_by_id.get(str(player_id))
        if not player:
            return {"error": f"Player {player_id} not found"}
        
        return {
            'name': player.get('full_name', f"Player {player_id}"),
            'position': player.get('position', 'Unknown'),
            'team': player.get('team', 'Free Agent'),
            'injury_status': player.get('injury_status', 'Healthy'),
            'injury_start_date': player.get('injury_start_date', None),
            'years_exp': player.get('years_exp', 'Unknown'),
            'age': player.get('age', 'Unknown'),
            'college': player.get('college', 'Unknown'),
            'status': player.get('status', 'Unknown')  # Active, Inactive, etc.
        }
    
    def get_injured_players(self, player_ids):
        """Get only players with injury concerns from a roster"""
        injured = []
        for player_id in player_ids:
            player = self.players_by_id.get(str(player_id))
            if player and player.get('injury_status'):
                status = player.get('injury_status', '').lower()
                if status in ['out', 'ir', 'doubtful', 'questionable', 'probable']:
                    injured.append({
                        'id': player_id,
                        'name': player.get('full_name', f"Player {player_id}"),
                        'position': player.get('position', 'UNK'),
                        'team': player.get('team', 'FA'),
                        'injury_status': player.get('injury_status', ''),
                        'injury_start_date': player.get('injury_start_date', '')
                    })
        return injured
    
    def get_players_by_position(self, player_ids, position):
        """Filter players by position (QB, RB, WR, TE, K, DEF)"""
        position_players = []
        for player_id in player_ids:
            player = self.players_by_id.get(str(player_id))
            if player and player.get('position') == position.upper():
                position_players.append({
                    'id': player_id,
                    'name': player.get('full_name', f"Player {player_id}"),
                    'team': player.get('team', 'FA'),
                    'injury_status': player.get('injury_status', '')
                })
        return position_players
