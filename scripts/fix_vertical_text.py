#!/usr/bin/env python3
"""
Fix vertical text issue in tool_result interactions.

The bug was that tool result content was being joined with '\n' instead of '',
causing each character to appear on a separate line.

This script fixes existing data in the database.
"""

import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.interaction import ClaudeInteraction, InteractionType
from app.database import DATABASE_URL

def fix_vertical_text():
    """Fix vertical text in tool_result interactions."""

    # Create database connection
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Find all tool_result interactions with vertical text pattern
        tool_results = db.query(ClaudeInteraction).filter(
            ClaudeInteraction.interaction_type == InteractionType.TOOL_RESULT
        ).all()

        fixed_count = 0

        for interaction in tool_results:
            content = interaction.content

            # Check if content has the vertical text pattern (many single chars separated by newlines)
            # Look for pattern like "T\no\no\nl\n" where single chars are separated by newlines
            lines = content.split('\n')

            # Detect vertical text: if we have many lines where most are single characters
            single_char_lines = [line for line in lines if len(line.strip()) == 1]

            # If more than 50% of lines are single characters and we have >10 lines, it's likely vertical
            if len(lines) > 10 and len(single_char_lines) > len(lines) * 0.5:
                print(f"Fixing interaction {interaction.id}: {len(lines)} lines, {len(single_char_lines)} single chars")

                # Reconstruct the content by joining single-char lines without newlines
                # But preserve intentional line breaks (lines with multiple chars)
                fixed_content = ""
                i = 0
                while i < len(lines):
                    line = lines[i].strip()

                    if len(line) == 1:
                        # Start collecting single characters
                        chars = [line]
                        i += 1

                        # Collect consecutive single-character lines
                        while i < len(lines) and len(lines[i].strip()) == 1:
                            chars.append(lines[i].strip())
                            i += 1

                        # Join single characters without spaces
                        fixed_content += ''.join(chars)

                        # Add a newline if there are more lines coming
                        if i < len(lines):
                            fixed_content += '\n'
                    else:
                        # Normal line, keep as is
                        fixed_content += line
                        i += 1

                        # Add newline if there are more lines
                        if i < len(lines):
                            fixed_content += '\n'

                # Update the interaction
                interaction.content = fixed_content
                fixed_count += 1

        # Commit the changes
        db.commit()
        print(f"Fixed {fixed_count} interactions with vertical text")

    except Exception as e:
        print(f"Error fixing vertical text: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    fix_vertical_text()