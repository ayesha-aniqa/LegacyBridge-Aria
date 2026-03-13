# remove_nbsp.py
with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace non-breaking spaces with normal spaces
content = content.replace("\u00A0", " ")

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Non-breaking spaces replaced with normal spaces!")