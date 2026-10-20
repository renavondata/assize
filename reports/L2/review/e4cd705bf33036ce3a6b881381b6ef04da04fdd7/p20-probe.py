import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))

import jsonschema
import referencing
from worlds.spec import purity

schemas, manifests = purity.load(purity.schema_files()), purity.load(purity.manifest_files())
registry = referencing.Registry().with_resources(
    (s["$id"], referencing.Resource.from_contents(s)) for s in schemas.values())
v = jsonschema.Draft202012Validator(schemas["manifest.schema.json"], registry=registry)
for name, m in manifests.items():
    conforms = "price" in m and v.is_valid(m)
    unpriced = {k: x for k, x in m.items() if k != "price"}
    rejects = not v.is_valid(unpriced)
    print(f"{name}: commits-price-and-conforms={conforms} rejects-without-price={rejects}")
