import os
import PyInstaller.__main__

# ------------------------
#  SETTINGS
# ------------------------

MAIN_SCRIPT = "launch.py"        # Or "app.py"
ICON_FILE = "icon.ico"         # Put your .ico in project folder

ADDITIONAL_DATA = [
]

# Build the --add-data arguments
data_args = []
for src, dest in ADDITIONAL_DATA:
    src = os.path.abspath(src)
    data_args.append(f"{src}{os.pathsep}{dest}")

# ------------------------
#  BUILD COMMAND
# ------------------------

PyInstaller.__main__.run([
    MAIN_SCRIPT,
    "--onefile",
    "--noconsole",                     # Remove this if you DO want console
    f"--icon={ICON_FILE}",

    # 🔥 FIX: Include the Python standard library
    "--hidden-import=encodings",
    "--hidden-import=codecs",
    "--hidden-import=importlib",
    "--hidden-import=importlib._bootstrap",
    "--hidden-import=importlib._bootstrap_external",
] + [
    f"--add-data={d}" for d in data_args
])
