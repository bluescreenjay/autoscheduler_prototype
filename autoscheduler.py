import pandas as pd
from ortools.sat.python import cp_model
import csv
import os
import re
import datetime as dt
from typing import List, Dict, Set, Tuple
import argparse
from pathlib import Path

# Constants
TEAMS = ['Astra', 'Juvo', 'Infinitum', 'Terra']

def parse_team_preferences(team_str: str) -> Set[str]:
    """Extract team preferences from the teams string."""
    teams = set()
    if pd.isna(team_str) or not team_str:
        return teams
    
    # Map full team names to short codes
    for team in TEAMS:
        if team in team_str:
            teams.add(team)
    
    return teams

def parse_availability_slot(slot_str: str) -> List[str]:
    """Parse time slots like '7 PM - 8 PM, 8 PM - 9 PM' into list of time ranges."""
    if pd.isna(slot_str) or not slot_str:
        return []
    
    # Find all time ranges in format "X PM/AM - Y PM/AM"
    time_pattern = r'(\d{1,2})\s*(AM|PM)\s*-\s*(\d{1,2})\s*(AM|PM)'
    matches = re.findall(time_pattern, slot_str)
    
    time_ranges = []
    for start_hour, start_period, end_hour, end_period in matches:
        # Convert to 24-hour format
        start_24 = convert_to_24h(int(start_hour), start_period)
        end_24 = convert_to_24h(int(end_hour), end_period)
        time_ranges.append(f"{start_24:02d}:00-{end_24:02d}:00")
    
    return time_ranges

def convert_to_24h(hour: int, period: str) -> int:
    """Convert 12-hour format to 24-hour format."""
    if period == 'AM':
        return hour if hour != 12 else 0
    else:  # PM
        return hour if hour == 12 else hour + 12

def parse_ranges(s):
    """Parse availability ranges from format like '2025-09-10 09:00-17:00;2025-09-11 09:00-17:00'"""
    if not s or str(s).strip() == '':
        return []
    spans = []
    for part in str(s).split(';'):
        part = part.strip()
        if not part:
            continue
        date_str, times = part.split(' ')
        start_t, end_t = times.split('-')
        start_dt = dt.datetime.fromisoformat(f'{date_str} {start_t}')
        end_dt = dt.datetime.fromisoformat(f'{date_str} {end_t}')
        spans.append((start_dt, end_dt))
    return spans

def interval_contains(interval, win):
    """Check if interval contains window."""
    (a, b), (x, y) = interval, win
    return a <= x and y <= b

def any_interval_contains(intervals, win):
    """Check if any interval contains the window."""
    return any(interval_contains(iv, win) for iv in intervals)

def load_applicants(path: str) -> List[Dict]:
    """Load and process applicant data."""
    df = pd.read_csv(path)
    applicants = []
    
    for i, (idx, row) in enumerate(df.iterrows()):
        email = row['Timestamp']  # Actual email is in Timestamp column
        name = row['Email Address']  # Actual name is in Email Address column
        
        if pd.isna(email) or pd.isna(name):
            continue
            
        # Ensure email is a string
        email = str(email) if not pd.isna(email) else ""
        
        # Create unique ID from email prefix
        if '@' in email:
            app_id = email.split('@')[0]
        else:
            app_id = "A" + str(i + 1)
        
        # Parse team preferences from the correct column 
        teams = parse_team_preferences(row.get('What year are you?', ''))  # Teams are in this column
        
        # Parse availability from Wednesday through Sunday
        availability_parts = []
        
        # Map columns to actual dates for September 11-14 schedule
        day_mapping = {
            'Thursday, September 11': '2025-09-11',   # Thursday 5-9 PM
            'Friday, September 12': '2025-09-12',     # Friday 5-9 PM  
            'Saturday, September 13': '2025-09-13',   # Saturday 10 AM-12 PM, 1-9 PM
            'Sunday, September 14': '2025-09-14'      # Sunday 10 AM-12 PM, 1-9 PM
        }
        
        for day_col, date_str in day_mapping.items():
            if day_col in row:
                time_ranges = parse_availability_slot(row[day_col])
                for time_range in time_ranges:
                    availability_parts.append(f"{date_str} {time_range}")
        
        # Join availability with semicolons
        availability_str = "; ".join(availability_parts) if availability_parts else ""
        
        applicants.append({
            'id': app_id,
            'name': name,
            'availability': availability_str,
            'teams': teams,
            'parsed_availability': parse_ranges(availability_str)
        })
    
    return applicants

def load_recruiters(path: str) -> List[Dict]:
    """Load recruiter data."""
    df = pd.read_csv(path)
    recruiters = []
    
    for _, row in df.iterrows():
        recruiters.append({
            'id': row['recruiter_id'],
            'name': row['recruiter_name'],
            'team': row['team'],
            'availability': row['availability'],
            'parsed_availability': parse_ranges(row['availability'])
        })
    
    return recruiters

def load_blocks(path: str) -> List[Dict]:
    """Load block data and create slot structure."""
    df = pd.read_csv(path)
    blocks = []
    
    for _, row in df.iterrows():
        start_dt = dt.datetime.fromisoformat(f"{row['date']} {row['start']}:00")
        end_dt = dt.datetime.fromisoformat(f"{row['date']} {row['end']}:00")
        
        # Create block structure for precise timing
        block_data = {
            'block_id': row['block_id'],
            'date': row['date'],
            'start': start_dt,
            'end': end_dt,
            'type': row['block_type'],
            'slots': [],
            'groups': []
        }
        
        if row['block_type'] == 'group':
            # Create single group for the 40-minute block
            block_data['groups'].append({
                'group_id': f"{row['block_id']}_G1",
                'slot1': {'start': start_dt, 'end': end_dt},
                'slot2': {'start': start_dt, 'end': end_dt},  # Same time for simplicity
                'priority': 'high'
            })
        
        else:  # individual block
            # Create single slot for the 20-minute block
            block_data['slots'].append({
                'slot_id': row['block_id'],
                'start': start_dt,
                'end': end_dt,
                'hour': 1
            })
        
        blocks.append(block_data)
    
    return blocks

