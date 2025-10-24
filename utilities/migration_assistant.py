"""
Migration Assistant for DocketWatch Script Modernization
=======================================================

This script helps migrate from the old monolithic scraper_base.py approach
to the new modular architecture.

Features:
- Analyzes existing scripts for dependencies
- Generates migration reports
- Creates backup copies
- Suggests refactoring steps
"""

import os
import re
import shutil
import json
from datetime import datetime
from pathlib import Path

class DocketWatchMigrator:
    """
    Assists with migrating DocketWatch scripts to the new modular architecture.
    """
    
    def __init__(self, python_dir="u:/docketwatch/python"):
        self.python_dir = Path(python_dir)
        self.analysis = {
            'production_scripts': [],
            'utility_scripts': [],
            'test_scripts': [],
            'dependencies': {},
            'function_usage': {},
            'migration_recommendations': []
        }
    
    def analyze_current_structure(self):
        """Analyze the current script structure and dependencies."""
        print("🔍 Analyzing current DocketWatch script structure...")
        
        # Find all Python files
        python_files = list(self.python_dir.glob("*.py"))
        
        for file_path in python_files:
            self._analyze_script(file_path)
        
        self._generate_recommendations()
        return self.analysis
    
    def _analyze_script(self, file_path):
        """Analyze a single Python script."""
        script_name = file_path.name
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Categorize script
            category = self._categorize_script(script_name, content)
            
            # Analyze imports from scraper_base
            scraper_base_imports = self._find_scraper_base_imports(content)
            
            # Find function calls
            function_calls = self._find_function_calls(content)
            
            script_info = {
                'name': script_name,
                'path': str(file_path),
                'category': category,
                'scraper_base_imports': scraper_base_imports,
                'function_calls': function_calls,
                'lines_of_code': len(content.splitlines()),
                'last_modified': datetime.fromtimestamp(file_path.stat().st_mtime)
            }
            
            # Add to appropriate category
            if category == 'production':
                self.analysis['production_scripts'].append(script_info)
            elif category == 'utility':
                self.analysis['utility_scripts'].append(script_info)
            else:
                self.analysis['test_scripts'].append(script_info)
            
            # Track dependencies
            if scraper_base_imports:
                self.analysis['dependencies'][script_name] = scraper_base_imports
            
            # Track function usage
            for func in function_calls:
                if func not in self.analysis['function_usage']:
                    self.analysis['function_usage'][func] = []
                self.analysis['function_usage'][func].append(script_name)
        
        except Exception as e:
            print(f"⚠️  Could not analyze {script_name}: {e}")
    
    def _categorize_script(self, script_name, content):
        """Categorize a script as production, utility, or test."""
        if script_name.startswith('docketwatch_'):
            return 'production'
        elif script_name.startswith('test') or 'test' in script_name.lower():
            return 'test'
        else:
            return 'utility'
    
    def _find_scraper_base_imports(self, content):
        """Find imports from scraper_base.py."""
        imports = []
        
        # Find 'from scraper_base import ...' statements
        pattern = r'from\s+scraper_base\s+import\s+([^\n]+)'
        matches = re.findall(pattern, content)
        
        for match in matches:
            # Split by comma and clean up
            functions = [f.strip() for f in match.split(',')]
            imports.extend(functions)
        
        return list(set(imports))  # Remove duplicates
    
    def _find_function_calls(self, content):
        """Find function calls that might be from scraper_base."""
        # Common scraper_base functions
        scraper_functions = [
            'log_message', 'get_db_cursor', 'setup_logging', 'mark_case_found',
            'mark_case_not_found', 'insert_new_case_events', 'update_case_records',
            'perform_ocr_for_documents', 'generate_ai_summary_for_documents',
            'create_case_update_if_needed', 'send_case_update_alert',
            'extract_and_store_pacer_billing', 'solve_recaptcha_2captcha'
        ]
        
        found_calls = []
        for func in scraper_functions:
            if re.search(rf'\b{func}\s*\(', content):
                found_calls.append(func)
        
        return found_calls
    
    def _generate_recommendations(self):
        """Generate migration recommendations based on analysis."""
        recs = []
        
        # Most used functions should be prioritized
        sorted_functions = sorted(self.analysis['function_usage'].items(), 
                                key=lambda x: len(x[1]), reverse=True)
        
        if sorted_functions:
            top_functions = sorted_functions[:5]
            recs.append({
                'type': 'priority',
                'title': 'Prioritize these functions for modularization',
                'details': [f"{func}: used by {len(scripts)} scripts" 
                          for func, scripts in top_functions]
            })
        
        # Production scripts that need updates
        prod_scripts = [s for s in self.analysis['production_scripts'] 
                       if s['scraper_base_imports']]
        
        if prod_scripts:
            recs.append({
                'type': 'critical',
                'title': 'Production scripts requiring migration',
                'details': [f"{s['name']}: imports {len(s['scraper_base_imports'])} functions"
                          for s in prod_scripts]
            })
        
        # Test files that can be archived
        old_test_files = [s for s in self.analysis['test_scripts']
                         if 'test' in s['name'] and 
                         (datetime.now() - s['last_modified']).days > 30]
        
        if old_test_files:
            recs.append({
                'type': 'cleanup',
                'title': 'Old test files that can be archived',
                'details': [f"{s['name']}: last modified {s['last_modified'].strftime('%Y-%m-%d')}"
                          for s in old_test_files]
            })
        
        self.analysis['migration_recommendations'] = recs
    
    def create_backup(self):
        """Create a backup of the current scripts before migration."""
        backup_dir = self.python_dir / "backup" / datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Creating backup in {backup_dir}")
        
        # Copy all Python files
        for py_file in self.python_dir.glob("*.py"):
            shutil.copy2(py_file, backup_dir)
        
        # Copy scraper_base.py specifically
        if (self.python_dir / "scraper_base.py").exists():
            shutil.copy2(self.python_dir / "scraper_base.py", backup_dir / "scraper_base_original.py")
        
        print(f"✅ Backup created: {len(list(backup_dir.glob('*.py')))} files")
        return backup_dir
    
    def generate_migration_plan(self):
        """Generate a detailed migration plan."""
        plan = {
            'phase_1': {
                'title': 'Create Modular Components',
                'tasks': [
                    'Create core/ directory with modular components',
                    'Extract PDF operations from scraper_base.py',
                    'Extract case event management functions',
                    'Create AI summarization module',
                    'Create alert system module'
                ],
                'estimated_days': 5
            },
            'phase_2': {
                'title': 'Update Production Scripts',
                'tasks': [],
                'estimated_days': 0
            },
            'phase_3': {
                'title': 'Testing and Cleanup',
                'tasks': [
                    'Test all production scripts in staging',
                    'Archive old test files',
                    'Update documentation',
                    'Deploy to production'
                ],
                'estimated_days': 3
            }
        }
        
        # Add specific tasks for production scripts
        for script in self.analysis['production_scripts']:
            if script['scraper_base_imports']:
                task = f"Update {script['name']} to use new modules"
                plan['phase_2']['tasks'].append(task)
                plan['phase_2']['estimated_days'] += 0.5
        
        return plan
    
    def generate_report(self, output_file=None):
        """Generate a comprehensive migration report."""
        if not output_file:
            output_file = self.python_dir / "migration_report.json"
        
        report = {
            'analysis_date': datetime.now().isoformat(),
            'summary': {
                'total_scripts': (len(self.analysis['production_scripts']) + 
                                len(self.analysis['utility_scripts']) + 
                                len(self.analysis['test_scripts'])),
                'production_scripts': len(self.analysis['production_scripts']),
                'utility_scripts': len(self.analysis['utility_scripts']),
                'test_scripts': len(self.analysis['test_scripts']),
                'scripts_using_scraper_base': len(self.analysis['dependencies'])
            },
            'analysis': self.analysis,
            'migration_plan': self.generate_migration_plan()
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"📊 Migration report saved to: {output_file}")
        return report
    
    def print_summary(self):
        """Print a summary of the analysis."""
        print("\n" + "="*60)
        print("🚀 DOCKETWATCH MIGRATION ANALYSIS SUMMARY")
        print("="*60)
        
        print(f"\n📈 SCRIPT INVENTORY:")
        print(f"   Production scripts (docketwatch_*): {len(self.analysis['production_scripts'])}")
        print(f"   Utility scripts: {len(self.analysis['utility_scripts'])}")
        print(f"   Test scripts: {len(self.analysis['test_scripts'])}")
        
        print(f"\n🔗 DEPENDENCIES:")
        print(f"   Scripts using scraper_base: {len(self.analysis['dependencies'])}")
        
        if self.analysis['function_usage']:
            print(f"\n📊 MOST USED FUNCTIONS:")
            sorted_funcs = sorted(self.analysis['function_usage'].items(), 
                                key=lambda x: len(x[1]), reverse=True)
            for func, scripts in sorted_funcs[:5]:
                print(f"   {func}: {len(scripts)} scripts")
        
        print(f"\n⚠️  RECOMMENDATIONS:")
        for rec in self.analysis['migration_recommendations']:
            print(f"   {rec['type'].upper()}: {rec['title']}")
            for detail in rec['details'][:3]:  # Show first 3
                print(f"      - {detail}")
        
        print("\n" + "="*60)

def main():
    """Main migration assistant function."""
    print("🔄 DocketWatch Migration Assistant Starting...")
    
    # Initialize migrator
    migrator = DocketWatchMigrator()
    
    # Analyze current structure
    analysis = migrator.analyze_current_structure()
    
    # Print summary
    migrator.print_summary()
    
    # Ask user for next steps
    print("\n🤔 What would you like to do next?")
    print("1. Create backup of current scripts")
    print("2. Generate detailed migration report")
    print("3. Both backup and report")
    print("4. Exit")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice in ['1', '3']:
        backup_dir = migrator.create_backup()
        print(f"✅ Backup completed: {backup_dir}")
    
    if choice in ['2', '3']:
        report = migrator.generate_report()
        print("✅ Migration report generated")
    
    print("\n🎉 Migration analysis complete!")
    print("\nNext steps:")
    print("1. Review the migration report")
    print("2. Create the new modular components (core/ directory)")
    print("3. Start with the most critical production scripts")
    print("4. Test each migration in staging before production")

if __name__ == "__main__":
    main()
