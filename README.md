# ⚡ Secure Comp

A full 6-phase compiler built in Python for **Volt** — a custom statically-typed programming language. Features a web-based frontend and a FastAPI backend.

---

## 🚀 Features

- **6 Compiler Phases:**
  1. 🔤 **Lexer** — Tokenizes source code into typed tokens
  2. 🌳 **Parser** — Builds an Abstract Syntax Tree (AST)
  3. 🔍 **Semantic Analyzer** — Type checking, scope validation, warnings
  4. ⚙️ **IR Generator** — Produces 3-address intermediate representation
  5. ✂️ **Optimizer** — Constant folding & dead store elimination
  6. 🖥️ **Code Generator** — Outputs pseudo x86-64 assembly

- REST API with individual endpoints for each phase
- Interactive web frontend to write and compile Volt code in the browser

---

## 🗂️ Project Structure
---

## 🔤 Volt Language Syntax

```volt
fn add(a: int, b: int) -> int {
    let result: int = a + b;
    return result;
}

fn main() -> void {
    let x: int = 10;
    let y: int = 20;
    print(add(x, y));
}
```

**Supported features:**
- Types: `int`, `float`, `bool`, `string`, `void`
- Functions with typed parameters and return types
- Variables with `let`
- `if` / `else`, `while` loops
- `print()` statement
- Arithmetic, comparison, and logical operators
- Single-line comments with `//`

---

## 🛠️ Setup & Run

### Prerequisites
- Python 3.11+
- FastAPI & Uvicorn

### Install dependencies
```bash
pip install fastapi uvicorn
```

### Start the server
```bash
python server.py
```

Server runs at `http://localhost:8000`

### Open the frontend
Just open `frontend.html` in your browser.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| POST | `/compile` | Run all 6 phases |
| POST | `/compile/lexer` | Lexer only |
| POST | `/compile/parser` | Lexer + Parser |
| POST | `/compile/semantic` | Up to Semantic Analysis |
| POST | `/compile/ir` | Up to IR Generation |
| POST | `/compile/optimizer` | Up to Optimizer |

**Request body:**
```json
{ "source": "fn main() -> void { print(42); }" }
```

---

## 👨‍💻 Author

**Divya Pratap Singh**  
[github.com/divy0512](https://github.com/divy0512)
