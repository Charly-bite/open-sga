import argparse
import os
import subprocess
import sys

VERSION_FILE = 'VERSION'

def read_version():
    if not os.path.exists(VERSION_FILE):
        return None
    with open(VERSION_FILE, 'r') as f:
        return f.read().strip()

def write_version(version):
    with open(VERSION_FILE, 'w') as f:
        f.write(version + '\n')

def run_cmd(cmd, check=True):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if check and result.returncode != 0:
        print(f"Error executing '{cmd}':\n{result.stderr}")
        sys.exit(1)
    return result.stdout.strip(), result.returncode

def bump_version(version, part):
    try:
        major, minor, patch = map(int, version.split('.'))
    except ValueError:
        print("Invalid version format. Expected X.Y.Z")
        sys.exit(1)
        
    if part == 'major':
        major += 1
        minor = 0
        patch = 0
    elif part == 'minor':
        minor += 1
        patch = 0
    elif part == 'patch':
        patch += 1
        
    return f"{major}.{minor}.{patch}"

def main():
    parser = argparse.ArgumentParser(description="Manage project version and Git tags.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Set command
    parser_set = subparsers.add_parser("set", help="Set to a specific version (e.g., 2.0.1)")
    parser_set.add_argument("version", help="The version string (e.g., 2.0.1)")
    parser_set.add_argument("--no-commit", action="store_true", help="Don't create a git commit and tag")
    
    # Bump command
    parser_bump = subparsers.add_parser("bump", help="Bump version (major, minor, patch)")
    parser_bump.add_argument("part", choices=["major", "minor", "patch"], help="Part of version to bump")
    parser_bump.add_argument("--no-commit", action="store_true", help="Don't create a git commit and tag")
    
    args = parser.parse_args()
    
    current_version = read_version()
    
    if args.command == "set":
        new_version = args.version
    elif args.command == "bump":
        if not current_version:
            print("No VERSION file found. Please use 'set' command to initialize the version first.")
            sys.exit(1)
        new_version = bump_version(current_version, args.part)
        
    if current_version == new_version:
        print(f"Version is already {new_version}. No changes made.")
        sys.exit(0)
        
    print(f"Updating version: {current_version or 'None'} -> {new_version}")
    write_version(new_version)
    
    if not args.no_commit:
        # Check if git is available and it's a repo
        _, rc = run_cmd("git rev-parse --is-inside-work-tree", check=False)
        if rc == 0:
            run_cmd(f"git add {VERSION_FILE}")
            
            # Check if there are changes to commit
            status, _ = run_cmd("git status --porcelain", check=False)
            if status:
                run_cmd(f'git commit -m "chore: set version to {new_version}"')
                run_cmd(f"git tag v{new_version}")
                print(f"Committed and tagged as v{new_version}")
                
                print("\nTo push changes and tags to GitHub, run:")
                print("  git push origin HEAD")
                print("  git push origin --tags")
            else:
                print("No changes to commit.")
        else:
            print("Not a git repository, skipping git commit.")

if __name__ == '__main__':
    main()
