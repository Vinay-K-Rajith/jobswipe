import urllib.request, json

# Option 1 - Ranked shortlist
r = urllib.request.urlopen('http://localhost:8000/api/ml/ranked-shortlist/CO001?top_k=5')
d = json.load(r)
print('=== OPTION 1: Ranked Shortlist for', d['company_name'], '===')
for s in d['shortlist']:
    print(f"  #{s['rank']} {s['full_name']:22s} {s['department']:6s} CGPA:{s['cgpa']} Score:{s['rank_score']}")

# Option 2 - Skill gap
print()
r2 = urllib.request.urlopen('http://localhost:8000/api/ml/skill-gap/S0001?top_k=5')
d2 = json.load(r2)
print(f"=== OPTION 2: Skill Gap for {d2['full_name']} ({d2['department']}) ===")
for rec in d2['recommendations']:
    print(f"  {rec['skill']:20s}  predicted_gain: +{rec['predicted_gain']:.4f}")

# Option 3 - Bias report
print()
r3 = urllib.request.urlopen('http://localhost:8000/api/ml/bias-report?flagged_only=true')
d3 = json.load(r3)
s = d3['summary']
print(f"=== OPTION 3: Bias Report ===")
print(f"  Companies: {s['n_companies']}, Flagged: {s['n_flagged']} ({s['flag_rate']*100:.1f}%)")
for f in d3['flagged_companies']:
    print(f"  FLAGGED: {f['company_name']:35s} disparity={f['disparity']:.3f} p={f['p_value']:.4f} driver={f['top_bias_criterion']}")

print()
print("ALL THREE ML ENDPOINTS WORKING")
