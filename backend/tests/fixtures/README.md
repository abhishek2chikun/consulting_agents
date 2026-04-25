# tests/fixtures

Static binary fixtures used by the unit and integration test suites.

## sample.pdf

A 2-page PDF containing deterministic text used by
`tests/unit/test_docling_parser.py`:

- Page 1: `Hello, this is page one. The quick brown fox.`
- Page 2: `Page two content. Lorem ipsum dolor sit amet.`

### Regenerating

We do not pull `reportlab` into the project dependencies — generate the
fixture in an isolated temporary environment instead:

```bash
cd backend
uv run --with reportlab python -c "
from reportlab.pdfgen import canvas
c = canvas.Canvas('tests/fixtures/sample.pdf', pagesize=(612, 792))
c.drawString(72, 720, 'Hello, this is page one. The quick brown fox.')
c.showPage()
c.drawString(72, 720, 'Page two content. Lorem ipsum dolor sit amet.')
c.showPage()
c.save()
"
```

Commit the resulting `sample.pdf` to the repo.
