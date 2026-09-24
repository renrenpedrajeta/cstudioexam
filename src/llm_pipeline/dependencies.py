"""Conservative checks for preparation dependencies; model audits still follow."""
import re

from .consistency import explicit_change_issues


def ingredient_name(line):
    name = re.sub(r"^[\d\s./]+", "", line.lower()).strip()
    name = re.sub(r"^(?:cups?|teaspoons?|tablespoons?|tsp|tbsp|grams?|ounces?|pounds?)\s+", "", name)
    name = re.sub(r"^(?:(?:packed|chopped|ground|hot|cold|fresh|sifted)\s+)+", "", name)
    return name.split(",")[0].strip()


def dependency_issues(original, candidate, intents):
    issues = explicit_change_issues(candidate)
    instructions = " ".join(candidate.recipe.instructions).lower()
    original_text = " ".join(original.instructions).lower()
    collective = any(term in instructions for term in ("all ingredients", "dry ingredients", "remaining ingredients"))
    # An unchanged ingredient explicitly used before must not lose its only use
    # while a neighboring ingredient or preparation step is being removed.
    for line in set(original.ingredients).intersection(candidate.recipe.ingredients):
        name = ingredient_name(line)
        if not name or collective:
            continue
        pattern = r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, original_text) and not re.search(pattern, instructions):
            issues.append(f"Retained ingredient '{name}' lost its explicit preparation step; preserve its use.")
    # Recognize explicit chilling-before-shaping/baking constraints. Other
    # sequencing language remains subject to the independent fidelity audit.
    for intent in intents:
        quote = intent.source_quote.lower()
        if intent.action == "add":
            amount = re.search(r"\b(?:(?:tiny|small|large)\s+)?(?:dash|pinch)\b", quote)
            names = re.findall(r"[a-z]+", intent.target.lower())
            matches = [line.lower() for line in candidate.recipe.ingredients
                       if names and all(re.search(r"\b" + re.escape(name) + r"\b", line.lower()) for name in names)]
            if amount and not any(amount[0] in line for line in matches):
                issues.append(f"Preserve the source amount '{amount[0]}' for '{intent.target}'; do not omit its qualifier or invent a numeric measure.")
        if intent.action == "remove":
            for line in candidate.recipe.instructions:
                if line not in original.instructions:
                    for sentence in re.split(r"[.;\n]", line.lower()):
                        if re.search(r"\bdissolve\b", sentence) and not re.search(r"\bin\b", sentence):
                            issues.append("A rewritten dissolve step has no liquid medium; replace the removed-liquid method with a coherent preparation step preserving the retained ingredients.")
        if intent.action != "technique" or not re.search(r"refrigerat|chill", quote) or "before" not in quote:
            continue
        after = quote.split("before", 1)[1]
        actions = []
        if re.search(r"scoop|shap|portion", after):
            actions.append(r"scoop\w*|drop\w*|shap\w*|portion\w*")
        if re.search(r"bak", after):
            actions.append(r"bake\w*|baking")
        text = ". ".join(candidate.recipe.instructions).lower()
        chill = re.search(r"(?:^|[.;\n]\s*|\bthen\s+)(?:refrigerate|chill)\b", text)
        for action in actions:
            following = re.search(r"(?:^|[.;\n]\s*|\bthen\s+)(?:" + action + r")\b", text)
            if not chill or not following or chill.start() >= following.start():
                issues.append(f"Instruction order must implement '{intent.source_quote}': place chilling before the actual shaping/baking step.")
                break
    return issues
