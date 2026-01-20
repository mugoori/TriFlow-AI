#!/usr/bin/env python
"""
Interactive Module Generator for TriFlow AI
Yeoman-style CLI for creating modules with templates

Usage:
    python scripts/create_module_interactive.py
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

try:
    from jinja2 import Environment, FileSystemLoader, Template
except ImportError:
    print("❌ Error: jinja2 not installed")
    print("Install: pip install jinja2")
    sys.exit(1)


def to_pascal_case(snake_str: str) -> str:
    """Convert snake_case to PascalCase"""
    components = snake_str.split('_')
    return ''.join(x.title() for x in components)


def validate_module_code(code: str) -> bool:
    """Validate module code format"""
    pattern = r'^[a-z][a-z0-9_]*$'
    return bool(re.match(pattern, code))


def prompt_input(question: str, default: str = '', validator=None) -> str:
    """Prompt for user input with optional validation"""
    while True:
        if default:
            user_input = input(f"{question} [{default}]: ").strip() or default
        else:
            user_input = input(f"{question}: ").strip()

        if not user_input:
            print("❌ This field is required")
            continue

        if validator:
            is_valid, error_msg = validator(user_input)
            if not is_valid:
                print(f"❌ {error_msg}")
                continue

        return user_input


def prompt_choice(question: str, choices: List[str], default: int = 1) -> str:
    """Prompt for user choice from a list"""
    print(f"\n{question}")
    for i, choice in enumerate(choices, 1):
        marker = "←" if i == default else " "
        print(f"  {i}. {choice} {marker}")

    while True:
        choice = input(f"Select (1-{len(choices)}) [{default}]: ").strip() or str(default)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print(f"❌ Please enter a number between 1 and {len(choices)}")


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt for yes/no answer"""
    default_str = "Y/n" if default else "y/N"
    while True:
        answer = input(f"{question} [{default_str}]: ").strip().lower()
        if not answer:
            return default
        if answer in ['y', 'yes']:
            return True
        if answer in ['n', 'no']:
            return False
        print("❌ Please enter 'y' or 'n'")


class Field:
    """Represents a data field in the module"""

    TYPE_MAP = {
        'str': {
            'python': 'str',
            'pydantic': 'str',
            'typescript': 'string',
            'sqlalchemy': 'String(255)'
        },
        'int': {
            'python': 'int',
            'pydantic': 'int',
            'typescript': 'number',
            'sqlalchemy': 'Integer'
        },
        'float': {
            'python': 'float',
            'pydantic': 'float',
            'typescript': 'number',
            'sqlalchemy': 'Float'
        },
        'bool': {
            'python': 'bool',
            'pydantic': 'bool',
            'typescript': 'boolean',
            'sqlalchemy': 'Boolean'
        },
        'date': {
            'python': 'datetime',
            'pydantic': 'datetime',
            'typescript': 'string',
            'sqlalchemy': 'DateTime'
        }
    }

    def __init__(
        self,
        name: str,
        field_type: str,
        required: bool,
        label: Optional[str] = None,
        default_value: Optional[str] = None,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None
    ):
        self.name = name
        self.type = field_type
        self.required = required
        self.label = label or name.replace('_', ' ').title()
        self.default_value = default_value
        self.min_value = min_value
        self.max_value = max_value

    @property
    def python_type(self) -> str:
        return self.TYPE_MAP[self.type]['python']

    @property
    def pydantic_type(self) -> str:
        return self.TYPE_MAP[self.type]['pydantic']

    @property
    def typescript_type(self) -> str:
        return self.TYPE_MAP[self.type]['typescript']

    @property
    def sqlalchemy_type(self) -> str:
        return self.TYPE_MAP[self.type]['sqlalchemy']

    @property
    def filterable(self) -> bool:
        """Whether this field can be used for filtering"""
        return self.type in ['str', 'int', 'bool']

    @property
    def filter_type(self) -> str:
        """Type of filter UI (select, text, etc)"""
        if self.type == 'bool':
            return 'select'
        elif self.type in ['str']:
            return 'text'
        elif self.type == 'int' and self.min_value and self.max_value:
            return 'select'
        return 'text'

    @property
    def filter_options(self) -> List[Dict[str, str]]:
        """Options for select filters"""
        if self.type == 'bool':
            return [
                {'value': 'true', 'label': 'Yes'},
                {'value': 'false', 'label': 'No'}
            ]
        elif self.type == 'int' and self.min_value and self.max_value:
            return [
                {'value': str(i), 'label': str(i)}
                for i in range(self.min_value, self.max_value + 1)
            ]
        return []

    @property
    def auto_generated(self) -> bool:
        """Whether this field is auto-generated (id, timestamps)"""
        return False

    @property
    def immutable(self) -> bool:
        """Whether this field cannot be updated"""
        return self.name in ['id', 'tenant_id', 'created_at']


