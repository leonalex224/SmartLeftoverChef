
# Flask handles routing (URLs) and rendering HTML templates
from flask import Flask, render_template, request

# re + Fraction are used to parse measurements like "1/2" or "1 1/2"
import re
from fractions import Fraction

# requests is used to call the external recipe API (TheMealDB)
import requests

# Create the Flask web app
app = Flask(__name__)

# Base URL for the TheMealDB API
MEALDB_BASE = "https://www.themealdb.com/api/json/v1/1"


# ---------- Helpers: parsing + unit conversion ----------

def parse_number(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None

    if re.match(r"^\d+\s+\d+/\d+$", text):
        whole, frac = text.split()
        return float(int(whole) + Fraction(frac))

    if re.match(r"^\d+/\d+$", text):
        return float(Fraction(text))

    try:
        return float(text)
    except ValueError:
        return None


def to_base(amount: float, unit: str) -> tuple[str, float] | None:
    unit = unit.lower().strip()
    unit = unit.replace(".", "")

    if unit in {"litre", "liter"}:
        unit = "l"
    if unit in {"gr", "gram", "grams", "gms"}:
        unit = "g"
    if unit in {"kgs", "kilogram", "kilograms"}:
        unit = "kg"
    if unit in {"millilitre", "millilitres", "milliliter", "milliliters"}:
        unit = "ml"
    if unit in {"ounces", "ounce"}:
        unit = "oz"
    if unit in {"pound", "pounds"}:
        unit = "lb"
    if unit in {"floz", "fluid ounce", "fluid ounces"}:
        unit = "fl oz"

    if unit == "g":
        return ("mass", amount)
    if unit == "kg":
        return ("mass", amount * 1000.0)
    if unit == "oz":
        return ("mass", amount * 28.3495)
    if unit == "lb":
        return ("mass", amount * 453.592)

    if unit == "ml":
        return ("volume", amount)
    if unit == "l":
        return ("volume", amount * 1000.0)
    if unit == "fl oz":
        return ("volume", amount * 29.5735)

    return None


def parse_measure(text: str) -> tuple[str, float] | None:
    if not text:
        return None

    s = text.strip().lower()
    s = re.sub(r"\s+", " ", s)

    m = re.match(r"^(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s*([a-z ]+)?$", s)
    if not m:
        return None

    num_str = m.group(1)
    unit_str = (m.group(2) or "").strip()

    amount = parse_number(num_str)
    if amount is None:
        return None

    if not unit_str:
        return None

    return to_base(amount, unit_str)


def extract_recipe_items(meal: dict) -> list[dict]:
    items = []
    for i in range(1, 21):
        ing = (meal.get(f"strIngredient{i}") or "").strip()
        meas = (meal.get(f"strMeasure{i}") or "").strip()
        if not ing:
            continue

        parsed = parse_measure(meas)
        kind, base_val = (parsed if parsed else (None, None))

        items.append({
            "name": ing.lower(),
            "measure_raw": meas,
            "base_kind": kind,
            "base_value": base_val,
        })
    return items


def build_user_stock(names, amounts, units):
    ingredients_display = []
    user_stock = {}

    for name, amount, unit in zip(names, amounts, units):
        n = (name or "").strip().lower()
        a = (amount or "").strip()
        u = (unit or "").strip().lower()

        if not n:
            continue

        quantity = f"{a} {u}".strip() if a and u else None
        ingredients_display.append({"name": n, "quantity": quantity})

        if a and u:
            try:
                a_val = float(a)
            except ValueError:
                a_val = None

            if a_val is not None:
                conv = to_base(a_val, u)
                if conv:
                    kind, base_val = conv
                    user_stock[n] = {"kind": kind, "base_value": base_val, "raw": quantity}
                else:
                    user_stock[n] = {"kind": None, "base_value": None, "raw": quantity}
        else:
            user_stock.setdefault(n, {"kind": None, "base_value": None, "raw": None})

    return ingredients_display, user_stock


def find_user_key(recipe_ing: str, user_stock: dict) -> str | None:
    recipe_ing = recipe_ing.lower().strip()
    recipe_tokens = recipe_ing.split()

    if recipe_ing in user_stock:
        return recipe_ing

    banned_second_words = {
        "stock", "broth", "bouillon", "gravy", "sauce", "paste", "cube", "cubes"
    }

    allowed_second_words = {
        "mince", "minced", "ground", "steak", "brisket",
        "chunks", "chunk", "strip", "strips"
    }

    for user_key in user_stock.keys():
        user_key = user_key.lower().strip()
        user_tokens = user_key.split()

        if len(user_tokens) > 1:
            if all(tok in recipe_tokens for tok in user_tokens):
                return user_key
            continue

        if len(recipe_tokens) >= 1 and recipe_tokens[0] == user_key:
            if len(recipe_tokens) == 1:
                return user_key

            second = recipe_tokens[1]
            if second in banned_second_words:
                continue

            if second in allowed_second_words:
                return user_key

            continue

    return None

def score_recipe(user_stock: dict, recipe_items: list[dict]):
    score = 0
    matched = 0
    comparable_matches = 0
    missing = []

    for item in recipe_items:
        key = find_user_key(item["name"], user_stock)

        if not key:
            missing.append(item["name"])
            continue

        matched += 1
        score += 3

        user = user_stock[key]
        if user["kind"] and item["base_kind"] and user["kind"] == item["base_kind"]:
            if user["base_value"] is not None and item["base_value"] is not None:
                comparable_matches += 1
                if user["base_value"] >= item["base_value"]:
                    score += 2

    return score, matched, comparable_matches, missing


def match_label(score: int, matched_count: int) -> str:
    if matched_count == 0:
        return "Low"

    max_score = matched_count * 5
    pct = score / max_score

    if pct >= 0.8:
        return "High"
    if pct >= 0.5:
        return "Medium"
    return "Low"


# ---------- Routes ----------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/results", methods=["POST"])
def results():

    names = request.form.getlist("ingredient_name")
    amounts = request.form.getlist("ingredient_amount")
    units = request.form.getlist("ingredient_unit")
    dietary = request.form.get("dietary", "none")

    ingredients, user_stock = build_user_stock(names, amounts, units)

    if not ingredients:
        return render_template(
            "results.html",
            ingredients=[],
            recipes=[],
            error="No ingredients were entered.",
            dietary=dietary
        )

    recipes = []
    error = None

    seen_ids = set()
    seen_titles = set()

    main_ing = ingredients[0]["name"].replace(" ", "_")

    try:
        if dietary == "vegetarian":
            r = requests.get(f"{MEALDB_BASE}/filter.php", params={"c": "Vegetarian"}, timeout=10)
        elif dietary == "vegan":
            r = requests.get(f"{MEALDB_BASE}/filter.php", params={"c": "Vegan"}, timeout=10)
        else:
            r = requests.get(f"{MEALDB_BASE}/filter.php", params={"i": main_ing}, timeout=10)

        r.raise_for_status()
        meals = (r.json().get("meals") or [])[:20]

        for m in meals:
            meal_id = m.get("idMeal")

            if meal_id and meal_id in seen_ids:
                continue

            d = requests.get(f"{MEALDB_BASE}/lookup.php", params={"i": meal_id}, timeout=10).json()
            full = (d.get("meals") or [None])[0]
            if not full:
                continue

            full_id = full.get("idMeal") or meal_id
            title = (full.get("strMeal") or "").strip()

            if full_id and full_id in seen_ids:
                continue
            if title and title in seen_titles:
                continue

            recipe_items = extract_recipe_items(full)

            # Vegan safeguard
            if dietary == "vegan":
                non_vegan_keywords = {
                    "milk", "cheese", "butter", "egg",
                    "honey", "cream", "yogurt"
                }
                if any(
                    any(word in item["name"] for word in non_vegan_keywords)
                    for item in recipe_items
                ):
                    continue

            # Require usable instruction link
            source = (full.get("strSource") or "").strip()
            youtube = (full.get("strYoutube") or "").strip()

            if source.startswith(("http://", "https://")):
                final_link = source
            elif youtube.startswith(("http://", "https://")):
                final_link = youtube
            else:
                continue  # Skip recipes with no usable link

            score, matched_count, comparable_matches, missing = score_recipe(user_stock, recipe_items)

            recipes.append({
                "title": title,
                "image": full.get("strMealThumb"),
                "category": full.get("strCategory"),
                "area": full.get("strArea"),
                "source": final_link,
                "match_score": score,
                "match_label": match_label(score, matched_count),
                "matched_count": matched_count,
                "comparable_matches": comparable_matches,
                "missing": missing[:3],  # limit to first 3 for clean UI
})

        recipes.sort(key=lambda x: x["match_score"], reverse=True)
        recipes = recipes[:6]

        if not recipes:
            error = "No recipes found. Try a more common ingredient."

    except requests.RequestException:
        error = "Could not reach the recipe service right now. Please try again."

    return render_template(
        "results.html",
        ingredients=ingredients,
        recipes=recipes,
        error=error,
        dietary=dietary
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
