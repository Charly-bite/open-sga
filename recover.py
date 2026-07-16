import re

with open("tara_weight_manager.py", "r", encoding="utf-8") as f:
    text = f.read()

# Replace multiple newlines with a single newline if there are way too many
# Actually, the quickest way to fix is:
text = text.replace("\r", "")

# Remove sequences of 3+ newlines
text = re.sub(r"\n{3,}", "\n\n", text)

with open("tara_weight_manager.py", "w", encoding="utf-8") as f:
    f.write(text)
