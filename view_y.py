import json
import glob

for f in glob.glob("label_templates/*.json"):
    try:
        data = json.loads(open(f, encoding="utf-8").read().strip())
        for idx, el in enumerate(data.get("elements", [])):
            if (
                el.get("field") == "peso_neto_label"
                or el.get("custom_text") == "PESO NETO:"
            ):
                print(f"FOUND IT: {el}")
    except Exception:
        pass
