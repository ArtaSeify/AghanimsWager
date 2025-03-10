import json, os, time, datetime
from pathlib import Path

import requests

import pandas as pd

from app_db import PGDB, MATCH_STATUS
from tokens import STEAM_API_KEY, CONNECTION_STRING

url_GetMatchDetails = 'https://api.steampowered.com/IDOTA2Match_570/GetMatchDetails/v001/'

def schuck_match_details(match_id):
	json_match_details = request_match_details(match_id)
	if not json_match_details:
		return MATCH_STATUS.UNRESOLVED
	result = json_match_details['result']
	if 'error' in result:
		print('Fetching {} failed: {}'.format(match_id,result['error']))
		return MATCH_STATUS.UNRESOLVED
	elif 'radiant_win' in result:
		json_file = 'match_details' + os.sep + str(match_id) + '.json'
		try:
			with open(json_file, 'w') as f:
				json.dump(json_match_details,f)
			print('dumped file at {}'.format(json_file))
		except IOError:
			print('Cannot write {}'.format(json_file))
		if result['radiant_win']:
			return MATCH_STATUS.RADIANT
		else:
			return MATCH_STATUS.DIRE
	else:
		json_file = 'match_details' + os.sep + str(match_id) + '.json'
		try:
			with open(json_file, 'w') as f:
				json.dump(json_match_details,f)
		except IOError:
			print('Cannot write {}'.format(json_file))
		print('Cannot parse match json data written at {}'.format(json_file))
		return MATCH_STATUS.ERROR
		

def request_match_details(match_id):
	req = {}
	req['key'] = STEAM_API_KEY
	req['match_id'] = match_id

	try:
		response = requests.get(url_GetMatchDetails,params = req,timeout = 5)
		status = response.status_code
		if status == 200:
			return response.json()
	except (requests.ConnectionError, requests.Timeout, requests.RequestException):
		print('request_match_details {} failed'.format(match_id))
		return None


def process_match_details(match_json,pgdb):
	match_json = match_json['result']
	match_id = match_json['match_id']
	players = match_json['players']
	del match_json['players']
	ability_upgrades = []
	bears = []
	for p in players:
		p['match_id'] = match_id
		player_slot = p['player_slot']
		try:
			try:
				additional_units = p['additional_units']
				for au in additional_units:
					au['match_id'] = match_id
					au['player_slot'] = player_slot
					# i guess it could not be a bear.
					bears.append(au)
				del p['additional_units']
			except KeyError:
				pass

			abilities = p['ability_upgrades']
			for ab in abilities:
				ab['match_id'] = match_id
				ab['player_slot'] = player_slot
				ability_upgrades.append(ab)
			del p['ability_upgrades']
		except KeyError:
			pass
	try:
		picks_bans = match_json['picks_bans']
		for pb in picks_bans:
			pb['match_id'] = match_id
		del match_json['picks_bans']
	except KeyError:
		picks_bans = None
		
	try:
		match_json['radiant_win']
	except KeyError:
		match_json['radiant_win'] = None

	match_df = pd.DataFrame([match_json])
	pgdb.insert_df('match_details',match_df)

	if len(bears) > 0:
		bear_df = pd.DataFrame(bears)
		pgdb.insert_df('bear_details',bear_df)

	if len(players) > 0:
		players_df = pd.DataFrame(players)
		pgdb.insert_df('player_match_details',players_df)

	if len(ability_upgrades) > 0:
		abilities_df = pd.DataFrame(ability_upgrades)
		pgdb.insert_df('ability_details',abilities_df)

	if picks_bans is not None:
		picks_df = pd.DataFrame(picks_bans)
		pgdb.insert_df('pick_details',picks_df)
		
def perform_import():
	db = PGDB(CONNECTION_STRING,'DotaWebAPI')
	md_path = Path.cwd() / 'match_details' 
	md_path.mkdir(exist_ok=True)
	imported_md_path = Path.cwd() / 'imported_match_details' 
	imported_md_path.mkdir(exist_ok=True)
	already_imported = list(map(lambda x: x.name, imported_md_path.glob('*.json')))
	successful = 0
	unsuccessful = 0
	for match_file in md_path.glob('*.json'):
		if match_file.name in already_imported:
			print(match_file,'already imported, removing')
			match_file.unlink()
		else:
			print('importing',match_file)
			try:
				with open(match_file) as f:
					match_json = json.load(f)
				process_match_details(match_json,db)
				new_match_file = imported_md_path / match_file.name
				match_file.rename(new_match_file)
				successful += 1
			except:
				print('error importing',match_file)
				unsuccessful += 1
	return successful,unsuccessful

if __name__ == '__main__':
	'''
	schuck_match_details(6112939577)
	sys.exit()
	'''
	perform_import()


