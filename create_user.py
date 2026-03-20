import bcrypt, sys, os
# bcrypt — password hashing library, deliberately slow to resist brute force
# sys — for reading command line arguments (sys.argv)
# os — for environment variables (used by load_dotenv indirectly)

from db import get_conn
# Imports the PostgreSQL connection — all database operations go through this

from dotenv import load_dotenv
load_dotenv()
# Loads .env file so POSTGRES_URL is available when get_conn() is called

def create_user(username: str, password: str, role: str = "user"):
    # Creates a new user in the database with a hashed password
    # role defaults to "user" — pass "admin" as fourth argument for admin access
    
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE username=%s", [username])
    existing = cursor.fetchone()
    # Checks if the username already exists before trying to insert
    # PostgreSQL has a UNIQUE constraint on username — inserting a duplicate would throw an error
    # This check gives a friendly message instead of a cryptic database error
    
    if existing:
        print(f"✗ User '{username}' already exists")
        return
        # Exits the function early — no database changes made
    
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    # password.encode() converts the string to bytes — bcrypt requires bytes
    # bcrypt.gensalt() generates a random salt — makes every hash unique
    # Even if two users have the same password, their hashes are completely different
    # bcrypt.hashpw() applies the hashing algorithm — designed to take ~100ms
    # That 100ms delay makes brute force attacks millions of times slower
    
    cursor.execute(
        "INSERT INTO users(username, password, role) VALUES(%s,%s,%s)",
        [username, hashed.decode(), role]
        # hashed.decode() converts bytes back to string for database storage
        # PostgreSQL stores it as text — bcrypt.checkpw() handles the comparison later
    )
    conn.commit()
    # Makes the INSERT permanent in the database
    print(f"✓ User '{username}' created with role '{role}'")

def list_users():
    # Shows all users — useful for verifying who has access
    # Deliberately omits the password column — never display password hashes
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, created_at FROM users")
    # Selects 4 safe columns — password is intentionally excluded
    rows = cursor.fetchall()
    # fetchall() returns all rows as a list of tuples
    
    if not rows:
        print("No users found")
        return
    
    print("\nUsers:")
    for row in rows:
        print(f"  ID:{row[0]} | {row[1]} | role:{row[2]} | created:{row[3]}")
        # row[0]=id, row[1]=username, row[2]=role, row[3]=created_at timestamp

def delete_user(username: str):
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE username=%s", [username])
    existing = cursor.fetchone()
    if not existing:
        print(f"✗ User '{username}' not found")
        return
        # Pre-check prevents silent failure — SQLite would delete 0 rows with no error
        # This gives explicit feedback that the username didn't exist
    
    cursor.execute("DELETE FROM users WHERE username=%s", [username])
    # Removes the user row from the database
    # Their message history in the messages table remains — session_id stays in the database
    # This is intentional — audit trail should not be deleted when a user is removed
    conn.commit()
    print(f"✓ User '{username}' deleted")

def update_password(username: str, new_password: str):
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE username=%s", [username])
    existing = cursor.fetchone()
    if not existing:
        print(f"✗ User '{username}' not found")
        return
        # Pre-check — avoids running UPDATE on a username that doesn't exist
    
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
    # Same hashing process as create_user — new salt generated every time
    # This means the same password produces a different hash each time it's set
    # That is correct and expected bcrypt behaviour
    
    cursor.execute(
        "UPDATE users SET password=%s WHERE username=%s",
        [hashed.decode(), username]
        # Updates only the password column for this specific username
    )
    conn.commit()
    print(f"✓ Password updated for '{username}'")

if __name__ == "__main__":
    # Only runs when called directly: python3 create_user.py
    # Does NOT run when other files import from this module
    
    if len(sys.argv) < 2:
        # No arguments provided — print usage instructions
        print("Usage:")
        print("  python3 create_user.py add username password")
        print("  python3 create_user.py add username password admin")
        print("  python3 create_user.py list")
        print("  python3 create_user.py delete username")
        print("  python3 create_user.py password username newpassword")
    
    elif sys.argv[1] == "add":
        role = sys.argv[4] if len(sys.argv) > 4 else "user"
        # sys.argv[4] is the optional role argument
        # If not provided, defaults to "user" — admin must be explicitly specified
        create_user(sys.argv[2], sys.argv[3], role)
        # sys.argv[2] = username, sys.argv[3] = password
    
    elif sys.argv[1] == "list":
        list_users()
    
    elif sys.argv[1] == "delete":
        delete_user(sys.argv[2])
        # sys.argv[2] = username to delete
    
    elif sys.argv[1] == "password":
        if len(sys.argv) < 4:
            print("Usage: python3 create_user.py password username newpassword")
        else:
            update_password(sys.argv[2], sys.argv[3])
            # sys.argv[2] = username, sys.argv[3] = new password