def load_rooms(path: str) -> List[Dict]:
    """Load room data."""
    df = pd.read_csv(path)
    rooms = []
    
    for _, row in df.iterrows():
        rooms.append({
            'room_id': row['room_id'],
            'room_type': row['room_type']
        })
    
    return rooms

def schedule_recruiters(recruiters: List[Dict], blocks: List[Dict], rooms: List[Dict]) -> Dict:
    """Round 1: Schedule recruiters to blocks using OR-Tools."""
    model = cp_model.CpModel()
    
    # Decision variables: recruiter_block[r][b] = 1 if recruiter r is assigned to block b
    recruiter_block = {}
    
    for r, recruiter in enumerate(recruiters):
        for b, block in enumerate(blocks):
            recruiter_block[(r, b)] = model.NewBoolVar(f'recruiter_{r}_block_{b}')
    
    # Constraint 1: Each recruiter can only be in one block at a time (no time overlap)
    for r, recruiter in enumerate(recruiters):
        for b1, block1 in enumerate(blocks):
            for b2, block2 in enumerate(blocks):
                if b1 < b2:  # Only check each pair once
                    # Check if blocks overlap in time
                    if not (block1['end'] <= block2['start'] or block2['end'] <= block1['start']):
                        # Blocks overlap, recruiter can't be in both
                        model.Add(recruiter_block[(r, b1)] + recruiter_block[(r, b2)] <= 1)
    
    # Constraint 2: For individual blocks, assign exactly one recruiter
    for b, block in enumerate(blocks):
        if block['type'] == 'individual':
            available_recruiters = []
            for r, recruiter in enumerate(recruiters):
                if any_interval_contains(recruiter['parsed_availability'], (block['start'], block['end'])):
                    available_recruiters.append(recruiter_block[(r, b)])
                else:
                    # Recruiter not available, force to 0
                    model.Add(recruiter_block[(r, b)] == 0)
            
            if available_recruiters:
                model.Add(sum(available_recruiters) == 1)  # Exactly one recruiter per individual block
    
    # Constraint 3: For group blocks, try to assign recruiters from different teams (but don't require all 4)
    for b, block in enumerate(blocks):
        if block['type'] == 'group':
            # Assign at least 2 recruiters total for group blocks
            available_recruiters = []
            for r, recruiter in enumerate(recruiters):
                if any_interval_contains(recruiter['parsed_availability'], (block['start'], block['end'])):
                    available_recruiters.append(recruiter_block[(r, b)])
                else:
                    # Recruiter not available, force to 0
                    model.Add(recruiter_block[(r, b)] == 0)
            
            if available_recruiters:
                # Require at least 1 recruiter (relaxed from requiring all teams)
                model.Add(sum(available_recruiters) >= 1)
    
    # Constraint 4: Force unavailable recruiters to 0 (redundant with above but clearer)
    for r, recruiter in enumerate(recruiters):
        for b, block in enumerate(blocks):
            if not any_interval_contains(recruiter['parsed_availability'], (block['start'], block['end'])):
                model.Add(recruiter_block[(r, b)] == 0)
    
    # Objective: Maximize total number of recruiters assigned
    objective_terms = []
    for r, recruiter in enumerate(recruiters):
        for b, block in enumerate(blocks):
            objective_terms.append(recruiter_block[(r, b)])
    
    model.Maximize(sum(objective_terms))
    
    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    print(f"Recruiter scheduling solver status: {solver.StatusName(status)}")
    
    # Extract solution
    recruiter_assignments = {}
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        assignments_count = 0
        for r, recruiter in enumerate(recruiters):
            for b, block in enumerate(blocks):
                if solver.Value(recruiter_block[(r, b)]) == 1:
                    assignments_count += 1
                    if block['block_id'] not in recruiter_assignments:
                        recruiter_assignments[block['block_id']] = []
                    
                    # Assign appropriate room based on block type
                    room = None
                    if block['type'] == 'individual':
                        individual_rooms = [room for room in rooms if room['room_type'] == 'individual']
                        if individual_rooms:
                            room = individual_rooms[0]  # Simplified room assignment
                    else:  # group
                        group_rooms = [room for room in rooms if room['room_type'] == 'group']
                        if group_rooms:
                            room = group_rooms[0]  # Simplified room assignment
                    
                    if room:
                        recruiter_assignments[block['block_id']].append({
                            'recruiter': recruiter,
                            'room': room,
                            'block': block
                        })
        
        print(f"Total recruiter assignments made: {assignments_count}")
    else:
        print("No feasible solution found for recruiter scheduling")
    
    return recruiter_assignments
    
    # Extract solution
    recruiter_assignments = {}
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        for r, recruiter in enumerate(recruiters):
            for b, block in enumerate(blocks):
                for room_idx, room in enumerate(rooms):
                    if (r, b, room_idx) in recruiter_block_room and solver.Value(recruiter_block_room[(r, b, room_idx)]) == 1:
                        if block['block_id'] not in recruiter_assignments:
                            recruiter_assignments[block['block_id']] = []
                        recruiter_assignments[block['block_id']].append({
                            'recruiter': recruiter,
                            'room': room,
                            'block': block
                        })
    
    return recruiter_assignments

