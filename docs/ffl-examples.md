# FFL examples — fwh_cookbook

Each block compiles against the domain's own FFL:

```bash
fw ffl compile --check --primary <block.ffl> --library src/cookbook/ffl/cookbook.ffl \
    --library <facetwork>/facetwork/ffl/http.ffl
```

## 1. Rebuild the book

```ffl
namespace demo.rebuild {
    use cookbook.workflows

    workflow Rebuild() => (recipes: Int, stats: Json) andThen {
        book = cookbook.workflows.Build()
        yield Rebuild(recipes = book.recipes, stats = book.stats)
    }
}
```

## 2. Just the nutrition data, fetched with the built-in `fw.http.Fetch`

```ffl
namespace demo.fetch {
    use cookbook.data

    workflow FetchOnly() => (paths: Json, count: Int) andThen {
        plan = cookbook.data.Sources()
        got = cookbook.data.FetchAll(sources = plan.sources, user_agent = plan.user_agent)
        yield FetchOnly(paths = got.paths, count = plan.count)
    }
}
```

## 3. Fetch one source by hand: `$`-scoping into a Json parameter

```ffl
namespace demo.one {
    use cookbook.data

    workflow FetchFirst() => (path: String) andThen {
        plan = cookbook.data.Sources()
        one = cookbook.data.FetchOne(source = plan.sources[0], user_agent = plan.user_agent)
        yield FetchFirst(path = one.path)
    }
}
```

## 4. Build twice: `after` for a dependency the compiler cannot see

The second build re-reads the pages the first build wrote. No value flows between the two builds, so the
order is stated with `after`.

```ffl
namespace demo.twice {
    use cookbook.data
    use cookbook.site

    workflow BuildTwice() => (first: Int, second: Int) andThen {
        plan = cookbook.data.Sources()
        got = cookbook.data.FetchAll(sources = plan.sources, user_agent = plan.user_agent)
        a = cookbook.site.Build(sources = plan.sources, paths = got.paths)
        b = cookbook.site.Build(sources = plan.sources, paths = got.paths) after a
        yield BuildTwice(first = a.files, second = b.files)
    }
}
```

## 5. Decide on the result: `when` attached to the step it gates

Inside the cases, `$` is the `Build` step, so `$.recipes` is that step's return.

```ffl
namespace demo.check {
    use cookbook.workflows

    workflow Check() => (message: String) andThen {
        book = cookbook.workflows.Build() andThen when {
            case $.recipes < 100 => {
                yield Check(message = "the book is short")
            }
            case _ => {
                yield Check(message = "book built")
            }
        }
    }
}
```

## 6. Cap the fetch fan-out from a parameter: `foreach … limit $.width`

```ffl
namespace demo.width {
    use cookbook.data

    facet FetchWide(sources: Json, user_agent: String, width: Int = 0) => (paths: Json)
        andThen foreach s in $.sources limit $.width {
            one = cookbook.data.FetchOne(source = $.s, user_agent = $.user_agent)
            yield FetchWide(paths += one.path)
        }

    workflow Wide(width: Int = 2) => (paths: Json) andThen {
        plan = cookbook.data.Sources()
        got = FetchWide(sources = plan.sources, user_agent = plan.user_agent, width = $.width)
        yield Wide(paths = got.paths)
    }
}
```

## Syntax cheat sheet

| Construct | Example |
|---|---|
| Step | `plan = cookbook.data.Sources()` |
| Reference | `plan.sources`, `$.width`, `$.s.url` |
| Fan-out, capped | `foreach s in $.sources limit 3 { … }` |
| Aggregate | `yield FetchAll(paths += one.path)` |
| Invisible order | `b = Build(…) after a` |
| Branch | `book = Build() andThen when { case $.recipes < 100 => { … } case _ => { … } }` |
