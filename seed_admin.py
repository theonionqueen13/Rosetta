import os, sqlite3, bcrypt

# Same DB path logic as your app
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "profiles.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)

# Ensure tables (matches your app schema)
conn.execute("""
CREATE TABLE IF NOT EXISTS users (
  username TEXT PRIMARY KEY,
  name     TEXT NOT NULL,
  email    TEXT NOT NULL,
  pw_hash  TEXT NOT NULL,
  role     TEXT NOT NULL DEFAULT 'user'
)""")
cols = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
if "role" not in cols:
  conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

conn.execute("""
CREATE TABLE IF NOT EXISTS profiles (
  user_id      TEXT NOT NULL,
  profile_name TEXT NOT NULL,
  payload      TEXT NOT NULL,
  PRIMARY KEY (user_id, profile_name)
)""")
conn.execute("""
CREATE TABLE IF NOT EXISTS community_profiles (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_name TEXT NOT NULL,
  payload      TEXT NOT NULL,
  submitted_by TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
)""")

# --- EDIT THESE IF YOU WANT ---
username = "admin"
name     = "Joylin"
email    = "the.onion.queen.13@gmail.com"
temp_pw  = "ChangeMe!123"   # use this to log in, then change it in the app
# ------------------------------

# Hash exactly like your create_user()
pw_hash = bcrypt.hashpw(temp_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
conn.execute(
  "INSERT OR REPLACE INTO users (username,name,email,pw_hash,role) VALUES (?,?,?,?,?)",
  (username, name, email, pw_hash, "admin")
)
conn.commit()

# Quick local verify (same check your app’s verify_password uses)
ok = bcrypt.checkpw(temp_pw.encode("utf-8"), pw_hash.encode("utf-8"))
print(f"Seeded admin '{username}' with temp password: {temp_pw} (verify: {ok})")
print("DB path:", DB_PATH)