def schedule_applicants_first(applicants: List[Dict], blocks: List[Dict], recruiters: List[Dict]) -> Tuple[Dict, List[str]]:
    """Schedule applicants to slots/groups first, without considering recruiter assignments."""
    
    # Filter individual blocks to limit slots based on recruiter availability
    filtered_blocks = []
    for block in blocks:
        if block['type'] == 'individual':
            # For individual blocks, limit slots to reasonable capacity (max 4 per slot)
            block_copy = block.copy()
            block_copy['slots'] = block['slots'][:4]  # Limit to 4 individual slots per block
            filtered_blocks.append(block_copy)
        else:
            filtered_blocks.append(block)
    
    blocks = filtered_blocks
    
    model = cp_model.CpModel()
    
    # Decision variables for individual slots and groups
    applicant_slot = {}
    applicant_group = {}
    
    # Create variables for each applicant-slot/group combination
    for a, applicant in enumerate(applicants):
        for b, block in enumerate(blocks):
            if block['type'] == 'individual':
                for slot in block['slots']:
                    applicant_slot[(a, block['block_id'], slot['slot_id'])] = model.NewBoolVar(f'app_{a}_slot_{slot["slot_id"]}')
            else:  # group
                for group in block['groups']:
                    applicant_group[(a, block['block_id'], group['group_id'])] = model.NewBoolVar(f'app_{a}_group_{group["group_id"]}')
    
    # Constraint 1: Each applicant gets at most one individual slot and at most one group (prefer both)
    for a, applicant in enumerate(applicants):
        # At most one individual slot
        individual_assignments = []
        for b, block in enumerate(blocks):
            if block['type'] == 'individual':
                for slot in block['slots']:
                    if (a, block['block_id'], slot['slot_id']) in applicant_slot:
                        individual_assignments.append(applicant_slot[(a, block['block_id'], slot['slot_id'])])
        if individual_assignments:
            model.Add(sum(individual_assignments) <= 1)
        
        # At most one group
        group_assignments = []
        for b, block in enumerate(blocks):
            if block['type'] == 'group':
                for group in block['groups']:
                    if (a, block['block_id'], group['group_id']) in applicant_group:
                        group_assignments.append(applicant_group[(a, block['block_id'], group['group_id'])])
        if group_assignments:
            model.Add(sum(group_assignments) <= 1)
    
    # Constraint 2: Same-day requirement for individual and group
    for a, applicant in enumerate(applicants):
        dates = set(block['date'] for block in blocks)
        
        for date in dates:
            individual_assignments_this_date = []
            for b, block in enumerate(blocks):
                if block['type'] == 'individual' and block['date'] == date:
                    for slot in block['slots']:
                        if (a, block['block_id'], slot['slot_id']) in applicant_slot:
                            individual_assignments_this_date.append(applicant_slot[(a, block['block_id'], slot['slot_id'])])
            
            group_assignments_this_date = []
            for b, block in enumerate(blocks):
                if block['type'] == 'group' and block['date'] == date:
                    for group in block['groups']:
                        if (a, block['block_id'], group['group_id']) in applicant_group:
                            group_assignments_this_date.append(applicant_group[(a, block['block_id'], group['group_id'])])
            
            if individual_assignments_this_date and group_assignments_this_date:
                individual_sum = sum(individual_assignments_this_date)
                group_sum = sum(group_assignments_this_date)
                model.Add(individual_sum == group_sum)
    
    # Constraint 3: Applicant availability
    for a, applicant in enumerate(applicants):
        for b, block in enumerate(blocks):
            if block['type'] == 'individual':
                for slot in block['slots']:
                    if (a, block['block_id'], slot['slot_id']) in applicant_slot:
                        available = any_interval_contains(applicant['parsed_availability'], (slot['start'], slot['end']))
                        if not available:
                            model.Add(applicant_slot[(a, block['block_id'], slot['slot_id'])] == 0)
            else:  # group
                for group in block['groups']:
                    if (a, block['block_id'], group['group_id']) in applicant_group:
                        available1 = any_interval_contains(applicant['parsed_availability'], 
                                                         (group['slot1']['start'], group['slot1']['end']))
                        available2 = any_interval_contains(applicant['parsed_availability'], 
                                                         (group['slot2']['start'], group['slot2']['end']))
                        if not (available1 and available2):
                            model.Add(applicant_group[(a, block['block_id'], group['group_id'])] == 0)
    
    # Constraint 4: Time overlap prevention
    for a, applicant in enumerate(applicants):
        for b1, block1 in enumerate(blocks):
            if block1['type'] == 'individual':
                for slot in block1['slots']:
                    if (a, block1['block_id'], slot['slot_id']) in applicant_slot:
                        for b2, block2 in enumerate(blocks):
                            if block2['type'] == 'group':
                                for group in block2['groups']:
                                    if (a, block2['block_id'], group['group_id']) in applicant_group:
                                        slot_start, slot_end = slot['start'], slot['end']
                                        group_start1 = group['slot1']['start']
                                        group_end1 = group['slot1']['end']
                                        group_start2 = group['slot2']['start']
                                        group_end2 = group['slot2']['end']
                                        
                                        if (slot_start < group_end1 and slot_end > group_start1) or \
                                           (slot_start < group_end2 and slot_end > group_start2):
                                            model.Add(applicant_slot[(a, block1['block_id'], slot['slot_id'])] + 
                                                    applicant_group[(a, block2['block_id'], group['group_id'])] <= 1)
    
    # Constraint 5: Group capacity (up to 8 applicants per group)
    for b, block in enumerate(blocks):
        if block['type'] == 'group':
            for group in block['groups']:
                group_assignments = []
                for a, applicant in enumerate(applicants):
                    if (a, block['block_id'], group['group_id']) in applicant_group:
                        group_assignments.append(applicant_group[(a, block['block_id'], group['group_id'])])
                if group_assignments:
                    model.Add(sum(group_assignments) <= 8)  # Max 8 per group

    # Constraint 6: Individual slot capacity (exactly 1 applicant per slot)
    for b, block in enumerate(blocks):
        if block['type'] == 'individual':
            for slot in block['slots']:
                slot_assignments = []
                for a, applicant in enumerate(applicants):
                    if (a, block['block_id'], slot['slot_id']) in applicant_slot:
                        slot_assignments.append(applicant_slot[(a, block['block_id'], slot['slot_id'])])
                if slot_assignments:
                    model.Add(sum(slot_assignments) <= 1)  # Max 1 applicant per individual slot

    # Objective: Maximize complete assignments while minimizing individual slot usage
    objective_terms = []
    
    # Strongly prioritize complete assignments (both individual and group)
    for a, applicant in enumerate(applicants):
        individual_var = model.NewBoolVar(f'has_individual_{a}')
        individual_assignments = []
        for b, block in enumerate(blocks):
            if block['type'] == 'individual':
                for slot in block['slots']:
                    if (a, block['block_id'], slot['slot_id']) in applicant_slot:
                        individual_assignments.append(applicant_slot[(a, block['block_id'], slot['slot_id'])])
        if individual_assignments:
            model.Add(individual_var == sum(individual_assignments))
        
        group_var = model.NewBoolVar(f'has_group_{a}')
        group_assignments = []
        for b, block in enumerate(blocks):
            if block['type'] == 'group':
                for group in block['groups']:
                    if (a, block['block_id'], group['group_id']) in applicant_group:
                        group_assignments.append(applicant_group[(a, block['block_id'], group['group_id'])])
        if group_assignments:
            model.Add(group_var == sum(group_assignments))
        
        # Complete assignment bonus
        complete_var = model.NewBoolVar(f'complete_{a}')
        if individual_assignments and group_assignments:
            model.Add(complete_var <= individual_var)
            model.Add(complete_var <= group_var)
            model.Add(complete_var >= individual_var + group_var - 1)
            objective_terms.append(100 * complete_var)  # High weight for complete assignments
    
    # Minimize individual slot usage (prefer concentrating applicants)
    for b, block in enumerate(blocks):
        if block['type'] == 'individual':
            for slot in block['slots']:
                slot_used = model.NewBoolVar(f'slot_used_{block["block_id"]}_{slot["slot_id"]}')
                slot_assignments = []
                for a, applicant in enumerate(applicants):
                    if (a, block['block_id'], slot['slot_id']) in applicant_slot:
                        slot_assignments.append(applicant_slot[(a, block['block_id'], slot['slot_id'])])
                if slot_assignments:
                    # Slot is used if any assignment exists
                    for assignment in slot_assignments:
                        model.Add(slot_used >= assignment)
                    objective_terms.append(-1 * slot_used)  # Small penalty for using slots
    
    model.Maximize(sum(objective_terms))
    
    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    # Extract solution
    applicant_assignments = {}
    unscheduled = []
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        scheduled_applicants = set()
        
        # Extract individual and group assignments
        for a, applicant in enumerate(applicants):
            individual_assignment = None
            group_assignment = None
            
            # Find individual assignment
            for b, block in enumerate(blocks):
                if block['type'] == 'individual':
                    for slot in block['slots']:
                        if (a, block['block_id'], slot['slot_id']) in applicant_slot and \
                           solver.Value(applicant_slot[(a, block['block_id'], slot['slot_id'])]) == 1:
                            individual_assignment = {
                                'individual_block_id': block['block_id'],
                                'individual_slot_id': slot['slot_id'],
                                'individual_start': slot['start'],
                                'individual_end': slot['end']
                            }
                            break
            
            # Find group assignment
            for b, block in enumerate(blocks):
                if block['type'] == 'group':
                    for group in block['groups']:
                        if (a, block['block_id'], group['group_id']) in applicant_group and \
                           solver.Value(applicant_group[(a, block['block_id'], group['group_id'])]) == 1:
                            group_assignment = {
                                'group_block_id': block['block_id'],
                                'group_id': group['group_id'],
                                'group_slot1_start': group['slot1']['start'],
                                'group_slot1_end': group['slot1']['end'],
                                'group_slot2_start': group['slot2']['start'],
                                'group_slot2_end': group['slot2']['end']
                            }
                            break
            
            # Include applicants with either individual OR group assignments (or both)
            if individual_assignment or group_assignment:
                assignment_data = {'applicant': applicant}
                if individual_assignment:
                    assignment_data.update(individual_assignment)
                if group_assignment:
                    assignment_data.update(group_assignment)
                
                applicant_assignments[applicant['id']] = assignment_data
                scheduled_applicants.add(applicant['id'])
        
        # Unscheduled applicants
        for applicant in applicants:
            if applicant['id'] not in scheduled_applicants:
                unscheduled.append(applicant['id'])
    else:
        # If no solution found, all applicants are unscheduled
        unscheduled = [applicant['id'] for applicant in applicants]
    
    return applicant_assignments, unscheduled

