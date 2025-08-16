import os, time
print("PWD:", os.getcwd())
for d in ("/opt/render/project", "/opt/render/project/src"):
    print(f"\n--- ls {d} ---")
    try:
        for name in sorted(os.listdir(d)):
            print(name)
    except Exception as e:
        print("ERR:", e)
print("\n--- find .py (depth 3) ---")
for root, dirs, files in os.walk("/opt/render/project"):
    depth = root.strip("/").count("/")
    if depth > 6:  # ~3 levels under /opt/render/project
        dirs[:] = []
    for f in files:
        if f.endswith(".py"):
            print(os.path.join(root, f))
time.sleep(600)
