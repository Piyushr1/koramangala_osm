import subprocess
import sys
import time
from pathlib import Path

def run_script(script_name):
    """Run a single script and return success status"""
    print(f"\n{'='*50}")
    print(f"Running: {script_name}")
    print('='*50)
    
    start_time = time.time()
    
    try:
        result = subprocess.run([sys.executable, f"scripts/{script_name}"], 
                              check=True, capture_output=False)
        duration = time.time() - start_time
        print(f"✅ {script_name} completed in {duration:.1f}s")
        return True
    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        print(f"❌ {script_name} failed after {duration:.1f}s")
        return False

def main():
    print("🚀 Koramangala OSM Data Processing Pipeline")
    print("=" * 50)
    
    scripts = [
        "01_extract_koramangala.py",
        "02_process_pois.py", 
        "03_process_roads.py",
        "04_create_business_datasets.py"
    ]
    
    total_start = time.time()
    
    for script in scripts:
        success = run_script(script)
        if not success:
            print(f"\n❌ Pipeline failed at: {script}")
            return False
    
    total_duration = time.time() - total_start
    
    print(f"\n🎉 Pipeline completed successfully!")
    print(f"Total time: {total_duration/60:.1f} minutes")
    print(f"\n📁 Check outputs in:")
    print(f"  - data/processed/ (GeoJSON files)")
    print(f"  - data/outputs/ (Business CSV/Excel files)")

if __name__ == "__main__":
    main()