# Document Rule Engine

Resolves which legal document templates apply to a client/account/product, driven
entirely by JSON rule files. This is step 2 of the larger pipeline:

1. **Parent contract generation** — product, governing law, client details (out of scope here).
2. **This engine** — given a product and a context (client, account, loan data, ...),
   resolves the exact set of document templates + language + variables to generate.
3. **AI verification** — ChatGPT/Grok/Claude checks the generated documents against
   structural rules (headers, footers, placeholders filled). Also out of scope here;
   this engine's `EvaluationResult` (which documents, which rule produced each one) is
   useful input for that verification/audit step.

No admin UI and no database. Rules live as plain JSON files under `rules/products/`,
edited by hand (or by a future tool) and validated at load time. **Adding a new rule
never requires a code change** — only a new JSON entry.

## How it works

```
rules/
  schema/
    rule.schema.json          JSON Schema for one rule (for editor validation)
    condition.schema.json      JSON Schema for the condition tree (recursive)
    rules_file.schema.json     JSON Schema for a whole product file (array of rules)
  products/
    mortgage.json               all rules for the "mortgage" product
    auto_loan.json               all rules for the "auto_loan" product
  documents/
    templates.json              registry of available document templates

engine/                          the rule engine itself (pure Python, no I/O except loader.py)
  context.py                     dotted-path field lookup ("client.country") into the context
  operators.py                   the operator registry (eq, gt, in, regex, between, ...)
  evaluator.py                   evaluates a condition tree (all/any/not/always + leaves)
  models.py                      pydantic models: Rule, RuleActions, DocumentAction, ...
  loader.py                      reads + validates JSON files from disk (the only I/O seam)
  engine.py                      RuleEngine: loads rules, evaluates them, resolves conflicts

api/
  main.py                        FastAPI app: /evaluate, /rules, /rules/reload, /health

scripts/
  validate_rules.py              standalone CLI to validate rule files (for CI or by hand)
```

### Rule anatomy

```jsonc
{
  "rule_id": "mortgage_de_language_docs",       // unique, snake_case
  "name": "German-language contract & KYC for DE-resident accounts",
  "description": "...",                          // optional, free text
  "product": "mortgage",                         // or ["mortgage", "auto_loan"], or "*" for all
  "priority": 10,                                // lower number = higher precedence (default 100)
  "is_active": true,                             // flip to false to disable without deleting
  "effective_from": "2024-01-01",                // optional, YYYY-MM-DD
  "effective_to": null,                          // optional
  "conditions": {
    "all": [
      { "field": "account.country", "op": "eq", "value": "DE" }
    ]
  },
  "actions": {
    "include_documents": [
      { "template_id": "mortgage_contract_de" },
      { "template_id": "kyc_form_de" }
    ],
    "exclude_documents": ["mortgage_contract_en", "kyc_form_en"],
    "set_variables": { "language": "de" }
  }
}
```

### Condition tree

A condition node is one of:

| Form | Meaning |
|---|---|
| `{"always": true}` | Unconditional match (used for baseline/default rules) |
| `{"all": [node, ...]}` | AND — every child must match |
| `{"any": [node, ...]}` | OR — at least one child must match |
| `{"not": node}` | Negation |
| `{"field": "client.country", "op": "eq", "value": "DE"}` | Leaf comparison |

These nest arbitrarily, e.g. `{"all": [leaf, {"any": [leaf, {"not": leaf}]}]}`.

`field` is a dot path into the context you pass to `/evaluate` (e.g.
`"client.address.country"`, `"loan.amount"`). A missing field never raises — it's
treated as absent, and every operator has defined behavior for that case (`eq` →
false, `not_exists` → true, etc.), so a rule referencing a field your context
doesn't happen to include simply doesn't match, instead of crashing.

### Operators

