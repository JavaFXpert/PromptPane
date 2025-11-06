#!/usr/bin/env python3
"""
Utility script to verify and fix message counts for all sessions.

This script checks all sessions and updates their cached message_count
field to match the actual number of messages in the database.

Usage:
    python fix_message_counts.py
"""

import db

def fix_message_counts():
    """Verify and fix message counts for all sessions"""
    # Get all sessions
    all_sessions = db.get_all_session_metadata()

    if not all_sessions:
        print("No sessions found in database.")
        return

    print(f"Checking message counts for {len(all_sessions)} session(s)...\n")

    fixed_count = 0
    correct_count = 0

    for session in all_sessions:
        session_id = session['session_id']
        session_name = session['name']
        old_count = session['message_count']

        # Get actual message count
        actual_messages = db.get_conversation(session_id)
        actual_count = len(actual_messages)

        if old_count != actual_count:
            # Count is incorrect, fix it
            db.update_session_message_count(session_id)
            fixed_count += 1
            print(f"✓ Fixed: '{session_name}' ({session_id[:12]}...)")
            print(f"  Cached count: {old_count}")
            print(f"  Actual count: {actual_count}")
            print()
        else:
            correct_count += 1

    # Summary
    print("=" * 50)
    if fixed_count > 0:
        print(f"✓ Fixed message counts for {fixed_count} session(s).")
    else:
        print("✓ All message counts are accurate!")

    print(f"  - Correct: {correct_count}")
    print(f"  - Fixed: {fixed_count}")
    print(f"  - Total: {len(all_sessions)}")

if __name__ == "__main__":
    fix_message_counts()
