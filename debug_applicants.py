import pandas as pd

# Test the team parsing function
def parse_team_preferences(team_str: str):
    """Extract team preferences from the teams string."""
    TEAMS = ['Astra', 'Juvo', 'Infinitum', 'Terra']
    teams = set()
    if pd.isna(team_str) or not team_str:
        return teams
    
    print(f"Parsing team string: '{team_str}'")
    
    # Map full team names to short codes
    for team in TEAMS:
        if team in team_str:
            teams.add(team)
            print(f"Found team: {team}")
    
    return teams

# Load and test first few applicants
df = pd.read_csv('applicant_info.csv')
print(f"Loaded {len(df)} rows from CSV")
print(f"Columns: {list(df.columns)}")

print("\nFirst 3 applicants:")
for i, (idx, row) in enumerate(df.iterrows()):
    if i >= 3:
        break
        
    email = row['Timestamp']  # Actual email is in Timestamp column
    name = row['Email Address']  # Actual name is in Email Address column
    team_col = row.get('What year are you?', '')  # Teams are in this column
    
    print(f"\nApplicant {i+1}:")
    print(f"  Email: {email}")
    print(f"  Name: {name}")
    print(f"  Team column: '{team_col}'")
    
    teams = parse_team_preferences(team_col)
    print(f"  Parsed teams: {teams}")
