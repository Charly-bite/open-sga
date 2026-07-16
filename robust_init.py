with open("sga_web/templates/templates/designer.html", "r", encoding="utf-8") as f:
    text = f.read()

# Add userWarehouse property
if "userWarehouse:" not in text:
    text = text.replace(
        "canvasWidth: 151,",
        'userWarehouse: "{{ user_warehouse }}",\\n            canvasWidth: 151,',
    )

# Add init logic
init_logic = """
            // Set correct dims dynamically
            if (this.templateName === 'Almacen2' || this.userWarehouse === 'Almacen2') {
                this.canvasWidth = 200;
                this.canvasHeight = 150;
            }
            
            {% if template_data %}
                {% if template_data.width_mm %}
                this.canvasWidth = {{ template_data.width_mm }};
                {% endif %}
                {% if template_data.height_mm %}
                this.canvasHeight = {{ template_data.height_mm }};
                {% endif %}
            {% endif %}
"""

if "this.templateName === 'Almacen2'" not in text and "init() {" in text:
    text = text.replace("init() {", "init() {" + init_logic)

with open("sga_web/templates/templates/designer.html", "w", encoding="utf-8") as f:
    f.write(text)

print("Applied robust logic")
