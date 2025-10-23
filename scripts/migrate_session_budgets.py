#!/usr/bin/env python3
"""
Migration Script: Initialize Budgets for Existing Sessions

This script:
1. Scans all existing sessions from llmops-sessions table
2. Creates budget records in llmops-budgets table for each session
3. Adds new fields to session records (session_name, budget_limit, etc.)
4. Calculates initial spent amounts from completed jobs

Usage:
    python scripts/migrate_session_budgets.py

Created: October 22, 2025
"""

import boto3
from datetime import datetime
from decimal import Decimal

# Configuration
DEFAULT_SESSION_BUDGET = Decimal('50.00')
REGION = 'us-east-1'

# Initialize clients
dynamodb = boto3.resource('dynamodb', region_name=REGION)
sessions_table = dynamodb.Table('llmops-sessions')
budgets_table = dynamodb.Table('llmops-budgets')
jobs_table = dynamodb.Table('llmops-jobs')


def get_all_sessions():
    """Scan all sessions from sessions table."""
    print("📋 Scanning existing sessions...")

    sessions = []
    response = sessions_table.scan()
    sessions.extend(response.get('Items', []))

    while 'LastEvaluatedKey' in response:
        response = sessions_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        sessions.extend(response.get('Items', []))

    print(f"   Found {len(sessions)} sessions")
    return sessions


def calculate_session_spent(session_id):
    """Calculate total spent for a session from completed jobs."""
    try:
        response = jobs_table.scan(
            FilterExpression='session_id = :sid',
            ExpressionAttributeValues={':sid': session_id}
        )

        jobs = response.get('Items', [])
        total_spent = sum(
            Decimal(str(job.get('cost_so_far', 0)))
            for job in jobs
            if job.get('status') in ['completed', 'failed']
        )

        return total_spent
    except Exception as e:
        print(f"   ⚠️  Error calculating spent for {session_id}: {e}")
        return Decimal('0.00')


def generate_session_name(session):
    """Generate a user-friendly session name."""
    # Try to use first user message as name
    messages = session.get('messages', [])
    if messages:
        first_message = messages[0] if isinstance(messages, list) else []
        if isinstance(first_message, dict):
            content = first_message.get('content', '')
            if content:
                # Use first 50 chars of first message
                name = content[:50].strip()
                if len(content) > 50:
                    name += "..."
                return name

    # Fallback: Use creation date
    created_at = session.get('created_at')
    if created_at:
        try:
            dt = datetime.fromtimestamp(int(created_at))
            return f"Session {dt.strftime('%b %d, %Y')}"
        except:
            pass

    # Final fallback
    return f"Session {session.get('session_id', 'Unknown')[:8]}"


def create_session_budget(session_id, session_name, spent=Decimal('0.00'), limit=DEFAULT_SESSION_BUDGET):
    """Create a budget record for a session."""
    now = int(datetime.utcnow().timestamp())
    now_iso = datetime.utcnow().isoformat() + 'Z'

    remaining = limit - spent

    budget_item = {
        'id': session_id,
        'type': 'session',
        'session_id': session_id,
        'session_name': session_name,
        'limit': limit,
        'spent': spent,
        'remaining': remaining,
        'created_at': now,
        'updated_at': now,
        'updated_at_iso': now_iso
    }

    try:
        budgets_table.put_item(Item=budget_item)
        return True
    except Exception as e:
        print(f"   ❌ Failed to create budget for {session_id}: {e}")
        return False


def update_session_metadata(session_id, session_name, budget_limit=DEFAULT_SESSION_BUDGET):
    """Add new metadata fields to session record."""
    now = int(datetime.utcnow().timestamp())
    now_iso = datetime.utcnow().isoformat() + 'Z'

    try:
        sessions_table.update_item(
            Key={'session_id': session_id},
            UpdateExpression='SET session_name = :name, budget_limit = :limit, is_archived = :archived, updated_at = :updated, updated_at_iso = :updated_iso',
            ExpressionAttributeValues={
                ':name': session_name,
                ':limit': budget_limit,
                ':archived': False,
                ':updated': now,
                ':updated_iso': now_iso
            }
        )
        return True
    except Exception as e:
        print(f"   ⚠️  Failed to update session metadata for {session_id}: {e}")
        return False


def migrate_session(session):
    """Migrate a single session: create budget + update metadata."""
    session_id = session.get('session_id')
    print(f"\n🔄 Migrating session: {session_id}")

    # Generate session name
    session_name = generate_session_name(session)
    print(f"   Name: {session_name}")

    # Calculate spent amount from jobs
    spent = calculate_session_spent(session_id)
    print(f"   Spent: ${float(spent):.2f}")

    # Create budget record
    budget_created = create_session_budget(session_id, session_name, spent=spent)
    if budget_created:
        print(f"   ✅ Budget record created")

    # Update session metadata
    metadata_updated = update_session_metadata(session_id, session_name)
    if metadata_updated:
        print(f"   ✅ Session metadata updated")

    return budget_created and metadata_updated


def calculate_global_spent():
    """Calculate total global spent from all session budgets."""
    print("\n💰 Calculating global spent...")

    response = budgets_table.scan(
        FilterExpression='#type = :type',
        ExpressionAttributeNames={'#type': 'type'},
        ExpressionAttributeValues={':type': 'session'}
    )

    session_budgets = response.get('Items', [])

    total_spent = sum(
        Decimal(str(budget.get('spent', 0)))
        for budget in session_budgets
    )

    print(f"   Total spent across all sessions: ${float(total_spent):.2f}")
    return total_spent


def update_global_budget(spent):
    """Update global budget with calculated spent amount."""
    print("\n🌍 Updating global budget...")

    try:
        # Get current global budget limit
        response = budgets_table.get_item(Key={'id': 'global'})
        global_budget = response.get('Item', {})
        limit = Decimal(str(global_budget.get('limit', 500)))

        remaining = limit - spent
        now = int(datetime.utcnow().timestamp())
        now_iso = datetime.utcnow().isoformat() + 'Z'

        budgets_table.update_item(
            Key={'id': 'global'},
            UpdateExpression='SET spent = :spent, remaining = :remaining, updated_at = :updated, updated_at_iso = :updated_iso',
            ExpressionAttributeValues={
                ':spent': spent,
                ':remaining': remaining,
                ':updated': now,
                ':updated_iso': now_iso
            }
        )

        print(f"   ✅ Global budget updated")
        print(f"      Limit: ${float(limit):.2f}")
        print(f"      Spent: ${float(spent):.2f}")
        print(f"      Remaining: ${float(remaining):.2f}")
        return True
    except Exception as e:
        print(f"   ❌ Failed to update global budget: {e}")
        return False


def main():
    """Main migration function."""
    print("=" * 70)
    print("SESSION BUDGET MIGRATION")
    print("=" * 70)

    # Get all sessions
    sessions = get_all_sessions()

    if not sessions:
        print("\n⚠️  No sessions found to migrate")
        return

    # Migrate each session
    print(f"\n🚀 Migrating {len(sessions)} sessions...")

    success_count = 0
    for session in sessions:
        if migrate_session(session):
            success_count += 1

    print(f"\n✅ Successfully migrated {success_count}/{len(sessions)} sessions")

    # Calculate and update global spent
    global_spent = calculate_global_spent()
    update_global_budget(global_spent)

    print("\n" + "=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)
    print(f"✅ {success_count} sessions migrated")
    print(f"💰 Global spent: ${float(global_spent):.2f}")
    print("=" * 70)


if __name__ == '__main__':
    main()
