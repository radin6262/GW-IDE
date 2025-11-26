import requests
import json
import os
import zipfile
import io
import shutil
from packaging.version import parse as parse_version
import sys
import subprocess
# --- CONFIGURATION ---
# The current version of your application installed locally.
# This should match the version in your current (local) package.json or similar file.
CURRENT_VERSION = "1.0.1.5"

# GitHub Repository Details
# GITHUB_OWNER = "YourGitHubUsername"      # e.g., "google"
# GITHUB_REPO = "YourRepositoryName"       # e.g., "ge     
# GITHUB_BRANCH = "main"                   # The branch to check for updates (e.g., 'main' or 'master')

# Filesystem paths
UPDATE_TEMP_DIR = "temp_update_download" # Temporary folder to extract the new source code
UPDATE_TARGET_DIR = os.getcwd()          # The directory where new files should be placed (current directory)

# URL for fetching the remote package.json
PACKAGE_JSON_URL = "https://raw.githubusercontent.com/IamAbolfazlGameMaker/GW-IDE/main/packages.json"

SOURCE_CODE_ZIP_URL = "https://github.com/IamAbolfazlGameMaker/GW-IDE/archive/refs/heads/main.zip"
# ---------------------


def get_remote_version():
    """Fetches the version from the remote package.json on GitHub."""
    print(f"-> Checking for update at: {PACKAGE_JSON_URL}")
    try:
        response = requests.get(PACKAGE_JSON_URL, timeout=10)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        remote_data = response.json()
        remote_version = remote_data.get("version")
        
        if not remote_version:
            print("Error: 'version' field not found in remote package.json.")
            return None
            
        return remote_version
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching remote package.json: {e}")
        return None
    except json.JSONDecodeError:
        print("Error: Could not decode JSON from remote package.json.")
        return None

def run_main_app(app_file="app.py"):
    """
    Launches the main app in a new PowerShell window and exits the updater.
    """
    if os.path.exists(app_file):
        subprocess.Popen([
            "powershell",
            "-NoExit",  # optional: keep the PowerShell window open
            "-Command",
            f'python "{os.path.abspath(app_file)}"'
        ])
        print(f"Main app '{app_file}' launched. Exiting updater...")
        sys.exit(0)
    else:
        print(f"Cannot run '{app_file}', file not found.")
def download_and_extract_update(remote_version):
    """Downloads the source code zip and extracts it."""
    print(f"\n-> Downloading source code for version {remote_version}...")
    try:
        # 1. Download the zip file
        zip_response = requests.get(SOURCE_CODE_ZIP_URL, stream=True, timeout=30)
        zip_response.raise_for_status()

        # 2. Use io.BytesIO to handle the file in memory
        zip_file_bytes = io.BytesIO(zip_response.content)

        # 3. Create the temporary directory if it doesn't exist
        if os.path.exists(UPDATE_TEMP_DIR):
            shutil.rmtree(UPDATE_TEMP_DIR) # Clean up previous temp dir if present
        os.makedirs(UPDATE_TEMP_DIR, exist_ok=True)
        print(f"Created temporary directory: {UPDATE_TEMP_DIR}")

        # 4. Extract the zip file contents
        with zipfile.ZipFile(zip_file_bytes, 'r') as zf:
            # GitHub zips typically contain a single root folder (e.g., 'repo-name-main/').
            # We need to extract the contents *of* that root folder.
            
            # Get the name of the root directory inside the zip
            root_dir = zf.namelist()[0].split('/')[0] + '/'
            
            # Extract only the necessary files, skipping the root folder itself
            for member in zf.namelist():
                if member.startswith(root_dir) and len(member) > len(root_dir):
                    # Define target path relative to the temporary directory
                    target_path = os.path.join(UPDATE_TEMP_DIR, member[len(root_dir):])
                    
                    # Ensure directory structure exists for the file
                    if member.endswith('/'):
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, 'wb') as outfile:
                            outfile.write(zf.read(member))
            
            print(f"Successfully extracted new source code to {UPDATE_TEMP_DIR}.")

        # 5. Move extracted files into the target directory (e.g., current directory)
        print(f"Moving updated files from {UPDATE_TEMP_DIR} to {UPDATE_TARGET_DIR}...")
        
        # NOTE: This step is destructive and overwrites existing files.
        # It's crucial to ensure the updater script itself is not overwritten while running!
        # A more advanced updater would handle moving all files EXCEPT the running updater.

        for item in os.listdir(UPDATE_TEMP_DIR):
            s = os.path.join(UPDATE_TEMP_DIR, item)
            d = os.path.join(UPDATE_TARGET_DIR, item)
            
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d) # Remove existing directory before copytree
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d) # copy2 preserves metadata
        
        print("Update applied successfully! Cleaning up temporary files.")
        shutil.rmtree(UPDATE_TEMP_DIR)
        
        return True

    except requests.exceptions.RequestException as e:
        print(f"Error during download or extraction: {e}")
        # Clean up in case of failure
        if os.path.exists(UPDATE_TEMP_DIR):
             shutil.rmtree(UPDATE_TEMP_DIR)
        return False
    except zipfile.BadZipFile:
        print("Error: Downloaded file is not a valid zip file.")
        if os.path.exists(UPDATE_TEMP_DIR):
             shutil.rmtree(UPDATE_TEMP_DIR)
        return False
    except Exception as e:
        print(f"An unexpected error occurred during file operations: {e}")
        if os.path.exists(UPDATE_TEMP_DIR):
             shutil.rmtree(UPDATE_TEMP_DIR)
        return False


def main():
    """Main function to run the update check."""
    print("--- Auto-Updater Initialized ---")
    print(f"Local Version: {CURRENT_VERSION}")

    remote_version = get_remote_version()

    if remote_version is None:
        print("\nUpdate check failed due to configuration or network error.")
        return

    print(f"Remote Version: {remote_version}")

    try:
        # Use the 'packaging.version' library for robust semantic version comparison
        current = parse_version(CURRENT_VERSION)
        remote = parse_version(remote_version)
    except Exception as e:
        print(f"Error parsing versions: {e}. Cannot proceed with comparison.")
        return

    if remote > current:
        print("A newer version is available! Initiating update...")
        download_and_extract_update(remote_version)
    elif remote < current:
        print("Warning: Remote version is older than local version. No update performed.")
    else:
        print("Local version is up-to-date. No update needed.")

    print("\n--- Auto-Updater Finished ---")
    run_main_app()

if __name__ == "__main__":
    # Ensure necessary libraries are available.
    try:
        import requests
        from packaging.version import parse
    except ImportError:
        print("Error: The 'requests' and 'packaging' libraries are required.")
        print("Please install them using: pip install requests packaging")
    else:
        main()
