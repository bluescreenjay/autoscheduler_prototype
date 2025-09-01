import pandas as pd
from ortools.sat.python import cp_model
import csv
import os
import argparse
from autoscheduler import (
    load_applicants, load_recruiters, load_blocks, load_rooms,
    schedule_recruiters, any_interval_contains, TEAMS
)

def relaxed_schedule_applicants(applicants, recruiter_assignments, blocks, unscheduled_ids):
    """Relaxed scheduling for unscheduled applicants - finds best possible assignments."""
    model = cp_model.CpModel()
    
    # Filter to only unscheduled applicants
    unscheduled_applicants = [a for a in applicants if a['id'] in unscheduled_ids]
    
    if not unscheduled_applicants:
        return {}, [], []
    
    # Decision variables with relaxed constraints
    applicant_slot = {}
    applicant_group = {}
    
    # Violation variables for constraint relaxation
    availability_violations = {}
    team_violations = {}
    
    # Create variables for individual slots and groups
    for a, applicant in enumerate(unscheduled_applicants):
        for b, block in enumerate(blocks):
            if block['type'] == 'individual':
                for slot in block['slots']:
                    var_name = f'app_{a}_slot_{slot["slot_id"]}'
                    applicant_slot[(a, block['block_id'], slot['slot_id'])] = model.NewBoolVar(var_name)
                    
                    # Availability violation variable
                    avail_var_name = f'avail_viol_{a}_slot_{slot["slot_id"]}'
                    availability_violations[(a, block['block_id'], slot['slot_id'], 'slot')] = model.NewBoolVar(avail_var_name)
                    
                    # Team violation variable
                    team_var_name = f'team_viol_{a}_slot_{slot["slot_id"]}'
                    team_violations[(a, block['block_id'], slot['slot_id'], 'slot')] = model.NewBoolVar(team_var_name)
                    
            else:  # group block
                for group in block['groups']:
                    var_name = f'app_{a}_group_{group["group_id"]}'
                    applicant_group[(a, block['block_id'], group['group_id'])] = model.NewBoolVar(var_name)
                    
                    # Availability violation variable
                    avail_var_name = f'avail_viol_{a}_group_{group["group_id"]}'
                    availability_violations[(a, block['block_id'], group['group_id'], 'group')] = model.NewBoolVar(avail_var_name)
                    
                    # Team violation variable
                    team_var_name = f'team_viol_{a}_group_{group["group_id"]}'
                    team_violations[(a, block['block_id'], group['group_id'], 'group')] = model.NewBoolVar(team_var_name)
    
    # Constraint 1: Each applicant assigned to at most one individual slot and one group
    for a, applicant in enumerate(unscheduled_applicants):
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
    
    # Relaxed availability constraints
    for a, applicant in enumerate(unscheduled_applicants):
        for b, block in enumerate(blocks):
            if block['type'] == 'individual':
                for slot in block['slots']:
                    if (a, block['block_id'], slot['slot_id']) in applicant_slot:
                        available = any_interval_contains(applicant['parsed_availability'], (slot['start'], slot['end']))
                        assignment_var = applicant_slot[(a, block['block_id'], slot['slot_id'])]
                        violation_var = availability_violations[(a, block['block_id'], slot['slot_id'], 'slot')]
                        
                        if not available:
                            # If not available, assignment implies violation
                            model.Add(assignment_var <= violation_var)
                        else:
                            # If available, no violation
                            model.Add(violation_var == 0)
            else:  # group
                for group in block['groups']:
                    if (a, block['block_id'], group['group_id']) in applicant_group:
                        available1 = any_interval_contains(applicant['parsed_availability'], 
                                                         (group['slot1']['start'], group['slot1']['end']))
                        available2 = any_interval_contains(applicant['parsed_availability'], 
                                                         (group['slot2']['start'], group['slot2']['end']))
                        assignment_var = applicant_group[(a, block['block_id'], group['group_id'])]
                        violation_var = availability_violations[(a, block['block_id'], group['group_id'], 'group')]
                        
                        if not (available1 and available2):
                            # If not available for both slots, assignment implies violation
                            model.Add(assignment_var <= violation_var)
                        else:
                            # If available for both, no violation
                            model.Add(violation_var == 0)
    
    # Relaxed team matching constraints
    for a, applicant in enumerate(unscheduled_applicants):
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
                    # Team mismatch - assignment implies violation
                    if block['type'] == 'individual':
                        for slot in block['slots']:
                            if (a, block_id, slot['slot_id']) in applicant_slot:
                                assignment_var = applicant_slot[(a, block_id, slot['slot_id'])]
                                violation_var = team_violations[(a, block_id, slot['slot_id'], 'slot')]
                                model.Add(assignment_var <= violation_var)
                    else:  # group
                        for group in block['groups']:
                            if (a, block_id, group['group_id']) in applicant_group:
                                assignment_var = applicant_group[(a, block_id, group['group_id'])]
                                violation_var = team_violations[(a, block_id, group['group_id'], 'group')]
                                model.Add(assignment_var <= violation_var)
                else:
                    # Team match - no violation
                    if block['type'] == 'individual':
                        for slot in block['slots']:
                            if (a, block_id, slot['slot_id']) in applicant_slot:
                                violation_var = team_violations[(a, block_id, slot['slot_id'], 'slot')]
                                model.Add(violation_var == 0)
                    else:  # group
                        for group in block['groups']:
                            if (a, block_id, group['group_id']) in applicant_group:
                                violation_var = team_violations[(a, block_id, group['group_id'], 'group')]
                                model.Add(violation_var == 0)
    
    # Objective: Maximize scheduled applicants, minimize violations
    objective_terms = []
    
    # High priority: schedule applicants (weight 100)
    for a, applicant in enumerate(unscheduled_applicants):
        for b, block in enumerate(blocks):
            if block['type'] == 'individual':
                for slot in block['slots']:
                    if (a, block['block_id'], slot['slot_id']) in applicant_slot:
                        objective_terms.append(100 * applicant_slot[(a, block['block_id'], slot['slot_id'])])
            else:  # group
                for group in block['groups']:
                    if (a, block['block_id'], group['group_id']) in applicant_group:
                        # Prioritize high-priority groups (G1, G3)
                        weight = 200 if group['priority'] == 'high' else 100
                        objective_terms.append(weight * applicant_group[(a, block['block_id'], group['group_id'])])
    
    # Medium penalty: availability violations (weight -10)
    for violation_var in availability_violations.values():
        objective_terms.append(-10 * violation_var)
    
    # Low penalty: team violations (weight -5)
    for violation_var in team_violations.values():
        objective_terms.append(-5 * violation_var)
    
    model.Maximize(sum(objective_terms))
    
    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    # Extract solution
    relaxed_assignments = {}
    violations = []
    still_unscheduled = []
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        scheduled_in_relaxed = set()
        
        # Extract individual slot assignments
        for a, applicant in enumerate(unscheduled_applicants):
            for b, block in enumerate(blocks):
                if block['type'] == 'individual':
                    for slot in block['slots']:
                        if (a, block['block_id'], slot['slot_id']) in applicant_slot and \
                           solver.Value(applicant_slot[(a, block['block_id'], slot['slot_id'])]) == 1:
                            relaxed_assignments[applicant['id']] = {
                                'type': 'individual',
                                'block_id': block['block_id'],
                                'slot_id': slot['slot_id'],
                                'slot': slot
                            }
                            scheduled_in_relaxed.add(applicant['id'])
                            
                            # Check for violations
                            if solver.Value(availability_violations[(a, block['block_id'], slot['slot_id'], 'slot')]) == 1:
                                violations.append(f"Availability violation: {applicant['id']} in slot {slot['slot_id']}")
                            if solver.Value(team_violations[(a, block['block_id'], slot['slot_id'], 'slot')]) == 1:
                                violations.append(f"Team mismatch: {applicant['id']} in slot {slot['slot_id']}")
        
        # Extract group assignments
        for a, applicant in enumerate(unscheduled_applicants):
            for b, block in enumerate(blocks):
                if block['type'] == 'group':
                    for group in block['groups']:
                        if (a, block['block_id'], group['group_id']) in applicant_group and \
                           solver.Value(applicant_group[(a, block['block_id'], group['group_id'])]) == 1:
                            if applicant['id'] not in relaxed_assignments:
                                relaxed_assignments[applicant['id']] = {}
                            relaxed_assignments[applicant['id']].update({
                                'group_type': 'group',
                                'group_block_id': block['block_id'],
                                'group_id': group['group_id'],
                                'group': group
                            })
                            scheduled_in_relaxed.add(applicant['id'])
                            
                            # Check for violations
                            if solver.Value(availability_violations[(a, block['block_id'], group['group_id'], 'group')]) == 1:
                                violations.append(f"Availability violation: {applicant['id']} in group {group['group_id']}")
                            if solver.Value(team_violations[(a, block['block_id'], group['group_id'], 'group')]) == 1:
                                violations.append(f"Team mismatch: {applicant['id']} in group {group['group_id']}")
        
        # Find still unscheduled applicants
        for applicant in unscheduled_applicants:
            if applicant['id'] not in scheduled_in_relaxed:
                still_unscheduled.append(applicant['id'])
    
    return relaxed_assignments, violations, still_unscheduled