`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `contains`, `not_contains`,
`exists`, `not_exists`, `is_empty`, `is_not_empty`, `regex`, `between`.

Full behavior is in [`engine/operators.py`](engine/operators.py). Adding a genuinely
new operator (rare — the above covers essentially all eligibility logic) means adding
one function decorated with `@operator("name")` there; it does not touch rule files,
the loader, or the evaluator.

### Actions

- `include_documents`: list of `{template_id, language?, variables?}` to add to the
  resolved set if the rule matches.
- `exclude_documents`: list of `template_id`s to remove from the resolved set, **even
  if another matching rule included them**. Exclusions are a deny mechanism and always
  win, regardless of priority — this matches how compliance/sanctions rules should
  behave (a deny should never lose to a lower-priority allow).
- `set_variables`: merged into every resolved document's `variables` (e.g.
  `{"language": "de"}`), for the AI-verification step or the document generator to use.

### Conflict resolution (multiple matching rules)

Rules are evaluated in ascending `priority` order (lower number = higher precedence).

- If two matching rules both `include_documents` the **same** `template_id` (or
  `set_variables` the same key) with different overrides, the first one encountered in
  priority order wins; the conflict is logged as a warning. In practice this is rare —
  most rules add *different* template_ids (see `mortgage_de_language_docs`, which adds
  DE-language templates and explicitly excludes the EN ones, rather than overriding the
  same template_id).
- `exclude_documents` always wins over any `include_documents`, regardless of priority.

See [`rules/products/mortgage.json`](rules/products/mortgage.json) and
[`rules/products/auto_loan.json`](rules/products/auto_loan.json) for worked examples,
including a time-boxed rule (`effective_from`) and a priority-conflict example.

## Adding a new rule

1. Open (or create) `rules/products/<product>.json` — it's a JSON array of rule objects.
2. Add a new rule object following the anatomy above. Pick a unique `rule_id`.
3. Validate it:
   ```
   python scripts/validate_rules.py
   ```
   This catches malformed JSON, unknown operators, duplicate `rule_id`s, malformed
   condition trees, and (in strict mode, the default) `template_id`s that don't exist
   in `rules/documents/templates.json`.
4. If a service is already running, call `POST /rules/reload` to pick up the change
   without restarting the process (or just restart it).

No Python code changes, no redeploy of the engine itself, ever required for a new rule.

### Editor autocomplete/validation while hand-editing JSON

In VS Code, add to `.vscode/settings.json`:

```jsonc
{
  "json.schemas": [
    {
      "fileMatch": ["rules/products/*.json"],
      "url": "./rules/schema/rules_file.schema.json"
    },
    {
      "fileMatch": ["rules/documents/templates.json"],
      "url": "./rules/schema/templates_file.schema.json"
    }
  ]
}
```

This gives inline validation and autocomplete for `op` values, required fields, etc.
while you type.

## Running

```bash
python -m venv .venv
.venv/Scripts/activate          # .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"

# validate rules without starting a server
python scripts/validate_rules.py

# run the API
uvicorn api.main:app --reload
OR
.venv/Scripts/python.exe -m uvicorn api.main:app --reload

# run tests
pytest
```

### API

- `GET /health` — rule/template counts, sanity check.
- `GET /rules?product=mortgage` — list loaded rules, optionally filtered by product.
- `GET /rules/{rule_id}` — single rule detail.
- `POST /rules/reload` — re-read JSON files from disk (hot reload after editing rules).
- `POST /evaluate` — resolve the document set:

  ```bash
  curl -X POST http://localhost:8000/evaluate \
    -H "Content-Type: application/json" \
    -d '{
      "product": "mortgage",
      "context": {
        "client": {"nationality": "FR", "risk_rating": "low"},
        "account": {"country": "DE"},
        "loan": {"amount": 250000}
      }
    }'
  ```

  Response includes the resolved `documents` (each with `template_id`, `file`,
  `language`, `variables`, and which `matched_rule_id` produced it), the merged
  `variables`, `matched_rule_ids`, and a full per-rule `trace` (matched/active/effective
  for every rule) — useful for audit and for feeding into the downstream AI-verification
  step.

Configuration is via environment variables (see top of `api/main.py`):
`RULE_ENGINE_RULES_DIR`, `RULE_ENGINE_TEMPLATES_FILE`, `RULE_ENGINE_STRICT_TEMPLATES`.

## Design notes for future extension

- **Swapping JSON for a database later**: `engine/loader.py` is the only module that
  touches the filesystem. Replacing it with a module that reads the same shape of data
  from Postgres (or exposes it from a future admin UI) requires no changes to
  `evaluator.py`, `engine.py`, or the API — they only depend on the `Rule`/`TemplateDef`
  pydantic models, not on where the data came from.
- **Effective dates**: `effective_from`/`effective_to` let you stage a regulatory change
  ahead of time without touching production traffic until the date arrives (see
  `auto_loan_new_disclosure_2026` in `rules/products/auto_loan.json`).
- **Audit trail**: every `/evaluate` call returns a full `trace` of every rule that was
  considered (not just the ones that matched), which is what you'd log for compliance
  review of *why* a given document set was generated for a given client.
