"""
Check current session ID state in the database.
"""
from app.database import get_db
from app.models.task import Task
from app.models.interaction import ClaudeInteraction
from app.models.session import Session


def check_current_session_ids():
    """Check the current state of session IDs in the database."""
    db = next(get_db())

    try:
        print("=== CHECKING SESSION ID CONSISTENCY ===\n")

        # Check all tasks
        tasks = db.query(Task).all()
        print(f"Total tasks in database: {len(tasks)}")

        # Check sessions first
        sessions = db.query(Session).all()
        print(f"Total sessions in database: {len(sessions)}")

        # Group tasks by session ID
        session_groups = {}
        tasks_without_session = []

        for task in tasks:
            if task.session_id:
                if task.session_id not in session_groups:
                    session_groups[task.session_id] = []
                session_groups[task.session_id].append(task)
            else:
                tasks_without_session.append(task)

        print(f"Tasks without session_id: {len(tasks_without_session)}")
        if tasks_without_session:
            print("Tasks missing session_id:")
            for task in tasks_without_session:
                print(f"  - Task {task.id}: {task.task_name} (status: {task.status})")

        print(f"\nUnique session IDs in tasks: {len(session_groups)}")

        # Show session groups with session details
        for session_id, task_list in session_groups.items():
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                print(f"\nSession ID: {session_id}")
                print(f"  Project path: {session.project_path}")
                print(f"  Created: {session.created_at}")
                print(f"  Tasks in this session:")
                for task in task_list:
                    print(f"    - Task {task.id}: {task.task_name} (status: {task.status})")
            else:
                print(f"\nOrphaned Session ID: {session_id} (no session record found)")
                for task in task_list:
                    print(f"  - Task {task.id}: {task.task_name} (status: {task.status})")

        # Check interactions (ClaudeInteraction doesn't have session_id field currently)
        print("\n=== CHECKING INTERACTIONS ===")
        interactions = db.query(ClaudeInteraction).all()
        print(f"Total interactions: {len(interactions)}")

        # Group interactions by task
        task_interaction_counts = {}
        for interaction in interactions:
            if interaction.task_id not in task_interaction_counts:
                task_interaction_counts[interaction.task_id] = 0
            task_interaction_counts[interaction.task_id] += 1

        print(f"Tasks with interactions: {len(task_interaction_counts)}")
        for task_id, count in task_interaction_counts.items():
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                print(f"  - Task {task_id} ({task.task_name}): {count} interactions (session: {task.session_id})")
            else:
                print(f"  - Orphaned interactions for deleted task {task_id}: {count}")

        # Check Claude session ID consistency
        print("\n=== CHECKING CLAUDE SESSION IDs ===")
        tasks_with_claude_session = db.query(Task).filter(Task.claude_session_id.isnot(None)).all()
        print(f"Tasks with Claude session ID: {len(tasks_with_claude_session)}")

        claude_session_groups = {}
        for task in tasks_with_claude_session:
            claude_sid = task.claude_session_id
            if claude_sid not in claude_session_groups:
                claude_session_groups[claude_sid] = []
            claude_session_groups[claude_sid].append(task)

        print(f"Unique Claude session IDs: {len(claude_session_groups)}")

        # Show Claude session sharing (potential issues)
        shared_claude_sessions = []
        for claude_sid, task_list in claude_session_groups.items():
            if len(task_list) > 1:
                shared_claude_sessions.append((claude_sid, task_list))
                print(f"\nClaude Session ID: {claude_sid} (SHARED by {len(task_list)} tasks)")
                for task in task_list:
                    print(f"  - Task {task.id}: {task.task_name} (DB session: {task.session_id}, status: {task.status})")
            else:
                print(f"\nClaude Session ID: {claude_sid}")
                task = task_list[0]
                print(f"  - Task {task.id}: {task.task_name} (DB session: {task.session_id}, status: {task.status})")

        if shared_claude_sessions:
            print(f"\n⚠️  WARNING: Found {len(shared_claude_sessions)} shared Claude session IDs!")
            print("This could cause conversation conflicts between tasks.")
        else:
            print("\n✓ No shared Claude session IDs found")

        # Check for orphaned sessions (sessions without tasks)
        print("\n=== CHECKING ORPHANED SESSIONS ===")
        used_session_ids = set(session_groups.keys())
        all_session_ids = {session.id for session in sessions}
        orphaned_sessions = all_session_ids - used_session_ids

        if orphaned_sessions:
            print(f"Found {len(orphaned_sessions)} orphaned sessions (no tasks):")
            for session_id in orphaned_sessions:
                session = db.query(Session).filter(Session.id == session_id).first()
                if session:
                    print(f"  - Session {session_id}: {session.project_path} (created: {session.created_at})")
        else:
            print("✓ No orphaned sessions found")

        print("\n=== SUMMARY ===")
        total_issues = len(tasks_without_session) + len(shared_claude_sessions)
        if total_issues == 0:
            print("✅ All session ID consistency checks passed!")
        else:
            print(f"❌ Found {total_issues} session ID consistency issues:")
            if tasks_without_session:
                print(f"  - {len(tasks_without_session)} tasks missing session_id")
            if shared_claude_sessions:
                print(f"  - {len(shared_claude_sessions)} shared Claude session IDs")

        print(f"\nSession Statistics:")
        print(f"- Total sessions: {len(sessions)}")
        print(f"- Sessions with tasks: {len(session_groups)}")
        print(f"- Orphaned sessions: {len(orphaned_sessions) if 'orphaned_sessions' in locals() else 0}")
        print(f"- Total tasks: {len(tasks)}")
        print(f"- Tasks with valid session_id: {len(tasks) - len(tasks_without_session)}")
        print(f"- Total interactions: {len(interactions)}")

    finally:
        db.close()


if __name__ == "__main__":
    check_current_session_ids()