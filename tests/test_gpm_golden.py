"""gpm:s beslut får inte ändras av generaliseringen till N bilar (2026-11-04). Facit genererades med koden
före ombyggnaden (tests/gpm_golden_gen.py): 260 scenarier x 10 varv med Emils två bilar."""
import gzip, json, os
import pytest

import gpm_golden_gen as gen

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "gpm_golden.json.gz")


def test_samma_beslut_som_fore_ombyggnaden():
    expected = json.load(gzip.open(FIX, "rt", encoding="utf-8"))
    got = gen.run()
    assert len(got) == len(expected)
    for i, (g_seq, e_seq) in enumerate(zip(got, expected)):
        for k, (g, e) in enumerate(zip(g_seq, e_seq)):
            g = {kk: vv for kk, vv in g.items() if kk in e}         # nya nycklar får finnas, gamla måste stämma
            if g != e:
                diff = {kk: (g.get(kk), e.get(kk)) for kk in set(g) | set(e) if g.get(kk) != e.get(kk)}
                pytest.fail(f"scenario {i} varv {k}: {json.dumps(diff, ensure_ascii=False)[:1500]}")
