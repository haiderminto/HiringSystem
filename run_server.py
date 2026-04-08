#!/usr/bin/env python3
"""Run the server and capture all output to a log file."""

import subprocess
import sys

print("Starting ATS Resume Evaluator Server...")
print("Logs will be written to: server.log")
print("\nOpen http://localhost:8000 in your browser")
print("Press Ctrl+C to stop the server")
print("-" * 60)

try:
    with open("server.log", "w") as logfile:
        process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=logfile,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Also print to console in real-time
        with open("server.log", "r") as follow:
            import time
            while process.poll() is None:
                for line in follow:
                    print(line.rstrip())
                time.sleep(0.1)

        # Get final output
        for line in open("server.log"):
            print(line.rstrip())

        returncode = process.wait()
        print(f"\nServer stopped with code: {returncode}")

except KeyboardInterrupt:
    print("\nServer stopped by user")
except Exception as e:
    print(f"Error: {e}")
    print("\nCheck server.log for details")
