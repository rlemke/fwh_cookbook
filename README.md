# fwh_cookbook — The Low-Carb Kitchen

A [Facetwork](https://github.com/rlemke/facetwork) domain that builds a low-carb cookbook as a static site:
151 recipes, 105 of them desserts. Every recipe is either dairy-free as written or gives a dairy-free swap
for each dairy ingredient. Each dish is also placed on a world map at the place its *kind* of dish comes from.

- **Index** (`index.html`): a map of where each dish comes from, plus every recipe with filters for chapter,
  net carbs, dairy-free as written, and nut-, egg- and coconut-free.
- **Recipe pages** (`recipes/<id>.html`): ingredients in US measures with grams, the method, the dairy-free version,
  nutrition per serving both as written and dairy-free, and the dish's history.
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