def schedule_recruiters_to_match(recruiters: List[Dict], applicant_assignments: Dict, blocks: List[Dict], rooms: List[Dict]) -> Dict:
    """Schedule recruiters to match the applicant assignments."""
    
    # Get blocks that have applicants assigned
    blocks_with_applicants = set()
    applicant_blocks = {}  # block_id -> list of applicants
    
    for app_id, assignment in applicant_assignments.items():
        individual_block = assignment.get('individual_block_id')
        group_block = assignment.get('group_block_id')
        
        if individual_block:
            blocks_with_applicants.add(individual_block)
            if individual_block not in applicant_blocks:
                applicant_blocks[individual_block] = []
            applicant_blocks[individual_block].append(assignment['applicant'])
        
        if group_block:
            blocks_with_applicants.add(group_block)
            if group_block not in applicant_blocks:
                applicant_blocks[group_block] = []
            applicant_blocks[group_block].append(assignment['applicant'])
    
    recruiter_assignments = {}
    
    for block_id in blocks_with_applicants:
        block = next(b for b in blocks if b['block_id'] == block_id)
        applicants_in_block = applicant_blocks[block_id]
        
        # Get teams needed for this block
        teams_needed = set()
        for app in applicants_in_block:
            if app['teams']:
                teams_needed.update(app['teams'])
        
        recruiter_assignments[block_id] = []
        
        if block['type'] == 'individual':
            # For individual blocks: 1 recruiter per applicant with team match
            for app in applicants_in_block:
                # Find a recruiter with matching team and availability
                best_recruiter = None
                for recruiter in recruiters:
                    # Check team match
                    if app['teams'] and recruiter['team'] not in app['teams']:
                        continue
                    
                    # Check availability
                    available = any_interval_contains(recruiter['parsed_availability'], 
                                                    (block['slots'][0]['start'], block['slots'][0]['end']))
                    if not available:
                        continue
                    
                    # Check if recruiter is already assigned to this block
                    already_assigned = any(assignment['recruiter']['id'] == recruiter['id'] 
                                         for assignment in recruiter_assignments[block_id])
                    if already_assigned:
                        continue
                    
                    best_recruiter = recruiter
                    break
                
                if best_recruiter:
                    recruiter_assignments[block_id].append({
                        'recruiter': best_recruiter,
                        'room': rooms[0] if rooms else {'room_id': 'TBD'},  # Simple room assignment
                        'block': block
                    })
        
        else:  # group block
            # For group blocks: Try to get diverse team representation
            assigned_teams = set()
            for team in teams_needed:
                # Find an available recruiter from this team
                for recruiter in recruiters:
                    if recruiter['team'] != team:
                        continue
                    if recruiter['team'] in assigned_teams:
                        continue
                    
                    # Check availability for both group slots
                    available1 = any_interval_contains(recruiter['parsed_availability'], 
                                                     (block['groups'][0]['slot1']['start'], 
                                                      block['groups'][0]['slot1']['end']))
                    available2 = any_interval_contains(recruiter['parsed_availability'], 
                                                     (block['groups'][0]['slot2']['start'], 
                                                      block['groups'][0]['slot2']['end']))
                    if not (available1 and available2):
                        continue
                    
                    recruiter_assignments[block_id].append({
                        'recruiter': recruiter,
                        'room': rooms[0] if rooms else {'room_id': 'TBD'},  # Simple room assignment
                        'block': block
                    })
                    assigned_teams.add(team)
                    break
    
    return recruiter_assignments

