import pandas as pd
import argparse
import os

def combine_schedules():
    """Combine regular and relaxed scheduling results into final comprehensive schedule."""
    
    # Load regular scheduling results
    print("Loading regular scheduling results...")
    regular_applicants = pd.read_csv('schedule_applicants.csv')
    print(f"Regular schedule: {len(regular_applicants)} applicants")
    
    # Load relaxed scheduling results
    print("Loading relaxed scheduling results...")
    relaxed_applicants = pd.read_csv('relaxed_schedule_new_applicants.csv')
    print(f"Relaxed schedule: {len(relaxed_applicants)} applicants")
    
    # Combine the two schedules
    combined_applicants = pd.concat([regular_applicants, relaxed_applicants], ignore_index=True)
    
    # Sort by applicant_id for easier reading
    combined_applicants = combined_applicants.sort_values('applicant_id')
    
    # Add a column to indicate scheduling mode
    combined_applicants['scheduling_mode'] = ['regular'] * len(regular_applicants) + ['relaxed'] * len(relaxed_applicants)
    
    # Save combined schedule
    combined_applicants.to_csv('schedule_final_combined.csv', index=False)
    print(f"Combined schedule saved: {len(combined_applicants)} total applicants")
    
    # Load constraint violations
    print("\nProcessing constraint violations...")
    
    # Regular violations (if any)
    regular_violations = []
    if os.path.exists('schedule_violations.txt'):
        with open('schedule_violations.txt', 'r') as f:
            content = f.read()
            if content.strip():
                regular_violations = content.strip().split('\n')
    
    # Relaxed violations
    relaxed_violations = []
    with open('relaxed_schedule_new_violations.txt', 'r') as f:
        content = f.read()
        # Skip the header lines
        lines = content.strip().split('\n')
        for line in lines:
            if line.strip() and line.startswith('- '):
                relaxed_violations.append(line[2:])  # Remove "- " prefix
    
    # Write combined violations report
    with open('schedule_final_violations.txt', 'w') as f:
        f.write("COMPREHENSIVE SCHEDULING VIOLATIONS REPORT\n")
        f.write("="*50 + "\n\n")
        
        f.write(f"REGULAR SCHEDULING VIOLATIONS ({len(regular_violations)}):\n")
        f.write("-" * 30 + "\n")
        if regular_violations:
            for violation in regular_violations:
                f.write(f"- {violation}\n")
        else:
            f.write("No violations in regular scheduling.\n")
        
        f.write(f"\nRELAXED SCHEDULING VIOLATIONS ({len(relaxed_violations)}):\n")
        f.write("-" * 30 + "\n")
        for violation in relaxed_violations:
            f.write(f"- {violation}\n")
        
        f.write(f"\nTOTAL VIOLATIONS: {len(regular_violations) + len(relaxed_violations)}\n")
    
    # Generate summary statistics
    print("\nGenerating summary statistics...")
    
    # Count applicants by scheduling mode
    regular_count = len(regular_applicants)
    relaxed_count = len(relaxed_applicants)
    total_count = regular_count + relaxed_count
    
    # Count individual vs group assignments
    individual_assignments = len(combined_applicants[combined_applicants['individual_slot_id'] != ''])
    group_assignments = len(combined_applicants[combined_applicants['group_id'] != ''])
    both_assignments = len(combined_applicants[
        (combined_applicants['individual_slot_id'] != '') & 
        (combined_applicants['group_id'] != '')
    ])
    
    # Team distribution
    team_stats = {}
    for _, row in combined_applicants.iterrows():
        teams = str(row['teams']).split(',') if pd.notna(row['teams']) and row['teams'] != 'None' else ['None']
        for team in teams:
            team = team.strip()
            if team not in team_stats:
                team_stats[team] = 0
            team_stats[team] += 1
    
    # Write summary report
    with open('schedule_final_summary.txt', 'w') as f:
        f.write("COMPREHENSIVE SCHEDULING SUMMARY\n")
        f.write("="*50 + "\n\n")
        
        f.write("OVERALL STATISTICS:\n")
        f.write(f"  Total applicants scheduled: {total_count}\n")
        f.write(f"  Regular scheduling: {regular_count} ({regular_count/total_count*100:.1f}%)\n")
        f.write(f"  Relaxed scheduling: {relaxed_count} ({relaxed_count/total_count*100:.1f}%)\n")
        f.write(f"  Overall success rate: {total_count}/154 ({total_count/154*100:.1f}%)\n\n")
        
        f.write("INTERVIEW TYPE DISTRIBUTION:\n")
        f.write(f"  Individual interviews: {individual_assignments}\n")
        f.write(f"  Group interviews: {group_assignments}\n")
        f.write(f"  Both individual and group: {both_assignments}\n\n")
        
        f.write("TEAM PREFERENCE DISTRIBUTION:\n")
        for team, count in sorted(team_stats.items()):
            f.write(f"  {team}: {count} applicants\n")
        
        f.write(f"\nCONSTRAINT VIOLATIONS:\n")
        f.write(f"  Regular scheduling: {len(regular_violations)} violations\n")
        f.write(f"  Relaxed scheduling: {len(relaxed_violations)} violations\n")
        f.write(f"  Total violations: {len(regular_violations) + len(relaxed_violations)} violations\n")
        
        if len(relaxed_violations) > 0:
            f.write(f"\nNOTE: Relaxed scheduling violations are expected as constraints\n")
            f.write(f"were deliberately relaxed to accommodate more applicants.\n")
    
    print(f"\nFinal Results Summary:")
    print(f"  📊 Total scheduled: {total_count}/154 ({total_count/154*100:.1f}%)")
    print(f"  ✅ Regular: {regular_count} applicants")
    print(f"  🔄 Relaxed: {relaxed_count} applicants")
    print(f"  ⚠️  Total violations: {len(regular_violations) + len(relaxed_violations)}")
    
    print(f"\nOutput files generated:")
    print(f"  📄 schedule_final_combined.csv - All applicant assignments")
    print(f"  📄 schedule_final_violations.txt - Comprehensive violation report")
    print(f"  📄 schedule_final_summary.txt - Summary statistics")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Combine regular and relaxed scheduling results')
    args = parser.parse_args()
    
    combine_schedules()
