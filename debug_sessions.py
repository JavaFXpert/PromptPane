"""
Debug script to show all sessions in the database
"""

import db

print("=" * 60)
print("ALL SESSIONS IN DATABASE")
print("=" * 60)

sessions = db.get_all_session_metadata()

if not sessions:
    print("No sessions found.")
else:
    for session in sessions:
        print(f"\nSession ID: {session['session_id']}")
        print(f"  Name: {session['name']}")
        print(f"  Icon: {session['icon']}")
        print(f"  Created: {session['created_at']}")
        print(f"  Last Accessed: {session['last_accessed']}")
        print(f"  Message Count: {session['message_count']}")

print(f"\nTotal: {len(sessions)} sessions")
print("=" * 60)