def schedule_applicants(applicants: List[Dict], recruiter_assignments: Dict, blocks: List[Dict]) -> Tuple[Dict, List[str]]:
    """Round 2: Schedule applicants to slots/groups using OR-Tools."""
    model = cp_model.CpModel()
    
    # Decision variables for individual slots and groups
    applicant_slot = {}
    applicant_group = {}
    
    # Create variables for individual slots
    for a, applicant in enumerate(applicants):
        for b, block in enumerate(blocks):
            if block['type'] == 'individual':
                for slot in block['slots']:
                    applicant_slot[(a, block['block_id'], slot['slot_id'])] = model.NewBoolVar(f'app_{a}_slot_{slot["slot_id"]}')
            else:  # group block
                for group in block['groups']:
                    applicant_group[(a, block['block_id'], group['group_id'])] = model.NewBoolVar(f'app_{a}_group_{group["group_id"]}')
    
    # Constraint 1: Each applicant should get exactly one individual slot and exactly one group, but allow partial scheduling
    for a, applicant in enumerate(applicants):
        # At most one individual slot
        individual_assignments = []
        for b, block in enumerate(blocks):
            if block['type'] == 'individual':
                for slot in block['slots']:
                    if (a, block['block_id'], slot['slot_id']) in applicant_slot:
                        individual_assignments.append(applicant_slot[(a, block['block_id'], slot['slot_id'])])
        if individual_assignments:
            model.Add(sum(individual_assignments) <= 1)  # At most one for now
        
        # At most one group
        group_assignments = []
        for b, block in enumerate(blocks):
            if block['type'] == 'group':
                for group in block['groups']:
                    if (a, block['block_id'], group['group_id']) in applicant_group:
                        group_assignments.append(applicant_group[(a, block['block_id'], group['group_id'])])
        if group_assignments:
            model.Add(sum(group_assignments) <= 1)  # At most one for now
    
    # Constraint 2: No time overlap between individual and group assignments
    for a, applicant in enumerate(applicants):
        for b1, block1 in enumerate(blocks):
            if block1['type'] == 'individual':
                for slot in block1['slots']:
                    if (a, block1['block_id'], slot['slot_id']) in applicant_slot:
                        # Check against all group assignments for time conflicts
                        for b2, block2 in enumerate(blocks):
                            if block2['type'] == 'group':
                                for group in block2['groups']:
                                    if (a, block2['block_id'], group['group_id']) in applicant_group:
                                        # Check if times overlap
                                        slot_start, slot_end = slot['start'], slot['end']
                                        group_start1 = group['slot1']['start']
                                        group_end1 = group['slot1']['end']
                                        group_start2 = group['slot2']['start']
                                        group_end2 = group['slot2']['end']
                                        
                                        if (slot_start < group_end1 and slot_end > group_start1) or \
                                           (slot_start < group_end2 and slot_end > group_start2):
                                            # Time conflict - can't assign both
                                            model.Add(applicant_slot[(a, block1['block_id'], slot['slot_id'])] + 
                                                    applicant_group[(a, block2['block_id'], group['group_id'])] <= 1)
    
    # Constraint 3: Applicant availability
    for a, applicant in enumerate(applicants):
        for b, block in enumerate(blocks):
            if block['type'] == 'individual':
                for slot in block['slots']:
                    if (a, block['block_id'], slot['slot_id']) in applicant_slot:
                        available = any_interval_contains(applicant['parsed_availability'], (slot['start'], slot['end']))
                        if not available:
                            model.Add(applicant_slot[(a, block['block_id'], slot['slot_id'])] == 0)
            else:  # group
                for group in block['groups']:
                    if (a, block['block_id'], group['group_id']) in applicant_group:
                        # Must be available for both slots in the group
                        available1 = any_interval_contains(applicant['parsed_availability'], 
                                                         (group['slot1']['start'], group['slot1']['end']))
                        available2 = any_interval_contains(applicant['parsed_availability'], 
                                                         (group['slot2']['start'], group['slot2']['end']))
                        if not (available1 and available2):
                            model.Add(applicant_group[(a, block['block_id'], group['group_id'])] == 0)
    
    # Constraint 3.5: Individual and group assignments must be on the same day
    for a, applicant in enumerate(applicants):
        # For each date, collect individual and group assignments
        dates = set(block['date'] for block in blocks)
        
        for date in dates:
            # Collect individual assignments for this date
            individual_assignments_this_date = []
            for b, block in enumerate(blocks):
                if block['type'] == 'individual' and block['date'] == date:
                    for slot in block['slots']:
                        if (a, block['block_id'], slot['slot_id']) in applicant_slot:
                            individual_assignments_this_date.append(applicant_slot[(a, block['block_id'], slot['slot_id'])])
            
            # Collect group assignments for this date  
            group_assignments_this_date = []
            for b, block in enumerate(blocks):
                if block['type'] == 'group' and block['date'] == date:
                    for group in block['groups']:
                        if (a, block['block_id'], group['group_id']) in applicant_group:
                            group_assignments_this_date.append(applicant_group[(a, block['block_id'], group['group_id'])])
            
            # If this applicant has assignments on this date, they must have both individual AND group
            if individual_assignments_this_date and group_assignments_this_date:
                individual_sum = sum(individual_assignments_this_date)
                group_sum = sum(group_assignments_this_date)
                # If individual on this date, must also have group on this date
                model.Add(individual_sum == group_sum)

    # Constraint 4: Team matching - applicants can only be assigned to blocks with recruiters from their teams
    for a, applicant in enumerate(applicants):
        if not applicant['teams']:  # Skip if no team preferences
            continue
            
        for b, block in enumerate(blocks):
            block_id = block['block_id']
            if block_id in recruiter_assignments:
                # Get teams of recruiters assigned to this block
                recruiter_teams = {assignment['recruiter']['team'] for assignment in recruiter_assignments[block_id]}
                
                # Check if applicant has any matching team
                has_matching_team = bool(applicant['teams'].intersection(recruiter_teams))
                
                if not has_matching_team:
                    # Can't assign this applicant to this block
                    if block['type'] == 'individual':
                        for slot in block['slots']:
                            if (a, block_id, slot['slot_id']) in applicant_slot:
                                model.Add(applicant_slot[(a, block_id, slot['slot_id'])] == 0)
                    else:  # group
                        for group in block['groups']:
                            if (a, block_id, group['group_id']) in applicant_group:
                                model.Add(applicant_group[(a, block_id, group['group_id'])] == 0)
    
    # Constraint 5: Individual blocks can have at most as many applicants as recruiters
    for b, block in enumerate(blocks):
        if block['type'] == 'individual':
            block_id = block['block_id']
            if block_id in recruiter_assignments:
                recruiter_count = len(recruiter_assignments[block_id])
                # Sum all applicants assigned to this individual block
                block_assignments = []
                for a, applicant in enumerate(applicants):
                    for slot in block['slots']:
                        if (a, block_id, slot['slot_id']) in applicant_slot:
                            block_assignments.append(applicant_slot[(a, block_id, slot['slot_id'])])
                
                if block_assignments:
                    model.Add(sum(block_assignments) <= recruiter_count)

    # Objective: Strongly prioritize applicants who get BOTH individual AND group slots
    objective_terms = []
    
    # For each applicant, create variables to track if they have both types
    complete_assignments = []
    for a, applicant in enumerate(applicants):
        # Get individual assignment variable
        individual_var = model.NewBoolVar(f'has_individual_{a}')
        individual_assignments = []
        for b, block in enumerate(blocks):
            if block['type'] == 'individual':
                for slot in block['slots']:
                    if (a, block['block_id'], slot['slot_id']) in applicant_slot:
                        individual_assignments.append(applicant_slot[(a, block['block_id'], slot['slot_id'])])
        if individual_assignments:
            model.Add(individual_var == sum(individual_assignments))
        
        # Get group assignment variable
        group_var = model.NewBoolVar(f'has_group_{a}')
        group_assignments = []
        for b, block in enumerate(blocks):
            if block['type'] == 'group':
                for group in block['groups']:
                    if (a, block['block_id'], group['group_id']) in applicant_group:
                        group_assignments.append(applicant_group[(a, block['block_id'], group['group_id'])])
        if group_assignments:
            model.Add(group_var == sum(group_assignments))
        
        # Create variable for complete assignment (both individual AND group)
        complete_var = model.NewBoolVar(f'complete_{a}')
        if individual_assignments and group_assignments:
            model.Add(complete_var <= individual_var)
            model.Add(complete_var <= group_var)
            model.Add(complete_var >= individual_var + group_var - 1)
            
            # Heavily weight complete assignments
            objective_terms.append(100 * complete_var)  # Very high weight for complete assignments
            
            # Small penalty for partial assignments
            objective_terms.append(-10 * individual_var)  # Penalty for individual only
            objective_terms.append(-10 * group_var)       # Penalty for group only
            objective_terms.append(20 * individual_var)   # But still some benefit
            objective_terms.append(20 * group_var)        # But still some benefit
    
    model.Maximize(sum(objective_terms))
    
    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    # Extract solution
    applicant_assignments = {}
    unscheduled = []
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        scheduled_applicants = set()
        
        # Extract individual slot assignments
        for a, applicant in enumerate(applicants):
            for b, block in enumerate(blocks):
                if block['type'] == 'individual':
                    for slot in block['slots']:
                        if (a, block['block_id'], slot['slot_id']) in applicant_slot and \
                           solver.Value(applicant_slot[(a, block['block_id'], slot['slot_id'])]) == 1:
                            applicant_assignments[applicant['id']] = {
                                'type': 'individual',
                                'block_id': block['block_id'],
                                'slot_id': slot['slot_id'],
                                'slot': slot
                            }
                            scheduled_applicants.add(applicant['id'])
        
        # Extract group assignments
        for a, applicant in enumerate(applicants):
            for b, block in enumerate(blocks):
                if block['type'] == 'group':
                    for group in block['groups']:
                        if (a, block['block_id'], group['group_id']) in applicant_group and \
                           solver.Value(applicant_group[(a, block['block_id'], group['group_id'])]) == 1:
                            if applicant['id'] not in applicant_assignments:
                                applicant_assignments[applicant['id']] = {}
                            applicant_assignments[applicant['id']].update({
                                'group_type': 'group',
                                'group_block_id': block['block_id'],
                                'group_id': group['group_id'],
                                'group': group
                            })
                            scheduled_applicants.add(applicant['id'])
        
        # Find unscheduled applicants
        for applicant in applicants:
            if applicant['id'] not in scheduled_applicants:
                unscheduled.append(applicant['id'])
    
    return applicant_assignments, unscheduled

