"""블라인드 판정 run 준비. usage: ta_judge_pair.py <run_dir> <left.txt> <right.txt> <cutoff YYYY-MM-DD> [--swap]
run_dir 에 A.txt/B.txt/cutoff.txt 를 만들고 mapping.json 에 실제 배정을 남긴다 (ta-report-judge 에는 mapping 을 열지 말라고 명시)."""
import json, os, shutil, sys
run, left, right, cutoff = sys.argv[1:5]
swap = '--swap' in sys.argv
d = run; os.makedirs(d, exist_ok=True)
a, b = (right, left) if swap else (left, right)
shutil.copy(a, os.path.join(d, 'A.txt')); shutil.copy(b, os.path.join(d, 'B.txt'))
open(os.path.join(d, 'cutoff.txt'), 'w', encoding='utf-8').write(cutoff + '\n')
json.dump({'A': os.path.basename(a), 'B': os.path.basename(b), 'cutoff': cutoff}, open(os.path.join(d, 'mapping.json'), 'w'), indent=1)
print(run, 'A=', os.path.basename(a), 'B=', os.path.basename(b))
