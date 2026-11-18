import pathlib
import re
import sys

p = pathlib.Path(r"C:\Users\hecto\AppData\Local\Temp\opencode\prng\clase%02d.txt" % int(sys.argv[1]))
lineas = p.read_text(encoding="utf-8").splitlines()
ruido = re.compile(r"(\.png|\.jpg|\.svg|_default|_hover|_visited|_disabled|_state|_temp|anbnsnf|Mesa de trabajo)")
salida = []
for l in lineas:
    if l.startswith("###"):
        salida.append(l)
    elif l.strip() and not ruido.search(l):
        salida.append(l.strip())
print("\n".join(salida)[:6000])
