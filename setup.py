"""
==========================================================
  QUICK SETUP — Ek baar chalao, sab set ho jayega
==========================================================
"""

import subprocess, sys, os, json

def run(cmd):
    print(f"  Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

print("\n== Installing packages ==")
run(f"{sys.executable} -m pip install flask pdf2image pillow pypdf --break-system-packages")

print("\n== Starting app + adding demo user ==")
import threading, time, urllib.request

def start_app():
    import app as myapp
    myapp.init_db()
    myapp.app.run(port=5000, debug=False, use_reloader=False)

thread = threading.Thread(target=start_app, daemon=True)
thread.start()
time.sleep(2)

# Add a demo user
demo = {
    "name":     "Demo User",
    "email":    "demo@example.com",
    "pdf_file": "sample.pdf"
}

print("\n  NOTE: Put your PDF inside the 'pdfs/' folder")
print("  Then add users like this:\n")
print('  curl -X POST http://localhost:5000/admin/add-user \\')
print('       -H "Content-Type: application/json" \\')
print('       -d \'{"name":"Rahul","email":"rahul@gmail.com","pdf_file":"document.pdf"}\'\n')
print("  Or use requests in Python:")
print("""
  import requests
  r = requests.post('http://localhost:5000/admin/add-user', json={
      'name':     'Rahul Sharma',
      'email':    'rahul@gmail.com',
      'pdf_file': 'document.pdf'   # must be in pdfs/ folder
  })
  print(r.json())  # shows generated password
""")

input("  Press Enter to exit setup...")