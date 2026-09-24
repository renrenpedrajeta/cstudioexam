"""Freeze cases and expected outcomes before the first live request."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
cases = []
def add(id, category, recipe, review, expected, status="applied", repeat=False):
    cases.append(dict(id=id, category=category, recipe_id=recipe, review_text=review,
                      expected=expected + " Preserve all unrelated ingredients and instructions.",
                      expected_status=status, repeat=repeat))

C="10813"; S="77935"; M="45613"; N="144299"; A="19117"
add("Q01","Quantity",C,"I used three quarters of a cup of white sugar rather than the full cup.","White sugar 3/4 cup; brown sugar unchanged.")
add("Q02","Quantity",C,"I reduced the flour by one third, using 2 cups instead of 3.","Flour 2 cups.")
add("Q03","Quantity",C,"I doubled the vanilla extract to 4 teaspoons.","Vanilla extract 4 teaspoons.")
add("Q04","Quantity",S,"I used 4 cups of chicken broth instead of 3 cups.","Chicken broth 4 cups.")
add("Q05","Quantity",M,"I cut the dried cherries to half a cup.","Dried cherries 1/2 cup.")
add("Q06","Quantity",N,"I used half the listed sake: one eighth of a cup.","Sake 1/8 cup.")
add("Q07","Quantity",A,"For the frosting, I used 1 1/2 cups of confectioners' sugar instead of 2 cups. I left both sugars in the cake batter unchanged.","Confectioners' sugar 1 1/2 cups; brown and white sugar unchanged.")
add("Q08","Quantity",C,"I increased the eggs from two to three. That was my only change.","Eggs 3.")
add("S01","Substitution",C,"I replaced the 1 cup of chopped walnuts with 1 cup of chopped pecans.","Pecans 1 cup replace walnuts in ingredients and mixing instructions.")
add("S02","Substitution",C,"I used 2 cups of milk chocolate chips instead of the 2 cups of semisweet chocolate chips.","Milk chocolate chips 2 cups replace semisweet chips; generic chocolate-chip instruction is acceptable.")
add("S03","Substitution",S,"I replaced all 3 cups of chicken broth with 3 cups of vegetable broth.","Vegetable broth 3 cups replaces chicken broth; generic broth instruction is acceptable.")
add("S04","Substitution",M,"I swapped the dried cherries for 3/4 cup dried cranberries.","Dried cranberries 3/4 cup replace cherries in ingredients and blender step.")
add("S05","Substitution",M,"I replaced the mango nectar with 1 1/2 cups of pineapple juice.","Pineapple juice 1 1/2 cups replaces mango nectar in ingredients and blender step.")
add("S06","Substitution",N,"I used 1/4 cup tamari in place of the soy sauce.","Tamari 1/4 cup replaces soy sauce in ingredients and simmering step.")
add("M01","Multiple changes",C,"I used 3/4 cup white sugar and 3 eggs. I also swapped the walnuts for 1 cup chopped pecans.","White sugar 3/4 cup, eggs 3, pecans 1 cup instead of walnuts with matching mixing step.",repeat=True)
add("M02","Multiple changes",C,"I used 2 1/2 cups flour, left out the walnuts, and mixed 1 teaspoon cinnamon into the batter. I refrigerated the dough for 45 minutes before dropping spoonfuls onto the baking sheets.","Flour 2 1/2 cups; walnuts absent from ingredients and steps; cinnamon 1 teaspoon with use step; refrigerate 45 minutes before spooning dough.",repeat=True)
add("M03","Multiple changes",M,"I used only 1 cup of mango nectar, replaced the cherries with 1/2 cup dried cranberries, and marinated the meat in the refrigerator for at least 4 hours instead of 2.","Mango nectar 1 cup; dried cranberries 1/2 cup replace cherries in blender; refrigerated marination at least 4 hours.",repeat=True)
add("M04","Multiple changes",S,"I used 3 cups vegetable broth instead of chicken broth, reduced the ground ginger to 1 teaspoon, and omitted the peanut garnish.","Vegetable broth 3 cups; ground ginger 1 teaspoon; peanuts absent, no peanut garnish instruction remains.",repeat=True)
add("T01","Technique",C,"I baked the cookies for 12 minutes instead of 10 minutes, at the same temperature.","Baking time 12 minutes, temperature unchanged.")
add("T02","Technique",M,"I refrigerated the meat in the marinade for at least 4 hours instead of at least 2 hours.","Refrigerated marination at least 4 hours; ingredients unchanged.")
add("T03","Technique",C,"I chilled the finished dough for 20 minutes before dropping spoonfuls onto the baking sheets.","Chill finished dough 20 minutes before dropping spoonfuls; baking unchanged.",repeat=True)
add("A01","Addition",C,"I added 1 teaspoon finely grated orange zest when stirring in the flour.","Orange zest 1 teaspoon added to ingredients and flour mixing step.")
add("A02","Addition",S,"I stirred in 1 tablespoon chopped fresh parsley just before serving.","Fresh parsley 1 tablespoon added to ingredients and finishing step before serving.")
add("R01","Removal",M,"I left out the garlic entirely.","Garlic removed from ingredients and blender step.")
add("N01","No change",C,"These cookies were wonderful. My family loved them exactly as written.","Original unchanged; no enhanced recipe.","skipped")
add("N02","Future only",M,"Next time I might replace the cherries with cranberries.","Future suggestion not applied; original unchanged.","skipped")
add("N03","Negation",C,"I did not leave out the walnuts and I did not change the sugar. I followed the recipe exactly.","Negated changes not applied; original unchanged.","skipped")
add("N04","Already satisfied",C,"I used exactly 1 cup of white sugar, just as the ingredient list says.","Already-satisfied quantity generates no edit; original unchanged.","skipped")
add("N05","Ambiguous",C,"I reduced the sugar to half a cup.","White versus brown sugar unresolved; original unchanged.","needs_review")
add("N06","Ambiguous",A,"I halved the shortening.","Batter versus frosting shortening unresolved; original unchanged.","needs_review")
add("N07","Conflicting",C,"I cannot remember whether I used 1 egg or 4 eggs instead of 2.","Uncertain egg quantity withheld; original unchanged.","needs_review")
add("N08","Unspecified substitution",C,"I replaced the butter with oil, but I did not measure the oil and cannot say how much I used.","No invented oil quantity; original unchanged pending clarification.","needs_review")
add("U01","Unsupported conversion",C,"I reduced the flour by 100 grams, but I do not know the flour's weight per cup.","Unsupported mass-to-volume conversion withheld; original unchanged.","needs_review")
add("U02","Unsupported count unit",N,"I used 6 potatoes instead of 4 potatoes.","Current quantity parser does not support potato counts; needs_review, no partial edits.","needs_review")
add("U03","Invalid quantity",C,"I multiplied the amount of white sugar by zero.","Nonpositive quantity rejected rather than silently removing the ingredient.","needs_review")
add("U04","Invalid quantity",C,"I used minus one cup of white sugar.","Negative quantity rejected; original unchanged.","needs_review")

out=HERE/'cases.json'
if out.exists(): raise SystemExit('Cases already frozen; refusing overwrite')
snapshots={}
for path in (ROOT/'data').glob('recipe_*.json'):
    raw=json.loads(path.read_text(encoding='utf-8'))
    if raw['recipe_id'] in {c['recipe_id'] for c in cases}: snapshots[raw['recipe_id']]=raw
payload=dict(created_at=datetime.now(timezone.utc).isoformat(), cases=cases, recipes=snapshots,
             criteria={'max_incorrect_publications':0,'min_supported_completion':0.95,'repeat_total_per_selected_case':5},
             source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').rglob('*.py')})
out.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('Frozen',len(cases),'cases;',sum(c['repeat'] for c in cases),'cases will run five times total.')