def write_output_files(recruiter_assignments: Dict, applicant_assignments: Dict, unscheduled: List[str], 
                      applicants: List[Dict], recruiters: List[Dict], blocks: List[Dict], output_dir: str = "results"):
    """Write output CSV files to organized directory structure."""
    
    # Create timestamped output directory
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(output_dir) / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories for better organization
    schedules_dir = run_dir / "schedules"
    summaries_dir = run_dir / "summaries"
    schedules_dir.mkdir(exist_ok=True)
    summaries_dir.mkdir(exist_ok=True)
    
    # File paths with organized structure
    recruiter_file = schedules_dir / "recruiters_schedule.csv"
    applicant_file = schedules_dir / "applicants_schedule.csv"
    unscheduled_file = schedules_dir / "unscheduled_applicants.csv"
    summary_file = summaries_dir / "run_summary.txt"
    
    # 1. Recruiter schedule
    recruiter_rows = []
    for block_id, assignments in recruiter_assignments.items():
        block = next(b for b in blocks if b['block_id'] == block_id)
        for assignment in assignments:
            recruiter_rows.append({
                'block_id': block_id,
                'recruiter_id': assignment['recruiter']['id'],
                'recruiter_name': assignment['recruiter']['name'],
                'team': assignment['recruiter']['team'],
                'room_id': assignment['room']['room_id'],
                'start': block['start'].strftime('%Y-%m-%d %H:%M:%S'),
                'end': block['end'].strftime('%Y-%m-%d %H:%M:%S')
            })
    
    with open(recruiter_file, 'w', newline='') as f:
        if recruiter_rows:
            writer = csv.DictWriter(f, fieldnames=recruiter_rows[0].keys())
            writer.writeheader()
            writer.writerows(recruiter_rows)
    
    # 2. Applicant schedule
    applicant_rows = []
    for app_id, assignment in applicant_assignments.items():
        applicant = next(a for a in applicants if a['id'] == app_id)
        row = {
            'applicant_id': app_id,
            'applicant_name': applicant['name'],
            'teams': ','.join(applicant['teams']) if applicant['teams'] else 'None'
        }
        
        # Individual slot info
        if 'individual_block_id' in assignment and assignment['individual_block_id']:
            row.update({
                'individual_block_id': assignment['individual_block_id'],
                'individual_slot_id': assignment['individual_slot_id'],
                'individual_start': assignment['individual_start'].strftime('%Y-%m-%d %H:%M:%S'),
                'individual_end': assignment['individual_end'].strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            row.update({
                'individual_block_id': '',
                'individual_slot_id': '',
                'individual_start': '',
                'individual_end': ''
            })
        
        # Group info
        if 'group_block_id' in assignment and assignment['group_block_id']:
            row.update({
                'group_block_id': assignment['group_block_id'],
                'group_id': assignment['group_id'],
                'group_slot1_start': assignment['group_slot1_start'].strftime('%Y-%m-%d %H:%M:%S'),
                'group_slot1_end': assignment['group_slot1_end'].strftime('%Y-%m-%d %H:%M:%S'),
                'group_slot2_start': assignment['group_slot2_start'].strftime('%Y-%m-%d %H:%M:%S'),
                'group_slot2_end': assignment['group_slot2_end'].strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            row.update({
                'group_block_id': '',
                'group_id': '',
                'group_slot1_start': '',
                'group_slot1_end': '',
                'group_slot2_start': '',
                'group_slot2_end': ''
            })
        
        applicant_rows.append(row)
    
    with open(applicant_file, 'w', newline='') as f:
        if applicant_rows:
            writer = csv.DictWriter(f, fieldnames=applicant_rows[0].keys())
            writer.writeheader()
            writer.writerows(applicant_rows)
    
    # 3. Unscheduled applicants
    with open(unscheduled_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['applicant_id'])
        for app_id in unscheduled:
            writer.writerow([app_id])
    
    # 4. Generate run summary
    thursday_count = sum(1 for assignment in applicant_assignments.values() 
                        if 'individual_block_id' in assignment and assignment['individual_block_id'] and assignment['individual_block_id'].startswith('T11'))
    friday_count = sum(1 for assignment in applicant_assignments.values() 
                      if 'individual_block_id' in assignment and assignment['individual_block_id'] and assignment['individual_block_id'].startswith('F12'))
    saturday_count = sum(1 for assignment in applicant_assignments.values() 
                        if 'individual_block_id' in assignment and assignment['individual_block_id'] and assignment['individual_block_id'].startswith('S13'))
    sunday_count = sum(1 for assignment in applicant_assignments.values() 
                      if 'individual_block_id' in assignment and assignment['individual_block_id'] and assignment['individual_block_id'].startswith('U14'))
    
    with open(summary_file, 'w') as f:
        f.write(f"SCHEDULING RUN SUMMARY\n")
        f.write(f"=====================\n")
        f.write(f"Run Date: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Output Directory: {run_dir}\n\n")
        f.write(f"SCHEDULE COVERAGE:\n")
        f.write(f"Thursday Sep 11 (5-9 PM): {22} blocks\n")
        f.write(f"Friday Sep 12 (5-9 PM): {22} blocks\n")
        f.write(f"Saturday Sep 13 (10 AM-12 PM, 1-9 PM): {56} blocks\n")
        f.write(f"Sunday Sep 14 (10 AM-12 PM, 1-9 PM): {56} blocks\n")
        f.write(f"Total Blocks: {len(blocks)}\n\n")
        f.write(f"RESULTS:\n")
        f.write(f"Total Applicants: {len(applicants)}\n")
        f.write(f"Successfully Scheduled: {len(applicant_assignments)} ({100*len(applicant_assignments)/len(applicants):.1f}%)\n")
        f.write(f"Unscheduled: {len(unscheduled)} ({100*len(unscheduled)/len(applicants):.1f}%)\n\n")
        f.write(f"DAY DISTRIBUTION:\n")
        f.write(f"Thursday Appointments: {thursday_count}\n")
        f.write(f"Friday Appointments: {friday_count}\n")
        f.write(f"Saturday Appointments: {saturday_count}\n")
        f.write(f"Sunday Appointments: {sunday_count}\n\n")
        f.write(f"OUTPUT FILES:\n")
        f.write(f"- schedules/recruiters_schedule.csv\n")
        f.write(f"- schedules/applicants_schedule.csv\n")
        f.write(f"- schedules/unscheduled_applicants.csv\n")
        f.write(f"- summaries/run_summary.txt\n")
    
    print(f"Output files written to: {run_dir}")
    print(f"  - schedules/recruiters_schedule.csv")
    print(f"  - schedules/applicants_schedule.csv") 
    print(f"  - schedules/unscheduled_applicants.csv")
    print(f"  - summaries/run_summary.txt")
    
    return str(run_dir)

def main():
    parser = argparse.ArgumentParser(description='Autoscheduler for interview blocks')
    parser.add_argument('--input-dir', default='.', help='Input directory containing CSV files')
    parser.add_argument('--output-dir', default='results', help='Output directory for results')
    
    args = parser.parse_args()
    
    # Load input files
    print("Loading input files...")
    applicants = load_applicants(os.path.join(args.input_dir, 'applicant_info.csv'))
    recruiters = load_recruiters(os.path.join(args.input_dir, 'recruiters.csv'))
    blocks = load_blocks(os.path.join(args.input_dir, 'blocks.csv'))
    rooms = load_rooms(os.path.join(args.input_dir, 'rooms.csv'))
    
    print(f"Loaded {len(applicants)} applicants, {len(recruiters)} recruiters, {len(blocks)} blocks, {len(rooms)} rooms")
    
    # Round 1: Schedule applicants to slots/groups first
    print("\nRound 1: Scheduling applicants to slots/groups...")
    applicant_assignments, unscheduled = schedule_applicants_first(applicants, blocks, recruiters)
    print(f"Scheduled {len(applicant_assignments)} applicants, {len(unscheduled)} unscheduled")
    
    # Round 2: Schedule recruiters to match applicant assignments
    print("\nRound 2: Scheduling recruiters to match applicants...")
    recruiter_assignments = schedule_recruiters_to_match(recruiters, applicant_assignments, blocks, rooms)
    print(f"Scheduled recruiters to {len(recruiter_assignments)} blocks with applicants")
    
    # Filter out empty blocks (blocks with no applicant assignments)
    print("\nFiltering out empty blocks...")
    blocks_with_applicants = set()
    for app_id, assignment in applicant_assignments.items():
        if 'individual_block_id' in assignment and assignment['individual_block_id']:
            blocks_with_applicants.add(assignment['individual_block_id'])
        if 'group_block_id' in assignment and assignment['group_block_id']:
            blocks_with_applicants.add(assignment['group_block_id'])
    
    # Filter recruiter assignments to only include blocks with applicants
    filtered_recruiter_assignments = {
        block_id: assignments for block_id, assignments in recruiter_assignments.items()
        if block_id in blocks_with_applicants
    }
    
    # Filter blocks list to only include blocks with applicants
    filtered_blocks = [
        block for block in blocks 
        if block['block_id'] in blocks_with_applicants
    ]
    
    print(f"Keeping {len(filtered_blocks)} blocks with applicants (removed {len(blocks) - len(filtered_blocks)} empty blocks)")
    
    # Write output files
    print("\nWriting output files...")
    output_dir = write_output_files(filtered_recruiter_assignments, applicant_assignments, unscheduled, 
                                  applicants, recruiters, filtered_blocks, args.output_dir)
    
    print(f"\nScheduling complete!")
    print(f"Success rate: {len(applicant_assignments)}/{len(applicants)} ({100*len(applicant_assignments)/len(applicants):.1f}%)")
    print(f"Results saved to: {output_dir}")

if __name__ == "__main__":
    main()
