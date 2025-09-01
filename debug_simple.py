#!/usr/bin/env python3

from ortools.sat.python import cp_model
from autoscheduler import load_recruiters, load_blocks, load_rooms, any_interval_contains, TEAMS

def debug_simple_scheduling():
    print("SIMPLE RECRUITER SCHEDULING DEBUG")
    print("=" * 50)
    
    # Load data
    recruiters = load_recruiters('recruiters.csv')
    blocks = load_blocks('blocks.csv')
    rooms = load_rooms('rooms.csv')
    
    # Try to schedule just one individual block
    individual_blocks = [b for b in blocks if b['type'] == 'individual']
    first_block = individual_blocks[0]
    
    print(f"Trying to schedule block: {first_block['block_id']}")
    print(f"Time: {first_block['start']} - {first_block['end']}")
    
    # Find available recruiters
    available_recruiters = []
    for i, recruiter in enumerate(recruiters):
        if any_interval_contains(recruiter['parsed_availability'], (first_block['start'], first_block['end'])):
            available_recruiters.append((i, recruiter))
            print(f"Recruiter {recruiter['id']} ({recruiter['team']}) is available")
    
    print(f"Total available: {len(available_recruiters)}")
    
    if len(available_recruiters) == 0:
        print("❌ No recruiters available for this block")
        return
    
    # Try simple OR-Tools model with just this block
    model = cp_model.CpModel()
    
    # Variables: one per available recruiter
    recruiter_vars = {}
    for i, (recruiter_idx, recruiter) in enumerate(available_recruiters):
        recruiter_vars[recruiter_idx] = model.NewBoolVar(f'recruiter_{recruiter_idx}')
    
    # Constraint: exactly one recruiter assigned
    model.Add(sum(recruiter_vars.values()) == 1)
    
    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    print(f"Solver status: {solver.StatusName(status)}")
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        for recruiter_idx, var in recruiter_vars.items():
            if solver.Value(var) == 1:
                recruiter = next(r for r in recruiters if recruiters.index(r) == recruiter_idx)
                print(f"✅ Assigned recruiter: {recruiter['id']} ({recruiter['team']})")
    else:
        print("❌ No solution found")

if __name__ == "__main__":
    debug_simple_scheduling()