def write_relaxed_output(relaxed_assignments, violations, still_unscheduled, 
                        all_applicants, output_prefix="relaxed_schedule"):
    """Write relaxed scheduling output files."""
    
    # 1. Relaxed applicant schedule
    applicant_rows = []
    for app_id, assignment in relaxed_assignments.items():
        applicant = next(a for a in all_applicants if a['id'] == app_id)
        row = {
            'applicant_id': app_id,
            'applicant_name': applicant['name'],
            'teams': ','.join(applicant['teams']) if applicant['teams'] else 'None'
        }
        
        # Individual slot info
        if 'type' in assignment and assignment['type'] == 'individual':
            row.update({
                'individual_block_id': assignment['block_id'],
                'individual_slot_id': assignment['slot_id'],
                'individual_start': assignment['slot']['start'].strftime('%Y-%m-%d %H:%M:%S'),
                'individual_end': assignment['slot']['end'].strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            row.update({
                'individual_block_id': '',
                'individual_slot_id': '',
                'individual_start': '',
                'individual_end': ''
            })
        
        # Group info
        if 'group_type' in assignment:
            row.update({
                'group_block_id': assignment['group_block_id'],
                'group_id': assignment['group_id'],
                'group_slot1_start': assignment['group']['slot1']['start'].strftime('%Y-%m-%d %H:%M:%S'),
                'group_slot1_end': assignment['group']['slot1']['end'].strftime('%Y-%m-%d %H:%M:%S'),
                'group_slot2_start': assignment['group']['slot2']['start'].strftime('%Y-%m-%d %H:%M:%S'),
                'group_slot2_end': assignment['group']['slot2']['end'].strftime('%Y-%m-%d %H:%M:%S')
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
    
    with open(f'{output_prefix}_applicants.csv', 'w', newline='') as f:
        if applicant_rows:
            writer = csv.DictWriter(f, fieldnames=applicant_rows[0].keys())
            writer.writeheader()
            writer.writerows(applicant_rows)
    
    # 2. Constraint violations
    with open(f'{output_prefix}_violations.txt', 'w') as f:
        f.write("RELAXED SCHEDULING CONSTRAINT VIOLATIONS\n")
        f.write("="*50 + "\n\n")
        if violations:
            for violation in violations:
                f.write(f"- {violation}\n")
        else:
            f.write("No constraint violations in relaxed schedule.\n")
    
    # 3. Still unscheduled applicants
    with open(f'{output_prefix}_still_unscheduled.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['applicant_id'])
        for app_id in still_unscheduled:
            writer.writerow([app_id])
    
    print(f"Relaxed scheduling output files written:")
    print(f"  - {output_prefix}_applicants.csv")
    print(f"  - {output_prefix}_violations.txt") 
    print(f"  - {output_prefix}_still_unscheduled.csv")

def main():
    parser = argparse.ArgumentParser(description='Relaxed scheduler for unscheduled applicants')
    parser.add_argument('--input-dir', default='.', help='Input directory containing CSV files')
    parser.add_argument('--unscheduled-file', default='schedule_unscheduled.csv', help='File with unscheduled applicants')
    parser.add_argument('--output', default='relaxed_schedule', help='Output file prefix')
    
    args = parser.parse_args()
    
    # Load input files
    print("Loading input files...")
    applicants = load_applicants(os.path.join(args.input_dir, 'applicant_info.csv'))
    recruiters = load_recruiters(os.path.join(args.input_dir, 'recruiters.csv'))
    blocks = load_blocks(os.path.join(args.input_dir, 'blocks.csv'))
    rooms = load_rooms(os.path.join(args.input_dir, 'rooms.csv'))
    
    # Load unscheduled applicants
    unscheduled_df = pd.read_csv(args.unscheduled_file)
    unscheduled_ids = unscheduled_df['applicant_id'].tolist()
    
    print(f"Loaded {len(applicants)} applicants, {len(unscheduled_ids)} unscheduled")
    
    if not unscheduled_ids:
        print("No unscheduled applicants to process.")
        return
    
    # Schedule recruiters (same as main scheduler)
    print("Scheduling recruiters to blocks...")
    recruiter_assignments = schedule_recruiters(recruiters, blocks, rooms)
    
    # Relaxed scheduling for unscheduled applicants
    print("Running relaxed scheduling for unscheduled applicants...")
    relaxed_assignments, violations, still_unscheduled = relaxed_schedule_applicants(
        applicants, recruiter_assignments, blocks, unscheduled_ids)
    
    print(f"Relaxed scheduling results:")
    print(f"  - {len(relaxed_assignments)} applicants scheduled in relaxed mode")
    print(f"  - {len(violations)} constraint violations")
    print(f"  - {len(still_unscheduled)} applicants still unscheduled")
    
    # Write output files
    write_relaxed_output(relaxed_assignments, violations, still_unscheduled, applicants, args.output)
    
    print("\nRelaxed scheduling complete!")

if __name__ == "__main__":
    main()
