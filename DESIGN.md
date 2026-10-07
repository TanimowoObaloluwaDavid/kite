# Kite — Language Design

A small, readable language for mobile apps. Compiles to Dart/Flutter
(real iOS & Android apps) and ships with a built-in interpreter for instant
feedback on your computer.

File extension: `.kite`

## 1. Variables

```
set name = "Ada"        // mutable variable
fix pi = 3.14159        // constant (cannot be reassigned)
score += 1              // compound assignment: = += -= *= /=
```

## 2. Functions

```
make greet(who) {
  ret "Hey " + who
}

set add = make(a, b) {
  ret a + b
}

print(greet("Ada"))     // => Hey Ada
```

## 3. Conditionals & loops

```
when score > 100 {
  print("high score")
} else when score > 50 {
  print("good")
} else {
  print("keep going")
}

each item in [1, 2, 3] {
  print(item)
}

each i in 0..5 {        // ranges: 0,1,2,3,4 (end is exclusive)
  print(i)
}

while score < 10 {
  score += 1
}
```

Comparison: `==` `!=` `<` `<=` `>` `>=` or the word forms `is` / `isnt`.
Logic: `and` `or` `not`.

## 4. Data

```
set nums = [1, 2, 3]
set user = #{name: "Ada", age: 36}
set greeting = "Hello, {user.name}!"   // string interpolation with { }

nums.push(4)
print(len(nums))        // 4
print(nums[0])
print(user["age"])
```

Methods: lists → `push pop contains join`, strings → `upper lower trim
split contains`, maps → `keys values has`, numbers → `round floor abs`.
Builtins: `print len str num type`.

Literals: numbers, `"strings"`, `[lists]`, `#{maps}`, `nil`, `true`, `false`.
Comments: `// line` and `/* block */`.

## 5. Mobile UI

An `app` block declares a mobile app. `state` declares reactive state —
the UI rebuilds automatically when it changes.

```
app Counter {
  state count = 0

  screen {
    col {
      text("Count: {count}")
      btn("Add +1") {
        count += 1
      }
      btn("Reset") {
        count = 0
      }
    }
  }
}
```

A `screen` may be named (`screen Home { }`); multiple named screens are a
state machine — `goto Home` switches screens and triggers a rebuild.

Widgets:

| Kite          | Flutter                    |
|---------------|----------------------------|
| `col { }`     | `Column`                   |
| `row { }`     | `Row`                      |
| `text(s)`     | `Text`                     |
| `text(s, size)` / `text(s, size, "#hex")` | `Text` + `TextStyle` |
| `btn(s) { }`  | `ElevatedButton` + setState|
| `btn(s, "#hex")` | `ElevatedButton.styleFrom` |
| `input(h)`    | `TextField`                |
| `img(url)`    | `Image.network`            |
| `spacer(n)`   | `SizedBox(height: n)`      |
| `bar(frac)`   | `LinearProgressIndicator`  |

A widget takes a trailing block for children (`col`) or an action (`btn`).

User-defined components: `make foo(a, b) { ret col { … } }` — the value
`ret`urned is spliced into any `col`/`row` where `foo(...)` is called.

## 6. Commands

```
python -m kite run  app.kite       # interpret on your computer (UI prints as a tree)
python -m kite build app.kite      # compile to lib/main.dart for Flutter
python -m kite ast app.kite        # debug: show the parse tree
```

## 7. Grammar (informal)

```
program    := stmt*
stmt       := "set" IDENT "=" expr
            | "fix" IDENT "=" expr
            | "make" IDENT "(" params ")" block        // named function
            | "ret" expr?
            | "when" expr block ("else" (stmt | block))?
            | "while" expr block
            | "each" IDENT "in" expr block
            | "break" | "continue"
            | "app" IDENT "{" (state | screen | stmt)* "}"
            | "state" IDENT "=" expr
            | "screen" IDENT? block
            | "goto" IDENT
            | expr ("="|"+="|"-="|"*="|"/=") expr
            | expr
block      := "{" stmt* "}"
expr       := or-expr with postfix ( ) [ ] . and trailing block
```
