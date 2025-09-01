import pandas as pd
import os
from datetime import datetime
import sys

def analyze_scheduling_run(run_path):
    """Analyze a specific scheduling run and create detailed breakdown."""
    
    print(f"Analyzing scheduling run: {run_path}")
    
    # File paths
    applicants_file = os.path.join(run_path, 'schedules', 'applicants_schedule.csv')
    recruiters_file = os.path.join(run_path, 'schedules', 'recruiters_schedule.csv')
    unscheduled_file = os.path.join(run_path, 'schedules', 'unscheduled_applicants.csv')
    blocks_file = '/Users/rivajain/Documents/luma/new_luma/blocks_sept11_14.csv'
    
    # Load data
    print("Loading scheduling data...")
    applicants_df = pd.read_csv(applicants_file)
    recruiters_df = pd.read_csv(recruiters_file)
    blocks_df = pd.read_csv(blocks_file)
    
    # Load unscheduled if exists
    unscheduled_df = pd.DataFrame()
    if os.path.exists(unscheduled_file):
        unscheduled_df = pd.read_csv(unscheduled_file)
    
    print(f"Loaded {len(applicants_df)} scheduled applicants")
    print(f"Loaded {len(recruiters_df)} recruiter assignments")
    print(f"Loaded {len(unscheduled_df)} unscheduled applicants")
    print(f"Loaded {len(blocks_df)} total blocks")
    
    # Create block breakdown
    block_breakdown = {}
    
    # Initialize all blocks
    for _, block_row in blocks_df.iterrows():
        block_id = block_row['block_id']
        block_type = block_row['block_type']
        
        block_breakdown[block_id] = {
            'type': block_type,
            'date': block_row['date'],
            'start_time': block_row['start'],
            'end_time': block_row['end'],
            'room': block_row.get('room_id', 'TBD'),
            'recruiters': [],
            'individual_applicants': [],
            'group_applicants': [],
            'individual_slots': {},
            'groups': {}
        }
    
    # Add recruiter information
    for _, recruiter_row in recruiters_df.iterrows():
        block_id = recruiter_row['block_id']
        if block_id in block_breakdown:
            block_breakdown[block_id]['recruiters'].append({
                'id': recruiter_row['recruiter_id'],
                'name': recruiter_row['recruiter_name'],
                'team': recruiter_row['team'],
                'room': recruiter_row['room_id']
            })
    
    # Process applicant assignments
    for _, app_row in applicants_df.iterrows():
        app_id = app_row['applicant_id']
        app_name = app_row['applicant_name']
        teams = app_row['teams'] if pd.notna(app_row['teams']) else 'None'
        
        applicant_info = {
            'id': app_id,
            'name': app_name,
            'teams': teams
        }
        
        # Individual slot assignment
        if pd.notna(app_row['individual_block_id']):
            ind_block_id = app_row['individual_block_id']
            slot_id = app_row['individual_slot_id']
            
            if ind_block_id in block_breakdown:
                if slot_id not in block_breakdown[ind_block_id]['individual_slots']:
                    block_breakdown[ind_block_id]['individual_slots'][slot_id] = []
                
                block_breakdown[ind_block_id]['individual_slots'][slot_id].append(applicant_info)
                block_breakdown[ind_block_id]['individual_applicants'].append(applicant_info)
        
        # Group assignment
        if pd.notna(app_row['group_block_id']):
            group_block_id = app_row['group_block_id']
            group_id = app_row['group_id']
            
            if group_block_id in block_breakdown:
                if group_id not in block_breakdown[group_block_id]['groups']:
                    block_breakdown[group_block_id]['groups'][group_id] = []
                
                block_breakdown[group_block_id]['groups'][group_id].append(applicant_info)
                
                # Add to group applicants if not already there
                if not any(a['id'] == app_id for a in block_breakdown[group_block_id]['group_applicants']):
                    block_breakdown[group_block_id]['group_applicants'].append(applicant_info)
    
    # Generate output directory
    run_name = os.path.basename(run_path)
    output_file = os.path.join(run_path, f'block_breakdown_{run_name}.txt')
    csv_output_file = os.path.join(run_path, f'block_breakdown_{run_name}.csv')
    
    # Write detailed breakdown to file
    with open(output_file, 'w') as f:
        f.write(f"BLOCK BREAKDOWN ANALYSIS - {run_name.upper()}\n")
        f.write("="*80 + "\n\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Run path: {run_path}\n\n")
        
        # Overall summary
        total_blocks = len(block_breakdown)
        individual_blocks = sum(1 for b in block_breakdown.values() if b['type'] == 'individual')
        group_blocks = sum(1 for b in block_breakdown.values() if b['type'] == 'group')
        total_individual_assignments = sum(len(b['individual_applicants']) for b in block_breakdown.values())
        total_group_assignments = sum(len(b['group_applicants']) for b in block_breakdown.values())
        
        f.write(f"SUMMARY:\n")
        f.write(f"Total blocks: {total_blocks} ({individual_blocks} individual, {group_blocks} group)\n")
        f.write(f"Individual assignments: {total_individual_assignments}\n")
        f.write(f"Group assignments: {total_group_assignments}\n")
        f.write(f"Unscheduled applicants: {len(unscheduled_df)}\n\n")
        
        # Sort blocks by date and time
        sorted_blocks = sorted(block_breakdown.items(), key=lambda x: (x[1]['date'], x[1]['start_time']))
        
        for block_id, block_info in sorted_blocks:
            f.write(f"BLOCK {block_id} ({block_info['type'].upper()})\n")
            f.write("-" * 50 + "\n")
            f.write(f"Date: {block_info['date']}\n")
            f.write(f"Time: {block_info['start_time']} - {block_info['end_time']}\n")
            f.write(f"Room: {block_info['room']}\n")
            
            # Recruiters
            f.write(f"\nRECRUITERS ({len(block_info['recruiters'])}):\n")
            if block_info['recruiters']:
                for recruiter in block_info['recruiters']:
                    f.write(f"  • {recruiter['name']} ({recruiter['id']}) - {recruiter['team']} Team - Room {recruiter['room']}\n")
            else:
                f.write("  No recruiters assigned\n")
            
            # Individual slots (for individual blocks)
            if block_info['type'] == 'individual' and block_info['individual_slots']:
                f.write(f"\nINDIVIDUAL SLOTS ({len(block_info['individual_applicants'])} total):\n")
                for slot_id in sorted(block_info['individual_slots'].keys()):
                    slot_applicants = block_info['individual_slots'][slot_id]
                    f.write(f"  {slot_id}:\n")
                    for app in slot_applicants:
                        f.write(f"    • {app['name']} ({app['id']}) - Teams: {app['teams']}\n")
            elif block_info['type'] == 'individual':
                f.write(f"\nINDIVIDUAL SLOTS: No applicants assigned\n")
            
            # Groups (for group blocks)
            if block_info['type'] == 'group' and block_info['groups']:
                f.write(f"\nGROUPS ({len(block_info['group_applicants'])} total):\n")
                for group_id in sorted(block_info['groups'].keys()):
                    group_applicants = block_info['groups'][group_id]
                    f.write(f"  {group_id}:\n")
                    for app in group_applicants:
                        f.write(f"    • {app['name']} ({app['id']}) - Teams: {app['teams']}\n")
            elif block_info['type'] == 'group':
                f.write(f"\nGROUPS: No applicants assigned\n")
            
            f.write("\n" + "="*80 + "\n\n")
        
        # Day-by-day breakdown
        f.write("DAY-BY-DAY BREAKDOWN\n")
        f.write("="*50 + "\n")
        
        day_stats = {}
        for block_id, block_info in block_breakdown.items():
            date = block_info['date']
            if date not in day_stats:
                day_stats[date] = {
                    'individual_blocks': 0,
                    'group_blocks': 0,
                    'individual_assignments': 0,
                    'group_assignments': 0,
                    'recruiters': set()
                }
            
            if block_info['type'] == 'individual':
                day_stats[date]['individual_blocks'] += 1
                day_stats[date]['individual_assignments'] += len(block_info['individual_applicants'])
            else:
                day_stats[date]['group_blocks'] += 1
                day_stats[date]['group_assignments'] += len(block_info['group_applicants'])
            
            for recruiter in block_info['recruiters']:
                day_stats[date]['recruiters'].add(recruiter['id'])
        
        for date in sorted(day_stats.keys()):
            stats = day_stats[date]
            total_blocks = stats['individual_blocks'] + stats['group_blocks']
            total_assignments = stats['individual_assignments'] + stats['group_assignments']
            f.write(f"\n{date}:\n")
            f.write(f"  Blocks: {total_blocks} ({stats['individual_blocks']} individual, {stats['group_blocks']} group)\n")
            f.write(f"  Assignments: {total_assignments} ({stats['individual_assignments']} individual, {stats['group_assignments']} group)\n")
            f.write(f"  Active recruiters: {len(stats['recruiters'])}\n")
        
        # Unscheduled applicants
        if len(unscheduled_df) > 0:
            f.write(f"\n\nUNSCHEDULED APPLICANTS ({len(unscheduled_df)}):\n")
            f.write("="*50 + "\n")
            for _, unsch_row in unscheduled_df.iterrows():
                app_id = unsch_row['applicant_id']
                app_name = unsch_row.get('applicant_name', f'Applicant {app_id}')
                reason = unsch_row.get('reason', 'Unknown') if pd.notna(unsch_row.get('reason', '')) else 'Unknown'
                f.write(f"• {app_name} ({app_id}) - Reason: {reason}\n")
    
    # Create CSV summary
    csv_rows = []
    for block_id, block_info in block_breakdown.items():
        base_row = {
            'block_id': block_id,
            'block_type': block_info['type'],
            'date': block_info['date'],
            'start_time': block_info['start_time'],
            'end_time': block_info['end_time'],
            'room': block_info['room'],
            'recruiter_count': len(block_info['recruiters']),
            'recruiters': '; '.join([f"{r['name']} ({r['team']})" for r in block_info['recruiters']]),
            'individual_count': len(block_info['individual_applicants']),
            'group_count': len(block_info['group_applicants']),
            'total_applicants': len(block_info['individual_applicants']) + len(block_info['group_applicants'])
        }
        csv_rows.append(base_row)
    
    df_summary = pd.DataFrame(csv_rows)
    df_summary.to_csv(csv_output_file, index=False)
    
    print(f"\nAnalysis complete!")
    print(f"📄 Detailed breakdown: {output_file}")
    print(f"📊 CSV summary: {csv_output_file}")
    
    # Print summary to console
    print(f"\nRUN SUMMARY:")
    print(f"  📋 {total_blocks} total blocks ({individual_blocks} individual, {group_blocks} group)")
    print(f"  👥 {total_individual_assignments} individual assignments")
    print(f"  🔗 {total_group_assignments} group assignments")
    print(f"  ❌ {len(unscheduled_df)} unscheduled applicants")
    print(f"  📈 Success rate: {((total_individual_assignments + total_group_assignments) / (total_individual_assignments + total_group_assignments + len(unscheduled_df)) * 100):.1f}%")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_path = sys.argv[1]
    else:
        run_path = "/Users/rivajain/Documents/luma/new_luma/results/run_20250831_170236"
    
    analyze_scheduling_run(run_path)
