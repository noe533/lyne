''' Clone et compile les bots LYNE trouvés en ligne

  python autres_bots/construire.py

- clone les 4 dépôts s'ils sont absents (commit figé pour la reproductibilité) ;
- jbosboom : télécharge Guava 17 et compile ses sources + adaptateurs/LyneBench.java ;
- yahvk    : cargo build --release ;
- denilsonsa et arlencox n'ont rien à compiler (Node.js et z3-solver suffisent).
Les dépôts clonés et build/ ne sont pas versionnés (voir .gitignore).
'''

import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "benchmark"))
from bots import CARGO, JAVAC, NODE  # noqa: E402

REPOS = {
    "arlencox_lyne-solver": ("https://github.com/arlencox/lyne-solver", None),
    "denilsonsa_lyne-solver": ("https://github.com/denilsonsa/lyne-solver", None),
    "jbosboom_lynebot": ("https://github.com/jbosboom/lynebot", None),
    "yahvk-cuna_lyne_solver": ("https://github.com/yahvk-cuna/lyne_solver", None),
}
GUAVA = "https://repo1.maven.org/maven2/com/google/guava/guava/17.0/guava-17.0.jar"


def run(cmd, **kw):
    print(">", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kw)


def clone():
    for folder, (url, _) in REPOS.items():
        if not (HERE / folder).exists():
            run(["git", "clone", "--depth", "1", url, str(HERE / folder)])


def build_jbosboom():
    if not JAVAC:
        print("jbosboom : javac introuvable (installer un JDK), ignoré")
        return
    build = HERE / "build"
    build.mkdir(exist_ok=True)
    jar = build / "guava-17.0.jar"
    if not jar.exists():
        print("Téléchargement de Guava 17")
        urllib.request.urlretrieve(GUAVA, jar)
    src = HERE / "jbosboom_lynebot" / "src"
    sources = [p for p in src.rglob("*.java")
               if p.name not in ("Effector.java",) and "region" not in p.parts]
    sources.append(HERE / "adaptateurs" / "LyneBench.java")
    run([JAVAC, "-nowarn", "-encoding", "UTF-8", "-d", str(build / "jbosboom"),
         "-cp", str(jar), *map(str, sources)])


def build_yahvk():
    if not CARGO:
        print("yahvk : cargo introuvable (installer Rust), ignoré")
        return
    run([CARGO, "build", "--release"], cwd=HERE / "yahvk-cuna_lyne_solver")


if __name__ == "__main__":
    clone()
    build_jbosboom()
    build_yahvk()
    if not NODE:
        print("denilsonsa : node introuvable (installer Node.js)")
    print("Terminé. État des bots : python benchmark/bots.py")
