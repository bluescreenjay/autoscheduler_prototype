#!/usr/bin/env python3

import pandas as pd
import datetime as dt
from autoscheduler import load_recruiters, load_blocks, load_rooms, any_interval_contains

def debug_recruiter_scheduling():
    print("DEBUGGING RECRUITER SCHEDULING")
    print("=" * 50)
    
    # Load data
    recruiters = load_recruiters('recruiters.csv')
    blocks = load_blocks('blocks.csv')
    rooms = load_rooms('rooms.csv')
    
    print(f"Loaded: {len(recruiters)} recruiters, {len(blocks)} blocks, {len(rooms)} rooms")
    print()
    
    # Check rooms by type
    individual_rooms = [r for r in rooms if r['room_type'] == 'individual']
    group_rooms = [r for r in rooms if r['room_type'] == 'group']
    print(f"Individual rooms: {len(individual_rooms)}")
    print(f"Group rooms: {len(group_rooms)}")
    print()
    
    # Check blocks by type
    individual_blocks = [b for b in blocks if b['type'] == 'individual']
    group_blocks = [b for b in blocks if b['type'] == 'group']
    print(f"Individual blocks: {len(individual_blocks)}")
    print(f"Group blocks: {len(group_blocks)}")
    print()
    
    # Check first few individual blocks
    print("SAMPLE INDIVIDUAL BLOCKS:")
    for i, block in enumerate(individual_blocks[:5]):
        print(f"Block {block['block_id']}: {block['start']} - {block['end']}")
        
        # Check how many recruiters are available
        available_recruiters = []
        for recruiter in recruiters:
            if any_interval_contains(recruiter['parsed_availability'], (block['start'], block['end'])):
                available_recruiters.append(f"{recruiter['id']}({recruiter['team']})")
        
        print(f"  Available recruiters: {len(available_recruiters)} - {', '.join(available_recruiters)}")
        print()
    
    # Check teams distribution
    print("RECRUITER TEAMS:")
    teams = {}
    for recruiter in recruiters:
        team = recruiter['team']
        if team not in teams:
            teams[team] = []
        teams[team].append(recruiter['id'])
    
    for team, recruiters_in_team in teams.items():
        print(f"{team}: {len(recruiters_in_team)} recruiters ({', '.join(recruiters_in_team)})")
    print()
    
    # Check a sample group block constraint
    print("SAMPLE GROUP BLOCK ANALYSIS:")
    if group_blocks:
        sample_block = group_blocks[0]
        print(f"Block {sample_block['block_id']}: {sample_block['start']} - {sample_block['end']}")
        
        for team in ['Astra', 'Juvo', 'Infinitum', 'Terra']:
            team_available = []
            for recruiter in recruiters:
                if recruiter['team'] == team:
                    if any_interval_contains(recruiter['parsed_availability'], (sample_block['start'], sample_block['end'])):
                        team_available.append(recruiter['id'])
            
            print(f"  {team}: {len(team_available)} available ({', '.join(team_available)})")
        
        # Check if all teams have at least one available recruiter
        all_teams_covered = True
        for team in ['Astra', 'Juvo', 'Infinitum', 'Terra']:
            team_has_available = False
            for recruiter in recruiters:
                if recruiter['team'] == team:
                    if any_interval_contains(recruiter['parsed_availability'], (sample_block['start'], sample_block['end'])):
                        team_has_available = True
                        break
            if not team_has_available:
                all_teams_covered = False
                print(f"  ❌ {team} has NO available recruiters")
        
        if all_teams_covered:
            print(f"  ✅ All teams covered for this block")
        else:
            print(f"  ❌ Not all teams covered - this block cannot be scheduled")

if __name__ == "__main__":
    debug_recruiter_scheduling()
