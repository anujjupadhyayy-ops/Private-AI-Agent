import bcrypt, sys, os
from db import get_conn
from dotenv import load_dotenv
load_dotenv()

def create_user(username: str, password: str, role: str = "user"):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username=%s", [username])
    existing = cursor.fetchone()
    if existing:
        print(f"✗ User '{username}' already exists")
        return
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    cursor.execute(
        "INSERT INTO users(username, password, role) VALUES(%s,%s,%s)",
        [username, hashed.decode(), role]
    )
    conn.commit()
    print(f"✓ User '{username}' created with role '{role}'")

def list_users():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, created_at FROM users")
    rows = cursor.fetchall()
    if not rows:
        print("No users found")
        return
    print("\nUsers:")
    for row in rows:
        print(f"  ID:{row[0]} | {row[1]} | role:{row[2]} | created:{row[3]}")

def delete_user(username: str):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username=%s", [username])
    existing = cursor.fetchone()
    if not existing:
        print(f"✗ User '{username}' not found")
        return
    cursor.execute("DELETE FROM users WHERE username=%s", [username])
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
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
    cursor.execute(
        "UPDATE users SET password=%s WHERE username=%s",
        [hashed.decode(), username]
    )
    conn.commit()
    print(f"✓ Password updated for '{username}'")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 create_user.py add username password")
        print("  python3 create_user.py add username password admin")
        print("  python3 create_user.py list")
        print("  python3 create_user.py delete username")
        print("  python3 create_user.py password username newpassword")
    elif sys.argv[1] == "add":
        role = sys.argv[4] if len(sys.argv) > 4 else "user"
        create_user(sys.argv[2], sys.argv[3], role)
    elif sys.argv[1] == "list":
        list_users()
    elif sys.argv[1] == "delete":
        delete_user(sys.argv[2])
    elif sys.argv[1] == "password":
        if len(sys.argv) < 4:
            print("Usage: python3 create_user.py password username newpassword")
        else:
            update_password(sys.argv[2], sys.argv[3])