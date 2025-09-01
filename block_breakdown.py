import pandas as pd
import os
from datetime import datetime

def create_block_breakdown():
    """Create a comprehensive breakdown showing who is in each block for both regular and relaxed scheduling."""
    
    print("Loading scheduling data...")
    
    # Load the combined schedule
    combined_schedule = pd.read_csv('schedule_final_combined.csv')
    
    # Load recruiter assignments
    recruiter_schedule = pd.read_csv('schedule_recruiters.csv')
    
    # Load block information
    blocks_df = pd.read_csv('blocks.csv')
    
    print(f"Loaded {len(combined_schedule)} applicant assignments")
    print(f"Loaded {len(recruiter_schedule)} recruiter assignments")
    
    # Create block breakdown
    block_breakdown = {}
    
    # Process each block
    for _, block_row in blocks_df.iterrows():
        block_id = block_row['block_id']
        block_type = block_row['block_type']
        
        block_breakdown[block_id] = {
            'type': block_type,
            'start_time': f"{block_row['date']} {block_row['start']}:00",
            'end_time': f"{block_row['date']} {block_row['end']}:00",
            'recruiters': [],
            'regular_applicants': [],
            'relaxed_applicants': [],
            'individual_slots': {},
            'groups': {}
        }
    
    # Add recruiter information
    for _, recruiter_row in recruiter_schedule.iterrows():
        block_id = recruiter_row['block_id']
        if block_id in block_breakdown:
            block_breakdown[block_id]['recruiters'].append({
                'id': recruiter_row['recruiter_id'],
                'name': recruiter_row['recruiter_name'],
                'team': recruiter_row['team'],
                'room': recruiter_row['room_id']
            })
    
    # Process applicant assignments
    for _, app_row in combined_schedule.iterrows():
        app_id = app_row['applicant_id']
        app_name = app_row['applicant_name']
        teams = app_row['teams']
        scheduling_mode = app_row['scheduling_mode']
        
        applicant_info = {
            'id': app_id,
            'name': app_name,
            'teams': teams,
            'mode': scheduling_mode
        }
        
        # Individual slot assignment
        if pd.notna(app_row['individual_block_id']) and app_row['individual_block_id'] != '':
            ind_block_id = app_row['individual_block_id']
            slot_id = app_row['individual_slot_id']
            
            if ind_block_id in block_breakdown:
                if slot_id not in block_breakdown[ind_block_id]['individual_slots']:
                    block_breakdown[ind_block_id]['individual_slots'][slot_id] = []
                
                block_breakdown[ind_block_id]['individual_slots'][slot_id].append(applicant_info)
                
                # Add to overall applicant list
                if scheduling_mode == 'regular':
                    block_breakdown[ind_block_id]['regular_applicants'].append(applicant_info)
                else:
                    block_breakdown[ind_block_id]['relaxed_applicants'].append(applicant_info)
        
        # Group assignment
        if pd.notna(app_row['group_block_id']) and app_row['group_block_id'] != '':
            group_block_id = app_row['group_block_id']
            group_id = app_row['group_id']
            
            if group_block_id in block_breakdown:
                if group_id not in block_breakdown[group_block_id]['groups']:
                    block_breakdown[group_block_id]['groups'][group_id] = []
                
                block_breakdown[group_block_id]['groups'][group_id].append(applicant_info)
                
                # Add to overall applicant list if not already added from individual
                found_in_regular = any(a['id'] == app_id for a in block_breakdown[group_block_id]['regular_applicants'])
                found_in_relaxed = any(a['id'] == app_id for a in block_breakdown[group_block_id]['relaxed_applicants'])
                
                if not found_in_regular and not found_in_relaxed:
                    if scheduling_mode == 'regular':
                        block_breakdown[group_block_id]['regular_applicants'].append(applicant_info)
                    else:
                        block_breakdown[group_block_id]['relaxed_applicants'].append(applicant_info)
    
    # Write detailed breakdown to file
    with open('schedule_block_breakdown.txt', 'w') as f:
        f.write("COMPREHENSIVE BLOCK BREAKDOWN - REGULAR AND RELAXED SCHEDULING\n")
        f.write("="*80 + "\n\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Sort blocks by ID for consistent output
        sorted_blocks = sorted(block_breakdown.items())
        
        for block_id, block_info in sorted_blocks:
            f.write(f"BLOCK {block_id} ({block_info['type'].upper()})\n")
            f.write("-" * 50 + "\n")
            f.write(f"Time: {block_info['start_time']} - {block_info['end_time']}\n")
            
            # Recruiters
            f.write(f"\nRECRUITERS ({len(block_info['recruiters'])}):\n")
            if block_info['recruiters']:
                for recruiter in block_info['recruiters']:
                    f.write(f"  • {recruiter['name']} ({recruiter['id']}) - {recruiter['team']} Team - Room {recruiter['room']}\n")
            else:
                f.write("  No recruiters assigned\n")
            
            # Summary counts
            regular_count = len(block_info['regular_applicants'])
            relaxed_count = len(block_info['relaxed_applicants'])
            total_count = regular_count + relaxed_count
            
            f.write(f"\nAPPLICANT SUMMARY:\n")
            f.write(f"  Regular scheduling: {regular_count} applicants\n")
            f.write(f"  Relaxed scheduling: {relaxed_count} applicants\n")
            f.write(f"  Total applicants: {total_count} applicants\n")
            
            # Individual slots breakdown
            if block_info['type'] == 'individual' and block_info['individual_slots']:
                f.write(f"\nINDIVIDUAL SLOTS:\n")
                for slot_id in sorted(block_info['individual_slots'].keys()):
                    slot_applicants = block_info['individual_slots'][slot_id]
                    f.write(f"  {slot_id}:\n")
                    for app in slot_applicants:
                        mode_symbol = "✓" if app['mode'] == 'regular' else "⚠"
                        f.write(f"    {mode_symbol} {app['name']} ({app['id']}) - Teams: {app['teams']}\n")
            
            # Group breakdown
            if block_info['type'] == 'group' and block_info['groups']:
                f.write(f"\nGROUPS:\n")
                for group_id in sorted(block_info['groups'].keys()):
                    group_applicants = block_info['groups'][group_id]
                    f.write(f"  {group_id}:\n")
                    for app in group_applicants:
                        mode_symbol = "✓" if app['mode'] == 'regular' else "⚠"
                        f.write(f"    {mode_symbol} {app['name']} ({app['id']}) - Teams: {app['teams']}\n")
            
            # All applicants in block (sorted by scheduling mode)
            f.write(f"\nALL APPLICANTS IN BLOCK:\n")
            f.write(f"  Regular Scheduling ({regular_count}):\n")
            for app in sorted(block_info['regular_applicants'], key=lambda x: x['name']):
                f.write(f"    ✓ {app['name']} ({app['id']}) - Teams: {app['teams']}\n")
            
            f.write(f"  Relaxed Scheduling ({relaxed_count}):\n")
            for app in sorted(block_info['relaxed_applicants'], key=lambda x: x['name']):
                f.write(f"    ⚠ {app['name']} ({app['id']}) - Teams: {app['teams']}\n")
            
            f.write("\n" + "="*80 + "\n\n")
        
        # Overall statistics
        f.write("OVERALL STATISTICS\n")
        f.write("="*50 + "\n")
        
        total_regular = sum(len(block['regular_applicants']) for block in block_breakdown.values())
        total_relaxed = sum(len(block['relaxed_applicants']) for block in block_breakdown.values())
        
        f.write(f"Total blocks: {len(block_breakdown)}\n")
        f.write(f"Individual blocks: {sum(1 for b in block_breakdown.values() if b['type'] == 'individual')}\n")
        f.write(f"Group blocks: {sum(1 for b in block_breakdown.values() if b['type'] == 'group')}\n")
        f.write(f"Total regular assignments: {total_regular}\n")
        f.write(f"Total relaxed assignments: {total_relaxed}\n")
        f.write(f"Grand total assignments: {total_regular + total_relaxed}\n")
        
        # Legend
        f.write(f"\nLEGEND:\n")
        f.write(f"✓ = Regular scheduling (strict constraints)\n")
        f.write(f"⚠ = Relaxed scheduling (with constraint violations)\n")
    
    # Create a CSV version for easier analysis
    csv_rows = []
    for block_id, block_info in block_breakdown.items():
        base_row = {
            'block_id': block_id,
            'block_type': block_info['type'],
            'start_time': block_info['start_time'],
            'end_time': block_info['end_time'],
            'recruiter_count': len(block_info['recruiters']),
            'recruiters': '; '.join([f"{r['name']} ({r['team']})" for r in block_info['recruiters']]),
            'regular_count': len(block_info['regular_applicants']),
            'relaxed_count': len(block_info['relaxed_applicants']),
            'total_count': len(block_info['regular_applicants']) + len(block_info['relaxed_applicants'])
        }
        
        # Add individual slot details
        if block_info['type'] == 'individual':
            for slot_id, slot_apps in block_info['individual_slots'].items():
                row = base_row.copy()
                row.update({
                    'slot_id': slot_id,
                    'slot_applicants': '; '.join([f"{a['name']} ({a['mode']})" for a in slot_apps]),
                    'slot_count': len(slot_apps)
                })
                csv_rows.append(row)
        else:
            # Group blocks
            for group_id, group_apps in block_info['groups'].items():
                row = base_row.copy()
                row.update({
                    'group_id': group_id,
                    'group_applicants': '; '.join([f"{a['name']} ({a['mode']})" for a in group_apps]),
                    'group_count': len(group_apps)
                })
                csv_rows.append(row)
        
        # Also add a summary row if no slots/groups were added
        if not csv_rows or csv_rows[-1]['block_id'] != block_id:
            csv_rows.append(base_row)
    
    # Write CSV
    if csv_rows:
        df = pd.DataFrame(csv_rows)
        df.to_csv('schedule_block_breakdown.csv', index=False)
    
    print(f"\nBlock breakdown files created:")
    print(f"  📄 schedule_block_breakdown.txt - Detailed text breakdown")
    print(f"  📄 schedule_block_breakdown.csv - Structured data breakdown")
    
    # Print summary
    print(f"\nBreakdown Summary:")
    individual_blocks = sum(1 for b in block_breakdown.values() if b['type'] == 'individual')
    group_blocks = sum(1 for b in block_breakdown.values() if b['type'] == 'group')
    total_regular = sum(len(block['regular_applicants']) for block in block_breakdown.values())
    total_relaxed = sum(len(block['relaxed_applicants']) for block in block_breakdown.values())
    
    print(f"  📊 {len(block_breakdown)} total blocks ({individual_blocks} individual, {group_blocks} group)")
    print(f"  ✅ {total_regular} regular scheduling assignments")
    print(f"  ⚠️  {total_relaxed} relaxed scheduling assignments")
    print(f"  🎯 {total_regular + total_relaxed} total assignments")

if __name__ == "__main__":
    create_block_breakdown()
