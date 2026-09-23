import json, re

with open('scratch/query_res.json') as f:
    d = json.load(f)
raw = d['research_report']

# Fix invalid JSON escapes like \| or \.
clean_json_str = re.sub(r'\\([^"\\/bfnrtu])', r'\1', raw)
parsed = json.loads(clean_json_str, strict=False)
print('SUCCESS!')
print('=== RESEARCH REPORT PREVIEW ===')
print(parsed['research_report'][:600])
