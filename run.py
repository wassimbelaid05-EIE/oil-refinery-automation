# Oil Refinery Automation — Entry Point
# Run the HMI dashboard:  python run.py
# Or directly:            streamlit run hmi/app.py

import subprocess
import sys

if __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "streamlit", "run", "hmi/app.py"])
