"""Launcher script to start both the ControlPlane backend and frontend."""

import subprocess
import sys
import time
import os
import shutil


def find_npm():
    """Resolve npm executable, using npm.cmd on Windows."""
    npm_name = "npm.cmd" if sys.platform == "win32" else "npm"
    npm_path = shutil.which(npm_name)
    if npm_path is None:
        print("ERROR: npm not found.")
        print("  Node.js/npm is required for the frontend.")
        print("  Install from https://nodejs.org/ and ensure it is on PATH.")
        sys.exit(1)
    return npm_path


def main():
    print("=" * 60)
    print("  ControlPlane AI Governance Control Plane")
    print("  Starting backend (FastAPI) and frontend (Vite)...")
    print("=" * 60)
    print()

    root_dir = os.path.dirname(os.path.abspath(__file__))
    ui_dir = os.path.join(root_dir, "ui")

    # Verify frontend directory exists
    if not os.path.isdir(ui_dir):
        print(f"ERROR: Frontend directory not found: {ui_dir}")
        sys.exit(1)

    npm = find_npm()

    # Start backend
    print("[1/2] Starting backend on http://localhost:8000 ...")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "controlplane.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=root_dir,
    )

    # Give backend a moment to start
    time.sleep(2)

    # Start frontend
    print("[2/2] Starting frontend on http://localhost:5173 ...")
    frontend = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=ui_dir,
    )

    print()
    print("=" * 60)
    print("  Backend:  http://localhost:8000")
    print("  Frontend: http://localhost:5173")
    print("  API Docs: http://localhost:8000/docs")
    print("=" * 60)
    print()
    print("Press Ctrl+C to stop both servers.")

    try:
        backend.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Always clean up both processes
        for proc in (backend, frontend):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        print("Done.")


if __name__ == "__main__":
    main()
