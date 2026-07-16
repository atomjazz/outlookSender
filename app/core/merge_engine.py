import re

class MergeEngine:
    @staticmethod
    def merge(template_text, values):
        """
        Replaces {{key}} in template_text with values[key].
        If a key is not found in values, it remains unchanged.
        """
        if not template_text:
            return ""
            
        def repl(match):
            key = match.group(1).strip()
            return str(values.get(key, match.group(0)))
            
        pattern = re.compile(r'\{\{([^}]+)\}\}')
        return pattern.sub(repl, template_text)

    @staticmethod
    def get_unmerged_keys(text):
        """
        Returns a list of unique placeholder keys that are still present as {{key}} in the text.
        """
        if not text:
            return []
        pattern = re.compile(r'\{\{([^}]+)\}\}')
        matches = pattern.findall(text)
        return list(set(match.strip() for match in matches))

    @staticmethod
    def highlight_unmerged(template_text):
        """
        Replaces {{key}} with a yellow highlight span for preview mode when no value is provided.
        """
        if not template_text:
            return ""
            
        def repl(match):
            key = match.group(1).strip()
            return f'<span style="background-color: #ffeb3b; padding: 2px 4px; border-radius: 4px; font-weight: bold; color: #333;">{{{{{key}}}}}</span>'
            
        pattern = re.compile(r'\{\{([^}]+)\}\}')
        return pattern.sub(repl, template_text)
