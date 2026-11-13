#!/usr/bin/env python3
"""Compile the actual shared CJK/math/TikZ preamble; no textbook is involved."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/textbook-to-zh-tw-notes/scripts'))
from book import find_xelatex


def run_smoke(engine):
    if not engine:
        raise ValueError('XeLaTeX unavailable; no smoke compilation performed')
    work = ROOT / 'work' / ('environment-smoke-' + uuid.uuid4().hex)
    work.mkdir(parents=True)
    template = (ROOT / 'skills/textbook-to-zh-tw-notes/assets/main.tex').read_text(encoding='utf-8')
    source = template.split(r'\begin{document}', 1)[0] + r'''
\begin{document}
\section{繁體中文與數學排版測試}
這是字型、公式、圖表和補充框的環境測試，不是原書講義。
\sourcepage{p.1（合成測試標記）}
\begin{principle}{原理框}中文（English）與數學符號。\end{principle}
\begin{examplebox}{例題1.1}測試題面。\end{examplebox}
\begin{equation}\frac{1}{\sqrt{1-x^2}}=1+\frac{x^2}{2}+O(x^4)\label{eq:smoke}\end{equation}
\begin{sourcederivation}{合成測試}多行公式：
\begin{align*}a&=b+c\\a-c&=b\end{align*}\end{sourcederivation}
\begin{aisupplement}{合成測試}僅作版面測試。\end{aisupplement}
\begin{correction}{合成測試}此框可記錄訂正依據。\end{correction}
\begin{center}\begin{tikzpicture}\draw[-{Stealth}] (0,0)--(2,0);\node at (1,0.4){$x$};\end{tikzpicture}\end{center}
參見式\ref{eq:smoke}。
\end{document}
'''
    (work / 'main.tex').write_text(source, encoding='utf-8')
    cmd = [engine, '-no-shell-escape', '-interaction=nonstopmode', '-halt-on-error', 'main.tex']
    records = []
    for _ in range(2):
        result = subprocess.run(cmd, cwd=work, capture_output=True, timeout=300)
        records.append({'returncode': result.returncode, 'stdout': result.stdout.decode('utf-8', errors='replace')[-12000:]})
        (work / 'compile.json').write_text(json.dumps({'command': cmd, 'passes': records}, indent=2), encoding='utf-8')
        if result.returncode:
            raise ValueError(f'Chinese/math smoke compilation failed. Inspect {work / "main.log"}')
    log = (work / 'main.log').read_text(encoding='utf-8', errors='replace')
    if 'Missing character:' in log or 'undefined references' in log or not (work / 'main.pdf').is_file():
        raise ValueError(f'Smoke PDF/log incomplete: {work}')
    from pypdf import PdfReader
    return {'status': 'compiled', 'pdf_pages': len(PdfReader(str(work / 'main.pdf')).pages),
            'work': str(work), 'visual_review': 'not_performed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xelatex')
    args = parser.parse_args()
    try:
        print(json.dumps(run_smoke(args.xelatex or find_xelatex()), ensure_ascii=True))
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=True))
        return 1


if __name__ == '__main__':
    sys.exit(main())
