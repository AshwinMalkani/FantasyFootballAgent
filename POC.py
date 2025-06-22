import json 
import requests 
from players import PlayerDatabase

username_request = 'https://api.sleeper.app/v1/user/'
league_request = 'https://api.sleeper.app/v1/league/'
player_db = PlayerDatabase()

if not player_db.load_from_file():
    print("No cache found, downloading fresh data...")
    player_db.fetch_and_store_players()
else:
    print("Loaded players from cache!")

# get client username 
username = str(input("What is your Sleeper username? "))

# get the client's user ID
response_userid = requests.get(username_request + username)
response_userid = json.loads(response_userid.text)
user_id = response_userid.get('user_id')

# get the ID for their most recent league 
response_leagueid = requests.get(username_request + user_id + '/leagues/nfl/2024')
response_leagueid = json.loads(response_leagueid.text)
league_id = response_leagueid[0].get('league_id')

# send league request 
response_rosters = requests.get(league_request + league_id + '/rosters')
response_rosters = json.loads(response_rosters.text)

rosters_by_owner = {}
for roster in response_rosters:
    owner_id = roster['owner_id']
    rosters_by_owner[owner_id] = roster

my_roster = rosters_by_owner[user_id]
# print(player_db.get_roster_names(my_roster['players']))  # List of player IDs

positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
for pos in positions:
    players = player_db.get_players_by_position(my_roster['players'], pos)
    if players:
        print(f"\n{pos}:")
        for player in players:
            injury = f" ({player['injury_status']})" if player['injury_status'] else ""
            print(f"  • {player['name']} - {player['team']}{injury}")