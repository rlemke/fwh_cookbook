# fwh_cookbook — The Low-Carb Kitchen

A [Facetwork](https://github.com/rlemke/facetwork) domain that builds a low-carb cookbook as a static site:
206 recipes: 112 desserts plus main dishes, sides, and BBQ sauces, rubs and marinades. Every recipe is either dairy-free as written or gives a dairy-free swap
for each dairy ingredient. Every recipe with egg either gives an egg-free swap for each egg (flax or chia
"eggs", aquafaba, silken tofu, egg-free mayonnaise) or, where the egg is the point of the dish, names a similar vegan
recipe; 165 of the 206 are vegan as written or have a vegan version. Each dish is also placed on a world map at the place its *kind* of dish comes from.

- **Index** (`index.html`): a map of where each dish comes from, plus every recipe with filters for chapter,
  net carbs, dairy-free as written, vegan (or vegan version), egg-free (or egg-free version), nut- and coconut-free.
- **Recipe pages** (`recipes/<id>.html`): ingredients in US measures with grams, the method, the dairy-free version, the vegan (or, with meat, egg-free) version or a vegan alternative,
  nutrition per serving as written, dairy-free, and as a rough estimate of an ordinary (not low-carb) version (`data/traditional.json`), and the dish's history.
- **Dinner menus** (`menus.html`, `menus/<id>.html`, from `data/menus.json`): Thanksgiving, Christmas, a family
  Sunday dinner and an outdoor barbecue — the dishes by course, how many batches feed the guests, a plate-of-everything
  nutrition total (as written, dairy-free, not low-carb) and a plan-ahead timeline. The build fails if a menu names a
  recipe that does not exist.
- **The whole book** (`book.html`): every recipe on one page, laid out so a browser's *Save as PDF* starts each
  recipe on a new page.
- **Method & guides** (`about.html`): how the nutrition is worked out, a sweetener guide, how the dairy-free swaps
  work, and every ingredient with its source.

Live at <https://rlemke.github.io/facetwork-maps/cookbook/>.

## FFL at a glance

```ffl
namespace demo {
    use cookbook.workflows

    // Fetch the USDA nutrition table (once; later runs get a 304) and rebuild the book.
    workflow Rebuild() => (recipes: Int, output_dir: String) andThen {
        book = cookbook.workflows.Build()
        yield Rebuild(recipes = book.recipes, output_dir = book.output_dir)
    }
}
```

More examples are in [docs/ffl-examples.md](docs/ffl-examples.md). Publishing is done by `cookbook.publish.PublishBook`
([ffl/cookbook_site.ffl](src/cookbook/ffl/cookbook_site.ffl)). It runs `Build`, then publishes the bundle `cookbook/`
through the shared Pages publisher.

## Recipes are data

Each recipe is one JSON file in `src/cookbook/data/recipes/`. Ingredients must be keys in
`src/cookbook/data/ingredients.json`. Every key there maps either to an exact food in USDA FoodData Central's
SR Legacy release (public domain) or to typical label values, for the foods SR Legacy lacks: low-carb sweeteners,
coconut flour, psyllium and dairy-free products.

A build fails if a recipe:

- names an unknown ingredient, or uses a unit with no weight;
- has a dairy ingredient without a dairy-free swap;
- has a swap that still contains dairy;
- has an egg ingredient with no egg-free swap (`vegan_swaps`) and names no vegan alternative (`vegan_alternative`);
- has a vegan swap to an animal food, or a vegan alternative that is not itself vegan;
- has an origin outside the 12 map regions.

To check new recipes and see their net carbs per serving:

```bash
python tools/check_recipes.py --fdc FoodData_Central_sr_legacy_food_csv_2018-04.zip [recipe.json ...]
```

## Method

- **Weights:** cups and spoons convert to grams using each ingredient's own weight, so a cup of almond flour
  counts as 96 g and a cup of cream cheese as 232 g.
- **Net carbs:** total carbohydrate minus fibre minus sugar alcohols and allulose. Pages always show the
  sugar-alcohol grams separately.
- **The dairy-free column:** worked out from the swapped ingredients rather than assumed to be the same.
- **Determinism:** pages depend only on the recipes and the nutrition table, so an unchanged book renders
  identical bytes and the publisher commits nothing.

## Limits

- **Not kitchen-tested.** The recipes follow established low-carb ratios, but none has been made in a test kitchen.
  The site says so on every page that matters.
- **Label values vary by brand.** Sweeteners, coconut flour and dairy-free products use typical label values,
  and each recipe lists which of its ingredients those are.
- **Disputed origins.** Many dishes' origins are contested. Where that is so, the recipe says it instead of
  choosing one claim.

## Run it

```bash
pip install -e ".[test]"
pytest -q                          # offline, synthetic nutrition table
fw runner start --domain cookbook -- --topics 'cookbook.*'
fw ffl run --primary src/cookbook/ffl/cookbook.ffl --library <facetwork>/facetwork/ffl/http.ffl \
    --workflow cookbook.workflows.Build
```
