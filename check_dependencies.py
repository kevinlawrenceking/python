#!/usr/bin/env python3
"""
Dependency checker for Python scripts
Usage: python check_dependencies.py <script_name.py>
"""

import ast
import sys
import importlib.util

def get_imports_from_file(filename):
    """Extract all import statements from a Python file."""
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()
    
    tree = ast.parse(content)
    imports = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split('.')[0])
    
    return list(set(imports))

def check_module_availability(module_name):
    """Check if a module is available."""
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except (ImportError, ValueError):
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python check_dependencies.py <script_name.py>")
        return
    
    script_file = sys.argv[1]
    
    try:
        imports = get_imports_from_file(script_file)
        print(f"Dependencies for {script_file}:")
        print("=" * 50)
        
        standard_library = [
            'os', 'sys', 'datetime', 'logging', 'json', 'time', 'urllib', 
            'collections', 'itertools', 'functools', 're', 'math', 'random',
            'string', 'io', 'pathlib', 'subprocess', 'threading', 'multiprocessing',
            'email', 'smtplib', 'html', 'xml', 'sqlite3', 'csv'
        ]
        
        built_in = []
        external = []
        missing = []
        
        for module in sorted(imports):
            if module in standard_library:
                built_in.append(module)
            else:
                if check_module_availability(module):
                    external.append(module)
                else:
                    missing.append(module)
        
        print("✅ Built-in modules (no installation needed):")
        for module in built_in:
            print(f"   {module}")
        
        print("\n✅ External modules (already installed):")
        for module in external:
            print(f"   {module}")
        
        print("\n❌ Missing modules (need installation):")
        if missing:
            for module in missing:
                print(f"   {module}")
            print(f"\nTo install missing modules:")
            print(f"pip install {' '.join(missing)}")
        else:
            print("   None - all dependencies are satisfied!")
            
    except FileNotFoundError:
        print(f"Error: File '{script_file}' not found")
    except Exception as e:
        print(f"Error analyzing file: {e}")

if __name__ == "__main__":
    main()
