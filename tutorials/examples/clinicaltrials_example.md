### ClinicalTrials.gov tool quick test

Use the new `query_clinicaltrials` data tool directly:

```python
from biomni.tool.database import query_clinicaltrials

# Free-text term
res = query_clinicaltrials(term="breast cancer", status="RECRUITING", page_size=5, max_pages=1, verbose=False)
print(res)

# Natural language prompt (uses LLM to infer parameters)
# res = query_clinicaltrials(prompt="recruiting phase 3 trials for lung cancer in the US", page_size=5, max_pages=1)
# print(res)

# Direct endpoint path
# res = query_clinicaltrials(endpoint="/studies?query.term=glioblastoma&pageSize=3")
# print(res)
```

To run quickly from repo root:

```bash
python - <<'PY'
from biomni.tool.database import query_clinicaltrials
print(query_clinicaltrials(term="type 2 diabetes", page_size=3, max_pages=1, verbose=False))
PY
```


