import importlib.util
from pathlib import Path

module_path = Path(__file__).parent / "inventory-service.py"
spec = importlib.util.spec_from_file_location("inventory_service_module", str(module_path))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

app = getattr(module, "app")
