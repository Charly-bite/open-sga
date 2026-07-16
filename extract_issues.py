def extract():
    with open(
        r"c:\Users\QB_DESARROLLO\Desktop\SGA_dev\scripts\audit_report.txt",
        "r",
        encoding="utf-8",
    ) as f:
        lines = f.readlines()

    in_section = False
    products = []
    current = None

    for line in lines:
        stripped = line.strip()
        if "SECTION 1:" in stripped:
            in_section = True
            continue
        if "SECTION 2:" in stripped:
            break
        if not in_section:
            continue

        if stripped.startswith("PRODUCT: "):
            if current:
                products.append(current)
            current = {
                "name": stripped.replace("PRODUCT: ", "").strip(),
                "code": "",
                "hds": "",
                "issues": [],
            }
        elif current and stripped.startswith("Code:"):
            current["code"] = stripped.replace("Code:", "").strip()
        elif current and stripped.startswith("HDS File:"):
            hds_path = stripped.replace("HDS File:", "").strip()
            current["hds"] = hds_path.split("\\")[-1] if hds_path else "N/A"
        elif current and stripped.startswith("→ "):
            current["issues"].append(stripped)

    if current:
        products.append(current)

    with open("preview_clean.txt", "w", encoding="utf-8") as out:
        for i, p in enumerate(products, 1):
            out.write(f"{i}. **{p['name']}** [{p['code']}]\n")
            out.write(f"   HDS: {p['hds']}\n")
            for iss in p["issues"]:
                out.write(f"   - {iss}\n")
            out.write("\n")


if __name__ == "__main__":
    extract()
