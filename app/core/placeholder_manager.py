class PlaceholderManager:
    def __init__(self, template_manager):
        self.template_manager = template_manager

    def load_placeholders(self, template_id=None):
        if not template_id:
            return []
        config = self.template_manager.load_config()
        for tmpl in config.get("templates", []):
            if tmpl.get("id") == template_id:
                return tmpl.get("placeholders", [])
        return []

    def save_placeholders(self, placeholders, template_id):
        if not template_id:
            return False
        config = self.template_manager.load_config()
        for tmpl in config.get("templates", []):
            if tmpl.get("id") == template_id:
                tmpl["placeholders"] = placeholders
                break
        return self.template_manager.save_config(config)

    def add_placeholder(self, key, label, template_id, target_field="custom"):
        if not template_id:
            return False
        placeholders = self.load_placeholders(template_id)
        # Check for duplicate keys
        for ph in placeholders:
            if ph["key"] == key:
                return False
        placeholders.append({
            "key": key,
            "label": label,
            "target_field": target_field
        })
        return self.save_placeholders(placeholders, template_id)

    def delete_placeholder(self, key, template_id):
        if not template_id:
            return False
        placeholders = self.load_placeholders(template_id)
        updated = [ph for ph in placeholders if ph["key"] != key]
        if len(updated) == len(placeholders):
            return False
        return self.save_placeholders(updated, template_id)

    def set_placeholder_multiple(self, template_id, key, is_multiple):
        if not template_id:
            return False
        placeholders = self.load_placeholders(template_id)
        changed = False
        for ph in placeholders:
            if ph["key"] == key:
                ph["is_multiple"] = is_multiple
                changed = True
                break
        if changed:
            return self.save_placeholders(placeholders, template_id)
        return False
