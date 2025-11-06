#!/usr/bin/env python3
"""
Cleanup script to remove test sessions from the database.

This script deletes all sessions whose names start with "Session test-".
Run this script when you want to clean up sessions created during testing.

Usage:
    python cleanup_test_sessions.py [--yes]

Options:
    --yes    Skip confirmation prompt and delete immediately
"""

import sys
import db
import config

def cleanup_test_sessions(auto_confirm=False):
    """Delete all sessions that start with 'Session test-'"""
    # Get all sessions
    all_sessions = db.get_all_session_metadata()

    # Filter sessions that start with "Session test-"
    test_sessions = [s for s in all_sessions if s["name"].startswith("Session test-")]

    if not test_sessions:
        print("✓ No test sessions found. Database is clean!")
        return

    print(f"Found {len(test_sessions)} test session(s) to delete:")
    for session in test_sessions:
        print(f"  - {session['name']} ({session['session_id']}) - {session['message_count']} messages")

    # Ask for confirmation (unless auto-confirmed)
    if not auto_confirm:
        response = input("\nDelete these sessions? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled. No sessions were deleted.")
            return
    else:
        print("\nAuto-confirmed with --yes flag. Proceeding with deletion...")

    # Delete each test session
    deleted_count = 0
    for session in test_sessions:
        session_id = session['session_id']

        # Skip the default session (just in case)
        if session_id == config.DEFAULT_SESSION_ID:
            print(f"⚠️  Skipping default session: {session['name']}")
            continue

        db.delete_session(session_id)
        deleted_count += 1
        print(f"✓ Deleted: {session['name']}")

    print(f"\n✓ Cleanup complete! Deleted {deleted_count} test session(s).")

    # Fix message counts for remaining sessions
    print("\nVerifying message counts for remaining sessions...")
    remaining_sessions = db.get_all_session_metadata()
    fixed_count = 0

    for session in remaining_sessions:
        session_id = session['session_id']
        old_count = session['message_count']

        # Get actual message count
        actual_messages = db.get_conversation(session_id)
        actual_count = len(actual_messages)

        if old_count != actual_count:
            db.update_session_message_count(session_id)
            fixed_count += 1
            print(f"  ✓ Fixed count for '{session['name']}': {old_count} → {actual_count}")

    if fixed_count > 0:
        print(f"\n✓ Fixed message counts for {fixed_count} session(s).")
    else:
        print("  ✓ All message counts are accurate.")

if __name__ == "__main__":
    # Check for --yes flag
    auto_confirm = "--yes" in sys.argv or "-y" in sys.argv
    cleanup_test_sessions(auto_confirm)
