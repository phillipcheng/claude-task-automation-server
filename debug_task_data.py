#!/usr/bin/env python3

import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = "mysql+pymysql://root:sitebuilder@localhost/claudesys"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def debug_task_data():
    db = SessionLocal()
    try:
        # Query for the specific task
        result = db.execute(
            text("SELECT task_name, projects, project_context FROM tasks WHERE task_name = :task_name"),
            {"task_name": "add_scene_event_codes_to_stra"}
        ).fetchone()

        if result:
            task_name, projects_data, project_context = result
            print(f"Task found: {task_name}")
            print(f"Raw projects data: {repr(projects_data)}")
            print(f"Raw project_context: {repr(project_context)}")

            if projects_data:
                try:
                    projects_parsed = json.loads(projects_data) if isinstance(projects_data, str) else projects_data
                    print(f"Parsed projects: {json.dumps(projects_parsed, indent=2)}")
                    print(f"Number of projects: {len(projects_parsed) if isinstance(projects_parsed, list) else 'not a list'}")
                except Exception as e:
                    print(f"Error parsing projects data: {e}")
            else:
                print("Projects data is NULL/empty")
        else:
            print("Task not found")

        # Show all tasks for context
        print("\nAll tasks in database:")
        all_tasks = db.execute(text("SELECT task_name, projects IS NOT NULL as has_projects FROM tasks")).fetchall()
        for task_name, has_projects in all_tasks:
            print(f"  {task_name}: has_projects={has_projects}")

    except Exception as e:
        print(f"Database error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    debug_task_data()