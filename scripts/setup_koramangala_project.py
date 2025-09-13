import os
import subprocess
import sys
from pathlib import Path

def create_directory_structure():
    """Create project directories"""
    directories = [
        'data/raw',
        'data/processed', 
        'data/outputs',
        'scripts/utils',
        'config'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created: {directory}")

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = [
        'geopandas', 'osmnx', 'pandas', 'shapely', 
        'fiona', 'pyproj', 'pyyaml', 'openpyxl'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package}")
        except ImportError:
            missing.append(package)
            print(f"✗ {package} (missing)")
    
    if missing:
        print(f"\nInstall missing packages:")
        print(f"pip install {' '.join(missing)}")
        return False
    
    return True

def main():
    print("Setting up Koramangala OSM Project")
    print("=" * 40)
    
    # Create directories
    print("\n📁 Creating directory structure...")
    create_directory_structure()
    
    # Check dependencies
    print("\n🐍 Checking Python packages...")
    deps_ok = check_dependencies()
    
    # Summary
    print("\n" + "=" * 40)
    if deps_ok:
        print("✅ Setup complete!")
        print("\nNext steps:")
        print("1. Run: python scripts/01_extract_koramangala.py")
        print("2. Run: python scripts/02_process_pois.py")
        print("3. Run: python scripts/03_process_roads.py") 
        print("4. Run: python scripts/04_create_business_datasets.py")
    else:
        print("❌ Please install missing dependencies first")

if __name__ == "__main__":
    main()