class ModuleGenerator:
    """Interactive module generator"""

    CATEGORIES = ['core', 'feature', 'industry', 'integration']
    TEMPLATES = ['CRUD Table', 'Dashboard', 'Chat Interface', 'Custom']

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.modules_dir = self.project_root / 'modules'
        self.templates_dir = self.project_root / 'module_templates'

        # Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def run(self):
        """Run the interactive generator"""
        print("\n" + "=" * 60)
        print("🚀 TriFlow AI Module Generator")
        print("=" * 60)

        # Step 1: Basic info
        module_code = self.prompt_module_code()
        name = self.prompt_name()
        description = self.prompt_description(name)
        category = self.prompt_category()
        icon = self.prompt_icon()

        # Step 2: Advanced settings
        requires_subscription = self.prompt_subscription()
        admin_only = self.prompt_admin_only()
        display_order = self.prompt_display_order()

        # Step 3: Template selection
        template = self.prompt_template()

        # Step 4: Fields definition (for CRUD template)
        fields = []
        if template == 'CRUD Table':
            fields = self.prompt_fields()

        # Step 5: Generate module
        print("\n" + "=" * 60)
        print("✨ Generating Module...")
        print("=" * 60)

        context = {
            'module_code': module_code,
            'pascal_name': to_pascal_case(module_code),
            'name': name,
            'description': description,
            'category': category,
            'icon': icon,
            'requires_subscription': requires_subscription,
            'admin_only': admin_only,
            'display_order': display_order,
            'fields': fields,
            'generation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        self.generate_from_template(template, context)

        # Step 6: Post-generation
        self.build_registry()

        print("\n" + "=" * 60)
        print(f"🎉 Module '{module_code}' created successfully!")
        print("=" * 60)
        print(f"\n📁 Location: {self.modules_dir / module_code}")
        print("\n📝 Next Steps:")
        print("  1. Review generated files")
        print("  2. Add DB model (if needed): backend/app/models/{}.py".format(module_code))
        print("  3. Restart backend:  uvicorn app.main:app --reload")
        print("  4. Restart frontend: npm run dev --prefix frontend")
        print("  5. Enable in Settings → Tenant Modules")
        print("\n💡 Tip: Check docs/INTERNAL_MODULE_DEVELOPMENT.md for details")

    def prompt_module_code(self) -> str:
        """Prompt for module code"""
        def validator(code):
            if not validate_module_code(code):
                return False, "Must start with lowercase letter and contain only lowercase, numbers, underscores"
            if (self.modules_dir / code).exists():
                return False, f"Module '{code}' already exists"
            return True, None

        return prompt_input("📝 Module Code (snake_case)", validator=validator)

    def prompt_name(self) -> str:
        """Prompt for display name"""
        return prompt_input("📝 Display Name")

    def prompt_description(self, name: str) -> str:
        """Prompt for description"""
        default = f"{name} 모듈"
        return prompt_input("📝 Description", default=default)

    def prompt_category(self) -> str:
        """Prompt for category"""
        print("\n📂 Category:")
        print("  1. core       - Core functionality")
        print("  2. feature    - Additional feature")
        print("  3. industry   - Industry-specific")
        print("  4. integration - External integration")

        return prompt_choice("Select category", self.CATEGORIES, default=2)

    def prompt_icon(self) -> str:
        """Prompt for Lucide icon name"""
        default = "Box"
        icon = prompt_input("🎨 Icon (Lucide icon name)", default=default)
        # TODO: Validate against Lucide icon list
        return icon

    def prompt_subscription(self) -> Optional[str]:
        """Prompt for subscription requirement"""
        if not prompt_yes_no("💳 Require subscription?", default=False):
            return None

        return prompt_choice(
            "Minimum subscription plan",
            ['free', 'standard', 'enterprise'],
            default=1
        )

    def prompt_admin_only(self) -> bool:
        """Prompt for admin-only access"""
        return prompt_yes_no("🔒 Admin only?", default=False)

    def prompt_display_order(self) -> int:
        """Prompt for display order"""
        order_str = prompt_input("📊 Display order", default="100")
        try:
            return int(order_str)
        except ValueError:
            return 100

    def prompt_template(self) -> str:
        """Prompt for template selection"""
        descriptions = [
            "CRUD Table       - Data management (Table + CRUD)",
            "Dashboard        - Statistics dashboard (Charts + Cards)",
            "Chat Interface   - AI chatbot interface",
            "Custom           - Empty template (implement yourself)"
        ]
        return prompt_choice("📋 Template", descriptions, default=1).split('-')[0].strip()

    def prompt_fields(self) -> List[Field]:
        """Prompt for field definitions"""
        print("\n" + "=" * 60)
        print("🔧 Define Fields (CRUD Table Template)")
        print("Press Enter without input to finish")
        print("=" * 60)

        fields = []
        field_num = 1

        while True:
            print(f"\nField {field_num}:")
            name = input("  Name (or Enter to finish): ").strip()
            if not name:
                break

            # Validate field name
            if not re.match(r'^[a-z][a-z0-9_]*$', name):
                print("  ❌ Invalid name. Use snake_case (e.g., product_name)")
                continue

            # Type
            type_choice = prompt_choice(
                "  Type",
                ['str', 'int', 'float', 'bool', 'date'],
                default=1
            )

            # Required
            required = prompt_yes_no("  Required", default=True)

            # Type-specific options
            min_value = None
            max_value = None
            default_value = None

            if type_choice == 'int':
                min_str = input("  Min value (optional): ").strip()
                if min_str:
                    try:
                        min_value = int(min_str)
                    except ValueError:
                        pass

                max_str = input("  Max value (optional): ").strip()
                if max_str:
                    try:
                        max_value = int(max_str)
                    except ValueError:
                        pass

            if not required:
                default_value = input("  Default value (optional): ").strip() or None

            # Create field
            field = Field(
                name=name,
                field_type=type_choice,
                required=required,
                default_value=default_value,
                min_value=min_value,
                max_value=max_value
            )

            fields.append(field)
            print(f"  ✅ Added: {name} ({type_choice}{', required' if required else ''})")

            field_num += 1

        return fields

    def generate_from_template(self, template: str, context: Dict):
        """Generate module from template"""
        module_code = context['module_code']
        module_dir = self.modules_dir / module_code

        # Create module directory
        module_dir.mkdir(parents=True, exist_ok=True)

        if template == 'CRUD Table':
            self.generate_crud_template(module_dir, context)
        elif template == 'Custom':
            self.generate_custom_template(module_dir, context)
        else:
            print(f"⚠️  Template '{template}' not yet implemented. Using Custom template.")
            self.generate_custom_template(module_dir, context)

    def generate_crud_template(self, module_dir: Path, context: Dict):
        """Generate CRUD table template"""
        template_dir = self.templates_dir / 'crud_table'

        # manifest.json
        self.render_template(
            template_dir / 'manifest.json.j2',
            module_dir / 'manifest.json',
            context
        )
        print(f"  ✅ manifest.json")

        # Backend files
        backend_dir = module_dir / 'backend'
        backend_dir.mkdir(exist_ok=True)

        self.render_template(
            template_dir / 'backend' / '__init__.py.j2',
            backend_dir / '__init__.py',
            context
        )
        print(f"  ✅ backend/__init__.py")

        self.render_template(
            template_dir / 'backend' / 'router.py.j2',
            backend_dir / 'router.py',
            context
        )
        print(f"  ✅ backend/router.py")

        self.render_template(
            template_dir / 'backend' / 'service.py.j2',
            backend_dir / 'service.py',
            context
        )
        print(f"  ✅ backend/service.py")

        self.render_template(
            template_dir / 'backend' / 'schemas.py.j2',
            backend_dir / 'schemas.py',
            context
        )
        print(f"  ✅ backend/schemas.py")

        # Frontend files
        frontend_dir = module_dir / 'frontend'
        frontend_dir.mkdir(exist_ok=True)

        pascal_name = context['pascal_name']
        self.render_template(
            template_dir / 'frontend' / 'Page.tsx.j2',
            frontend_dir / f'{pascal_name}Page.tsx',
            context
        )
        print(f"  ✅ frontend/{pascal_name}Page.tsx")

        # README
        self.render_template(
            template_dir / 'README.md.j2',
            module_dir / 'README.md',
            context
        )
        print(f"  ✅ README.md")

    def generate_custom_template(self, module_dir: Path, context: Dict):
        """Generate custom (empty) template"""
        # Use existing create_module.py logic for custom
        from create_module import create_manifest, create_backend_files, create_frontend_files

        # manifest.json
        manifest = create_manifest(
            module_code=context['module_code'],
            name=context['name'],
            description=context['description'],
            category=context['category'],
            icon=context['icon'],
            requires_subscription=context.get('requires_subscription'),
            display_order=context.get('display_order', 100),
            admin_only=context.get('admin_only', False)
        )

        manifest_path = module_dir / 'manifest.json'
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        print(f"  ✅ manifest.json")

        # Backend
        create_backend_files(module_dir, context['module_code'], context['name'])
        print(f"  ✅ backend/router.py")
        print(f"  ✅ backend/service.py")

        # Frontend
        create_frontend_files(
            module_dir,
            context['module_code'],
            context['name'],
            context['icon']
        )
        pascal_name = context['pascal_name']
        print(f"  ✅ frontend/{pascal_name}Page.tsx")

    def render_template(self, template_path: Path, output_path: Path, context: Dict):
        """Render Jinja2 template to file"""
        try:
            # Read template
            template_content = template_path.read_text(encoding='utf-8')
            template = Template(template_content)

            # Render
            rendered = template.render(**context)

            # Write output
            output_path.write_text(rendered, encoding='utf-8')

        except Exception as e:
            print(f"  ❌ Error rendering {template_path.name}: {e}")
            raise

    def build_registry(self):
        """Build module registry and frontend imports"""
        print("\n🔨 Building registry...")

        try:
            # Build module registry
            subprocess.run(
                [sys.executable, 'scripts/build_module_registry.py'],
                cwd=str(self.project_root),
                check=True,
                capture_output=True
            )
            print("  ✅ modules/_registry.json updated")

            # Build frontend imports
            subprocess.run(
                [sys.executable, 'scripts/build_frontend_imports.py'],
                cwd=str(self.project_root),
                check=True,
                capture_output=True
            )
            print("  ✅ frontend/src/modules/_imports.ts updated")

        except subprocess.CalledProcessError as e:
            print(f"  ⚠️  Warning: Registry build failed: {e}")
            print("  You may need to run manually:")
            print("    python scripts/build_module_registry.py")
            print("    python scripts/build_frontend_imports.py")


def main():
    """Main entry point"""
    try:
        generator = ModuleGenerator()
        generator.run()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
