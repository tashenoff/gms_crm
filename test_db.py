import sqlite3

# Connect to database
conn = sqlite3.connect('crm.db')
cursor = conn.cursor()

# Check if leads table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='leads'")
if cursor.fetchone():
    print("Table 'leads' exists")
    
    # Get all leads
    cursor.execute("SELECT * FROM leads ORDER BY created_at DESC")
    leads = cursor.fetchall()
    print(f"Found {len(leads)} leads")
    
    # Print first lead
    if leads:
        lead = leads[0]
        print(f"First lead: {lead}")
else:
    print("Table 'leads' does not exist")

conn.close()
